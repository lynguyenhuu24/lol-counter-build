"""Đường dẫn tài nguyên, chạy được cả khi đóng gói thành .exe.

- Chạy từ mã nguồn: mọi thứ nằm trong thư mục dự án.
- Chạy từ .exe (PyInstaller): dữ liệu tướng/trang bị nằm trong gói (chỉ đọc,
  ở `sys._MEIPASS`), còn cache icon ghi cạnh file .exe để không phải tải lại.
  Nếu cạnh .exe có `data/` (do người dùng tải lại dữ liệu) thì ưu tiên bản đó.
"""
from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_root() -> Path:
    """Nơi chứa dữ liệu đi kèm (chỉ đọc khi đã đóng gói)."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base)
    return Path(__file__).resolve().parent.parent


def app_root() -> Path:
    """Nơi ghi được: cạnh file .exe, hoặc thư mục dự án khi chạy mã nguồn."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def data_dir(create: bool = False) -> Path:
    """Thư mục `data` đang dùng: ưu tiên bản ghi được nếu đã có dữ liệu."""
    local = app_root() / "data"
    if (local / "champions.json").exists():
        return local
    bundled = resource_root() / "data"
    if bundled.exists():
        return bundled
    if create:
        local.mkdir(parents=True, exist_ok=True)
    return local


def icon_dir() -> Path:
    """Cache icon: luôn nằm cạnh .exe để dùng lại giữa các lần chạy."""
    return app_root() / "data" / "icons"
