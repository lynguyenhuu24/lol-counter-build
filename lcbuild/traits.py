"""Trích xuất đặc điểm bộ kỹ năng tướng từ dữ liệu đã cache.

Ba lớp:
  1. PHRASES  - cụm từ có thật trong mô tả kỹ năng (Data Dragon vi_VN).
     Kiểm tra bằng `python -m lcbuild.traits_audit <trait>` để xem câu làm căn cứ.
  2. TAG_MAP  - championTagInfo do Riot gán trong CommunityDragon (Self Healing,
     Auto-attack, Durable…), bắt các ca mô tả không nói rõ.
  3. KIT      - cơ chế không nằm trong hai nguồn trên, phải kiểm tay khi Riot đổi
     chiêu. Mọi mục ở đây đều là chủ ý, không suy diễn.

Chỉ số dùng được (Meraki attributeRatings, 1..3): damage, toughness, control,
mobility, utility. `None` với tướng mới chưa có dữ liệu -> coi như 0.
"""
from __future__ import annotations

# ---------------------------------------------------------------- lớp 1: câu chữ
PHRASES: dict[str, tuple[str, ...]] = {
    # tự hồi máu cho bản thân (KHÔNG tính "hồi máu cho đồng minh")
    "heal": (
        "hồi máu cho bản thân",
        "hồi máu bằng một phần sát thương",
        "hồi máu khi gây sát thương",
        "hồi máu cho hắn",
        "hồi máu cho cô",
        "hồi máu cho ả",
        "hồi máu cho nó",
        "hồi máu dựa trên",
        "hồi máu dựa vào",
        "hồi máu lại dựa vào",
        "hồi máu một phần sát thương",
    ),
    "lifesteal": ("hút máu", "hút lấy máu", "hút máu cho bản thân"),
    "shield": ("tạo một lá chắn", "nhận một lá chắn", "nhận lá chắn", "lá chắn giảm dần"),
    "hard_cc": (
        "làm choáng", "hất tung", "khiêu khích", "mê hoặc", "sợ hãi",
        "áp chế", "hóa đá", "đóng băng", "trói chân", "trói buộc", "đẩy lùi",
    ),
    "crit": ("chí mạng", "tỉ lệ chí mạng"),
    "true_damage": ("sát thương chuẩn",),
    "burst": ("lượng lớn sát thương", "gây lượng lớn", "sát thương phép lớn",
              "sát thương cực lớn", "sát thương lớn lên một kẻ địch"),
    "stealth": ("tàng hình", "vô hình", "ngụy trang", "ẩn thân"),
    "sustain_zone": ("hồi máu cho các đồng minh", "hồi máu cho đồng minh"),
    "zone_damage": ("trong khu vực này", "theo thời gian trong khu vực",
                    "gây sát thương theo thời gian"),
}

# --- lớp 2: championTagInfo của CommunityDragon (Riot tự gán) ---
TAG_MAP: dict[str, set[str]] = {
    "Self Healing": {"heal", "regen"},
    "Auto-attack": {"dps", "attack_speed"},
    "Hypercarry": {"dps"},
    "Sustained Damage": {"dps"},
    "Burst": {"burst"},
    "Crowd Control": {"hard_cc"},
    "Durable": {"tanky"},
    "Mobile": {"mobile"},
    "Stealth": {"stealth"},
    "Summon": {"summon"},
    "Damage-over-Time": {"zone_damage"},
    "Ally Protection": {"protect"},
    "Initiator": {"initiator"},
    "Long Range": {"ranged"},
    "Dive": {"dive"},
    "Shapeshift": {"shapeshift"},
    "Battlecaster": {"magic_melee"},
    "Duelist": {"duelist"},
    "AoE": {"aoe"},
}

