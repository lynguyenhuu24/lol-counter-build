"""Kiểm tra chất lượng gán đặc điểm: in câu văn làm căn cứ cho từng tướng.

Chạy:  python -m lcbuild.traits_audit [trait ...]
"""
from __future__ import annotations

import re
import sys

from .data import dataset
from .traits import PHRASES, detect


def contexts(text: str, words: tuple[str, ...], width: int = 70) -> list[str]:
    out = []
    for w in words:
        for m in re.finditer(re.escape(w), text, re.I):
            a = max(0, m.start() - width)
            out.append("…" + text[a : m.end() + width].strip() + "…")
    return out


def main() -> int:
    wanted = sys.argv[1:] or sorted(PHRASES)
    ds = dataset()
    for trait in wanted:
        words = PHRASES.get(trait, ())
        print(f"\n===== {trait} =====")
        for key, champ in sorted(ds.champions.items(), key=lambda kv: kv[1]["name"]):
            if trait not in detect(champ):
                continue
            seen = contexts(champ["ability_text"].lower(), words)
            uniq = []
            for c in seen:
                if c not in uniq:
                    uniq.append(c)
            print(f"-- {champ['name']}")
            for c in uniq[:2]:
                print(f"     {c[:230]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
