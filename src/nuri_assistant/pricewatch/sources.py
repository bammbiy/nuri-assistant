from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


USER_AGENT = "NuriAssistant/1.0 (+desktop price watch)"
TIMEOUT = 15


class PriceSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class Offer:
    title: str
    price: int
    mall: str
    link: str
    product_id: str = ""


Opener = Callable[[Request], Any]


def _default_opener(request: Request) -> Any:
    return urlopen(request, timeout=TIMEOUT)  # noqa: S310 - fixed https endpoints or a user-given product URL


def _read_json(opener: Opener, request: Request, service: str) -> dict[str, Any]:
    try:
        with opener(request) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:200]
        if exc.code in (401, 403):
            raise PriceSourceError(f"{service} 인증에 실패했어요. 키를 확인해 주세요. ({exc.code})") from exc
        if exc.code == 429:
            raise PriceSourceError(f"{service} 호출 한도를 넘었어요. 잠시 뒤에 다시 확인할게요.") from exc
        raise PriceSourceError(f"{service} 요청 실패 ({exc.code}): {detail}") from exc
    except (URLError, TimeoutError) as exc:
        raise PriceSourceError(f"{service}에 연결하지 못했어요.") from exc
    except ValueError as exc:
        raise PriceSourceError(f"{service} 응답을 읽지 못했어요.") from exc


def _clean_title(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", text)).strip()


def relevant(offers: list[Offer], query: str) -> list[Offer]:
    """Keep offers whose title contains every word of the query (drops cases, cables...)."""

    words = [word.lower() for word in re.split(r"\s+", query.strip()) if word]
    squashed = lambda text: re.sub(r"\s+", "", text.lower())  # noqa: E731 - "에어팟프로" matches "에어팟 프로"
    return [offer for offer in offers if all(word in offer.title.lower() or word in squashed(offer.title) for word in words)]


class NaverShopping:
    """네이버 쇼핑 검색 API — free with a developers.naver.com app (25,000 calls/day)."""

    name = "네이버 쇼핑"
    URL = "https://openapi.naver.com/v1/search/shop.json"

    def __init__(self, client_id: str, client_secret: str, opener: Opener = _default_opener) -> None:
        self.client_id, self.client_secret, self.opener = client_id.strip(), client_secret.strip(), opener

    def search(self, query: str, display: int = 40) -> list[Offer]:
        params = urlencode({"query": query, "display": display, "sort": "sim", "exclude": "used:rental:cbshop"})
        request = Request(
            f"{self.URL}?{params}",
            headers={"X-Naver-Client-Id": self.client_id, "X-Naver-Client-Secret": self.client_secret, "User-Agent": USER_AGENT},
        )
        data = _read_json(self.opener, request, self.name)
        offers = []
        for item in data.get("items", []):
            try:
                price = int(item.get("lprice") or 0)
            except ValueError:
                continue
            if price > 0:
                offers.append(Offer(_clean_title(item.get("title", "")), price, item.get("mallName") or "네이버",
                                    item.get("link", ""), str(item.get("productId", ""))))
        return offers


_BLOCKING_SITES = ("coupang.com",)


def fetch_page_price(url: str, opener: Opener = _default_opener) -> Offer:
    """Best-effort price from a product page: schema.org JSON-LD or price meta tags.

    Many shops (notably 쿠팡) block automated requests; that is reported as an error
    rather than worked around.
    """

    host = urlparse(url).netloc.lower()
    if not url.startswith(("http://", "https://")):
        raise PriceSourceError("상품 링크는 http(s) 주소여야 해요.")
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "ko-KR,ko;q=0.9"})
    try:
        with opener(request) as response:
            page = response.read(2_000_000).decode("utf-8", errors="replace")
    except HTTPError as exc:
        hint = " 쿠팡은 자동 조회를 막고 있어서, 상품 이름으로 감시하는 걸 추천해요." if any(site in host for site in _BLOCKING_SITES) else ""
        raise PriceSourceError(f"상품 페이지를 열지 못했어요 ({exc.code}).{hint}") from exc
    except (URLError, TimeoutError) as exc:
        raise PriceSourceError("상품 페이지에 연결하지 못했어요.") from exc

    title_match = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)', page) or re.search(r"<title>([^<]+)</title>", page)
    title = _clean_title(title_match.group(1)) if title_match else host
    price = _json_ld_price(page) or _meta_price(page)
    if price is None:
        raise PriceSourceError("페이지에서 가격 정보를 찾지 못했어요. 상품 이름으로 감시해 보세요.")
    return Offer(title, price, host.removeprefix("www."), url)


def _json_ld_price(page: str) -> int | None:
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page, re.S | re.I):
        try:
            data = json.loads(block.strip())
        except ValueError:
            continue
        for node in _walk(data):
            offers = node.get("offers") if isinstance(node, dict) else None
            for offer in offers if isinstance(offers, list) else [offers] if offers else []:
                if isinstance(offer, dict):
                    value = offer.get("price") or offer.get("lowPrice")
                    price = _to_int(value)
                    if price:
                        return price
    return None


def _walk(node: Any):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def _meta_price(page: str) -> int | None:
    for prop in ("product:price:amount", "og:price:amount"):
        match = re.search(rf'<meta[^>]+property=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)', page)
        if match and (price := _to_int(match.group(1))):
            return price
    return None


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    digits = re.sub(r"[^\d.]", "", str(value))
    try:
        price = int(float(digits)) if digits else 0
    except ValueError:
        return None
    return price or None