# --- lớp 3: bảng cơ chế kiểm tay ---------------------------------------------------
KIT: dict[str, set[str]] = {
    # --- Hồi máu mạnh / hút máu là cơ chế chính (nguồn: bộ chiêu + chỉ số) ---
    "Aatrox": {"heal", "lifesteal"},
    "Ahri": {"heal"},
    "Belveth": {"lifesteal"},
    "Briar": {"heal", "lifesteal"},
    "Camille": {"heal"},
    "Cassiopeia": {"heal"},
    "Chogath": {"heal", "max_hp"},
    "Darius": {"heal"},
    "DrMundo": {"heal", "heal_big", "max_hp"},
    "Elise": {"heal"},
    "Fiora": {"heal"},
    "Gangplank": {"heal"},
    "Garen": {"heal", "heal_big"},
    "Gwen": {"heal"},
    "Hecarim": {"heal"},
    "Illaoi": {"heal", "heal_big"},
    "Irelia": {"lifesteal"},
    "KSante": {"heal"},
    "Kayn": {"heal"},
    "LeeSin": {"lifesteal", "shield"},
    "Lillia": {"heal"},
    "Maokai": {"heal"},
    "Mordekaiser": {"heal", "shield"},
    "Nasus": {"heal", "lifesteal"},
    "Nidalee": {"heal"},
    "Nunu": {"heal"},
    "Olaf": {"lifesteal", "heal"},
    "Rengar": {"heal"},
    "Samira": {"heal"},
    "Sett": {"heal", "shield"},
    "Shyvana": {"heal"},
    "Sion": {"lifesteal", "max_hp", "shield"},
    "Swain": {"heal", "heal_big"},
    "Sylas": {"heal"},
    "TahmKench": {"heal", "heal_big", "max_hp", "shield"},
    "Taric": {"heal", "shield"},
    "Trundle": {"heal"},
    "Tryndamere": {"heal", "crit"},
    "Udyr": {"heal", "shield"},
    "Viego": {"lifesteal", "heal"},
    "Vladimir": {"heal", "heal_big"},
    "Volibear": {"heal", "shield"},
    "Warwick": {"heal", "lifesteal"},
    "Yone": {"heal", "shield", "crit"},
    "Yorick": {"heal"},
    "Yuumi": {"heal", "shield"},
    "Zac": {"heal", "heal_big"},
    # --- Tạo lá chắn (đội địch có khiên -> Kiếm Ác Xà) ---
    "Ambessa": {"shield"},
    "Annie": {"shield"},
    "Azir": {"shield"},
    "Blitzcrank": {"shield"},
    "Braum": {"shield"},
    "Diana": {"shield"},
    "Ekko": {"shield"},
    "Ivern": {"shield"},
    "Janna": {"shield"},
    "Kaisa": {"shield"},
    "Karma": {"shield"},
    "Kassadin": {"shield"},
    "Kled": {"shield"},
    "Leona": {"shield"},
    "Lulu": {"shield"},
    "Malphite": {"shield"},
    "Milio": {"shield", "heal"},
    "Morgana": {"shield"},
    "Nautilus": {"shield"},
    "Nocturne": {"shield"},
    "Orianna": {"shield"},
    "Pantheon": {"shield"},
    "Poppy": {"shield"},
    "Rakan": {"shield", "heal"},
    "Rell": {"shield"},
    "Renata": {"shield"},
    "Renekton": {"shield"},
    "Riven": {"shield"},
    "Rumble": {"shield"},
    "Ryze": {"shield"},
    "Senna": {"shield", "heal"},
    "Seraphine": {"shield", "heal"},
    "Shen": {"shield"},
    "Skarner": {"shield"},
    "Sona": {"shield", "heal"},
    "Vi": {"shield"},
    "Viktor": {"shield"},
    "Yasuo": {"shield", "crit"},
    # --- Tăng máu tối đa vô hạn / trữ máu (Liandry, Trượng Hư Vô không liên quan) ---
    "AurelionSol": {"max_hp"},
    "KogMaw": {"percent_hp"},
    "Malzahar": {"percent_hp"},
    "Smolder": {"percent_hp"},
    "Vayne": {"percent_hp", "true_damage"},
    "Varus": {"percent_hp"},
    # --- Chí mạng / đánh thường là nguồn sát thương chính ---
    "Ashe": {"crit"},
    "Caitlyn": {"crit"},
    "Jhin": {"crit"},
    "Jinx": {"dps", "crit"},
    "MasterYi": {"crit", "true_damage"},
    "MissFortune": {"crit"},
    "Shaco": {"crit"},
    "Sivir": {"crit"},
    "Talon": {"crit"},
    "Twitch": {"crit", "true_damage"},
    "Xayah": {"crit"},
    "Zeri": {"crit"},
    # --- Buff sát thương chuẩn thật ---
}
KIT = {k: v for k, v in KIT.items() if v}

# --- tướng có cơ chế hồi máu rất mạnh (ưu tiên Giảm Hồi Máu) ---
BIG_HEAL = {
    "Aatrox", "Briar", "DrMundo", "Garen", "Illaoi", "Kayn", "Maokai",
    "Mordekaiser", "Nasus", "Olaf", "Samira", "Swain", "Sylas", "TahmKench",
    "Trundle", "Vladimir", "Warwick", "Yuumi", "Zac", "Fiora", "Belveth",
    "Soraka", "Yone", "Sett",
}

# --- tướng có khống chế cứng đơn mục tiêu kéo dài (cần giải khống chế) ---
LOCKDOWN = {"Malzahar", "Warwick", "Skarner", "Shen", "Lissandra", "Zoe", "Nautilus"}


def _norm_key(key: str) -> str:
    """Khoá có dấu chấm/space -> dạng liền (Dr. Mundo -> DrMundo)."""
    return key.replace(".", "").replace(" ", "").replace("'", "")


