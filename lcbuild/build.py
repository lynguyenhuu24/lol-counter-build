"""Ghép build đầy đủ 6 món cho chế độ ARAM (Mayhem).

Nguyên tắc:
  1. Món khắc chế đội hình địch (từ lcbuild/advisor.py) được ưu tiên trước —
     đây là thứ quyết định thắng thua khi địch có 3-4 tướng cùng loại sát thương.
  2. Còn chỗ thì lấy món chuẩn của tướng (op.gg, xem lcbuild/fetch_builds.py).
  3. Cuối cùng mới tới món tăng chỉ số chung hợp vai trò.

Đầu ra là 6 ô, mỗi ô là (nhóm đồ, món, lý do) để giao diện hiển thị được.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache

from .advisor import Suggestion, build_profile, recommend, role_of
from .data import dataset
from .paths import data_dir

# thứ tự ưu tiên khi lên đồ; món khắc chế nhóm cao hơn món chuẩn của tướng
KIND_PRIORITY = {
    "giảm hồi máu": 100,
    "phá khiên": 96,
    "giải khống chế": 92,
    "chống đánh thường": 88,
    "chống tướng trâu": 80,
    "xuyên giáp/phép": 78,
    "kháng": 70,
    "giày": 60,
    "sinh tồn": 50,
    "hỗ trợ": 40,
    "mở giao tranh": 30,
}

# nhóm đồ bắt buộc chỉ được có 1 món trong build cuối (tránh 2 giày, 2 đồ giải...)
SINGLETON = {"giày", "giải khống chế", "phá khiên", "giảm hồi máu"}

# giày mặc định khi không có luật khắc chế nào chỉ ra giày
DEFAULT_BOOTS = {
    "ap": 3020,        # Giày Pháp Sư
    "crit": 3006,      # Giày Cuồng Nộ
    "ad": 3047,        # Giày Thép Gai
    "tank": 3047,
    "support": 3172,   # Giày Hắc Kim (điểm hồi kỹ năng)
}
# món thành phần rẻ: chỉ dùng khi chưa có món nâng cấp tương ứng
CHEAP_CUTOFF = 1500

# không xếp món rẻ hơn mức này vào 6 ô cuối (để dành ô cho món hoàn chỉnh)
MIN_SLOT_GOLD = 1000

# bậc trang bị được coi là "món hoàn chỉnh" (không phải món thành phần)
COMPLETED = {"LEGENDARY", "MYTHIC", "BOOTS"}

# món tăng chỉ số chung khi không còn gì để lên, theo nhóm tướng
FILLER: dict[str, list[int]] = {
    "ad": [3143, 3071, 6333, 2504, 3153],          # Randuin, Rìu Đen, DD, Kaenic, BOTRK
    "crit": [3031, 3036, 3072, 6676, 3053],         # Vô Cực, Dominik, Huyết Kiếm, Hải Tặc, Sterak
    "ap": [3089, 3135, 4645, 3157, 3165],           # Rabadon, Hư Vô, Hắc Hóa, Zhonya, Morello
    "tank": [3068, 3075, 4401, 6665, 3083],         # Thái Dương, Gai, Thiên Nhiên, Jak'Sho, Warmog
    "support": [2065, 3190, 6617, 3222, 3107],      # Shurelya, Solari, Nguyệt Thạch, Mikael, Chuộc Tội
}

# nhóm tướng -> giỏ đồ dùng chung
ROLE_FILLER = {
    "carry": "crit", "caster": "ap", "utility": "support",
    "tank": "tank", "fighter": "ad",
}


@dataclass
class BuildSlot:
    item: dict
    kind: str
    reasons: list[str]
    source: str          # "khắc chế" | "món chuẩn" | "chỉ số"


@dataclass
class FullBuild:
    champion: dict
    role: str | None
    slots: list[BuildSlot] = field(default_factory=list)
    enemies: list[str] = field(default_factory=list)


@lru_cache(maxsize=1)
def load_builds() -> dict[str, dict]:
    try:
        return json.loads((data_dir() / "builds.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


# nhóm chỉ số -> tag trang bị dùng để lấp ô trống
KIND_TAGS = {
    "crit": {"Damage", "CriticalStrike", "AttackSpeed", "LifeSteal"},
    "ad": {"Damage", "Health", "LifeSteal"},
    "ap": {"SpellDamage", "MagicPenetration"},
    "tank": {"Health", "Armor", "SpellBlock"},
    "support": {"Health", "SpellDamage", "ManaRegen", "Aura"},
}
LEGENDARY = {"LEGENDARY", "MYTHIC"}


def _filler_items(champ: dict, role: str | None = None) -> list[int]:
    """Món hoàn chỉnh để lấp ô trống, ưu tiên món đắt (mạnh) và đúng nhóm tướng."""
    from .data import dataset

    ds = dataset()
    kind = _filler_kind(champ, role)
    wanted = KIND_TAGS.get(kind, set())
    pool = []
    for item in ds.items.values():
        if not (set(item.get("ranks") or []) & LEGENDARY):
            continue
        if item["gold"] < MIN_SLOT_GOLD:
            continue
        overlap = len(set(item.get("tags") or []) & wanted)
        if overlap:
            pool.append((overlap, item["gold"], item["id"]))
    pool.sort(key=lambda x: (-x[0], -x[1]))
    seen: list[int] = []
    for _overlap, _gold, item_id in pool:
        if item_id not in seen:
            seen.append(item_id)
    # nối thêm danh sách thủ công để chắc chắn đủ ô
    for item_id in FILLER[kind] + FILLER["tank"]:
        if item_id not in seen:
            seen.append(item_id)
    return seen


def _filler_kind(champ: dict, role: str | None = None) -> str:
    """Nhóm món tăng chỉ số phù hợp — suy từ chính tướng, không cần hỏi vai trò."""
    return ROLE_FILLER.get(role or role_of(champ), "ad")


def suggest_full_build(
    champion_key: str,
    enemy_keys: list[str] | None = None,
    size: int = 6,
) -> FullBuild:
    """6 món đầy đủ: giày + món chủ lực của tướng + món khắc chế + chỉ số.

    Có hạn mức ô cho từng nhóm, nếu không thì món khắc chế sẽ chiếm hết 6 ô và
    bạn ra trận với 0 sát thương (đúng lỗi của bản đầu tiên).
    """
    ds = dataset()
    champ = ds.champion(champion_key)
    if champ is None:
        raise KeyError(f"không có tướng {champion_key!r}")
    enemy_keys = enemy_keys or []
    role = role_of(champ)   # tự suy từ tướng, không hỏi người dùng

    build = FullBuild(
        champion=champ,
        role=role,
        enemies=[ds.champion(k)["name"] for k in enemy_keys if ds.champion(k)],
    )
    chosen: dict[int, BuildSlot] = {}
    kinds_used: set[str] = set()
    boots_taken: set[str] = set()

    def take(item: dict, kind: str, reasons: list[str], source: str) -> bool:
        if item["id"] in chosen or len(chosen) >= size:
            return False
        if kind in SINGLETON and kind in kinds_used:
            return False
        # giày có thể tới từ nhiều nhóm luật khác nhau (giày / giải khống chế),
        # nên phải chặn theo chính món đồ chứ không chỉ theo nhóm.
        if "Boots" in (item.get("tags") or []) and "boots" in boots_taken:
            return False
        # 6 ô cuối chỉ nhận món hoàn chỉnh: dữ liệu op.gg trả cả món thành phần
        # (Kiếm B.F., Nước Mắt Nữ Thần…) nên phải lọc theo bậc trang bị.
        ranks = set(item.get("ranks") or [])
        if source in ("món chuẩn", "chỉ số") and not (ranks & COMPLETED):
            return False
        chosen[item["id"]] = BuildSlot(item, kind, reasons, source)
        kinds_used.add(kind)
        if "Boots" in (item.get("tags") or []):
            boots_taken.add("boots")
        return True

    # ---- 1) giày (món chuẩn của tướng, không có thì lấy giày mặc định) ----
    std = load_builds().get(champ["key"])
    boot_item = None
    if std:
        for ids, plays in std.get("boots") or []:
            for item_id in ids:
                candidate = ds.item(item_id)
                if candidate is not None and candidate["gold"] > 0:
                    boot_item = candidate
                    take(candidate, "giày",
                         [f"giày được lên nhiều nhất cho {champ['name']} ({plays} trận)"],
                         "món chuẩn")
                    break
            if boot_item:
                break
    if boot_item is None:
        boot = ds.item(DEFAULT_BOOTS[_filler_kind(champ, role)])
        if boot is not None:
            take(boot, "giày", ["giày mặc định: tăng tốc độ di chuyển"], "chỉ số")

    # ---- 2) món chủ lực của tướng: tối đa 3 ô ----
    core_budget = 3
    if std:
        for ids, plays in std.get("core") or []:
            if core_budget <= 0:
                break
            added = 0
            for item_id in ids:
                item = ds.item(item_id)
                if item is None:
                    continue
                if take(item, "món chuẩn",
                        [f"món chủ lực của {champ['name']} ({plays} trận)"], "món chuẩn"):
                    added += 1
                    core_budget -= 1
            if added == 0:
                continue

    # ---- 3) món khắc chế đội địch: tối đa 2 ô ----
    counter, _profile, _notes = recommend(
        enemy_keys, role=role, max_total=20, max_per_kind=2
    )
    counter_budget = 2
    for sug in counter:
        if counter_budget <= 0:
            break
        if take(sug.item, sug.kind, sug.reasons, "khắc chế"):
            counter_budget -= 1

    # ---- 4) món chủ lực còn lại của tướng ----
    if std and len(chosen) < size:
        for field_name in ("core", "last"):
            for ids, plays in std.get(field_name) or []:
                if len(chosen) >= size:
                    break
                for item_id in ids:
                    item = ds.item(item_id)
                    if item is not None:
                        take(item, "món chuẩn",
                             [f"món chủ lực của {champ['name']} ({plays} trận)"],
                             "món chuẩn")

    # ---- 5) lấp bằng món hoàn chỉnh hợp nhóm tướng ----
    for item_id in _filler_items(champ, role):
        if len(chosen) >= size:
            break
        item = ds.item(item_id)
        if item is not None:
            take(item, "chỉ số", ["tăng chỉ số phù hợp với tướng của bạn"], "chỉ số")

    # bỏ món thành phần rẻ nếu món nâng cấp của nó cũng đã được chọn
    chosen_ids = set(chosen)
    for item_id, slot in list(chosen.items()):
        if slot.item["gold"] <= CHEAP_CUTOFF:
            if set(slot.item.get("into") or []) & (chosen_ids - {item_id}):
                del chosen[item_id]
                kinds_used.discard(slot.kind)

    # không để món quá rẻ chiếm ô (ví dụ Nước Mắt Nữ Thần 400 vàng)
    for item_id, slot in list(chosen.items()):
        if slot.item["gold"] < MIN_SLOT_GOLD and len(chosen) > size:
            del chosen[item_id]

    # sắp xếp: giày trước, rồi món chủ lực, rồi khắc chế, cuối là chỉ số
    order = {"món chuẩn": 0, "khắc chế": 1, "chỉ số": 2}
    build.slots = sorted(
        chosen.values(),
        key=lambda s: (
            0 if s.kind == "giày" else 1,
            order.get(s.source, 3),
            -KIND_PRIORITY.get(s.kind, 10),
        ),
    )[:size]
    return build


def format_text(build: FullBuild) -> str:
    from .advisor import ROLE_LABEL

    label = ROLE_LABEL.get(build.role or "", build.role or "")
    lines = [f"# Build đầy đủ: {build.champion['name']}"
             + (f" — nhóm {label}" if label else "")]
    if build.enemies:
        lines.append(f"# Địch: {', '.join(build.enemies)}")
    for i, slot in enumerate(build.slots, 1):
        lines.append(
            f"{i}. {slot.item['name']:<28} {slot.item['gold']:>5} vàng  "
            f"[{slot.source}/{slot.kind}]  {slot.reasons[0] if slot.reasons else ''}"
        )
    total = sum(s.item["gold"] for s in build.slots)
    lines.append(f"Tổng: {total} vàng")
    return "\n".join(lines)
