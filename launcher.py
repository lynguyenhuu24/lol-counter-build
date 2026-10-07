"""Điểm vào cho bản .exe.

Vì bản đóng gói chạy không có console, mọi lỗi khởi động phải hiện bằng hộp thoại
thay vì biến mất im lặng.
"""
from __future__ import annotations

import argparse
import sys
import traceback


def _setup_console() -> None:
    """Bản .exe là GUI nên không có console: gắn vào console của cmd nếu có.

    Cũng ép stdout/stderr sang UTF-8 vì mặc định Windows dùng cp1258, in tiếng Việt
    sẽ lỗi UnicodeEncodeError.
    """
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.kernel32.AttachConsole(-1)  # ATTACH_PARENT_PROCESS
        except Exception:
            pass
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _report(error: BaseException) -> None:
    text = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    try:
        import tkinter.messagebox as box
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        box.showerror("LoL Counter Build — lỗi", text[-1500:])
        root.destroy()
    except Exception:
        pass
    try:
        from pathlib import Path

        log = Path(sys.executable).resolve().parent / "lcbuild-error.log"
        log.write_text(text, encoding="utf-8")
    except Exception:
        pass
    sys.stderr.write(text)


def main() -> int:
    _setup_console()
    ap = argparse.ArgumentParser(description="Gợi ý lên đồ khắc chế đội hình địch")
    ap.add_argument("--enemies", help="danh sách tướng địch, cách nhau dấu phẩy")
    ap.add_argument("--text", action="store_true", help="chỉ in ra terminal")
    ap.add_argument("--selftest", action="store_true", help="kiểm tra bảng luật")
    ap.add_argument("--bench", action="store_true",
                    help="in trạng thái hàng đợi tướng client đang báo (để chẩn đoán)")
    ap.add_argument("--raw", action="store_true",
                    help="đi kèm --bench: in toàn bộ phiên chọn tướng")
    ap.add_argument("--champion", help="chỉ để thử tay: coi như bạn đang chơi tướng này")
    ap.add_argument("--update-data", action="store_true",
                    help="tải lại dữ liệu tướng/trang bị về cạnh file exe")
    ap.add_argument("--update-builds", action="store_true",
                    help="tải lại build chuẩn của tướng (op.gg)")
    ap.add_argument("--update-augments", action="store_true",
                    help="tải lại danh sách lõi ARAM: Mayhem")
    args = ap.parse_args()

    if args.selftest:
        from lcbuild.selftest import main as run
        return run()

    if args.bench:
        import sys as _sys

        from lcbuild.bench import _main as run

        return run([a for a in _sys.argv[1:] if a != "--bench"])

    if args.update_data:
        from lcbuild.fetch_data import main as run
        return run()

    if args.update_builds:
        from lcbuild.fetch_builds import main as run
        return run()

    if args.update_augments:
        from lcbuild.fetch_augments import main as run
        return run()

    from lcbuild.ui import main as run

    sys.argv = ["lcbuild", *(("--enemies", args.enemies) if args.enemies else ()),
                *(("--champion", args.champion) if args.champion else ()),
                *(("--text",) if args.text else ())]
    return run()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException as exc:  # giữ cửa sổ lỗi thay vì thoát im lặng
        _report(exc)
        raise SystemExit(1)
