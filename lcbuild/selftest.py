"""Kiểm tra động cơ gợi ý trên các đội hình địch mẫu.

Chạy:  python -m lcbuild.selftest
Mục đích: bắt lỗi im lặng (luật bắn sai, thiếu luật hiển nhiên, món đồ vô lý
theo vai trò). Không thay thế việc chạy thật.
"""
from __future__ import annotations

from .advisor import RULES, ROLE_LABEL, recommend, role_of
from .augments import TIER_ORDER, load_augments, rank_augments
from .bench import BENCH_COOLDOWN, parse_bench, queue_name
from .build import CHEAP_CUTOFF, suggest_full_build
from .data import dataset
from .swapsched import Scheduler

# (tên kịch bản, đội hình địch, TƯỚNG CỦA BẠN, món BẮT BUỘC phải có)
# Không còn vai trò: công cụ tự suy nhóm tướng từ chính tướng bạn chơi.
CASES = [
    ("full AD + chí mạng", ["Darius", "LeeSin", "Zed", "Jinx", "Leona"], "Zed",
     ["Giáp Gai", "Khiên Băng Randuin", "Giày Thép Gai", "Đao Thủy Ngân"]),
    ("nhiều hồi máu", ["Vladimir", "Warwick", "Soraka", "Aatrox", "Zac"], "Yasuo",
     ["Giáp Gai", "Cưa Xích Hóa Kỹ"]),
    ("nhiều hồi máu (xạ thủ)", ["Vladimir", "Warwick", "Soraka", "Aatrox", "Zac"], "Jinx",
     ["Lời Nhắc Tử Vong"]),
    ("nhiều hồi máu (pháp sư)", ["Vladimir", "Warwick", "Soraka", "Aatrox", "Zac"], "Ahri",
     ["Quỷ Thư Morello"]),
    ("full AP", ["Syndra", "Vladimir", "Elise", "Brand", "Zyra"], "Amumu",
     ["Vòng Sắt Cổ Tự"]),
    ("nhiều lá chắn", ["LeeSin", "Shen", "Sona", "Sett", "Yasuo"], "Ahri",
     ["Kiếm Ác Xà"]),
    ("nhiều khống chế", ["Malzahar", "Leona", "Amumu", "Thresh", "Skarner"], "Jinx",
     ["Đao Thủy Ngân"]),
    ("nhiều tank", ["Malphite", "Zac", "Sion", "Ornn", "Shen"], "Jinx",
     ["Gươm Suy Vong"]),
    ("tank + xuyên giáp", ["Malphite", "Zac", "Sion", "Ornn", "Shen"], "Zed",
     ["Rìu Đen"]),
    ("tank + pháp sư", ["Malphite", "Zac", "Sion", "Ornn", "Shen"], "Ahri",
     ["Trượng Hư Vô"]),
]

class _FakeFrame:
    """Giả lập widget Tk để kiểm tra logic mà không mở cửa sổ."""

    def winfo_children(self) -> list:
        return []


def item_groups() -> dict[str, set[str]]:
    """Món đồ -> nhóm tướng được dùng, SUY TỪ chính bảng luật.

    Không viết tay bản đồ này nữa: trước đây bản viết tay bị lệch với luật thật
    sau khi đổi hệ vai trò, khiến test báo lỗi sai.
    """
    ds = dataset()
    out: dict[str, set[str]] = {}
    free: set[str] = set()
    for rule in RULES:
        for item_id in rule.item_ids:
            item = ds.item(item_id)
            if item is None:
                continue
            if not rule.roles:
                # luật không giới hạn -> món này dùng được cho mọi nhóm
                free.add(item["name"])
            else:
                out.setdefault(item["name"], set()).update(rule.roles)
    for name in free:
        out.pop(name, None)
    return out


