from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError

from src.nuri_assistant.companion import ToolBox
from src.nuri_assistant.pricewatch import (
    NaverShopping, Offer, PriceChecker, PriceSourceError, PriceTools, WatchStore,
    fetch_page_price, relevant,
)
from src.nuri_assistant.pricewatch.tools import _price
from src.nuri_assistant.schedule import ScheduleStore, ScheduleTools


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def opener_returning(payload, seen: list | None = None):
    def opener(request):
        if seen is not None:
            seen.append(request)
        body = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        return FakeResponse(body)
    return opener


class SourcesTest(unittest.TestCase):
    def test_naver_parses_items_and_sends_keys(self) -> None:
        seen: list = []
        payload = {"items": [
            {"title": "<b>에어팟</b> 프로 2세대", "lprice": "289000", "mallName": "쿠팡", "link": "https://a", "productId": "1"},
            {"title": "에어팟 케이스", "lprice": "", "mallName": "x", "link": "https://b"},
        ]}
        offers = NaverShopping("id", "secret", opener_returning(payload, seen)).search("에어팟 프로")

        self.assertEqual(offers, [Offer("에어팟 프로 2세대", 289000, "쿠팡", "https://a", "1")])
        request = seen[0]
        self.assertEqual(request.get_header("X-naver-client-id"), "id")
        self.assertIn("exclude=used%3Arental%3Acbshop", request.full_url)

    def test_naver_auth_error_is_friendly(self) -> None:
        def opener(request):
            raise HTTPError(request.full_url, 401, "unauthorized", {}, io.BytesIO(b"{}"))

        with self.assertRaisesRegex(PriceSourceError, "인증"):
            NaverShopping("id", "bad", opener).search("x")

    def test_page_price_from_json_ld_and_meta(self) -> None:
        ld = b'<html><head><meta property="og:title" content="Nice Mouse"><script type="application/ld+json">{"@type":"Product","offers":{"@type":"Offer","price":"39,900"}}</script></head></html>'
        self.assertEqual(fetch_page_price("https://shop.example/p/1", opener_returning(ld)), Offer("Nice Mouse", 39900, "shop.example", "https://shop.example/p/1"))
        meta = b'<html><title>Desk</title><meta property="product:price:amount" content="129000"></html>'
        self.assertEqual(fetch_page_price("https://www.store.kr/d", opener_returning(meta)).price, 129000)

    def test_blocked_coupang_page_suggests_name_watch(self) -> None:
        def opener(request):
            raise HTTPError(request.full_url, 403, "forbidden", {}, io.BytesIO(b""))

        with self.assertRaisesRegex(PriceSourceError, "상품 이름"):
            fetch_page_price("https://www.coupang.com/vp/products/1", opener)

    def test_relevant_drops_accessories(self) -> None:
        offers = [Offer("에어팟 프로 2세대", 289000, "a", ""), Offer("에어팟 케이스 실리콘", 5000, "b", ""), Offer("에어팟프로 정품", 299000, "c", "")]

        self.assertEqual([o.mall for o in relevant(offers, "에어팟 프로")], ["a", "c"])


class FakeSource:
    name = "fake"

    def __init__(self, prices: list[int]) -> None:
        self.prices = prices

    def search(self, query: str) -> list[Offer]:
        return [Offer(f"{query} 정품", self.prices.pop(0), "몰", "https://shop/1")]


class CheckerAndToolsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = WatchStore(Path(self.tmp.name) / "companion.sqlite3")
        self.source = FakeSource([])
        self.checker = PriceChecker(self.store, lambda: [self.source])
        self.tools = PriceTools(self.store, self.checker)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_target_price_alerts_once_per_new_price(self) -> None:
        watch = self.store.add("에어팟 프로", target_price=300000)
        self.source.prices = [320000, 299000, 299000, 290000]
        results = [self.checker.check(self.store.get(watch.id)) for _ in range(4)]

        self.assertEqual([r.alert for r in results], [False, True, False, True])
        self.assertEqual(self.store.get(watch.id).lowest_seen, 290000)
        self.assertEqual(len(self.store.history(watch.id)), 4)

    def test_without_target_first_check_is_baseline_then_new_lows_alert(self) -> None:
        watch = self.store.add("모니터")
        self.source.prices = [250000, 260000, 240000]
        results = [self.checker.check(self.store.get(watch.id)) for _ in range(3)]

        self.assertEqual([(r.alert, r.reason) for r in results], [(False, ""), (False, ""), (True, "new_low")])

    def test_errors_are_recorded_not_raised(self) -> None:
        watch = self.store.add("없는상품")
        checker = PriceChecker(self.store, lambda: [])

        result = checker.check(watch)

        self.assertIn("API 키", result.error)
        self.assertIn("API 키", self.store.get(watch.id).last_error)

    def test_price_words(self) -> None:
        self.assertEqual(_price("30만원"), 300000)
        self.assertEqual(_price("29만 9천원"), 299000)
        self.assertEqual(_price("1,250,000"), 1250000)
        self.assertEqual(_price(300000), 300000)
        self.assertIsNone(_price(""))

    def test_add_and_remove_need_confirmation(self) -> None:
        result = self.tools.execute("add_price_watch", {"query": "에어팟 프로", "target_price": "30만원"})
        self.assertTrue(result["ok"])
        self.assertEqual(self.store.all(), [])
        (action,) = self.tools.take_pending()
        self.assertEqual((action.heading, action.when), ("최저가 알림 등록", "300,000원 이하"))
        self.tools.confirm(action)
        (watch,) = self.store.all()
        self.assertEqual((watch.query, watch.target_price), ("에어팟 프로", 300000))

        self.assertTrue(self.tools.execute("remove_price_watch", {"keyword": "에어팟"})["ok"])
        self.tools.confirm(self.tools.take_pending()[0])
        self.assertEqual(self.store.all(), [])

    def test_search_reports_cheapest(self) -> None:
        self.source.prices = [289000]
        result = self.tools.execute("search_prices", {"query": "에어팟 프로"})
        self.assertEqual(result["cheapest"], ["289,000원 몰 - 에어팟 프로 정품"])

    def test_without_keys_tools_explain(self) -> None:
        tools = PriceTools(self.store, PriceChecker(self.store, lambda: []))
        self.assertIn("API 키", tools.execute("add_price_watch", {"query": "x"})["error"])
        self.assertTrue(tools.execute("add_price_watch", {"url": "https://shop/1"})["ok"])

    def test_toolbox_routes_calls_and_confirmations(self) -> None:
        schedule = ScheduleTools(ScheduleStore(Path(self.tmp.name) / "companion.sqlite3"))
        box = ToolBox([schedule, self.tools])

        self.assertEqual(len(box.specs), 7)
        self.assertTrue(box.execute("add_price_watch", {"query": "키보드"})["ok"])
        self.assertTrue(box.execute("add_event", {"title": "회의", "when": "내일 3시"})["ok"])
        actions = box.take_pending()
        self.assertEqual({type(a).__name__ for a in actions}, {"PendingAction", "WatchAction"})
        for action in actions:
            box.confirm(action)
        self.assertEqual(len(self.store.all()), 1)


if __name__ == "__main__":
    unittest.main()
