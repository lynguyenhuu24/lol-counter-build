"""Hàng đợi tướng (bench) ARAM + đặt lệnh đổi tướng đúng lúc hết thời gian.

ARAM cho phép đổi sang tướng nằm trên "bench" (do đồng đội reroll ra). LCU có sẵn
endpoint đổi tướng:

    POST /lol-champ-select/v1/session/bench/swap/{championId}

Tính năng đặt lệnh: bạn bấm chọn một tướng trên bench, công cụ **không** đổi ngay mà
chờ tới sát lúc hết thời gian chọn tướng mới gửi yêu cầu — đúng như mô tả "vừa hết
thời gian phải swap tướng đó liền cho tui".

Lưu ý: sau khi bench vừa xuất hiện, client khoá đổi tướng khoảng 3 giây, nên trong
khoảng đó công cụ không gửi yêu cầu (gửi cũng bị từ chối).
"""
from __future__ import annotations

import base64
import json
import os
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from .data import dataset
from .detect import _install_roots  # cùng cách tìm thư mục cài game
from .paths import data_dir

@lru_cache(maxsize=1)
def queue_names() -> dict[str, str]:
    """id hàng đợi -> tên chế độ (từ data/queues.json)."""
    try:
        raw = json.loads((data_dir() / "queues.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}
    return {str(k): str(v) for k, v in raw.items()}


def queue_name(queue_id: int | None) -> str:
    if queue_id is None:
        return "?"
    return queue_names().get(str(queue_id), f"hàng đợi {queue_id}")


# client khoá đổi tướng ngần này giây sau khi bench xuất hiện
BENCH_COOLDOWN = 3.0
# gửi sớm bao nhiêu giây trước khi hết thời gian, CHỈ dùng ở chế độ "chờ sát hết giờ"
# (bù độ trễ mạng nội bộ). Không để sát 0s vì lúc đó pha đã kết thúc.
DEFAULT_LEAD = 1.0
# nhịp hỏi trạng thái bench (giây) — càng nhỏ càng bám sát thời điểm hết giờ
POLL_INTERVAL = 0.4
# nếu không đọc được đồng hồ của client thì tự đếm lùi
FALLBACK_LEAD = 1.0


@dataclass
class Bench:
    """Trạng thái hàng đợi tướng hiện tại."""

    in_champ_select: bool = False    # có đang ở màn hình chọn tướng không
    queue_id: int | None = None      # 450 = ARAM, 2400 = ARAM: Mayhem
    game_mode: str = ""              # "ARAM" / "CLASSIC"…
    rerolls_left: int = 0            # số lượt đổi tướng còn lại (ARAM mới đã bỏ)
    rerolls_seen: bool = False       # client có trả trường rerollsRemaining không
    raw_bench: list[int] = field(default_factory=list)  # id thô client trả về
    unknown: list[int] = field(default_factory=list)    # id không có trong dữ liệu
    custom_game: bool = False        # phòng tự tạo
    allow_rerolling: bool = True     # chế độ có cho đổi tướng không

    enabled: bool = False
    champions: list[dict] = field(default_factory=list)   # tướng đang có trên bench
    mine: dict | None = None                              # tướng bạn đang giữ
    seconds_left: float | None = None                     # thời gian còn lại của pha
    phase: str = ""
    locked: bool = False                                  # đã khoá tướng chưa

    @property
    def usable(self) -> bool:
        return self.enabled and bool(self.champions)

    @property
    def is_aram(self) -> bool:
        if self.queue_id in (450, 2400, 65, 100, 720):
            return True
        return self.game_mode.upper() == "ARAM"

    def diagnose(self) -> str:
        """Giải thích vì sao chưa hiện tướng, để người dùng tự kiểm tra."""
        if not self.in_champ_select:
            return ("Chưa vào màn hình chọn tướng. Hãy mở chọn tướng "
                    "(ARAM thường hoặc ARAM: Mayhem).")

        mode = queue_name(self.queue_id)
        if not self.enabled:
            return (f"Client báo KHÔNG bật hàng đợi tướng (benchEnabled=false, "
                    f"chế độ {mode}). Công cụ chỉ hiện được tướng khi client thật sự "
                    f"cho phép đổi tướng — kiểm tra bằng `python -m lcbuild.bench`.")

        if self.champions:
            if self.unknown:
                return (f"Đang có {len(self.champions)} tướng trên bench, nhưng "
                        f"{len(self.unknown)} tướng công cụ chưa biết: id "
                        f"{', '.join(map(str, self.unknown))}. Chạy --update-data "
                        f"để cập nhật dữ liệu tướng.")
            return ""

        if self.unknown:
            return (f"Client báo có {len(self.unknown)} tướng trên bench nhưng công cụ "
                    f"chưa biết tướng nào: id {', '.join(map(str, self.unknown))}. "
                    f"Chạy --update-data để cập nhật dữ liệu tướng.")

        if self.custom_game:
            return (f"Hàng đợi tướng rỗng ở phòng tự tạo ({mode}). Phòng tự tạo có "
                    f"thể không dùng Thẻ Tướng, nên bench không được phát tướng sẵn. "
                    f"Hãy thử ở hàng đợi ARAM thật.")

        # ARAM hiện dùng Thẻ Tướng: bạn chọn 1 trong 2-3 thẻ, thẻ KHÔNG chọn sẽ
        # rơi xuống bench. Nên bench sẽ có tướng ngay sau khi bạn chọn thẻ.
        if self.mine:
            return (f"Hàng đợi tướng rỗng. Ở ARAM, thẻ tướng bạn KHÔNG chọn sẽ rơi "
                    f"xuống bench — nếu bạn đã chọn thẻ mà bench vẫn rỗng thì có thể "
                    f"bench đã bị lấy hết, hoặc chế độ này không dùng Thẻ Tướng.")
        return f"Hàng đợi tướng rỗng ({mode})."


def _lockfile() -> tuple[str, str] | None:
    # cho phép chỉ định thẳng lockfile (client cài ở chỗ lạ, hoặc để test)
    override = os.environ.get("LCU_LOCKFILE")
    if override:
        creds = _parse_lockfile(Path(override))
        if creds:
            return creds
    for root in _install_roots():
        creds = _parse_lockfile(Path(root) / "lockfile")
        if creds:
            return creds
    return None


def _parse_lockfile(lock: Path) -> tuple[str, str] | None:
    if not lock.exists():
        return None
    try:
        parts = lock.read_text(encoding="utf-8", errors="replace").split(":")
    except OSError:
        return None
    if len(parts) >= 5:
        return parts[2], parts[3]
    return None


def _context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _request(method: str, path: str, timeout: float = 2.0):
    """Gọi LCU. Trả (ok, dữ liệu hoặc thông báo lỗi)."""
    creds = _lockfile()
    if creds is None:
        return False, "chưa mở League Client"
    port, password = creds
    url = f"https://127.0.0.1:{port}{path}"
    token = base64.b64encode(f"riot:{password}".encode()).decode()
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Basic {token}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_context()) as r:
            body = r.read().decode("utf-8", "replace")
            return True, (json.loads(body) if body.strip() else None)
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:200]
        except Exception:
            pass
        return False, f"HTTP {exc.code} {detail}"
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return False, str(exc)


