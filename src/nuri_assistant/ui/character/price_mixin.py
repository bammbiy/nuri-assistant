"""Price watch: periodic checks in a thread, alerts and the price window.

Mixed into ``MascotApp``; relies on its ``watches``/price checker, ``events`` queue and ``talk``.
"""

from __future__ import annotations

import threading

from ...announcements import price_alert_line
from ...pricewatch import CheckResult
from ..windows.price import PriceWindow
from .timing import MIN_PRICE_CHECK_MINUTES, PRICE_ALERT_GAP_MS


class PriceMixin:
    """Lowest-price checks and alerts."""

    # ----- price watch --------------------------------------------------------------

    def _price_loop(self) -> None:
        try:
            self.check_prices_now()
        finally:
            self.after(max(self.settings.price_check_minutes, MIN_PRICE_CHECK_MINUTES) * 60_000, self._price_loop)

    def check_prices_now(self) -> None:
        """Check every watch on a worker thread; results come back through the event queue."""

        if self._price_checking or not self.watches.all():
            return
        self._price_checking = True

        def work() -> None:
            results = []
            try:
                for watch in self.watches.all():
                    results.append(self.price_checker.check(watch))
            finally:
                self.events.put(("prices", results))

        threading.Thread(target=work, daemon=True).start()

    def _show_price_results(self, results: list[CheckResult]) -> None:
        self._price_checking = False
        alerts = [result for result in results if result.alert and result.offer]
        for index, result in enumerate(alerts):
            self.after(index * PRICE_ALERT_GAP_MS, lambda result=result: self._announce_price(result))

    def _announce_price(self, result: CheckResult) -> None:
        line = price_alert_line(self.persona, result)
        self.say(f"{line}\n(말풍선을 누르면 상품 페이지가 열려요)", "surprised")
        self.speak(line)
        self.bubble.link = result.offer.link
        self.bell()

    def open_price_window(self) -> None:
        PriceWindow(self, self.watches, self.check_prices_now, lambda: bool(self._price_sources()))
