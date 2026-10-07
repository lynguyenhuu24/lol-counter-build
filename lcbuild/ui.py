"""Overlay hiển thị gợi ý lên đồ khắc chế đội hình địch.

Chạy:  python -m lcbuild.ui            (tự dò trận đang chơi / màn hình chọn tướng)
       python -m lcbuild.ui --enemies Darius,LeeSin,Ahri,Jinx,Leona
       python -m lcbuild.ui --shot out.png --enemies ... (xuất ảnh để kiểm tra)
"""
from __future__ import annotations

import argparse
import threading
import time
import tkinter as tk
import urllib.request
from pathlib import Path
from tkinter import ttk

from .advisor import (ROLE_LABEL, Suggestion, champion_notes, recommend,
                      role_of)
from .augments import (RARITY_LABEL, TIER_COLOR, TIER_LABEL, TIER_ORDER,
                       AugmentPick, rank_augments)
from .bench import (BENCH_COOLDOWN, DEFAULT_LEAD, POLL_INTERVAL, Bench,
                    read_bench, swap_to)
from .build import suggest_full_build
from .data import dataset
from .detect import Comp, current_comp
from .paths import icon_dir
from .swapsched import Scheduler

ICONS = icon_dir()

BG = "#101216"
CARD = "#181b21"
TXT = "#e8eaed"
MUTED = "#9aa0a6"
ACCENT = "#4da3ff"
WARN = "#ffb74d"


ICON_TIMEOUT = 6


def icon_path(url: str, name: str) -> Path | None:
    """Đường dẫn icon trong cache; tải nếu chưa có (tối đa ICON_TIMEOUT giây)."""
    if not url:
        return None
    dest = ICONS / f"{name}.png"
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    return _download(url, dest)


def _download(url: str, dest: Path) -> Path | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "counter-build"})
        with urllib.request.urlopen(req, timeout=ICON_TIMEOUT) as r:
            blob = r.read()
        if not blob:
            return None
        ICONS.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(blob)
        return dest
    except Exception:
        return None


def prefetch_icons(champs: list[dict], items: list[dict]) -> None:
    """Tải trước icon song song để lần vẽ đầu không phải chờ từng cái."""
    jobs: list[tuple[str, str]] = []
    for champ in champs:
        jobs.append((champ["icon"], f"champ_{champ['key']}"))
    for item in items:
        jobs.append((item["icon"], f"item_{item['id']}"))
    todo = [
        job for job in jobs
        if not (ICONS / f"{job[1]}.png").exists()
    ]
    if not todo:
        return
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=8) as ex:
        for url, name in todo:
            ex.submit(_download, url, ICONS / f"{name}.png")


