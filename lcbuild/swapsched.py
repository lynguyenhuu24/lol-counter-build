"""Máy trạng thái đặt lệnh đổi tướng: chờ sát hết thời gian rồi swap.

Tách khỏi giao diện để test được: đầu vào là trạng thái bench + thời gian còn lại,
đầu ra là "có nên gửi yêu cầu đổi tướng ngay bây giờ không".

Hai chế độ:
  * "immediate" (mặc định): gửi NGAY khi client cho phép — dùng khi bạn sợ người
    khác lấy mất tướng trên bench. Có thể trễ tối đa một nhịp hỏi trạng thái.
  * "deadline": chờ tới sát lúc hết thời gian chọn tướng mới gửi.

Chung cho cả hai:
  * chỉ gửi khi đã qua thời gian khoá 3 giây (BENCH_COOLDOWN) kể từ lúc thấy bench;
  * nếu hết thời gian mà chưa gửi (bị khoá / chưa đọc được đồng hồ) thì gửi ngay;
  * mỗi lệnh chỉ gửi một lần.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .bench import BENCH_COOLDOWN, DEFAULT_LEAD, FALLBACK_LEAD


IMMEDIATE = "immediate"
DEADLINE = "deadline"


@dataclass
class PendingSwap:
    champion: dict
    created_at: float
    lead: float = DEFAULT_LEAD
    reason: str = ""
    mode: str = IMMEDIATE


@dataclass
class Scheduler:
    """Quyết định thời điểm gửi yêu cầu đổi tướng."""

    pending: PendingSwap | None = None
    fired: bool = False
    note: str = ""
    history: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------ lệnh
    def arm(self, champion: dict, created_at: float, lead: float = DEFAULT_LEAD,
            reason: str = "", mode: str = IMMEDIATE) -> None:
        self.pending = PendingSwap(champion, created_at, lead, reason, mode)
        self.fired = False
        when = "ngay khi có thể" if mode == IMMEDIATE else "sát lúc hết giờ"
        self.note = f"đã đặt lệnh đổi sang {champion['name']} ({when})"

    def cancel(self) -> None:
        if self.pending is not None:
            self.history.append(f"huỷ lệnh {self.pending.champion['name']}")
        self.pending = None
        self.fired = False
        self.note = ""

    # ------------------------------------------------------------------ quyết định
    def step(
        self,
        now: float,
        seconds_left: float | None,
        bench_ids: set[int],
        bench_seen_at: float | None,
    ) -> dict | None:
        """Trả về tướng cần đổi tới nếu tới lúc gửi, ngược lại None.

        `bench_ids` là id các tướng đang có trên bench; nếu tướng đã đặt lệnh
        không còn trên bench thì tự huỷ.
        """
        if self.pending is None or self.fired:
            return None

        target = self.pending.champion
        if int(target["id"]) not in bench_ids:
            self.history.append(f"{target['name']} đã rời bench")
            self.cancel()
            return None

        locked_for = None
        if bench_seen_at is not None:
            locked_for = BENCH_COOLDOWN - (now - bench_seen_at)
        if locked_for is not None and locked_for > 0:
            self.note = (f"client đang khoá đổi tướng, còn {locked_for:.1f}s…")
            return None

        # đổi ngay: hết khoá là gửi luôn
        if self.pending.mode == IMMEDIATE:
            return self._fire(target, "đổi ngay")

        if seconds_left is None:
            # không đọc được đồng hồ client: chỉ gửi khi đã qua thời gian khoá
            if bench_seen_at is not None and now - bench_seen_at >= (
                BENCH_COOLDOWN + FALLBACK_LEAD
            ):
                return self._fire(target, "không đọc được đồng hồ, gửi theo thời gian chờ")
            self.note = "chờ đồng hồ của client…"
            return None

        if seconds_left <= self.pending.lead:
            return self._fire(target, f"còn {seconds_left:.1f}s")

        self.note = f"chờ còn {self.pending.lead:.1f}s (hiện {seconds_left:.1f}s)"
        return None

    def _fire(self, champion: dict, detail: str) -> dict:
        self.fired = True
        self.note = f"đã gửi đổi tướng ({detail})"
        self.history.append(f"gửi đổi sang {champion['name']} ({detail})")
        return champion