def main() -> int:
    ds = dataset()
    failures: list[str] = []
    comps = [
        ["Syndra", "Vladimir", "Elise", "Brand", "Zyra"],
        ["Malphite", "Zac", "Sion", "Ornn", "Shen"],
        ["Darius", "LeeSin", "Zed", "Jinx", "Leona"],
    ]
    for title, enemies, champion, must_have in CASES:
        unknown = [e for e in enemies if ds.champion(e) is None]
        if unknown:
            failures.append(f"{title}: không nhận diện được tướng {unknown}")
            continue
        suggestions, profile, notes = recommend(
            enemies, role=role_of(ds.champion(champion))
        )
        names = [s.item["name"] for s in suggestions]
        print(f"\n### {title} | tướng: {champion} | {len(profile.champs)} tướng địch")
        for note in notes:
            print("   •", note)
        for sug in suggestions:
            print(f"   [{sug.kind:>17}] {sug.item['name']} — {sug.reasons[0]}")
        for want in must_have:
            if want not in names:
                failures.append(f"{title} ({champion}): thiếu '{want}'")

    # đồ gợi ý phải đúng nhóm tướng của nó (nhóm suy từ chính tướng bạn chơi)
    families = item_groups()
    for role, champ_key in (("carry", "Jinx"), ("caster", "Ahri"),
                            ("tank", "Amumu"), ("utility", "Sona"),
                            ("fighter", "Yasuo")):
        for enemies in comps:
            suggestions, _, _ = recommend(enemies, role=role)
            for sug in suggestions:
                family = families.get(sug.item["name"])
                if family and role not in family:
                    failures.append(
                        f"{champ_key} ({role}) + {enemies[0]}…: '{sug.item['name']}' "
                        f"chỉ hợp {sorted(family)}"
                    )

    # đổi tướng đang xem thì build PHẢI đổi theo (lỗi cũ: bấm tướng khác trên bench
    # mà build vẫn đứng yên ở tướng cũ)
    foes = ["Malphite", "Zac", "Sion"]
    seen: dict[str, list[str]] = {}
    for key in ("Jinx", "Ahri", "Amumu", "Sona", "Yasuo"):
        seen[key] = [s.item["name"] for s in suggest_full_build(key, foes).slots]
        if len(seen[key]) != 6:
            failures.append(f"đổi tướng: build {key} chỉ có {len(seen[key])} món")
    if seen["Jinx"] == seen["Ahri"]:
        failures.append("đổi tướng: build Jinx và Ahri giống nhau — không đổi theo tướng")
    if len({tuple(v) for v in seen.values()}) < 4:
        failures.append(
            f"đổi tướng: build 5 tướng khác nhóm nhưng chỉ ra "
            f"{len({tuple(v) for v in seen.values()})} kiểu build"
        )

    # nhóm tướng phải suy được cho MỌI tướng, không tướng nào rơi vào nhóm lạ
    unknown_groups = [
        c["key"] for c in ds.champions.values() if role_of(c) not in ROLE_LABEL
    ]
    if unknown_groups:
        failures.append(f"nhóm tướng không xác định cho: {unknown_groups[:8]}")

    # --- gợi ý lõi ---------------------------------------------------------
    for champ_key in ("Jinx", "Ahri", "Amumu", "Sona", "Yasuo"):
        tiers = rank_augments(champ_key, ["Malphite", "Zac", "Sion", "Ornn", "Shen"])
        if not tiers.get("S+") and not tiers.get("S"):
            failures.append(f"lõi {champ_key}: không có gợi ý bậc S/S+ nào")
        for tier in TIER_ORDER:
            for pick in tiers.get(tier) or []:
                if pick.augment.tier != tier:
                    failures.append(
                        f"lõi {champ_key}: {pick.augment.name} sai bậc "
                        f"({pick.augment.tier} vs {tier})"
                    )
                if not pick.reasons:
                    failures.append(f"lõi {champ_key}: {pick.augment.name} không có lý do")
                if not pick.augment.description:
                    failures.append(f"lõi {champ_key}: {pick.augment.name} không có mô tả")

    # dữ liệu lõi: phải có mô tả đầy đủ, không còn placeholder của nguồn cũ
    pool = load_augments()
    if len(pool) < 150:
        failures.append(f"dữ liệu lõi quá ít: {len(pool)}")
    no_desc = [a.name for a in pool.values() if not a.description]
    if no_desc:
        failures.append(f"lõi thiếu mô tả: {no_desc[:5]}")
    placeholder = [
        a.name for a in pool.values() if "the required number of" in a.description
    ]
    if placeholder:
        failures.append(f"lõi còn placeholder chưa giải: {placeholder[:5]}")
    bad_tier = [a.name for a in pool.values() if a.tier not in TIER_ORDER]
    if bad_tier:
        failures.append(f"lõi có bậc lạ: {bad_tier[:5]}")

    # --- đọc hàng đợi tướng: client mới trả `benchChampions`, bản cũ trả id ---
    timer = {"phase": "BAN_PICK", "adjustedTimeLeftInPhase": 1000, "isInfinite": False}
    common = {"benchEnabled": True, "queueId": 450, "localPlayerCellId": 0,
              "myTeam": [{"cellId": 0, "championId": 12}], "timer": timer}

    modern = parse_bench({**common, "benchChampions": [{"championId": 54},
                                                       {"championId": 64}]})
    if [c["key"] for c in modern.champions] != ["Malphite", "LeeSin"]:
        failures.append(
            "bench: không đọc được định dạng mới `benchChampions` "
            f"(nhận {[c['key'] for c in modern.champions]})"
        )
    legacy = parse_bench({**common, "benchChampionIds": [54, 64]})
    if [c["key"] for c in legacy.champions] != ["Malphite", "LeeSin"]:
        failures.append("bench: không đọc được định dạng cũ `benchChampionIds`")
    unknown = parse_bench({**common, "benchChampions": [{"championId": 54},
                                                         {"championId": 999999}]})
    if unknown.unknown != [999999]:
        failures.append(f"bench: không đánh dấu được id lạ ({unknown.unknown})")
    custom = parse_bench({**common, "queueId": 3220, "isCustomGame": True,
                          "rerollsRemaining": 0, "benchChampions": []})
    if not custom.custom_game or "phòng tự tạo" not in custom.diagnose():
        failures.append("bench: ca phòng custom chẩn đoán không đúng")
    if queue_name(3220) != "Howling Abyss All Random":
        failures.append(f"bench: tên chế độ queue 3220 sai ({queue_name(3220)!r})")
    if queue_name(2400) != "ARAM: Mayhem":
        failures.append(f"bench: tên chế độ queue 2400 sai ({queue_name(2400)!r})")
    # ARAM không còn reroll -> không được nhắc tới "lượt đổi"
    empty = parse_bench({**common, "rerollsRemaining": 0, "benchChampions": []})
    note = empty.diagnose()
    if "Thẻ Tướng" not in note:
        failures.append(f"bench: bench rỗng không nhắc Thẻ Tướng ({note!r})")
    if "lượt đổi" in note:
        failures.append(f"bench: còn nói tới lượt đổi (ARAM đã bỏ reroll) ({note!r})")

    # --- đổi tướng thành công thì phải quay về xem tướng thật --------------
    # Lỗi cũ: view_champ bị "ghim" vĩnh viễn ở tướng đã bấm xem, nên sau khi đổi
    # tướng xong build/lõi vẫn đứng ở tướng cũ.
    # Kiểm tra trên CHÍNH Overlay (không mở cửa sổ, không gọi mạng): gọi thẳng
    # _bench_loaded với dữ liệu phiên chọn tướng giả.
    from .ui import Overlay as _Overlay

    ov = _Overlay.__new__(_Overlay)
    ov.my_champ = ds.champion("Jinx")
    ov.view_champ = ds.champion("Malphite")
    ov.view_pinned = True
    ov.bench = None
    ov.bench_ids = set()
    ov.bench_seen_at = None
    ov.sched = Scheduler()
    ov.comp = None
    ov.body = _FakeFrame()
    ov._render_bench = lambda: None
    ov.render = lambda enemies: ov.__dict__.setdefault("rendered", []).append(list(enemies))

    swapped = parse_bench({**common, "benchEnabled": True, "benchChampions": [],
                           "myTeam": [{"cellId": 0, "championId": 54}]})
    ov._bench_loaded(swapped, 0.0, None)
    if ov.view_pinned:
        failures.append("đổi tướng: sau khi đổi xong vẫn còn ghim tướng đã bấm xem")
    if ov.view_champ is None or ov.view_champ["id"] != 54:
        failures.append(
            "đổi tướng: build vẫn trỏ tướng cũ "
            f"({ov.view_champ and ov.view_champ['name']})"
        )
    if not ov.rendered:
        failures.append("đổi tướng: không vẽ lại build sau khi đổi tướng")

    # --- hẹn giờ đổi tướng -------------------------------------------------
    target = ds.champion("Malphite")
    bench_ids = {target["id"]}

    # đổi ngay: hết khoá là gửi liền, không chờ hết giờ
    now_sched = Scheduler()
    now_sched.arm(target, created_at=500.0, mode="immediate")
    if now_sched.step(500.0 + BENCH_COOLDOWN - 0.5, 0.5, bench_ids, 500.0) is not None:
        failures.append("đổi ngay: gửi trong thời gian khoá")
    if now_sched.step(500.0 + BENCH_COOLDOWN + 0.2, 55.0, bench_ids, 500.0) is None:
        failures.append("đổi ngay: không gửi dù đã hết khoá (còn 55s)")

    # chờ hết giờ vẫn phải chờ (giữ để không hồi quy hành vi)
    late = Scheduler()
    late.arm(target, created_at=600.0, mode="deadline")
    if late.step(604.0, 55.0, bench_ids, 600.0) is not None:
        failures.append("chờ hết giờ: gửi quá sớm")
    if late.step(658.0, 0.5, bench_ids, 600.0) is None:
        failures.append("chờ hết giờ: không gửi khi sát hết thời gian")

    # tướng rời bench thì tự huỷ; đã gửi thì không gửi lại
    gone = Scheduler()
    gone.arm(target, created_at=300.0)
    if gone.step(310.0, 0.5, set(), 300.0) is not None or gone.pending is not None:
        failures.append("đổi tướng: không tự huỷ khi tướng rời bench")
    once = Scheduler()
    once.arm(target, created_at=700.0)
    if once.step(704.0, 30.0, bench_ids, 700.0) is None:
        failures.append("đổi ngay: không gửi sau khi hết khoá")
    if once.step(705.0, 29.0, bench_ids, 700.0) is not None:
        failures.append("đổi tướng: gửi lặp lại sau khi đã gửi")

    print("\n" + "=" * 60)
    if failures:
        for f in failures:
            print("FAIL:", f)
        return 1
    print(f"OK: {len(CASES)} kịch bản đều đạt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
