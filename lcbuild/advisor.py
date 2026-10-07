"""Bảng luật chọn đồ khắc chế theo đội hình địch.

Cách hoạt động: mỗi luật có một hàm `trigger(profile)` trả về danh sách tướng địch
kích hoạt luật đó (rỗng = không kích hoạt). Nhờ vậy lý do luôn nêu đích danh tướng
và không có luật nào bắn mà không rõ căn cứ.

Chỉ dùng item_id có thật trong data/items.json; `_validate_items()` chạy lúc import
nên id sai sẽ lỗi ngay, không lọt ra gợi ý rác.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .data import dataset
from .traits import LABELS, detect

# ------------------------------------------------------------------ hồ sơ đội địch


@dataclass
class Profile:
    champs: list[dict] = field(default_factory=list)
    traits: dict[str, set[str]] = field(default_factory=dict)  # key -> traits
    _name_by_key: dict[str, str] = field(default_factory=dict)

    def names(self, *traits: str, any_of: bool = True) -> list[str]:
        out: list[str] = []
        for key, traits_set in self.traits.items():
            ok = (
                any(t in traits_set for t in traits)
                if any_of
                else all(t in traits_set for t in traits)
            )
            if ok:
                out.append(self._name_by_key[key])
        return out

    def count(self, *traits: str, any_of: bool = True) -> int:
        return len(self.names(*traits, any_of=any_of))

    def has(self, *traits: str, any_of: bool = True) -> bool:
        return self.count(*traits, any_of=any_of) > 0

    @property
    def size(self) -> int:
        return len(self.champs)


def build_profile(enemy_keys: list[str]) -> Profile:
    ds = dataset()
    profile = Profile()
    for key in enemy_keys:
        champ = ds.champion(key)
        if champ is None:
            continue
        profile.champs.append(champ)
        profile.traits[champ["key"]] = detect(champ)
        profile._name_by_key[champ["key"]] = champ["name"]
    return profile


# ------------------------------------------------------------------ loại trang bị
RESIST = "kháng"
ANTIHEAL = "giảm hồi máu"
ANTISHIELD = "phá khiên"
BOOTS = "giày"
ANTIAUTO = "chống đánh thường"
PEN = "xuyên giáp/phép"
ANTITANK = "chống tướng trâu"
CLEANSE = "giải khống chế"
SURVIVAL = "sinh tồn"
SUPPORT = "hỗ trợ"
SNOWBALL = "mở giao tranh"

# Nhóm tướng — suy ra từ CHÍNH TƯỚNG bạn chơi, không hỏi người dùng.
# ARAM không có vai trò cố định nên hỏi "bạn đánh đường nào" là vô nghĩa.
FIGHTER = "fighter"
CARRY = "carry"
CASTER = "caster"
TANK = "tank"
UTILITY = "utility"

ROLE_LABEL = {
    FIGHTER: "đấu sĩ",
    CARRY: "xạ thủ",
    CASTER: "pháp sư",
    TANK: "đỡ đòn",
    UTILITY: "hỗ trợ",
}


def role_of(champ: dict) -> str:
    """Nhóm tướng của một tướng, suy từ chỉ số + vai trò Riot gán.

    Thứ tự xét quan trọng: xạ thủ trước (vì nhiều tướng lai cũng có sát thương phép),
    rồi mới tới đỡ đòn / pháp sư / hỗ trợ / đấu sĩ.
    """
    from .traits import detect

    traits = detect(champ)
    roles = set(champ.get("roles") or [])
    magic = champ.get("damage_type") in ("magic", "mixed")

    # hỗ trợ hồi máu/lá chắn là nhóm riêng, không lẫn với pháp sư
    if "enchanter" in traits:
        return UTILITY
    # xạ thủ: đánh xa, sát thương đến từ đòn đánh
    if "marksman" in roles and "dps" in traits:
        return CARRY
    # đỡ đòn: vai trò tank VÀ không phải pháp sư thuần
    if "tank" in roles and not (magic and "mage" in roles and "tank" not in roles):
        if "tank" in roles and "mage" in roles:
            # lai tank/mage (Malphite, Galio…): chọn theo chỉ số chống chịu
            tough = (champ.get("ratings") or {}).get("toughness") or 0
            return TANK if tough >= 3 else CASTER
        return TANK
    if "tank" in roles:
        return TANK
    # pháp sư: chủ lực phép
    if "ap_threat" in traits:
        return CASTER
    if "support" in roles:
        return UTILITY
    return FIGHTER


@dataclass
class Rule:
    id: str
    kind: str
    item_ids: list[int]
    reason: str                          # có {who} -> tên tướng địch
    score: float
    trigger: Callable[[Profile], list[str]]
    roles: tuple[str, ...] = ()


# ------------------------------------------------------------------ các luật

def _physical(p: Profile) -> list[str]:
    return p.names("physical_threat")


def _magic(p: Profile) -> list[str]:
    return p.names("magic_threat")


def _regen(p: Profile) -> list[str]:
    """Tướng hồi máu đáng phải mua đồ giảm hồi máu."""
    big = p.names("heal_big")
    return big if big else (p.names("regen") if p.count("regen") >= 2 else [])


def _shields(p: Profile) -> list[str]:
    names = p.names("shield")
    return names if len(names) >= 2 else []


def _crit(p: Profile) -> list[str]:
    return p.names("crit")


def _as_dps(p: Profile) -> list[str]:
    """Tướng sát thương chủ yếu đến từ đòn đánh."""
    return p.names("dps", "attack_speed")


def _hard_cc(p: Profile) -> list[str]:
    names = p.names("hard_cc")
    return names if len(names) >= 2 else []


def _lockdown(p: Profile) -> list[str]:
    """Khống chế đơn mục tiêu kéo dài (Malzahar, Warwick, Skarner…)."""
    return p.names("lockdown")


def _cleanse_names(p: Profile) -> list[str]:
    """Khống chế đủ nhiều để đáng mua đồ giải."""
    lockdown = _lockdown(p)
    return lockdown if lockdown else _hard_cc(p)


def _tanky(p: Profile) -> list[str]:
    return p.names("tanky")


def _hp_stack(p: Profile) -> list[str]:
    return p.names("max_hp", "percent_hp")


def _burst(p: Profile) -> list[str]:
    names = p.names("burst", "assassin")
    return names if len(names) >= 2 else []


def _heavy(mode: str, threshold: int = 3):
    """Luật chỉ bật khi tỉ lệ sát thương vượt ngưỡng."""

    def trigger(p: Profile) -> list[str]:
        names = _physical(p) if mode == "phys" else _magic(p)
        return names if len(names) >= threshold else []

    return trigger


def _mixed(p: Profile) -> list[str]:
    if len(_physical(p)) >= 2 and len(_magic(p)) >= 2:
        return p.names("physical_threat") + p.names("magic_threat")
    return []


RULES: list[Rule] = [
    # ------------------------------------------------ kháng theo loại sát thương
    Rule("armor_thornmail", RESIST, [3075],
         "{who} gây sát thương vật lý chủ yếu",
         62, _heavy("phys", 3), (FIGHTER, TANK)),
    Rule("armor_dd", RESIST, [6333], "{who} dồn sát thương vật lý bộc phát",
         56, lambda p: [n for n in _burst(p) if n in _physical(p)], (FIGHTER, CARRY)),
    Rule("mr_kaenic", RESIST, [2504], "{who} gây sát thương phép nặng",
         62, _heavy("magic", 3), (FIGHTER, TANK)),
    Rule("mr_spirit", RESIST, [3065],
         "{who} gây sát thương phép, bản thân lại cần hồi phục",
         58, lambda p: [n for n in _magic(p) if n in _regen(p)], (FIGHTER, TANK)),
    Rule("mr_force", RESIST, [4401], "{who} gây sát thương phép kéo dài",
         56, _heavy("magic", 2), (FIGHTER, TANK)),
    Rule("mixed_jaksho", RESIST, [6665],
         "địch chia đều sát thương vật lý lẫn phép ({who})",
         60, _mixed, (FIGHTER, TANK)),
    Rule("mixed_abyssal", RESIST, [8020],
         "địch chia đều cả hai loại sát thương ({who}) và đội bạn có phép",
         54, _mixed, (TANK,)),
    # ------------------------------------------------ chống đánh thường / chí mạng
    Rule("anti_crit_randuin", ANTIAUTO, [3143], "{who} gây sát thương chí mạng",
         72, _crit),
    Rule("anti_as_frozen", ANTIAUTO, [3110], "{who} phụ thuộc tốc độ đánh",
         66, lambda p: _as_dps(p) if len(_as_dps(p)) >= 2 else [], (FIGHTER, TANK)),
    Rule("anti_as_randuin", ANTIAUTO, [3143], "{who} sống bằng đòn đánh",
         60, lambda p: [n for n in _as_dps(p) if n in _physical(p)]),
    # ------------------------------------------------ giày
    Rule("boots_steel", BOOTS, [3047], "đội địch nặng sát thương vật lý",
         68, _heavy("phys", 3), (FIGHTER, TANK)),
    Rule("boots_mercs", BOOTS, [3111], "{who} khống chế nhiều, cần giảm thời gian bị giữ",
         68, _hard_cc, (FIGHTER, TANK, CASTER, UTILITY)),
    Rule("boots_upgrade_armor", BOOTS, [3173],
         "còn nhiều sát thương phép, nâng cấp Giày Giáp Sắt",
         40, lambda p: _mixed(p) or ([n for n in _magic(p) if len(_physical(p)) >= 2]),
         (FIGHTER, TANK)),
    # ------------------------------------------------ giảm hồi máu
    Rule("antiheal_thornmail", ANTIHEAL, [3075],
         "{who} hồi máu mạnh, Giáp Gai vừa giảm hồi máu vừa cho giáp",
         86, _regen, (FIGHTER, TANK)),
    Rule("antiheal_mortal", ANTIHEAL, [3033],
         "{who} hồi máu mạnh — Lời Nhắc Tử Vong là món giảm hồi máu cho xạ thủ",
         84, _regen, (CARRY,)),
    Rule("antiheal_morello", ANTIHEAL, [3165],
         "{who} hồi máu mạnh — Quỷ Thư Morello là món giảm hồi máu cho pháp sư",
         84, _regen, (CASTER,)),
    Rule("antiheal_chemtech", ANTIHEAL, [6609],
         "{who} hồi máu mạnh — Cưa Xích Hóa Kỹ dành cho đấu sĩ",
         82, _regen, (FIGHTER,)),
    Rule("antiheal_early_thorn", ANTIHEAL, [3076],
         "{who} hồi máu mạnh, mua sớm Áo Choàng Gai để ép đường",
         56, _regen, (FIGHTER, TANK)),
    Rule("antiheal_early_exec", ANTIHEAL, [3123],
         "{who} hồi máu mạnh, mua sớm Gươm Đồ Tể để ép đường",
         56, _regen, (CARRY, FIGHTER)),
    Rule("antiheal_early_orb", ANTIHEAL, [3916],
         "{who} hồi máu mạnh, mua sớm Ngọc Quên Lãng để ép đường",
         56, _regen, (CASTER,)),
    # ------------------------------------------------ phá khiên
    Rule("antishield_serpent", ANTISHIELD, [6695],
         "{who} tạo lá chắn cho bản thân/đồng đội, Phá Khiên cắt phần lớn lượng đó",
         80, _shields),
    # ------------------------------------------------ xuyên giáp / xuyên phép
    Rule("pen_void", PEN, [3135], "địch ({who}) xếp kháng phép, cần xuyên phép",
         60, lambda p: _magic(p) if len(p.names("tanky")) >= 2 else [], (CASTER,)),
    Rule("pen_bloodletter", PEN, [8010],
         "địch ({who}) xếp kháng phép, Lời Nguyền Huyết Tự giúp cả đội xuyên phép",
         56, lambda p: _mixed(p) if p.count("magic_threat") >= 2 else [], (CASTER,)),
    Rule("pen_ldr", PEN, [3036],
         "địch ({who}) xếp giáp, Nỏ Thần Dominik xuyên theo % máu tối đa",
         60, lambda p: _physical(p) if len(p.names("tanky")) >= 2 else [], (CARRY,)),
    Rule("pen_serylda", PEN, [6694], "địch ({who}) xếp giáp, kèm hiệu ứng làm chậm",
         58, lambda p: _physical(p) if len(p.names("tanky")) >= 2 else [], (FIGHTER,)),
    Rule("pen_cleaver", PEN, [3071],
         "địch ({who}) xếp giáp, Rìu Đen còn giúp đồng đội xuyên giáp",
         58, lambda p: _physical(p) if len(p.names("tanky")) >= 2 else [], (FIGHTER,)),
    # ------------------------------------------------ chống tướng trâu / nhiều máu
    Rule("tank_liandry", ANTITANK, [6653],
         "{who} trâu và nhiều máu, Liandry đốt theo % máu tối đa",
         62, lambda p: _tanky(p) + [n for n in _hp_stack(p) if n not in _tanky(p)], (CASTER,)),
    Rule("tank_botrk", ANTITANK, [3153],
         "{who} nhiều máu, Gươm Suy Vong hút theo % máu hiện tại",
         60, lambda p: _tanky(p) + [n for n in _hp_stack(p) if n not in _tanky(p)],
         (CARRY, FIGHTER)),
    Rule("tank_despair", ANTITANK, [2502],
         "{who} nhiều máu, Áo Choàng Diệt Vong đốt và hồi máu cho bạn",
         52, lambda p: _tanky(p) if len(_tanky(p)) >= 2 else [], (TANK,)),
    # ------------------------------------------------ khống chế / sinh tồn
    Rule("cleanse_qss", CLEANSE, [3139],
         "{who} khống chế, cần giải khống chế",
         76, _cleanse_names, (CARRY, FIGHTER)),
    Rule("cleanse_banshee", CLEANSE, [3102],
         "{who} mở giao tranh từ xa (móc, áp chế, mê hoặc)",
         68, _lockdown, (CASTER,)),
    Rule("cleanse_mikael", CLEANSE, [3222],
         "{who} khống chế đội bạn, Chuông Bảo Hộ Mikael giải cho đồng minh",
         66, _cleanse_names, (UTILITY,)),
    Rule("cleanse_merc", CLEANSE, [3111], "{who} khống chế nhiều, Giày Thủy Ngân giảm thời gian bị giữ",
         64, _hard_cc),
    Rule("survive_ga", SURVIVAL, [3026],
         "địch ({who}) dồn sát thương bộc phát, Giáp Thiên Thần cho thêm một mạng",
         58, _burst),
    Rule("survive_maw", SURVIVAL, [3156],
         "{who} gây sát thương phép bộc phát, Chùy Gai Malmortius cho lá chắn phép",
         56, lambda p: [n for n in _burst(p) if n in _magic(p)], (FIGHTER, CARRY)),
    Rule("survive_sterak", SURVIVAL, [3053],
         "địch ({who}) bộc phát mạnh, Móng Vuốt Sterak cho lá chắn + máu",
         54, _burst, (FIGHTER,)),
    Rule("survive_zhonya", SURVIVAL, [3157],
         "{who} lao vào ám sát, Đồng Hồ Cát Zhonya để chờ đồng đội",
         56, lambda p: _burst(p) if p.count("assassin") >= 1 else [], (CASTER,)),
    # ------------------------------------------------ đồ hỗ trợ
    Rule("sup_locket", SUPPORT, [3190],
         "địch ({who}) có nhiều sát thương bộc phát, Dây Chuyền Iron Solari che đồng đội",
         52, _burst, (UTILITY,)),
    Rule("sup_knight", SUPPORT, [3109],
         "{who} dồn sát thương, Lời Thề Hiệp Sĩ chia sẻ bớt sát thương",
         50, lambda p: _burst(p)[:1], (UTILITY,)),
    Rule("sup_zeke", SUPPORT, [3050],
         "địch đánh thường nhiều, Tụ Bão Zeke làm chậm và thêm sát thương",
         46, lambda p: _as_dps(p) if len(_as_dps(p)) >= 2 else [], (UTILITY,)),
    Rule("sup_shurelya", SNOWBALL, [2065],
         "địch cơ động/khống chế nhiều ({who}), Shurelya để mở hoặc thoát giao tranh",
         44, lambda p: p.names("mobile") if p.count("hard_cc") >= 2 or
         p.count("mobile") >= 3 else [], (UTILITY,)),
    Rule("sup_redemption", SUPPORT, [3107],
         "đội hình địch gây sát thương theo vùng, Dây Chuyền Chuộc Tội hồi máu diện rộng",
         42, lambda p: p.names("zone_damage") if p.count("zone_damage") >= 2 else [],
         (UTILITY,)),
    # ------------------------------------------------ chống hồi máu cho đồ đấu sĩ phép
    Rule("ap_tank_void", PEN, [3135],
         "địch trâu kháng phép ({who})",
         58, lambda p: _magic(p) if p.count("magic_threat") >= 2 else [], (CASTER,)),
]

# ------------------------------------------------------------------ kiểm tra & nạp


def _item(item_id: int) -> dict:
    item = dataset().item(item_id)
    if item is None:
        raise KeyError(f"trang bị id={item_id} không có trong data/items.json")
    return item


def _validate() -> None:
    seen: set[str] = set()
    for rule in RULES:
        if rule.id in seen:
            raise ValueError(f"trùng id luật: {rule.id}")
        seen.add(rule.id)
        for item_id in rule.item_ids:
            item = _item(item_id)
            if item["gold"] <= 0:
                raise ValueError(f"luật {rule.id}: {item['name']} không mua được")
        unknown = set(rule.roles) - set(ROLE_LABEL)
        if unknown:
            raise ValueError(f"luật {rule.id}: nhóm tướng lạ {unknown}")


_validate()

# ------------------------------------------------------------------ máy gợi ý


@dataclass
class Suggestion:
    item: dict
    kind: str
    score: float
    reasons: list[str]
    rules: list[str]


def _gate(rule: Rule, role: str | None) -> bool:
    """Luật này có hợp với nhóm tướng không. role=None -> bỏ qua luật giới hạn."""
    if not rule.roles:
        return True
    return role is not None and role in rule.roles


def recommend(
    enemy_keys: list[str],
    role: str | None = None,
    max_total: int = 12,
    max_per_kind: int = 2,
) -> tuple[list[Suggestion], Profile, list[str]]:
    """(danh sách gợi ý đã xếp hạng, hồ sơ đội địch, ghi chú tổng quan)."""
    profile = build_profile(enemy_keys)
    if not profile.size:
        return [], profile, ["Chưa nhận diện được tướng địch nào."]

    found: dict[int, Suggestion] = {}
    for rule in RULES:
        if not _gate(rule, role):
            continue
        who = rule.trigger(profile)
        if not who:
            continue
        names = ", ".join(who[:3]) + ("…" if len(who) > 3 else "")
        for item_id in rule.item_ids:
            item = _item(item_id)
            score = rule.score + min(len(who), 3)
            entry = found.get(item_id)
            if entry is None:
                found[item_id] = Suggestion(
                    item, rule.kind, score, [rule.reason.format(who=names)], [rule.id]
                )
            else:
                entry.score = max(entry.score, score)
                entry.rules.append(rule.id)
                reason = rule.reason.format(who=names)
                if reason not in entry.reasons:
                    entry.reasons.append(reason)

    ordered = sorted(found.values(), key=lambda s: (-s.score, s.item["gold"]))
    per_kind: dict[str, int] = {}
    kept: list[Suggestion] = []
    for sug in ordered:
        per_kind[sug.kind] = per_kind.get(sug.kind, 0) + 1
        if per_kind[sug.kind] <= max_per_kind:
            kept.append(sug)
        if len(kept) >= max_total:
            break
    return kept, profile, overview(profile)


def overview(p: Profile) -> list[str]:
    """Tóm tắt đội hình địch -> hướng lên đồ."""
    notes: list[str] = []
    physical = p.names("physical_threat")
    magic = p.names("magic_threat")
    if len(physical) >= 3:
        notes.append(
            f"Địch nặng sát thương vật lý ({len(physical)}/{p.size} tướng) → ưu tiên Giáp."
        )
    if len(magic) >= 3:
        notes.append(
            f"Địch nặng sát thương phép ({len(magic)}/{p.size} tướng) → ưu tiên Kháng Phép."
        )
    if len(physical) >= 2 and len(magic) >= 2:
        notes.append("Địch chia đều vật lý và phép → cần đồ kháng hỗn hợp (Jak'Sho).")
    regen = p.names("regen")
    if len(regen) >= 2:
        notes.append(
            f"{len(regen)} tướng hồi máu ({', '.join(regen[:3])}…) → phải có Giảm Hồi Máu."
        )
    elif p.names("heal_big"):
        notes.append(f"{', '.join(p.names('heal_big'))} hồi máu rất mạnh → nên có Giảm Hồi Máu.")
    shield = p.names("shield")
    if len(shield) >= 2:
        notes.append(
            f"{len(shield)} tướng tạo lá chắn ({', '.join(shield[:3])}…) → Kiếm Ác Xà hiệu quả."
        )
    crit = p.names("crit")
    if len(crit) >= 2:
        notes.append(f"{len(crit)} tướng gây chí mạng → Khiên Băng Randuin.")
    cc = p.names("hard_cc")
    if len(cc) >= 2:
        notes.append(f"{len(cc)} tướng khống chế cứng → Giày Thủy Ngân / đồ giải khống chế.")
    tank = p.names("tanky")
    if len(tank) >= 2:
        notes.append(f"{len(tank)} tướng trâu → cần xuyên giáp/xuyên phép theo % máu.")
    if not notes:
        notes.append("Đội hình địch cân bằng — lên đồ theo món đối đầu trực tiếp ở đường.")
    return notes


NOTE_ORDER = [
    "heal_big", "heal", "lifesteal", "shield", "true_damage", "percent_hp", "crit",
    "attack_speed", "burst", "hard_cc", "heavy_cc", "lockdown", "stealth", "mobile",
    "tanky", "max_hp", "assassin", "dps", "enchanter", "magic_threat",
    "physical_threat", "magic_melee", "zone_damage", "sustain_zone",
]


def champion_notes(champ: dict) -> list[str]:
    traits = detect(champ)
    return [LABELS[t] for t in NOTE_ORDER if t in traits]
