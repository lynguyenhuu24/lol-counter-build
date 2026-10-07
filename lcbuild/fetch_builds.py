"""Tải build chuẩn của từng tướng (giày, món chủ lực) về data/builds.json.

Nguồn: op.gg champion API công khai. Đây là build xếp hạng (Summoner's Rift) — dùng
làm "khung xương" món chuẩn của tướng; các món khắc chế đội địch vẫn được ưu tiên
hơn khi lên đồ đầy đủ (xem lcbuild/build.py).

Chạy:  python -m lcbuild.fetch_builds
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import sys
import time
import urllib.request
from pathlib import Path

from .data import dataset
from .paths import app_root

API = "https://lol-api-champion.op.gg/api/global"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126 Safari/537.36"}
DATA = app_root() / "data"

# op.gg dùng tên vị trí riêng
POSITIONS = ("TOP", "JUNGLE", "MID", "ADC", "SUPPORT")


def _get(url: str, attempts: int = 3, timeout: int = 25):
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as exc:
            last = exc
            if attempt < attempts - 1:
                time.sleep(1.0 * (attempt + 1))
    raise RuntimeError(f"không tải được {url}: {last}")


def _slots(entries) -> list[tuple[list[int], int]]:
    """[{ids, play, win}] -> [(ids, play)] đã sắp theo số trận."""
    out = []
    for e in entries or []:
        ids = e.get("ids") or []
        if ids:
            out.append(([int(i) for i in ids], int(e.get("play") or 0)))
    out.sort(key=lambda x: -x[1])
    return out


def fetch_position_list() -> dict[str, str]:
    """Một lần gọi trả về mọi tướng kèm vị trí chơi nhiều nhất của nó."""
    payload = _get(f"{API}/champions/ranked?tier=gold_plus&region=global")
    out: dict[str, str] = {}
    for entry in payload.get("data") or []:
        positions = entry.get("positions") or []
        if not positions:
            continue
        best = max(positions, key=lambda p: (p.get("stats") or {}).get("play") or 0)
        name = best.get("name")
        if name in POSITIONS:
            out[str(entry.get("id"))] = name
    return out


def fetch_champion(champ_id: int, key: str, position: str) -> dict | None:
    """Lấy build ở vị trí được chơi nhiều nhất của tướng."""
    payload = _get(f"{API}/champions/ranked/{champ_id}/{position}").get("data") or {}
    if not payload.get("core_items") and not payload.get("boots"):
        return None
    return {
        "key": key,
        "position": position,
        "starter": _slots(payload.get("starter_items")),
        "boots": _slots(payload.get("boots")),
        "core": _slots(payload.get("core_items")),
        "last": _slots(payload.get("last_items")),
    }


def main() -> int:
    ds = dataset()
    print("· Lấy bảng xếp hạng tướng (op.gg) ...", flush=True)
    positions = fetch_position_list()
    if not positions:
        raise RuntimeError("không đọc được danh sách tướng từ op.gg")
    print(f"  {len(positions)} tướng có dữ liệu vị trí", flush=True)

    champs = [
        (c["id"], c["key"], positions[str(c["id"])])
        for c in ds.champions.values()
        if str(c["id"]) in positions
    ]
    missing = [c["key"] for c in ds.champions.values() if str(c["id"]) not in positions]
    if missing:
        print(f"  ! không có build cho: {missing[:10]}", flush=True)

    print(f"· Lấy build cho {len(champs)} tướng ...", flush=True)
    out: dict[str, dict] = {}
    done = 0
    with cf.ThreadPoolExecutor(5) as ex:
        futures = {
            ex.submit(fetch_champion, cid, key, pos): key for cid, key, pos in champs
        }
        for fut in cf.as_completed(futures):
            key = futures[fut]
            done += 1
            try:
                res = fut.result()
            except Exception as exc:
                print(f"  ! {key}: {exc}", flush=True)
                continue
            if res:
                out[key] = res
            if done % 25 == 0 or done == len(champs):
                print(f"  {done}/{len(champs)}", flush=True)

    # chỉ giữ item id có thật trong data/items.json
    known = set(ds.items)
    kept, dropped = 0, set()
    for build in out.values():
        for field in ("starter", "boots", "core", "last"):
            slots = []
            for ids, play in build[field]:
                good = [i for i in ids if i in known]
                for i in ids:
                    if i not in known:
                        dropped.add(i)
                if good:
                    slots.append((good, play))
                    kept += 1
            build[field] = slots

    (DATA / "builds.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"  ok: {len(out)} tướng, {kept} ô build → {DATA / 'builds.json'}")
    if dropped:
        print(f"  ! bỏ {len(dropped)} item id lạ: {sorted(dropped)[:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
