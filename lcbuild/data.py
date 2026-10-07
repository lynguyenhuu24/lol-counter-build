"""Nạp dữ liệu đã cache và tạo chỉ mục tra cứu."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .paths import data_dir


class Dataset:
    def __init__(self) -> None:
        data = data_dir()
        self.champions: dict[str, dict] = json.loads(
            (data / "champions.json").read_text(encoding="utf-8")
        )
        self.items: dict[int, dict] = {
            int(k): v
            for k, v in json.loads(
                (data / "items.json").read_text(encoding="utf-8")
            ).items()
        }
        self.meta: dict = json.loads((data / "meta.json").read_text(encoding="utf-8"))

        self.by_key = self.champions
        self.by_name = {c["name"]: c for c in self.champions.values()}
        self.by_name_lower = {c["name"].lower(): c for c in self.champions.values()}
        self.by_id = {c["id"]: c for c in self.champions.values()}
        # tra theo tên hiển thị của game (Live Client API trả "Nunu & Willump")
        self.by_slug: dict[str, dict] = {}
        for champ in self.champions.values():
            for raw in (champ["key"], champ.get("cd_alias"), champ.get("cd_name"),
                        champ["name"], champ["name_en"]):
                if raw:
                    self.by_slug.setdefault(slug(raw), champ)

    def champion(self, token: str | int) -> dict | None:
        """Tìm tướng theo key, tên (vi/en), tên hiển thị trong game, hoặc id."""
        if isinstance(token, int):
            return self.by_id.get(token)
        token = str(token).strip()
        return (
            self.by_key.get(token)
            or self.by_name.get(token)
            or self.by_name_lower.get(token.lower())
            or self.by_slug.get(slug(token))
            or self.by_id.get(_as_int(token))
        )

    def item(self, item_id: int) -> dict | None:
        return self.items.get(int(item_id))


def _as_int(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None


def slug(name: str) -> str:
    """Chuẩn hoá tên tướng: bỏ dấu cách, chấm, nháy, chữ &."""
    return (
        name.replace(".", "").replace("'", "").replace(" ", "")
        .replace("&", "").replace("-", "").lower()
    )


@lru_cache(maxsize=1)
def dataset() -> Dataset:
    return Dataset()
