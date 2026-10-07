"""Đọc đội hình địch từ game.

Hai kênh, dùng song song:
  * Live Client Data (127.0.0.1:2999) - có dữ liệu NGAY khi vào trận
    (thời điểm "load trận"), đọc được cả 10 tướng của 2 đội.
  * LCU (lockfile) - dùng ở màn hình CHỌN TƯỚNG, khi địch mới lộ 1 phần.

Không cần API key, không đọc bộ nhớ game.
"""
from __future__ import annotations

import base64
import json
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

LIVE_URL = "https://127.0.0.1:2999/liveclientdata/allgamedata"

# Live API trả TOP/JUNGLE/MIDDLE/BOTTOM/UTILITY, LCU trả chữ thường.
POSITIONS = {
    "top": "top",
    "jungle": "jungle",
    "middle": "mid",
    "mid": "mid",
    "bottom": "marksman",
    "adc": "marksman",
    "utility": "support",
    "support": "support",
}


def normalize_role(raw: str | None) -> str | None:
    return POSITIONS.get((raw or "").strip().lower())


_INSECURE = ssl.create_default_context()
_INSECURE.check_hostname = False
_INSECURE.verify_mode = ssl.CERT_NONE


@dataclass
class Side:
    side: str          # "ORDER" | "CHAOS"
    keys: list[str]    # champion key (ddragon) suy từ championName
    raw: list[dict]


@dataclass
class Comp:
    source: str
    enemies: list[str]
    allies: list[str]
    enemy_by_side: list[Side]
    local_role: str | None = None
    active_player: str | None = None
    my_champion: str | None = None      # tướng BẠN đang chơi (để gợi ý lõi/build)
    queue_id: int | None = None         # 2400 = ARAM: Mayhem, 450 = ARAM
    position_known: bool = True         # ARAM không có vị trí cố định

    @property
    def is_aram(self) -> bool:
        return self.queue_id in (450, 2400, 65) or not self.position_known


# ------------------------------------------------------------------ Live Client API


def _get(url: str, timeout: float = 1.5):
    req = urllib.request.Request(url, headers={"User-Agent": "counter-build"})
    with urllib.request.urlopen(req, timeout=timeout, context=_INSECURE) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def read_live(timeout: float = 1.5) -> Comp | None:
    """Đọc trận đang chạy. None nếu game chưa mở."""
    try:
        data = _get(LIVE_URL, timeout)
    except (urllib.error.URLError, OSError, ValueError):
        return None

    active = (data.get("activePlayer") or {}).get("summonerName")
    players = data.get("allPlayers") or []
    sides: dict[str, Side] = {"ORDER": Side("ORDER", [], []), "CHAOS": Side("CHAOS", [], [])}
    me_side = None
    for p in players:
        side = p.get("team")
        if side not in sides:
            continue
        key = p.get("championName") or ""
        if not key or key == "None":
            continue
        sides[side].keys.append(key)
        sides[side].raw.append(p)
        if active and p.get("summonerName") == active:
            me_side = side

    if not sides["ORDER"].keys and not sides["CHAOS"].keys:
        return None

    enemy_side = "CHAOS" if me_side == "ORDER" else "ORDER" if me_side else None
    enemy_keys = sides[enemy_side].keys if enemy_side else []
    ally_keys = sides[me_side].keys if me_side else []
    local_role = None
    my_champion = None
    if me_side:
        for p in sides[me_side].raw:
            if p.get("summonerName") == active:
                local_role = p.get("selectedPosition") or p.get("assignedPosition")
                my_champion = p.get("championName") or None

    game = data.get("gameData") or {}
    queue_id = game.get("queueId") or game.get("gameQueueConfigId")
    try:
        queue_id = int(queue_id) if queue_id is not None else None
    except (TypeError, ValueError):
        queue_id = None

    return Comp(
        source="live",
        enemies=enemy_keys,
        allies=ally_keys,
        enemy_by_side=[sides["ORDER"], sides["CHAOS"]],
        local_role=normalize_role(local_role),
        active_player=active,
        my_champion=my_champion,
        queue_id=queue_id,
        position_known=bool(local_role),
    )


# ------------------------------------------------------------------ LCU (chọn tướng)


def lcu_credentials() -> tuple[str, str] | None:
    """Tìm lockfile của League Client, trả (port, password)."""
    for root in _install_roots():
        lock = root / "lockfile"
        if not lock.exists():
            continue
        try:
            parts = lock.read_text(encoding="utf-8", errors="replace").split(":")
        except OSError:
            continue
        if len(parts) >= 5:
            return parts[2], parts[3]
    return None


def _install_roots() -> list[Path]:
    roots: list[Path] = []
    for drive in _drives():
        roots.append(Path(f"{drive}:/Riot Games/League of Legends"))
    # đọc đường dẫn thật từ RiotClientInstalls.json
    try:
        info = json.loads(
            Path("C:/ProgramData/Riot Games/RiotClientInstalls.json").read_text(
                encoding="utf-8"
            )
        )
        for path in info.get("associated_client", {}):
            roots.insert(0, Path(path))
    except (OSError, ValueError):
        pass
    return roots


def _drives() -> list[str]:
    return [chr(c) for c in range(ord("C"), ord("Z") + 1) if Path(f"{chr(c)}:/").exists()]


def champ_select_comp(timeout: float = 1.5) -> Comp | None:
    """Đọc phiên chọn tướng. None nếu không ở màn hình chọn tướng."""
    creds = lcu_credentials()
    if not creds:
        return None
    port, password = creds
    url = f"https://127.0.0.1:{port}/lol-champ-select/v1/session"
    req = urllib.request.Request(url, headers={"User-Agent": "counter-build"})

    token = base64.b64encode(f"riot:{password}".encode()).decode()
    req.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_INSECURE) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, OSError, ValueError):
        return None
    return parse_champ_select(data)


def parse_champ_select(data: dict) -> Comp | None:
    """Chuyển payload /lol-champ-select/v1/session thành Comp."""
    my_team = data.get("myTeam") or []
    their_team = data.get("theirTeam") or []
    local_cell = data.get("localPlayerCellId")

    my_role = next(
        (c.get("assignedPosition") for c in my_team
         if c.get("cellId") == local_cell and c.get("assignedPosition")),
        None,
    )

    enemies = _team_champions(their_team)
    allies = _team_champions(my_team)
    if not enemies and not allies:
        return None
    return Comp(
        source="champ_select",
        enemies=enemies,
        allies=allies,
        enemy_by_side=[],
        local_role=normalize_role(my_role),
    )


def _team_champions(team: list[dict]) -> list[str]:
    """championId trong phiên chọn tướng -> ddragon key."""
    from .data import dataset

    ds = dataset()
    out: list[str] = []
    for member in team:
        cid = member.get("championId")
        if not cid:
            continue
        champ = ds.champion(cid)
        out.append(champ["key"] if champ else str(cid))
    return out


def current_comp() -> Comp | None:
    """Ưu tiên dữ liệu trong trận, sau đó tới màn hình chọn tướng."""
    live = read_live()
    if live and live.enemies:
        return live
    return champ_select_comp()
