from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Protocol

from .sources import Offer, PriceSourceError, fetch_page_price, relevant
from .store import Watch, WatchStore


class PriceSource(Protocol):
    name: str

    def search(self, query: str) -> list[Offer]: ...


def won(price: int) -> str:
    return f"{price:,}원"


@dataclass(frozen=True)
class CheckResult:
    watch: Watch
    offer: Offer | None
    alert: bool
    reason: str = ""  # "target" | "new_low"
    error: str = ""


class PriceChecker:
    """Finds the current lowest price for a watch and decides whether to alert.

    Alerts fire when the price is at or under the target, or (with no target) when it
    drops below the lowest price seen so far. The first check only sets the baseline,
    and the same price never alerts twice.
    """

    def __init__(self, store: WatchStore, sources: Callable[[], list[PriceSource]],
                 page_fetcher: Callable[[str], Offer] = fetch_page_price) -> None:
        self.store = store
        self.sources = sources
        self.page_fetcher = page_fetcher

    def lowest(self, query: str) -> tuple[list[Offer], list[str]]:
        """Relevant offers from every configured source, cheapest first, plus source errors."""

        offers: list[Offer] = []
        errors: list[str] = []
        for source in self.sources():
            try:
                offers.extend(relevant(source.search(query), query))
            except PriceSourceError as exc:
                errors.append(str(exc))
        return sorted(offers, key=lambda offer: offer.price), errors

    def check(self, watch: Watch, now: datetime | None = None) -> CheckResult:
        now = now or datetime.now()
        try:
            if watch.url:
                offer = self.page_fetcher(watch.url)
            else:
                if not self.sources():
                    raise PriceSourceError("가격 조회 API 키가 없어요. 메뉴의 '가격 알림 설정'에서 네이버 쇼핑 키를 넣어 주세요.")
                offers, errors = self.lowest(watch.query)
                if not offers:
                    raise PriceSourceError(errors[0] if errors else f"'{watch.query}'에 맞는 상품을 찾지 못했어요.")
                offer = offers[0]
        except PriceSourceError as exc:
            self.store.record_error(watch.id, str(exc), now)
            return CheckResult(watch, None, False, error=str(exc))

        reason = ""
        already = watch.notified_price is not None and offer.price >= watch.notified_price
        if watch.target_price is not None:
            if offer.price <= watch.target_price and not already:
                reason = "target"
        elif watch.lowest_seen is not None and offer.price < watch.lowest_seen and not already:
            reason = "new_low"
        self.store.record(watch.id, offer.price, offer.mall, offer.link, now, notified=bool(reason))
        return CheckResult(self.store.get(watch.id) or watch, offer, bool(reason), reason)