def parse_bench(data: dict) -> Bench:
    """Chuyển payload phiên chọn tướng thành Bench (thuần, để test được)."""
    ds = dataset()
    bench = Bench(in_champ_select=True)
    bench.enabled = bool(data.get("benchEnabled"))
    # Client mới trả `benchChampions` (mảng object {championId}); bản cũ trả
    # `benchChampionIds` (mảng id). Phải đọc CẢ HAI, nếu không sẽ luôn thấy bench rỗng.
    ids: list[int] = []
    for entry in data.get("benchChampions") or []:
        if isinstance(entry, dict) and entry.get("championId"):
            ids.append(int(entry["championId"]))
        elif isinstance(entry, int):
            ids.append(int(entry))
    if not ids:
        ids = [int(cid) for cid in (data.get("benchChampionIds") or [])]
    bench.raw_bench = ids
    bench.champions = [
        champ
        for cid in bench.raw_bench
        if (champ := ds.champion(cid)) is not None
    ]
    bench.unknown = [
        cid for cid in bench.raw_bench if ds.champion(cid) is None
    ]
    bench.custom_game = bool(data.get("isCustomGame"))
    bench.allow_rerolling = bool(data.get("allowRerolling", True))
    bench.rerolls_seen = data.get("rerollsRemaining") is not None
    bench.rerolls_left = int(data.get("rerollsRemaining") or 0)

    cell = data.get("localPlayerCellId")
    for member in data.get("myTeam") or []:
        if member.get("cellId") != cell:
            continue
        champ = ds.champion(member.get("championId")) if member.get("championId") else None
        bench.mine = champ
        bench.locked = bool(member.get("championId"))

    # chế độ chơi: LCU để ở nhiều chỗ tuỳ phiên bản client
    bench.queue_id = None
    for source in (
        data.get("queueId"),
        (data.get("gameData") or {}).get("queueId"),
        ((data.get("entitledFeatureState") or {}).get("queueId")),
    ):
        if isinstance(source, int):
            bench.queue_id = source
            break
    bench.game_mode = str(data.get("gameMode") or "")

    timer = data.get("timer") or {}
    bench.phase = timer.get("phase") or ""
    if not timer.get("isInfinite"):
        left = timer.get("adjustedTimeLeftInPhase")
        if left is None:
            left = timer.get("timeLeftInPhase")
        if left is not None:
            bench.seconds_left = max(0.0, float(left) / 1000.0)
    return bench


