"""Gợi ý Lõi (Augment) cho ARAM: Mayhem.

Dữ liệu lõi đọc từ data/augments.json (xem lcbuild/fetch_augments.py).
Mỗi luật nêu rõ vì sao hợp với TƯỚNG CỦA BẠN và/hoặc ĐỘI HÌNH ĐỊCH; tên lõi được
kiểm tra tồn tại lúc import nên không thể gợi ý lõi ma.

Trong game bạn chọn lõi theo tên hiển thị; công cụ không đọc được 3 lựa chọn đang
hiện ra (Live Client API không có dữ liệu lõi), nên nó xếp hạng cả pool.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Callable

from .data import dataset
from .paths import data_dir
from .traits import detect

# Bậc mạnh yếu do playaram.gg xếp hạng; dùng để xếp hạng khi không có luật riêng.
# trọng số khi kết hợp điểm luật (hợp tướng/đội hình) với bậc xếp hạng chung.
# Chỉ dùng điểm luật thì lõi bậc D có thể vượt lõi bậc S+; chỉ dùng bậc thì mất hết
# yếu tố "hợp tướng này, hợp đội hình kia".
RULE_WEIGHT = 0.55

TIER_ORDER = ("S+", "S", "A", "B", "C", "D")
TIER_LABEL = {
    "S+": "Bậc S+",
    "S": "Bậc S",
    "A": "Bậc A",
    "B": "Bậc B",
    "C": "Bậc C",
    "D": "Bậc D",
}
TIER_COLOR = {
    "S+": "#ff7a7a",
    "S": "#ffb74d",
    "A": "#ffd54f",
    "B": "#9fd97a",
    "C": "#7fc4ff",
    "D": "#9aa0a6",
}
# độ hiếm (bậc lõi) — dùng để hiện màu và nhóm
RARITY_LABEL = {
    "prismatic": "Kim Cương",
    "gold": "Vàng",
    "silver": "Bạc",
}
RARITY_COLOR = {
    "prismatic": "#b98cff",
    "gold": "#e0b23c",
    "silver": "#9fb0c0",
}


@dataclass
class Augment:
    key: str                  # khoá ổn định (không dấu, không ký tự lạ)
    name: str
    tier: str                 # bậc mạnh yếu: S+ … D
    rarity: str               # độ hiếm: prismatic / gold / silver
    tier_score: float         # điểm nền theo bậc
    categories: list[str]     # ad / ap / tank / crit / support / cd / amp / mechanic
    description: str          # mô tả tiếng Việt (đã giải đầy đủ số liệu)
    icon: str | None


@lru_cache(maxsize=1)
def load_augments() -> dict[str, Augment]:
    raw = json.loads((data_dir() / "augments.json").read_text(encoding="utf-8"))
    out: dict[str, Augment] = {}
    for entry in raw:
        name = entry.get("name") or entry.get("slug") or ""
        key = entry.get("key") or re.sub(r"[^a-z0-9]", "", str(entry.get("slug", name)).lower())
        out[key] = Augment(
            key=key,
            name=name,
            tier=entry.get("tier") or "C",
            rarity=entry.get("rarity") or "silver",
            tier_score=float(entry.get("tier_score") or 50.0),
            categories=list(entry.get("categories") or []),
            description=entry.get("description") or "",
            icon=entry.get("icon"),
        )
    return out


# ------------------------------------------------------------------ ngữ cảnh

@dataclass
class Ctx:
    """Tướng của bạn + đội hình địch, đủ để mọi luật ra quyết định."""

    champ: dict
    traits: set[str] = field(default_factory=set)
    enemies: object | None = None       # advisor.Profile

    def has(self, *tags: str) -> bool:
        return all(t in self.traits for t in tags)

    def any(self, *tags: str) -> bool:
        return any(t in self.traits for t in tags)

    def foes(self, *tags: str) -> int:
        return self.enemies.count(*tags) if self.enemies else 0

    @property
    def auto_attacker(self) -> bool:
        """Sát thương chính đến từ đòn đánh vật lý.

        Chỉ dựa vào `dps` (vai trò marksman) là sai: Data Dragon gắn cả pháp sư
        như Aurelion Sol, Karthus, Ryze vào marksman. Nên phải kèm sát thương vật lý.
        """
        return self.has("crit") or (self.has("dps") and self.has("ad_threat"))

    @property
    def caster(self) -> bool:
        """Sát thương chính đến từ kỹ năng phép."""
        return self.has("ap_threat") and not self.any("dps")


@dataclass(frozen=True)
class AugmentRule:
    id: str
    keys: tuple[str, ...]     # khoá lõi (xem fetch_augments.aug_key)
    score: float
    reason: str
    cond: Callable[[Ctx], bool]


def _need(name: str) -> str:
    return f"{{champ}} {name}"


# ------------------------------------------------------------------ bảng luật
RULES: list[AugmentRule] = [
    # ============ đấu sĩ / xạ thủ vật lý ============
    AugmentRule("draw_your_sword", ("drawyoursword",), 94,
                "tướng đánh xa chuyển sang cận chiến kèm +30% AD, +25% Tốc Độ Đánh, +30% máu",
                lambda c: c.has("ranged") and c.has("ad_threat")),
    AugmentRule("dual_wield", ("dualwield",), 82,
                "đòn đánh bắn thêm tia theo % AD",
                lambda c: c.auto_attacker),
    AugmentRule("fan_the_hammer", ("fanthehammer",), 78,
                "đòn đánh kế tiếp theo 4 hướng bắn thêm 5 tia",
                lambda c: c.auto_attacker),
    AugmentRule("freeze_burn", ("triggeredinferno",), 76,
                "đòn đánh/kỹ năng lên tướng khác nhau gây thêm sát thương theo thời gian",
                lambda c: c.auto_attacker or c.caster),
    AugmentRule("execute", ("dropkick",), 80,
                "chiêu cuối kết liễu tướng dưới ngưỡng máu",
                lambda c: c.has("assassin") or c.has("burst")),
    AugmentRule("ult_reset_ks", ("itskillingtime",), 78,
                "dùng chiêu cuối là đánh dấu Tử Ấn lên mọi tướng địch",
                lambda c: c.has("assassin")),
    AugmentRule("fey_magic", ("feymagic",), 74,
                "chiêu cuối biến tướng địch thành thú nhỏ",
                lambda c: c.has("hard_cc")),
    AugmentRule("stuck_with_me", ("stuckinherewithme",), 70,
                "chiêu cuối tạo vùng cấm địch rời ra",
                lambda c: c.has("tanky")),
    AugmentRule("ad_percent", ("bluntforce",), 92,
                "tăng thẳng 20% Sức Mạnh Công Kích — lõi Bạc mạnh nhất cho tướng AD",
                lambda c: c.has("ad_threat")),
    AugmentRule("as_flat", ("deft",), 88,
                "cộng 60% Tốc Độ Đánh, rất hợp tướng sống bằng đòn đánh",
                lambda c: c.auto_attacker),
    AugmentRule("omnivamp", ("goredrink",), 90,
                "15% hút máu toàn phần — duy trì giao tranh liên tục ở ARAM",
                lambda c: c.has("ad_threat") and not c.caster),
    AugmentRule("conqueror", ("symphonyofwar",), 86,
                "cho sẵn Chinh Phục + Nhịp Độ Chết Người, hợp tướng đánh lâu",
                lambda c: c.auto_attacker),
    AugmentRule("heavy_hitter", ("heavyhitter",), 84,
                "đòn đánh gây thêm 3,5% máu tối đa — ăn cả tướng trâu",
                lambda c: c.auto_attacker or c.has("tanky")),
    AugmentRule("twin_fire", ("twinfire",), 78,
                "kỹ năng bắn thêm tên lửa, tăng sát thương theo Tỉ Lệ Chí Mạng",
                lambda c: c.has("crit")),
    AugmentRule("tap_dancer", ("tapdancer",), 70,
                "đánh trúng là tăng Tốc Độ Di Chuyển — né chiêu tốt hơn",
                lambda c: c.auto_attacker),
    AugmentRule("magic_missile", ("magicmissile",), 74,
                "kỹ năng gây thêm 3 tên lửa — hợp tướng spam chiêu",
                lambda c: c.caster or c.has("ap_threat")),
    AugmentRule("marksmage", ("marksmage",), 82,
                "đòn đánh gây thêm 75% Sức Mạnh Phép — lõi cho tướng lai AP",
                lambda c: c.has("ap_threat") and c.auto_attacker),
    AugmentRule("mystic_punch", ("mysticpunch",), 80,
                "đòn đánh giảm hồi chiêu kỹ năng — xoay chiêu liên tục",
                lambda c: c.auto_attacker and c.has("ap_threat")
                or c.auto_attacker),
    AugmentRule("goldrend", ("goldrend",), 76,
                "đòn đánh/kỹ năng lên tướng gây thêm sát thương theo AD + AP",
                lambda c: c.has("ad_threat")),
    # ============ chí mạng ============
    AugmentRule("crit_chance", ("itscritical",), 92,
                "cộng thẳng 50% Tỉ Lệ Chí Mạng",
                lambda c: c.has("crit")),
    AugmentRule("crit_heal", ("soulsiphon",), 88,
                "chí mạng hồi máu 12% sát thương — sống sót khi giao tranh",
                lambda c: c.has("crit")),
    AugmentRule("crit_as", ("criticalrhythm",), 84,
                "chí mạng cộng dồn Tốc Độ Đánh",
                lambda c: c.has("crit")),
    AugmentRule("crit_missile", ("criticalmissile",), 80,
                "chí mạng bắn thêm tên lửa — thêm sát thương diện rộng",
                lambda c: c.has("crit")),
    AugmentRule("double_tap", ("doubletap",), 82,
                "đòn chí mạng kích hoạt hiệu ứng trên đòn thêm một lần",
                lambda c: c.has("crit")),
    AugmentRule("crit_conversion", ("tankitorleaveit",), 66,
                "đổi Tỉ Lệ Chí Mạng thành khả năng chống đỡ",
                lambda c: c.has("crit") and c.has("tanky")),
    AugmentRule("zealot", ("zealot",), 74,
                "cộng Tốc Độ Đánh và Tỉ Lệ Chí Mạng theo Sức Mạnh Phép",
                lambda c: c.has("crit")),
    AugmentRule("vulnerability", ("vulnerability",), 78,
                "sát thương trang bị và hiệu ứng theo thời gian có thể chí mạng",
                lambda c: c.has("crit") or c.has("ad_threat")),
    AugmentRule("crit_heal_shield", ("criticalhealing",), 70,
                "hồi máu/lá chắn có thể tăng theo Tỉ Lệ Chí Mạng",
                lambda c: c.has("crit")),
    # ============ pháp sư ============
    AugmentRule("ability_crit", ("jeweledgauntlet",), 96,
                "kỹ năng có thể chí mạng — lõi mạnh nhất cho pháp sư",
                lambda c: c.caster),
    AugmentRule("haste_ap", ("eureka",), 92,
                "Điểm Hồi Kỹ Năng bằng 30% Sức Mạnh Phép — pháp sư spam chiêu",
                lambda c: c.caster),
    AugmentRule("ap_flat", ("witchfulthinking",), 86,
                "cộng 20-80 Sức Mạnh Phép theo cấp",
                lambda c: c.caster),
    AugmentRule("haste_flat", ("recursion",), 84,
                "cộng 60 Điểm Hồi Kỹ Năng",
                lambda c: c.caster or c.has("hard_cc")),
    AugmentRule("back_to_basics", ("backtobasics",), 90,
                "kỹ năng gây thêm 35% sát thương, +70 hồi kỹ năng (đổi lại mất chiêu cuối)",
                lambda c: c.caster and c.foes("tanky") == 0),
    AugmentRule("archmage", ("archmage",), 76,
                "niệm chiêu hoàn lại hồi chiêu của chiêu khác — spam tốt hơn",
                lambda c: c.caster),
    AugmentRule("big_brain", ("bigbrain",), 74,
                "lá chắn bằng 300% Sức Mạnh Phép — chống đỡ cho pháp sư",
                lambda c: c.has("ap_threat")),
    AugmentRule("infernal_conduit", ("infernalconduit",), 88,
                "kỹ năng đốt theo thời gian, cộng dồn vô hạn",
                lambda c: c.caster),
    AugmentRule("ap_to_ad", ("escapade",), 60,
                "đổi Sức Mạnh Phép thành Sức Mạnh Công Kích",
                lambda c: c.has("ad_threat") and c.has("ap_threat")),
    AugmentRule("ethereal", ("etherealweapon",), 80,
                "kỹ năng kích hoạt hiệu ứng đòn đánh",
                lambda c: c.caster and c.has("attack_speed")),
    AugmentRule("overflow", ("overflow",), 68,
                "tốn mana gấp đôi nhưng tăng 10% sát thương",
                lambda c: c.caster),
    AugmentRule("phenomenal_evil", ("phenomenalevil",), 72,
                "mỗi lần tiêu diệt/tung chiêu tích luỹ sức mạnh vĩnh viễn",
                lambda c: c.caster),
    AugmentRule("duality", ("masterofduality",), 74,
                "đòn đánh cho Sức Mạnh Phép, kỹ năng cho Sức Mạnh Công Kích",
                lambda c: c.has("ap_threat") and c.auto_attacker),
    AugmentRule("ad_to_ap", ("adapt",), 62,
                "đổi Sức Mạnh Công Kích thành Sức Mạnh Phép",
                lambda c: c.has("ap_threat") and c.has("ad_threat")),
    # ============ chống chịu / đỡ đòn ============
    AugmentRule("hp_percent", ("goliath",), 92,
                "cộng 35% máu tối đa — tuyến trước dày hơn hẳn",
                lambda c: c.has("tanky")),
    AugmentRule("celestial", ("celestialbody",), 78,
                "cộng 1250 máu (đổi lại giảm 10% sát thương) — hợp người chịu đòn",
                lambda c: c.has("tanky")),
    AugmentRule("tank_engine", ("tankengine",), 86,
                "mỗi mạng hạ gục cộng 5% máu tối đa vô hạn",
                lambda c: c.has("tanky")),
    AugmentRule("porcupine", ("porcupine",), 72,
                "bị đánh trả lại sát thương và làm chậm",
                lambda c: c.has("tanky")),
    AugmentRule("pressure_cooker", ("pressurecooker",), 80,
                "đốt liên tục theo máu tối đa quanh bản thân",
                lambda c: c.has("tanky")),
    AugmentRule("ocean_soul", ("oceansoul",), 70,
                "hồi máu theo sát thương gây ra — trụ đường tốt",
                lambda c: c.has("tanky")),
    AugmentRule("mountain_soul", ("mountainsoul",), 72,
                "lá chắn theo máu tối đa",
                lambda c: c.has("tanky")),
    AugmentRule("warmog_style", ("mindtomatter",), 64,
                "đổi 50% năng lượng tối đa thành máu",
                lambda c: c.has("tanky")),
    AugmentRule("titan", ("titansresolve",), 74,
                "tích cộng dồn khi giao tranh để tăng Sức Mạnh Thích Ứng + Giáp/Kháng Phép",
                lambda c: c.has("tanky")),
    AugmentRule("minionmancer", ("minionmancer",), 70,
                "thú triệu hồi mạnh hơn 40%",
                lambda c: c.has("summon")),
    AugmentRule("stackosaurus", ("stackosaurusrex",), 88,
                "tăng 100% tốc độ tích cộng dồn vĩnh viễn — lõi cực mạnh cho tướng tích stack",
                lambda c: c.has("max_hp") or c.has("percent_hp")),
    # ============ hồi máu / lá chắn ============
    AugmentRule("heal_shield_20", ("firstaidkit",), 88,
                "cộng 20% hiệu lực hồi máu và lá chắn cho cả bản thân lẫn đồng đội",
                lambda c: c.has("enchanter") or (c.any("shield") and c.has("heal"))),
    AugmentRule("all_for_you", ("allforyou",), 84,
                "hồi máu/lá chắn cho đồng đội mạnh hơn 30%",
                lambda c: c.has("enchanter") or (c.any("shield") and c.has("heal"))),
    AugmentRule("heal_to_damage", ("circleofdeath",), 82,
                "hồi máu của bạn gây sát thương phép ra xung quanh",
                lambda c: c.has("heal") or c.has("regen")),
    AugmentRule("spirit_bomb", ("spiritbomb",), 74,
                "hồi máu/lá chắn đồng đội tích thành bom nổ",
                lambda c: c.any("enchanter", "shield")),
    AugmentRule("sonic_boom", ("sonicboom",), 72,
                "hồi máu/lá chắn cho đồng minh gây sát thương chuẩn quanh họ",
                lambda c: c.any("enchanter", "shield")),
    AugmentRule("protein", ("proteinshake",), 70,
                "tăng hiệu lực hồi máu/lá chắn theo Giáp và Kháng Phép",
                lambda c: c.any("enchanter", "shield") and c.has("tanky")),
    AugmentRule("windspeaker", ("windspeakersblessing",), 72,
                "hồi máu/lá chắn cho thêm Tốc Độ Di Chuyển cho mục tiêu",
                lambda c: c.any("enchanter", "shield")),
    # ============ khống chế / mở giao tranh ============
    AugmentRule("cc_shield_heavy", ("courageofthecolossus",), 94,
                "{champ} khống chế nhiều → mỗi lần khống chế địch là có lá chắn",
                lambda c: c.has("heavy_cc")),
    AugmentRule("cc_shield", ("courageofthecolossus",), 76,
                "khống chế địch là nhận lá chắn — vào giao tranh an toàn hơn",
                lambda c: c.has("hard_cc")),
    AugmentRule("cc_comet_heavy", ("cruelty",), 90,
                "{champ} khống chế nhiều → sao băng giáng liên tục",
                lambda c: c.has("heavy_cc")),
    AugmentRule("cc_comet", ("cruelty",), 72,
                "khống chế địch là gọi sao băng giáng xuống",
                lambda c: c.has("hard_cc")),
    AugmentRule("cc_soul_eater_heavy", ("souleater",), 92,
                "{champ} khống chế nhiều → cộng máu vĩnh viễn mỗi lần khống chế",
                lambda c: c.has("heavy_cc")),
    AugmentRule("cc_soul_eater", ("souleater",), 74,
                "khống chế địch cộng máu vĩnh viễn",
                lambda c: c.has("hard_cc")),
    AugmentRule("cc_slap_heavy", ("slaparound",), 88,
                "{champ} khống chế nhiều → cộng Sức Mạnh Thích Ứng vĩnh viễn",
                lambda c: c.has("heavy_cc")),
    AugmentRule("cc_slap", ("slaparound",), 70,
                "khống chế địch cộng Sức Mạnh Thích Ứng vĩnh viễn",
                lambda c: c.has("hard_cc")),
    AugmentRule("cc_heal", ("ravenousbind",), 76,
                "khống chế bằng chiêu được chọn gây thêm sát thương và hồi máu",
                lambda c: c.has("hard_cc")),
    AugmentRule("cc_chain", ("chainreaction",), 74,
                "đẩy lùi trúng tướng khác thì hất tung và gây thêm sát thương",
                lambda c: c.has("hard_cc")),
    # ============ cơ động / sát thủ ============
    AugmentRule("dash_haste", ("dashing",), 90,
                "kỹ năng lướt/dịch chuyển được +175 Điểm Hồi Kỹ Năng",
                lambda c: c.has("mobile")),
    AugmentRule("dash_shield", ("swiftandsafe",), 84,
                "lướt xong nhận lá chắn — vào sâu mà vẫn sống",
                lambda c: c.has("mobile")),
    AugmentRule("dash_ms", ("shadowrunner",), 78,
                "lướt xong cộng 300 Tốc Độ Di Chuyển",
                lambda c: c.has("mobile")),
    AugmentRule("dash_resist", ("outlawsgrit",), 76,
                "lướt xong cộng Giáp và Kháng Phép, cộng dồn 5 lần",
                lambda c: c.has("mobile") and c.foes("magic_threat") >= 1),
    AugmentRule("assassin_burst", ("frombeginningtoend",), 84,
                "cho sẵn Hái Tử Thần + Chiến Lợi Phẩm Đầu Tiên — sát thủ dồn sát thương",
                lambda c: c.has("assassin")),
    AugmentRule("nightstalking", ("nightstalking",), 80,
                "hạ gục trong 3 giây sau khi gây sát thương thì tàng hình",
                lambda c: c.has("assassin")),
    # ============ chống lại đội hình địch ============
    AugmentRule("vs_tank_pen", ("threadtheneedle",), 92,
                "địch có {foes} tướng trâu → cộng 18% xuyên giáp và xuyên phép",
                lambda c: c.foes("tanky") >= 2),
    AugmentRule("vs_tank_tooth", ("toothfairy",), 86,
                "địch trâu ({foes} tướng) → tích Xuyên Giáp và Xuyên Phép vĩnh viễn",
                lambda c: c.foes("tanky") >= 2),
    AugmentRule("vs_tank_erosion", ("erosion",), 84,
                "địch trâu ({foes} tướng) → mỗi đòn giảm Giáp/Kháng Phép của chúng",
                lambda c: c.foes("tanky") >= 2),
    AugmentRule("vs_tank_giant", ("giantslayer",), 80,
                "địch nhiều máu ({foes} tướng) → gây thêm sát thương lên tướng trâu",
                lambda c: c.foes("tanky") >= 2 or c.foes("max_hp") >= 1),
    AugmentRule("vs_tank_firebrand", ("firebrand",), 78,
                "địch nhiều máu → đòn đánh đốt theo % máu tối đa",
                lambda c: c.foes("tanky") >= 2),
    AugmentRule("vs_burst_escape", ("escapeplan",), 90,
                "địch dồn sát thương bộc phát ({foes} tướng) → dưới 35% máu là có lá chắn lớn",
                lambda c: c.foes("burst", "assassin") >= 2),
    AugmentRule("vs_burst_hellbent", ("hellbent",), 82,
                "địch bộc phát mạnh ({foes} tướng) → hồi sinh mạnh hơn sau khi chết",
                lambda c: c.foes("burst", "assassin") >= 2),
    AugmentRule("vs_burst_dawnbringer", ("dawnbringersresolve",), 84,
                "địch bộc phát mạnh → dưới 50% máu được hồi 30% máu tối đa",
                lambda c: c.foes("burst", "assassin") >= 2),
    AugmentRule("vs_cc_unstoppable", ("ultimateunstoppable",), 86,
                "địch nhiều khống chế ({foes} tướng) → miễn khống chế 3 giây khi dùng chiêu cuối",
                lambda c: c.foes("hard_cc") >= 2),
    AugmentRule("vs_cc_invuln", ("canttouchthis",), 80,
                "địch khống chế nhiều → bất tử 2 giây khi dùng chiêu cuối",
                lambda c: c.foes("hard_cc") >= 2),
    AugmentRule("vs_cc_slow_resist", ("legday",), 70,
                "địch làm chậm nhiều → cộng Tốc Độ Di Chuyển và kháng làm chậm",
                lambda c: c.foes("hard_cc", "slow") >= 2),
    AugmentRule("vs_heal", ("forgedbythemaster",), 84,
                "địch hồi máu mạnh ({foes} tướng) → tăng sát thương trang bị và lõi",
                lambda c: c.foes("regen") >= 2),
    # ============ chiêu cuối ============
    AugmentRule("ult_awakening", ("ultimateawakening",), 86,
                "dùng chiêu cuối là hồi lại toàn bộ chiêu thường",
                lambda c: (c.champ.get("ratings") or {}).get("abilityReliance", 0) >= 80),
    AugmentRule("ult_revolution", ("ultimaterevolution",), 80,
                "chiêu cuối được hồi lại gần như ngay lập tức",
                lambda c: (c.champ.get("ratings") or {}).get("abilityReliance", 0) >= 80),
    AugmentRule("ult_surge", ("surgefield",), 76,
                "dùng chiêu cuối tạo vùng tăng hồi kỹ năng và tốc độ cho cả đội",
                lambda c: c.has("ap_threat")),
    AugmentRule("ult_final_form", ("finalform",), 78,
                "dùng chiêu cuối nhận lá chắn theo máu tối đa — tuyến trước vào sâu",
                lambda c: c.has("tanky")),
    # ============ chọn chiêu (ability augment) ============
    AugmentRule("chosen_haste", ("breadandbutter",), 88,
                "chiêu Q được +100 Điểm Hồi Kỹ Năng — chọn Q khi game hỏi",
                lambda c: (c.champ.get("ratings") or {}).get("abilityReliance", 0) >= 70),
    AugmentRule("chosen_haste_w", ("breadandjam",), 84,
                "chiêu W được +100 Điểm Hồi Kỹ Năng — chọn W khi game hỏi",
                lambda c: (c.champ.get("ratings") or {}).get("abilityReliance", 0) >= 70),
    AugmentRule("chosen_haste_e", ("breadandcheese",), 82,
                "chiêu E được +100 Điểm Hồi Kỹ Năng — chọn E khi game hỏi",
                lambda c: (c.champ.get("ratings") or {}).get("abilityReliance", 0) >= 70),
    AugmentRule("chosen_triple", ("tripleshot",), 86,
                "chiêu được chọn bắn thêm 2 mục tiêu — chọn chiêu gây sát thương chính",
                lambda c: c.has("ad_threat") or c.has("ap_threat")),
    AugmentRule("chosen_split", ("spellsplit",), 80,
                "chiêu được chọn tách thành 2 đường đạn",
                lambda c: c.has("ap_threat")),
    AugmentRule("chosen_multishot", ("multishot",), 84,
                "chiêu được chọn bắn thêm đường đạn sau khi hoàn thành nhiệm vụ",
                lambda c: c.has("ad_threat") or c.has("ap_threat")),
    AugmentRule("chosen_reset", ("overloaded",), 82,
                "dùng chiêu khác là hồi lại chiêu được chọn",
                lambda c: (c.champ.get("ratings") or {}).get("abilityReliance", 0) >= 70),
    AugmentRule("chosen_echo", ("echocast",), 78,
                "chiêu được chọn được niệm thêm một lần bằng bản sao",
                lambda c: c.has("ap_threat")),
    AugmentRule("chosen_terrain", ("terraind",), 74,
                "chiêu được chọn gây sát thương theo vùng",
                lambda c: c.has("ap_threat")),
    AugmentRule("chosen_quickstep", ("quickstep",), 76,
                "dùng chiêu được chọn là lướt theo con trỏ",
                lambda c: c.has("mobile") or c.has("ap_threat")),
    AugmentRule("chosen_range", ("lilextrahelp",), 70,
                "tăng tầm đánh và Tốc Độ Đánh trong lúc dùng chiêu được chọn",
                lambda c: c.auto_attacker),
    AugmentRule("chosen_pursuit", ("pursuitofhaste",), 72,
                "trúng chiêu được chọn để tăng dần Điểm Hồi Kỹ Năng",
                lambda c: (c.champ.get("ratings") or {}).get("abilityReliance", 0) >= 70),
    # ============ tầm xa ============
    AugmentRule("range_250", ("scopiestweapons",), 84,
                "cộng 250 tầm đánh — xạ thủ/pháp sư đứng xa hơn hẳn",
                lambda c: c.has("ranged") and c.auto_attacker),
    AugmentRule("range_200", ("scopierweapons",), 80,
                "cộng 200 tầm đánh",
                lambda c: c.has("ranged") and c.auto_attacker),
    AugmentRule("range_75", ("scopedweapons",), 74,
                "cộng 75 tầm đánh",
                lambda c: c.has("ranged")),
    # ============ snowball / ARAM ============
    AugmentRule("snowball", ("snowday",), 66,
                "Ném Tuyết được +100 Điểm Hồi Kỹ Năng và gây thêm sát thương",
                lambda c: True),
    AugmentRule("snowball_big", ("biggestsnowballever",), 64,
                "Ném Tuyết to hơn, xuyên qua nhiều mục tiêu hơn",
                lambda c: True),
    AugmentRule("poro", ("porostampede",), 62,
                "cho Chiêu Triệu Hồi Poro Charge sau khi hoàn thành nhiệm vụ",
                lambda c: True),
    # ============ kinh tế / chỉ số chung ============
    AugmentRule("gold_now", ("donation",), 88,
                "nhận ngay 2500 vàng — mua được món lớn sớm hơn hẳn",
                lambda c: True),
    AugmentRule("anvils_5", ("statsonstatsonstats",), 90,
                "5 Đe Chỉ Số (tỉ lệ ra Vàng/Lăng Kính cao nhất)",
                lambda c: True),
    AugmentRule("anvils_4", ("statsonstats",), 84,
                "4 Đe Chỉ Số — tăng chỉ số gọn gàng, không cần điều kiện",
                lambda c: True),
    AugmentRule("anvils_3", ("stats",), 76,
                "3 Đe Chỉ Số — tăng chỉ số cơ bản",
                lambda c: True),
    AugmentRule("transmute_prismatic", ("transmuteprismatic",), 92,
                "đổi lõi Vàng này thành 1 lõi Lăng Kính ngẫu nhiên",
                lambda c: True),
    AugmentRule("transmute_chaos", ("transmutechaos",), 84,
                "nhận 2 lõi ngẫu nhiên — may rủi nhưng tiềm năng cao",
                lambda c: True),
    AugmentRule("pandora", ("pandorasbox",), 86,
                "biến toàn bộ lõi hiện có thành lõi Lăng Kính ngẫu nhiên",
                lambda c: c.champ is not None),
    AugmentRule("omni_soul", ("omnisoul",), 78,
                "nhận 3 Linh Hồn Rồng ngẫu nhiên",
                lambda c: True),
    AugmentRule("hextech_soul", ("hextechsoul",), 68,
                "nhận Linh Hồn Rồng Hextech (hút máu + hồi chiêu)",
                lambda c: True),
    AugmentRule("infernal_soul", ("infernalsoul",), 70,
                "nhận Linh Hồn Rồng Hỏa (thêm sát thương)",
                lambda c: True),
    AugmentRule("flash2", ("flash2",), 66,
                "thêm một Tốc Biến nữa + 70 hồi chiêu triệu hồi",
                lambda c: True),
    AugmentRule("homeguard", ("homeguard",), 62,
                "cộng 100% Tốc Độ Di Chuyển (mất 3 giây sau khi bị đánh)",
                lambda c: True),
]


def _clean(rules: list[AugmentRule]) -> list[AugmentRule]:
    return [r for r in rules if r.score > 0]


def validate() -> None:
    """Mọi tên lõi trong luật phải tồn tại trong dữ liệu đã tải."""
    known = load_augments()
    missing: list[str] = []
    for rule in RULES:
        for key in rule.keys:
            if key not in known:
                missing.append(f"{rule.id}: {key}")
    if missing:
        raise ValueError("luật lõi trỏ tới tên không có trong dữ liệu: " + "; ".join(missing))


@dataclass
class AugmentPick:
    augment: Augment
    score: float
    reasons: list[str]


def build_ctx(champion_key: str, enemy_keys: list[str] | None = None) -> Ctx:
    champ = dataset().champion(champion_key)
    if champ is None:
        raise KeyError(f"không có tướng {champion_key!r}")
    profile = None
    if enemy_keys:
        from .advisor import build_profile

        profile = build_profile(enemy_keys)
    return Ctx(champ=champ, traits=detect(champ), enemies=profile)


def rank_augments(
    champion_key: str,
    enemy_keys: list[str] | None = None,
    per_tier: int = 5,
) -> dict[str, list[AugmentPick]]:
    """Xếp hạng lõi theo từng bậc; ưu tiên lõi hợp tướng, sau đó tới lõi phổ quát."""
    validate()
    ctx = build_ctx(champion_key, enemy_keys)
    known = load_augments()

    # điểm nền theo bậc xếp hạng của playaram.gg: không bỏ sót lõi mạnh nào
    merged: dict[str, AugmentPick] = {}
    for aug in known.values():
        merged[aug.name] = AugmentPick(
            aug, aug.tier_score, [f"bậc {aug.tier} theo xếp hạng ARAM: Mayhem"]
        )

    for rule in RULES:
        if rule.score <= 0:
            continue
        try:
            ok = rule.cond(ctx)
        except Exception:
            ok = False
        if not ok:
            continue
        reason = rule.reason.replace("{champ}", ctx.champ["name"]).replace(
            "{foes}", str(ctx.foes("tanky") or ctx.foes("burst", "assassin") or "")
        )
        for key in rule.keys:
            aug = known.get(key)
            if aug is None:
                continue
            # Điểm cuối = kết hợp luật theo tướng/đội hình với bậc xếp hạng chung.
            # Nếu chỉ lấy điểm luật thì lõi bậc D vẫn có thể vượt lõi bậc S+; nếu chỉ
            # lấy bậc thì mất hết yếu tố "hợp tướng này, hợp đội hình kia".
            blended = rule.score * RULE_WEIGHT + aug.tier_score * (1 - RULE_WEIGHT)
            pick = merged.get(key)
            if pick is None:
                merged[key] = AugmentPick(aug, blended, [reason])
            else:
                pick.score = max(pick.score, blended)
                if reason not in pick.reasons:
                    # lý do theo tướng/đội hình phải đứng TRƯỚC lý do bậc xếp hạng
                    pick.reasons.insert(0, reason)

    out: dict[str, list[AugmentPick]] = {}
    for tier in TIER_ORDER:
        picks = [p for p in merged.values() if p.augment.tier == tier]
        picks.sort(key=lambda p: -p.score)
        out[tier] = picks[:per_tier]
    return out