def detect(champion: dict) -> set[str]:
    """Bộ đặc điểm của một tướng."""
    text = (champion.get("ability_text") or "").lower()
    traits: set[str] = set()
    for trait, phrases in PHRASES.items():
        if any(p in text for p in phrases):
            traits.add(trait)

    # thẻ do Riot gán trong CommunityDragon
    for tag in champion.get("tags_cd") or []:
        traits |= TAG_MAP.get(tag, set())

    ratings = champion.get("ratings") or {}
    roles = set(champion.get("roles") or [])
    control = ratings.get("control") or 0
    toughness = ratings.get("toughness") or 0
    mobility = ratings.get("mobility") or 0

    # Bảng ghi tay (KIT) phải gộp TRƯỚC các đặc điểm suy diễn, vì ví dụ
    # "enchanter" cần biết tướng có tạo lá chắn hay không.
    traits |= KIT.get(champion["key"], set()) | KIT.get(
        _norm_key(champion["name"]), set()
    )

    if control >= 3:
        traits.add("heavy_cc")
    if control >= 2:
        traits.add("some_cc")
    if mobility >= 3:
        traits.add("mobile")
    if toughness >= 3 or "tank" in roles:
        traits.add("tanky")
    if "assassin" in roles:
        traits.add("assassin")
    if "marksman" in roles:
        traits.add("dps")
    # Hỗ trợ hồi máu/lá chắn: phải là support thật VÀ thiên về bảo kê đồng đội.
    # Chỉ có "hồi máu" là chưa đủ (Swain, Maokai cũng hồi máu nhưng không phải
    # tướng bảo kê) — nên đòi thêm lá chắn hoặc chỉ số hỗ trợ cao.
    utility = ratings.get("utility") or 0
    if "support" in roles and (
        "shield" in traits or utility >= 2
    ) and (traits & {"shield", "heal", "sustain_zone"}):
        traits.add("enchanter")
    if champion.get("damage_type") in ("magic", "mixed"):
        traits.add("magic_threat")
    if champion.get("damage_type") in ("physical", "mixed"):
        traits.add("physical_threat")
    if champion.get("attack_type") == "ranged":
        traits.add("ranged")
    if champion.get("adaptive") == "magic" and champion.get("attack_type") == "melee":
        # tướng cận chiến sát thương phép: ít bị Giáp Gai/Khiên Băng đe doạ
        traits.add("magic_melee")
    # AP carry: phải đi đường bằng sát thương phép và thiên về kỹ năng
    if champion.get("adaptive") == "magic" and "dps" not in traits:
        traits.add("ap_threat")
    if champion.get("adaptive") == "physical":
        traits.add("ad_threat")

    if champion["key"] in BIG_HEAL or _norm_key(champion["name"]) in BIG_HEAL:
        traits.add("heal_big")
        traits.add("heal")
    if champion["key"] in LOCKDOWN:
        traits.add("lockdown")

    if "heal" in traits or "lifesteal" in traits:
        traits.add("regen")
    return traits


def trait_label(trait: str) -> str:
    return LABELS.get(trait, trait)


LABELS = {
    "heal": "tự hồi máu",
    "heal_big": "hồi máu rất mạnh",
    "lifesteal": "hút máu",
    "regen": "có hồi phục",
    "shield": "tạo lá chắn",
    "hard_cc": "khống chế cứng",
    "heavy_cc": "nhiều khống chế",
    "lockdown": "khống chế đơn mục tiêu lâu",
    "crit": "chí mạng",
    "attack_speed": "tăng tốc độ đánh",
    "true_damage": "sát thương chuẩn",
    "percent_hp": "sát thương theo % máu",
    "burst": "sát thương bùng nổ",
    "stealth": "tàng hình",
    "mobile": "cơ động cao",
    "tanky": "chống chịu tốt",
    "max_hp": "tăng máu vô hạn",
    "assassin": "sát thủ",
    "dps": "xạ thủ đánh thường",
    "enchanter": "hỗ trợ hồi máu/lá chắn",
    "magic_threat": "sát thương phép",
    "physical_threat": "sát thương vật lý",
    "ap_threat": "chủ lực phép",
    "ad_threat": "chủ lực vật lý",
    "magic_melee": "cận chiến sát thương phép",
    "ranged": "đánh xa",
    "some_cc": "có khống chế",
    "zone_damage": "sát thương theo thời gian",
    "sustain_zone": "hồi máu đồng đội",
    "protect": "bảo kê đồng đội",
    "initiator": "mở giao tranh",
    "dive": "lao vào đội hình",
    "shapeshift": "biến đổi hình dạng",
    "duelist": "mạnh khi đấu tay đôi",
    "aoe": "sát thương diện rộng",
    "summon": "triệu hồi",
}
