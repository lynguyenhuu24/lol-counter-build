"""Tải dữ liệu Lõi (augment) ARAM: Mayhem từ playaram.gg.

Vì sao dùng nguồn này thay vì nguồn cũ (arammayhem.com):
  * tên và **mô tả tiếng Việt đã giải đầy đủ** — nguồn cũ trả cả placeholder
    kiểu "the required number of" ở 16 lõi;
  * có **bậc mạnh yếu (S+ → D)** do họ xếp hạng, thay vì chỉ có tỉ lệ thắng;
  * có **nhóm** (ad / ap / tank / crit / support / cd / amp / mechanic…).

Cấu trúc nguồn:
  * `/en/loi-aram-hon-loan` — danh sách lõi kèm bậc, độ hiếm, nhóm, id tooltip;
  * `/tooltip/augment/{id}` — tên + mô tả tiếng Việt + độ hiếm (HTML nhỏ).

Chạy:  python -m lcbuild.fetch_augments
"""
from __future__ import annotations

import concurrent.futures as cf
import html
import json
import re
import sys
import time
import urllib.request

from .paths import app_root

BASE = "https://playaram.gg"
LIST_PAGE = f"{BASE}/en/loi-aram-hon-loan"
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "vi,en;q=0.9",
}
DATA = app_root() / "data"

# bậc mạnh yếu -> điểm nền (để xếp hạng khi không có luật riêng)
TIER_SCORE = {"S+": 100.0, "S": 88.0, "A": 76.0, "B": 64.0, "C": 52.0, "D": 40.0}

TAGS = re.compile(r"<[^>]+>")


def _get(url: str, attempts: int = 4, timeout: int = 30) -> str:
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as exc:
            last = exc
            if attempt < attempts - 1:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"không tải được {url}: {last}")


def _text(raw: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(TAGS.sub(" ", raw))).strip()


def aug_key(slug: str) -> str:
    """Khoá ổn định cho một lõi: bỏ mọi ký tự không phải chữ/số.

    Nguồn đổi cách viết slug theo thời gian ("draw-your-sword" -> "draw your sword",
    "Stackosaurus Rex" -> "stackosaurusrex"), nên luật phải bám khoá này chứ không
    bám tên hiển thị (tên là tiếng Việt và có thể đổi bản dịch).
    """
    return re.sub(r"[^a-z0-9]", "", slug.lower())


def parse_list(page: str) -> list[dict]:
    """Trang danh sách -> lõi kèm bậc, độ hiếm, nhóm."""
    out: list[dict] = []
    bands = re.findall(
        r'<h2 aria-label="Tier ([^"]+)"[^>]*>.*?</h2>\s*<ul class="cores__grid[^"]*">(.*?)</ul>',
        page,
        re.S,
    )
    for tier, block in bands:
        for name, rarity, cats, tooltip_id in re.findall(
            r'<li data-core-name="([^"]*)" data-core-rarity="([^"]*)" '
            r'data-core-cats="([^"]*)" data-tooltip-id="([^"]*)"',
            block,
        ):
            out.append(
                {
                    "slug": name,
                    "key": aug_key(name),
                    "tier": tier,
                    "rarity": rarity,
                    "categories": cats.split(),
                    "tooltip_id": int(tooltip_id),
                }
            )
    return out


def parse_tooltip(page: str) -> dict:
    """Trang tooltip -> tên, mô tả, độ hiếm."""
    title = re.search(r"<strong>([^<]*)</strong>", page)
    body = re.search(r'<p class="tp-card__body">(.*?)</p>', page, re.S)
    rarity = re.search(r"tp-card__rarity--([a-z]+)", page)
    icon = re.search(r'<img src="([^"]+)"', page)
    return {
        "name": _text(title.group(1)) if title else None,
        "description": _text(body.group(1)) if body else None,
        "rarity": rarity.group(1) if rarity else None,
        "icon": (BASE + icon.group(1)) if icon and icon.group(1).startswith("/") else None,
    }


def fetch_all(pause: float = 0.0, workers: int = 8) -> list[dict]:
    core = parse_list(_get(LIST_PAGE))
    if not core:
        raise RuntimeError("không đọc được danh sách lõi từ playaram.gg")
    print(f"· {len(core)} lõi trong danh sách, lấy mô tả tiếng Việt ...", flush=True)

    def detail(entry: dict) -> dict:
        try:
            info = parse_tooltip(_get(f"{BASE}/tooltip/augment/{entry['tooltip_id']}"))
        except Exception as exc:
            print(f"  ! {entry['slug']}: {exc}", flush=True)
            info = {}
        merged = dict(entry)
        merged.update({k: v for k, v in info.items() if v})
        merged["name"] = merged.get("name") or entry["slug"].title()
        merged["tier_score"] = TIER_SCORE.get(entry["tier"], 50.0)
        return merged

    out: list[dict] = []
    done = 0
    with cf.ThreadPoolExecutor(workers) as ex:
        for res in ex.map(detail, core):
            out.append(res)
            done += 1
            if done % 50 == 0:
                print(f"  {done}/{len(core)}", flush=True)
            if pause:
                time.sleep(pause)
    return out


def main() -> int:
    DATA.mkdir(exist_ok=True)
    augments = fetch_all()
    (DATA / "augments.json").write_text(
        json.dumps(augments, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    have = sum(1 for a in augments if a.get("description"))
    placeholder = sum(
        1 for a in augments
        if a.get("description") and "the required number of" in a["description"]
    )
    print(f"  ok: {len(augments)} lõi ({have} có mô tả, {placeholder} còn placeholder) "
          f"→ {DATA / 'augments.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