def read_bench() -> Bench | None:
    """Đọc phiên chọn tướng hiện tại. None nếu không ở màn hình chọn tướng."""
    ok, data = _request("GET", "/lol-champ-select/v1/session")
    if not ok or not isinstance(data, dict):
        return None
    return parse_bench(data)


def swap_to(champion_id: int) -> tuple[bool, str]:
    """Gửi yêu cầu đổi sang tướng trên bench."""
    ok, data = _request(
        "POST", f"/lol-champ-select/v1/session/bench/swap/{int(champion_id)}"
    )
    if ok:
        return True, "đã gửi yêu cầu đổi tướng"
    return False, str(data)


def _main(argv: list[str] | None = None) -> int:
    """Chẩn đoán nhanh: in đúng những gì client trả về cho phần hàng đợi tướng."""
    import sys

    argv = list(sys.argv[1:] if argv is None else argv)
    if "--raw" in argv:
        # In thô để tìm chỗ client giấu dữ liệu Thẻ Tướng (2-3 thẻ lúc đầu trận).
        paths = [
            "/lol-champ-select/v1/session",
            "/lol-champ-select/v1/session/my-selection",
            "/lol-champ-select/v1/current-champion",
        ]
        got = False
        for path in paths:
            ok, data = _request("GET", path, timeout=3)
            print(f"===== {path} ({'OK' if ok else 'lỗi'})")
            if not ok:
                print("  ", str(data)[:160])
                continue
            got = True
            if isinstance(data, dict):
                chat = data.get("chatDetails")
                if isinstance(chat, dict):
                    for key in list(chat):
                        if "assword" in key:
                            chat[key] = "<ẩn>"
            print(json.dumps(data, ensure_ascii=False, indent=1))
        if not got:
            print("\nKhông đọc được phiên chọn tướng — hãy chạy lại lúc ĐANG ở màn "
                  "hình chọn tướng ARAM.")
            return 1
        return 0

    bench = read_bench()
    if bench is None:
        print("Không đọc được phiên chọn tướng.")
        print("· Chưa mở League Client, hoặc chưa vào màn hình chọn tướng.")
        print("· Có thể trỏ tay: đặt biến môi trường LCU_LOCKFILE=<đường dẫn lockfile>")
        return 1
    print(f"Đang ở màn hình chọn tướng: {bench.in_champ_select}")
    print(f"  chế độ            : {queue_name(bench.queue_id)} (queue {bench.queue_id})")
    print(f"  phòng tự tạo      : {bench.custom_game} | cho đổi tướng: {bench.allow_rerolling}")
    print(f"  benchEnabled      : {bench.enabled}")
    print(f"  benchChampionIds  : {bench.raw_bench}")
    print(f"  nhận diện được    : {[c['name'] for c in bench.champions]}")
    print(f"  không nhận diện   : {bench.unknown}")
    print(f"  tướng của bạn     : {bench.mine['name'] if bench.mine else '?'}")
    print(f"  lượt đổi còn lại  : {bench.rerolls_left}"
          + ("" if bench.rerolls_seen else " (client không trả trường này)"))
    print(f"  pha               : {bench.phase} (còn {bench.seconds_left}s)")
    note = bench.diagnose()
    print("\nKết luận:", note or "có tướng trên bench, sẵn sàng đổi.")
    return 0


if __name__ == "__main__":
    import sys as _sys

    _sys.exit(_main())
