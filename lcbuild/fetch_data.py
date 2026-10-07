"""Tải dữ liệu tướng + trang bị về data/ để dùng offline.

Nguồn:
  - Data Dragon (vi_VN): tên tiếng Việt, tag, giá, mô tả, kỹ năng, enemytips.
  - CommunityDragon: tacticalInfo (damageType/attackType), roles, chỉ số.
  - Meraki Analytics: attributeRatings (control/toughness/mobility/utility).

Chạy:  python -m lcbuild.fetch_data
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

from .paths import app_root

ROOT = app_root()
DATA = ROOT / "data"
UA = {"User-Agent": "lol-counter-build/1.0"}
CD = "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1"
TAGS = re.compile(r"<[^>]+>")


def get_json(url: str, timeout: int = 40, attempts: int = 4):
    """GET + parse JSON, thử lại khi CD/Cloudflare trả lỗi tạm thời."""
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as exc:  # HTTPError, URLError, timeout, JSON lỗi
            last = exc
            if attempt < attempts - 1:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"không tải được {url}: {last}")


def plain(text: str) -> str:
    """Bỏ thẻ HTML và placeholder {{ ... }} của wiki."""
    if not text:
        return ""
    text = TAGS.sub(" ", text)
    text = re.sub(r"\{\{[^}]*?\|([^}|]*)\}\}", r"\1", text)
    text = re.sub(r"\{\{|\}\}", "", text)
    return re.sub(r"\s+", " ", text).strip()


def main() -> int:
    DATA.mkdir(exist_ok=True)
    print("· Data Dragon version ...", flush=True)
    version = get_json("https://ddragon.leagueoflegends.com/api/versions.json")[0]
    base = f"https://ddragon.leagueoflegends.com/cdn/{version}"
    print(f"  {version}")

    print("· DDragon vi_VN champion.json / item.json ...", flush=True)
    dd_champs = get_json(f"{base}/data/vi_VN/champion.json")["data"]
    dd_items = get_json(f"{base}/data/vi_VN/item.json")["data"]

    print("· CommunityDragon champion-summary + items ...", flush=True)
    cd_summary = [c for c in get_json(f"{CD}/champion-summary.json") if c["id"] > 0]

    print("· CommunityDragon queues ...", flush=True)
    cd_queues = get_json(f"{CD}/queues.json")
    queues = {}
    for entry in cd_queues if isinstance(cd_queues, list) else cd_queues.values():
        qid = entry.get("id") if isinstance(entry, dict) else None
        name = entry.get("name") if isinstance(entry, dict) else None
        if qid is not None and name:
            queues[str(qid)] = name

    print("· Meraki champions + items ...", flush=True)
    meraki_champs = get_json(
        "https://cdn.merakianalytics.com/riot/lol/resources/latest/en-US/champions.json"
    )
    meraki_items = get_json(
        "https://cdn.merakianalytics.com/riot/lol/resources/latest/en-US/items.json"
    )

    # alias -> summary (id, roles); CD dùng "Fiddlesticks", DDragon dùng "FiddleSticks"
    by_key = {c["alias"]: c for c in cd_summary}
    by_key_lower = {c["alias"].lower(): c for c in cd_summary}
    for key in dd_champs:
        if key not in by_key and key.lower() in by_key_lower:
            by_key[key] = by_key_lower[key.lower()]
    keys = [k for k in dd_champs if k in by_key]
    missing = sorted(set(dd_champs) - set(by_key))
    if missing:
        print(f"  ! tướng không có trong CD: {missing}")

    def champ_detail(key: str):
        cid = by_key[key]["id"]
        tactical = get_json(f"{CD}/champions/{cid}.json")
        vi = get_json(f"{base}/data/vi_VN/champion/{key}.json")["data"][key]
        return key, tactical, vi

    print(f"· Chi tiết {len(keys)} tướng (CD + DDragon vi) ...", flush=True)
    details: dict[str, dict] = {}
    partial = DATA / "champions.partial.json"
    if partial.exists():
        try:
            details = json.loads(partial.read_text(encoding="utf-8"))
            print(f"  tiếp tục từ {len(details)} tướng đã tải", flush=True)
        except ValueError:
            details = {}
    todo = [k for k in keys if k not in details]
    BATCH = 25
    for start in range(0, len(todo), BATCH):
        chunk = todo[start : start + BATCH]
        with cf.ThreadPoolExecutor(12) as ex:
            for key, tactical, vi in ex.map(champ_detail, chunk):
                details[key] = {"tactical": tactical, "vi": vi}
        partial.write_text(
            json.dumps(details, ensure_ascii=False), encoding="utf-8"
        )
        print(f"  {min(start + BATCH, len(todo))}/{len(todo)}", flush=True)

    champions = {}
    for key in keys:
        tactical = details[key]["tactical"]
        vi = details[key]["vi"]
        summary = by_key[key]
        meraki = meraki_champs.get(key, {})
        ability_text = " ".join(
            plain(vi["spells"][i]["description"]) for i in range(len(vi["spells"]))
        )
        ability_text += " " + plain(vi["passive"]["description"])
        champions[key] = {
            "key": key,
            "name": vi["name"],
            "name_en": vi["id"],
            "cd_alias": summary["alias"],
            "cd_name": summary["name"],
            "id": summary["id"],
            "roles": summary["roles"],
            "tags": vi["tags"],
            "damage_type": {
                "kPhysical": "physical",
                "kMagic": "magic",
                "kMixed": "mixed",
            }.get(tactical["tacticalInfo"]["damageType"], "mixed"),
            "attack_type": "ranged"
            if tactical["tacticalInfo"]["attackType"] == "ranged"
            else "melee",
            "adaptive": {
                "PHYSICAL_DAMAGE": "physical",
                "MAGIC_DAMAGE": "magic",
            }.get(meraki.get("adaptiveType"), None),
            "ratings": {
                k: meraki.get("attributeRatings", {}).get(k)
                for k in ("damage", "toughness", "control", "mobility", "utility",
                          "abilityReliance", "difficulty")
            },
            "info": vi["info"],
            "tags_cd": [
                t
                for t in (
                    tactical["championTagInfo"]["championTagPrimary"],
                    tactical["championTagInfo"]["championTagSecondary"],
                )
                if t
            ],
            "ability_text": ability_text,
            "enemytips": [plain(t) for t in vi.get("enemytips", [])],
            "allytips": [plain(t) for t in vi.get("allytips", [])],
            # icon: DDragon trả nhanh & ổn định (CD thường timeout)
            "icon": f"{base}/img/champion/{key}.png",
        }

    # ---- items: gộp các biến thể của cùng một trang bị về một mục ----
    # DDragon lặp mỗi trang bị thành nhiều id: 3075 (gốc), 223075 (URF),
    # 323075 (Arena), 773075 (ARAM), 6676/667666... Cùng một món thật.
    # Gộp theo TÊN, sau đó chọn bản gốc; các id khác chỉ dùng để dịch buildsFrom.
    groups: dict[str, list[tuple[str, dict]]] = {}
    for did, item in dd_items.items():
        if not item.get("maps", {}).get("11"):
            continue
        if not item.get("gold", {}).get("purchasable"):
            continue
        groups.setdefault(item["name"], []).append((did, item))

    by_id_mk = {v["id"]: v for v in meraki_items.values()}

    def pick_original(members: list[tuple[str, dict]]) -> tuple[str, dict]:
        """Bản gốc = biến thể có id nằm trong danh sách id chính thức của Meraki.

        Meraki chỉ liệt kê id thật (3075, 6676…), không có biến thể chế độ chơi
        (323075 Arena, 7666…). Nếu không có id nào khớp thì lấy id ngắn nhất.
        """
        official = [m for m in members if int(m[0]) in by_id_mk]
        pool = official or members
        return min(pool, key=lambda m: (len(m[0]), m[0]))

    # gán id đại diện cho từng biến thể (để dịch buildsFrom/buildsInto)
    variant_to_base: dict[str, int] = {}
    originals: dict[str, tuple[str, dict]] = {}
    for key, members in groups.items():
        chosen = pick_original(members)
        originals[key] = chosen
        for did, _ in members:
            variant_to_base[did] = int(chosen[0])

    def norm_id(raw) -> int | None:
        return variant_to_base.get(str(raw))

    items: dict[int, dict] = {}
    for key, members in groups.items():
        did, item = originals[key]
        bid = int(did)
        mk = by_id_mk.get(bid)
        entry = {
            "id": bid,
            "name": item["name"],
            "gold": item["gold"]["total"],
            "tags": item.get("tags", []),
            "from": [n for n in (norm_id(x) for x in item.get("from", []) or []) if n],
            "into": [n for n in (norm_id(x) for x in item.get("into", []) or []) if n],
            "description": plain(item.get("description", ""))[:1200],
            "stats": {k: v for k, v in (mk or {}).get("stats", {}).items()
                      if v.get("flat") or v.get("percent")},
            "ranks": (mk or {}).get("rank", []),
            "icon": f"{base}/img/item/{did}.png",
        }
        items[bid] = entry

    (DATA / "champions.json").write_text(
        json.dumps(champions, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (DATA / "items.json").write_text(
        json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (DATA / "queues.json").write_text(
        json.dumps(queues, ensure_ascii=False, indent=1, sort_keys=True),
        encoding="utf-8",
    )

    (DATA / "meta.json").write_text(
        json.dumps({"ddragon": version, "champions": len(champions),
                    "items": len(items)}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    partial.unlink(missing_ok=True)
    print(f"  ok: {len(champions)} tướng, {len(items)} trang bị, {len(queues)} chế độ "
          f"→ {DATA}")
    no_adaptive = [c["key"] for c in champions.values() if not c["adaptive"]]
    if no_adaptive:
        print(f"  ! thiếu adaptiveType: {no_adaptive}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