class Overlay:
    def __init__(self, enemies: list[str], static: bool = False,
                 champion: str | None = None):
        self.static = static
        self.champion = champion
        self.comp: Comp | None = None
        self.root = tk.Tk()
        self.root.title("LoL Counter Build")
        self.root.configure(bg=BG)
        self.root.geometry("500x820")
        self.root.attributes("-topmost", True)
        self.images: dict[str, tk.PhotoImage] = {}
        self._last_sig: tuple | None = None
        self._busy = False
        self._bench_busy = False
        self.my_champ: dict | None = None      # tướng thật của tôi, lấy từ client
        self.view_champ: dict | None = None    # tướng đang xem build (có thể khác)
        self.view_pinned = False               # True khi do người dùng bấm chọn để xem

        bar = tk.Frame(self.root, bg=BG)
        bar.pack(fill="x", padx=10, pady=(8, 2))
        self.title = tk.Label(bar, text="Đội hình địch", bg=BG, fg=TXT,
                              font=("Segoe UI", 12, "bold"))
        self.title.pack(side="left")
        self.status = tk.Label(bar, text="", bg=BG, fg=MUTED, font=("Segoe UI", 8))
        self.status.pack(side="right")
        tk.Button(bar, text="Cập nhật (F5)", command=self.refresh,
                  bg=CARD, fg=TXT, activebackground=CARD, relief="flat",
                  font=("Segoe UI", 8)).pack(side="right", padx=6)

        # Tướng của bạn: tự lấy từ client (hoặc từ tướng vừa bấm trên bench).
        me = tk.Frame(self.root, bg=BG)
        me.pack(fill="x", padx=10)
        tk.Label(me, text="Tướng của bạn:", bg=BG, fg=MUTED,
                 font=("Segoe UI", 8)).pack(side="left")
        self.champ_var = tk.StringVar(value=champion or "đang chờ client…")
        tk.Label(me, textvariable=self.champ_var, bg=BG, fg=ACCENT,
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=6)
        self.champ_hint = tk.Label(me, text="", bg=BG, fg=MUTED,
                                   font=("Segoe UI", 8))
        self.champ_hint.pack(side="left")

        self.enemy_row = tk.Frame(self.root, bg=BG)
        self.enemy_row.pack(fill="x", padx=10, pady=(6, 4))

        # ---- hàng đợi tướng ARAM (bench) + đặt lệnh đổi tướng ----
        self.bench = None
        self.sched = Scheduler()
        self.bench_seen_at = None
        self.bench_ids: set[int] = set()
        self.bench_panel = tk.Frame(self.root, bg=BG)

        self.bench_head = tk.Frame(self.root, bg=BG)
        bench_head = self.bench_head
        bench_head.pack(fill="x", padx=10)
        tk.Label(bench_head, text="Hàng đợi tướng (bench)", bg=BG, fg=TXT,
                 font=("Segoe UI", 11, "bold")).pack(side="left")
        self.bench_clock = tk.Label(bench_head, text="", bg=BG, fg=ACCENT,
                                    font=("Segoe UI", 10, "bold"))
        self.bench_clock.pack(side="right")
        self.bench_panel.pack(fill="x", padx=10, pady=(2, 0))

        self.bench_note = tk.Label(self.root, text="", bg=BG, fg=MUTED,
                                   justify="left", wraplength=470, anchor="w",
                                   font=("Segoe UI", 8))
        self.bench_note.pack(fill="x", padx=10)

        wrap = tk.Frame(self.root, bg=BG)
        wrap.pack(fill="both", expand=True, padx=10, pady=(2, 8))
        self.canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        self.body = tk.Frame(self.canvas, bg=BG)
        self.body.bind(
            "<Configure>",
            lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.canvas.configure(yscrollcommand=scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)
        self.root.bind("<F5>", lambda _e: self.refresh())
        self.root.bind("<Escape>", lambda _e: self.root.destroy())

        self.initial = enemies
        self.refresh()
        if not static:
            self.root.after(4000, self._poll)
            self.root.after(int(POLL_INTERVAL * 1000), self._bench_tick)

    # ------------------------------------------------------------- vòng cập nhật
    def _poll(self) -> None:
        """Đọc dữ liệu game trong luồng nền để không treo giao diện."""
        if not self._busy:
            self._busy = True
            threading.Thread(target=self._load_async, daemon=True).start()
        self.root.after(4000, self._poll)

    def refresh(self) -> None:
        if self.static:
            self.render(self.initial)
            return
        if not self._busy:
            self._busy = True
            threading.Thread(target=self._load_async, daemon=True).start()

    def _load_async(self) -> None:
        try:
            comp = self.comp if (self.comp and self.comp.source == "live") else current_comp()
        except Exception:
            comp = None
        self.root.after(0, lambda: self._loaded(comp))

    def _loaded(self, comp: Comp | None) -> None:
        self._busy = False
        if comp is None or not comp.enemies:
            self.status.config(
                text="chưa vào trận / chưa chọn tướng — đang chờ…", fg=WARN
            )
            if self.initial:
                self.render(self.initial)
            return
        sig = tuple(comp.enemies)
        self.comp = comp
        if comp.my_champion:
            from .data import dataset

            mine = dataset().champion(comp.my_champion)
            if mine is not None:
                self.my_champ = mine
        if sig != self._last_sig:
            self._last_sig = sig
            self.render(comp.enemies)

    # -------------------------------------------------------- hàng đợi tướng ARAM
    def _bench_tick(self) -> None:
        """Hỏi trạng thái bench. Không dùng chung cờ bận với vòng dò đội hình,
        nếu không thì lúc vẽ đội hình (tải icon) sẽ làm lỡ thời điểm đổi tướng."""
        if not self._bench_busy:
            self._bench_busy = True
            threading.Thread(target=self._bench_worker, daemon=True).start()
        self.root.after(int(POLL_INTERVAL * 1000), self._bench_tick)

    def _bench_worker(self) -> None:
        """Đọc bench + quyết định + gửi yêu cầu đổi tướng — TẤT CẢ trong luồng nền.

        Phần quyết định thời điểm không được chạy trên luồng giao diện, vì chỉ cần
        giao diện bận vẽ là lệnh đổi tướng bị trễ tới lúc hết giờ.
        """
        try:
            bench = read_bench()
        except Exception:
            bench = None
        now = time.monotonic()
        if bench is None or not bench.usable:
            self.root.after(0, lambda: self._bench_loaded(bench, now, None))
            return

        first_seen = self.bench is None or not self.bench.enabled
        if first_seen:
            # client khoá đổi tướng ~3s sau khi bench xuất hiện
            self.bench_seen_at = now
        ids = {c["id"] for c in bench.champions}
        self.bench_ids = ids
        target = self.sched.step(now, bench.seconds_left, ids, self.bench_seen_at)
        error = None
        if target is not None:
            ok, message = swap_to(target["id"])
            self.sched.note = (
                f"✔ đã đổi sang {target['name']}" if ok
                else f"✘ không đổi được sang {target['name']}: {message}"
            )
            if not ok:
                error = message
        self.root.after(0, lambda: self._bench_loaded(bench, now, error))

    def _bench_loaded(self, bench: Bench | None, now: float, error: str | None) -> None:
        self._bench_busy = False
        self.bench = bench
        # tự nhận tướng của mình ngay ở màn hình chọn tướng
        champion_changed = False
        if bench is not None and bench.mine is not None:
            previous = self.my_champ
            self.my_champ = bench.mine
            # Tướng thật vừa ĐỔI (đổi thành công trên bench) -> bỏ ghim và quay về
            # xem tướng thật. Nếu không bỏ ghim thì view_champ dính vĩnh viễn ở tướng
            # cũ và build/lõi không bao giờ cập nhật nữa.
            if previous is None or previous["id"] != bench.mine["id"]:
                self.view_champ = bench.mine
                self.view_pinned = False
                champion_changed = True
        if bench is None or not bench.usable:
            self.bench_ids = set()
            self.bench_seen_at = None
            if self.sched.pending is not None:
                self.sched.cancel()
        self._render_bench()
        # chưa ghim tướng nào để xem -> luôn xem tướng thật của mình
        if not self.view_pinned:
            self.view_champ = self.my_champ
        # vẽ khi tướng đổi, hoặc khi màn hình còn trống (lần đầu)
        if champion_changed or not self.body.winfo_children():
            self.render(self.comp.enemies if self.comp else [])

    def _arm_swap(self, champion: dict) -> None:
        """Bấm vào tướng trên bench: đổi ngay khi client cho phép + xem build của nó."""
        lead = DEFAULT_LEAD
        if self.bench and self.bench.seconds_left is not None:
            # nếu đang trong thời gian khoá thì gửi ngay khi hết khoá
            lead = min(DEFAULT_LEAD, self.bench.seconds_left)
        self.sched.arm(champion, time.monotonic(), lead=lead)
        self.view_champ = champion      # xem build/lõi của tướng vừa bấm
        self.view_pinned = True         # người dùng chủ động chọn -> giữ cho tới khi đổi xong
        # PHẢI vẽ lại cả phần build/lõi, không chỉ panel bench — nếu không thì
        # bấm tướng khác mà build vẫn đứng yên ở tướng cũ.
        self.render(self.comp.enemies if self.comp else [])
        self._render_bench()

    def _render_bench(self) -> None:
        for child in self.bench_panel.winfo_children():
            child.destroy()
        # đã vào trận thì hàng đợi tướng không còn nghĩa lý -> ẩn cả tiêu đề
        in_game = self.comp is not None and self.comp.source == "live"
        if in_game:
            self.bench_clock.config(text="")
            self.bench_note.config(text="")
            self.bench_head.pack_forget()
            return
        if not self.bench_head.winfo_manager():
            self.bench_head.pack(fill="x", padx=10, before=self.bench_panel)
        bench = self.bench
        if bench is None or not bench.usable:
            self.bench_clock.config(text="")
            if bench is None:
                self.bench_note.config(
                    text="Chưa vào màn hình chọn tướng ARAM (bench chưa có tướng).",
                    fg=MUTED,
                )
            else:
                # nói rõ client đang báo gì, thay vì im lặng
                hint = bench.diagnose()
                if bench.enabled and not bench.unknown and not bench.custom_game:
                    hint += (" Thẻ tướng bạn KHÔNG chọn sẽ rơi xuống bench "
                             "(ARAM không còn lượt đổi tướng).")
                self.bench_note.config(text=hint, fg=WARN)
                # vẫn vẽ tướng nếu có (trường hợp thiếu 1 vài id)
                for champ in bench.champions:
                    self._bench_cell(champ, False)
            return

        left = bench.seconds_left
        if left is None:
            self.bench_clock.config(text="")
        elif bench.phase:
            self.bench_clock.config(text=f"{bench.phase} · còn {left:.0f}s")
        else:
            self.bench_clock.config(text=f"còn {left:.0f}s")
        pending_id = self.sched.pending.champion["id"] if self.sched.pending else None
        for champ in bench.champions:
            self._bench_cell(champ, champ["id"] == pending_id)

        parts = []
        if bench.mine:
            parts.append(f"bạn đang giữ {bench.mine['name']}")
        if self.sched.pending is not None:
            parts.append(f"đã đặt lệnh: {self.sched.pending.champion['name']}")
        if self.sched.note:
            parts.append(self.sched.note)
        if self.sched.pending is None:
            parts.append("bấm vào tướng để đổi ngay khi client cho phép")
        elif not self.sched.fired:
            parts.append("sẽ gửi ngay khi hết khoá 3 giây")
        self.bench_note.config(text=" · ".join(parts), fg=WARN)

    def _bench_cell(self, champ: dict, armed: bool) -> None:
        cell = tk.Frame(self.bench_panel, bg=ACCENT if armed else BG, padx=2, pady=2)
        cell.pack(side="left", padx=2)
        path = icon_path(champ["icon"], f"champ_{champ['key']}")
        if path:
            lbl = tk.Label(cell, image=self._photo(path, 40), bg=cell["bg"],
                           cursor="hand2")
        else:
            lbl = tk.Label(cell, text=champ["name"][:6], bg=cell["bg"], fg=TXT,
                           width=6, height=2, font=("Segoe UI", 8), cursor="hand2")
        lbl.pack()
        name = tk.Label(cell, text=champ["name"][:10], bg=cell["bg"], fg=TXT,
                        font=("Segoe UI", 7, "bold"), cursor="hand2")
        name.pack()
        for widget in (lbl, name, cell):
            widget.bind("<Button-1>", lambda _e, c=champ: self._arm_swap(c))

    def _on_wheel(self, event) -> None:
        self.canvas.yview_scroll(-1 * (event.delta // 120), "units")

    # ------------------------------------------------------------------- render
    def render(self, enemy_keys: list[str]) -> None:
        ds = dataset()
        for frame in (self.enemy_row, self.body):
            for child in frame.winfo_children():
                child.destroy()

        # Tướng đang xem build: ưu tiên tướng vừa bấm trên bench; nếu chưa bấm thì
        # lấy tướng thật của mình từ client; cuối cùng mới tới tham số dòng lệnh.
        view = self.view_champ or self.my_champ
        if view is None and self.champion:
            view = ds.champion(self.champion)
        self.view_champ = view

        suggestions = []
        profile = None
        notes: list[str] = []
        if enemy_keys:
            suggestions, profile, notes = recommend(
                enemy_keys, role=role_of(view) if view else None
            )
        else:
            from .advisor import build_profile

            profile = build_profile([])

        my_champ = view
        build = None
        augments = None
        if my_champ is not None:
            build = suggest_full_build(my_champ["key"], enemy_keys)
            augments = rank_augments(my_champ["key"], enemy_keys)

        icon_items = [s.item for s in suggestions]
        if build:
            icon_items += [slot.item for slot in build.slots]
        prefetch_icons(
            (profile.champs if profile else []) + ([my_champ] if my_champ else []),
            icon_items,
        )

        # nhãn tướng của bạn
        if view is not None:
            label = view["name"]
            if self.my_champ and view["id"] != self.my_champ["id"]:
                label += f" (đang xem build; bạn đang giữ {self.my_champ['name']})"
            self.champ_var.set(label)
            self.champ_hint.config(text=f"nhóm {ROLE_LABEL.get(role_of(view), '?')}")
        else:
            self.champ_var.set("đang chờ client…")
            self.champ_hint.config(text="")

        missing = [k for k in enemy_keys if ds.champion(k) is None]
        src = {"live": "trong trận", "champ_select": "chọn tướng"}.get(
            self.comp.source if self.comp else "", "thủ công"
        )
        mode = ""
        if self.comp is not None and self.comp.queue_id == 2400:
            mode = " · ARAM: Mayhem"
        elif self.comp is not None and self.comp.is_aram:
            mode = " · ARAM"
        n_enemies = len(profile.champs) if profile else 0
        self.status.config(
            text=f"{n_enemies} tướng địch · nguồn: {src}{mode}"
            + (f" · lạ: {', '.join(missing)}" if missing else ""),
            fg=MUTED,
        )

        for champ in (profile.champs if profile else []):
            self._champ_cell(champ)

        if build:
            self._section(f"Build 6 món — {my_champ['name']}")
            for i, slot in enumerate(build.slots, 1):
                self._build_row(i, slot)
            total = sum(s.item["gold"] for s in build.slots)
            tk.Label(self.body, text=f"Tổng {total} vàng", bg=BG, fg=MUTED,
                     font=("Segoe UI", 8)).pack(anchor="w", pady=(0, 6))

        if augments:
            self._section("Lõi nên chọn (ARAM: Mayhem)")
            for tier in TIER_ORDER:
                picks = augments.get(tier) or []
                if not picks:
                    continue
                tk.Label(self.body, text=TIER_LABEL[tier], bg=BG, fg=TIER_COLOR[tier],
                         font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(4, 2))
                for pick in picks[:3]:
                    self._augment_row(pick)

        if notes:
            self._section("Đội hình địch — nhận xét")
            for note in notes:
                tk.Label(self.body, text="• " + note, bg=BG, fg=WARN, justify="left",
                         wraplength=460, anchor="w", font=("Segoe UI", 9)).pack(anchor="w", pady=1)

        if suggestions:
            self._section("Món khắc chế chi tiết")
            for sug in suggestions:
                self._suggest_row(sug)

    def _section(self, title: str) -> None:
        tk.Label(self.body, text=title, bg=BG, fg=TXT,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(8, 2))

    def _build_row(self, index: int, slot) -> None:
        row = tk.Frame(self.body, bg=CARD)
        row.pack(fill="x", pady=2, padx=1)
        item = slot.item
        path = icon_path(item["icon"], f"item_{item['id']}")
        tk.Label(row, text=f"{index}", bg=CARD, fg=ACCENT, width=2,
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=(6, 0))
        if path:
            tk.Label(row, image=self._photo(path, 36), bg=CARD).pack(side="left", padx=6, pady=5)
        text = tk.Frame(row, bg=CARD)
        text.pack(side="left", fill="x", expand=True, pady=4)
        head = tk.Frame(text, bg=CARD)
        head.pack(fill="x")
        tk.Label(head, text=item["name"], bg=CARD, fg=TXT,
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        tk.Label(head, text=f"{item['gold']} vàng", bg=CARD, fg=ACCENT,
                 font=("Segoe UI", 8)).pack(side="right", padx=4)
        reason = slot.reasons[0] if slot.reasons else ""
        tk.Label(text, text=f"{slot.source}: {reason}", bg=CARD, fg=MUTED,
                 justify="left", wraplength=330, anchor="w",
                 font=("Segoe UI", 8)).pack(anchor="w")

    def _augment_row(self, pick) -> None:
        aug = pick.augment
        row = tk.Frame(self.body, bg=CARD)
        row.pack(fill="x", pady=2, padx=1)
        # icon lõi là webp, Tk không giải mã được -> hiển thị bằng chữ
        text = tk.Frame(row, bg=CARD)
        text.pack(side="left", fill="x", expand=True, pady=4)
        head = tk.Frame(text, bg=CARD)
        head.pack(fill="x")
        tk.Label(head, text=aug.name, bg=CARD, fg=TXT,
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        tk.Label(head, text=f"{aug.tier} · {RARITY_LABEL.get(aug.rarity, '')}",
                 bg=CARD, fg=TIER_COLOR.get(aug.tier, ACCENT),
                 font=("Segoe UI", 8, "bold")).pack(side="right", padx=4)
        reason = pick.reasons[0] if pick.reasons else ""
        tk.Label(text, text=reason, bg=CARD, fg=MUTED, justify="left",
                 wraplength=330, anchor="w", font=("Segoe UI", 8)).pack(anchor="w")

    def _champ_cell(self, champ: dict) -> None:
        cell = tk.Frame(self.enemy_row, bg=BG)
        cell.pack(side="left", padx=2)
        path = icon_path(champ["icon"], f"champ_{champ['key']}")
        if path:
            img = self._photo(path, 44)
            tk.Label(cell, image=img, bg=BG).pack()
        else:
            tk.Label(cell, text=champ["name"][:6], bg=CARD, fg=TXT,
                     width=6, height=2, font=("Segoe UI", 8)).pack()
        tags = champion_notes(champ)
        short = ", ".join(tags[:2]) if tags else ""
        tk.Label(cell, text=champ["name"], bg=BG, fg=TXT,
                 font=("Segoe UI", 8, "bold")).pack()
        tk.Label(cell, text=short[:22], bg=BG, fg=MUTED, wraplength=76,
                 font=("Segoe UI", 7)).pack()

    def _suggest_row(self, sug: Suggestion) -> None:
        row = tk.Frame(self.body, bg=CARD)
        row.pack(fill="x", pady=3, padx=1)
        item = sug.item
        path = icon_path(item["icon"], f"item_{item['id']}")
        if path:
            img = self._photo(path, 38)
            tk.Label(row, image=img, bg=CARD).pack(side="left", padx=6, pady=6)
        text = tk.Frame(row, bg=CARD)
        text.pack(side="left", fill="x", expand=True, pady=5)
        head = tk.Frame(text, bg=CARD)
        head.pack(fill="x")
        tk.Label(head, text=item["name"], bg=CARD, fg=TXT,
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        tk.Label(head, text=f"{item['gold']} vàng · {sug.kind}", bg=CARD, fg=ACCENT,
                 font=("Segoe UI", 8)).pack(side="right", padx=4)
        for reason in sug.reasons:
            tk.Label(text, text="– " + reason, bg=CARD, fg=MUTED, justify="left",
                     wraplength=330, anchor="w", font=("Segoe UI", 8)).pack(anchor="w")

    def _photo(self, path: Path, size: int) -> tk.PhotoImage:
        key = f"{path}|{size}"
        if key in self.images:
            return self.images[key]
        img = tk.PhotoImage(file=str(path))
        factor = max(1, round(img.width() / size))
        if factor > 1:
            img = img.subsample(factor, factor)
        self.images[key] = img
        return img


def render_image(enemies: list[str], out: str,
                 wait: float = 4.0, champion: str | None = None) -> None:
    """Chụp ảnh cửa sổ để kiểm tra giao diện (dùng ImageGrab)."""
    from PIL import ImageGrab

    overlay = Overlay(enemies, static=True, champion=champion)
    overlay.render(enemies)
    overlay.root.update()
    overlay.root.after(int(wait * 1000), overlay.root.quit)
    overlay.root.mainloop()
    x, y = overlay.root.winfo_rootx(), overlay.root.winfo_rooty()
    w, h = overlay.root.winfo_width(), overlay.root.winfo_height()
    overlay.root.update()
    img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
    img.save(out)
    overlay.root.destroy()
    print(f"đã lưu {out} ({w}x{h})")


def main() -> int:
    ap = argparse.ArgumentParser(description="Gợi ý lên đồ khắc chế đội hình địch")
    ap.add_argument("--enemies", help="danh sách tướng địch, cách nhau dấu phẩy")
    ap.add_argument("--champion",
                    help="chỉ để thử tay: coi như bạn đang chơi tướng này")
    ap.add_argument("--shot", help="xuất ảnh giao diện ra file rồi thoát")
    ap.add_argument("--text", action="store_true", help="chỉ in ra terminal, không mở cửa sổ")
    args = ap.parse_args()

    enemies = [e.strip() for e in (args.enemies or "").split(",") if e.strip()]
    if args.text:
        if args.champion:
            from .augments import TIER_LABEL, rank_augments
            from .build import format_text, suggest_full_build

            print(format_text(suggest_full_build(args.champion, enemies)))
            print()
            for tier, picks in rank_augments(args.champion, enemies).items():
                print(f"--- Lõi {TIER_LABEL[tier]}")
                for pick in picks:
                    print(f"   {pick.score:5.0f}  {pick.augment.name:<30} "
                          f"{pick.reasons[0] if pick.reasons else ''}")
            return 0
        from .data import dataset as _dataset

        my = _dataset().champion(args.champion) if args.champion else None
        suggestions, profile, notes = recommend(
            enemies, role=role_of(my) if my else None
        )
        print("\n".join("• " + n for n in notes))
        for s in suggestions:
            print(f"[{s.kind:>14}] {s.item['name']:<26} {s.item['gold']:>5} vàng  "
                  f"{' | '.join(s.reasons)}")
        return 0
    if args.shot:
        render_image(enemies, args.shot, champion=args.champion)
        return 0
    Overlay(enemies, champion=args.champion).root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
