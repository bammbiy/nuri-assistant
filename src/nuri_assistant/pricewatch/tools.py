from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .checker import PriceChecker, won
from .store import WatchStore


TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_prices",
            "description": "상품의 현재 최저가를 찾아볼 때 호출한다 (네이버 쇼핑/쿠팡 등). 결과에 없는 가격은 지어내지 않는다.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "상품 이름. 예: 에어팟 프로 2세대"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_price_watch",
            "description": (
                "최저가가 뜨면 알려 달라는 요청일 때 호출한다. 상품 이름이나 상품 링크 중 하나가 필요하다. "
                "실제 등록은 사용자가 화면의 확인 버튼을 눌러야 끝난다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "상품 이름. 예: 에어팟 프로 2세대"},
                    "url": {"type": "string", "description": "사용자가 준 상품 링크가 있을 때만"},
                    "target_price": {"type": "integer", "description": "이 가격(원) 이하가 되면 알림. 사용자가 말한 경우에만. 예: 30만원 -> 300000"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_price_watches",
            "description": "등록된 최저가 알림 목록과 현재 가격을 볼 때 호출한다.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_price_watch",
            "description": "최저가 알림을 해제할 때 호출한다. 실제 해제는 사용자가 화면의 확인 버튼을 눌러야 끝난다.",
            "parameters": {
                "type": "object",
                "properties": {"keyword": {"type": "string", "description": "해제할 알림의 상품 이름 일부"}},
                "required": ["keyword"],
            },
        },
    },
]


@dataclass(frozen=True)
class WatchAction:
    """A price-watch change waiting for confirmation (same shape the confirm card reads)."""

    kind: str  # "add" | "cancel"
    title: str
    target_price: int | None = None
    url: str = ""
    watch_id: int | None = None

    @property
    def heading(self) -> str:
        return "최저가 알림 등록" if self.kind == "add" else "최저가 알림 해제"

    @property
    def when(self) -> str:
        return f"{won(self.target_price)} 이하" if self.target_price else "최저가 갱신 시"


def _price(value: Any) -> int | None:
    """Accept 300000, "300000", "30만원", "29만 9천원"."""

    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return int(value) or None
    text = str(value).replace(",", "").replace(" ", "")
    total = 0
    for amount, unit in re.findall(r"(\d+(?:\.\d+)?)(만|천)", text):
        total += int(float(amount) * (10_000 if unit == "만" else 1_000))
        text = text.replace(f"{amount}{unit}", "", 1)
    rest = re.sub(r"\D", "", text)
    total += int(rest) if rest else 0
    return total or None


class PriceTools:
    specs = TOOL_SPECS

    def __init__(self, store: WatchStore, checker: PriceChecker) -> None:
        self.store = store
        self.checker = checker
        self.pending: list[WatchAction] = []

    @property
    def names(self) -> set[str]:
        return {spec["function"]["name"] for spec in self.specs}

    def owns(self, action: object) -> bool:
        return isinstance(action, WatchAction)

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        args = {key: value for key, value in arguments.items() if value not in (None, "")}
        if name == "search_prices":
            return self._search(str(args.get("query", "")))
        if name == "add_price_watch":
            return self._add(str(args.get("query", "")), str(args.get("url", "")), args.get("target_price"))
        if name == "list_price_watches":
            return self._list()
        if name == "remove_price_watch":
            return self._remove(str(args.get("keyword", "")))
        return {"ok": False, "error": f"알 수 없는 도구: {name}"}

    def _search(self, query: str) -> dict[str, Any]:
        if not query.strip():
            return {"ok": False, "error": "상품 이름이 필요해요."}
        if not self.checker.sources():
            return {"ok": False, "error": "가격 조회 API 키가 없어요. 메뉴의 '가격 알림 설정'에서 키를 넣어 달라고 안내한다."}
        offers, errors = self.checker.lowest(query)
        if not offers:
            return {"ok": False, "error": errors[0] if errors else "맞는 상품을 찾지 못했어요."}
        return {"ok": True, "query": query, "cheapest": [f"{won(o.price)} {o.mall} - {o.title}" for o in offers[:3]]}

    def _add(self, query: str, url: str, target: Any) -> dict[str, Any]:
        if not query.strip() and not url.strip():
            return {"ok": False, "error": "상품 이름이나 링크가 필요해요."}
        if not url and not self.checker.sources():
            return {"ok": False, "error": "가격 조회 API 키가 없어요. 메뉴의 '가격 알림 설정'에서 네이버 쇼핑 키를 넣어 달라고 안내한다."}
        action = WatchAction("add", query.strip() or url.strip(), _price(target), url.strip())
        self.pending.append(action)
        return {"ok": True, "status": "사용자 확인 대기 중 (아직 등록되지 않음)", "title": action.title, "condition": action.when}

    def _list(self) -> dict[str, Any]:
        watches = self.store.all()
        return {
            "ok": True,
            "count": len(watches),
            "watches": [
                f"{w.label}: 현재 {won(w.last_price) if w.last_price else '확인 전'}"
                + (f" ({w.last_mall})" if w.last_mall else "")
                + (f", 목표 {won(w.target_price)}" if w.target_price else "")
                + (f", 최저 {won(w.lowest_seen)}" if w.lowest_seen else "")
                for w in watches
            ],
        }

    def _remove(self, keyword: str) -> dict[str, Any]:
        matches = [w for w in self.store.all() if keyword.strip() and keyword.strip() in w.label]
        if not matches:
            return {"ok": False, "error": "그런 알림이 없어요."}
        if len(matches) > 1:
            return {"ok": False, "error": "여러 알림이 해당돼요. 어떤 것인지 물어본다.", "candidates": [w.label for w in matches]}
        watch = matches[0]
        self.pending.append(WatchAction("cancel", watch.label, watch.target_price, watch.url, watch.id))
        return {"ok": True, "status": "사용자 확인 대기 중 (아직 해제되지 않음)", "title": watch.label}

    def take_pending(self) -> list[WatchAction]:
        pending, self.pending = self.pending, []
        return pending

    def confirm(self, action: WatchAction) -> str:
        if action.kind == "add":
            query = action.title if not action.url or action.title != action.url else ""
            self.store.add(query, action.url, action.target_price)
            condition = f"{won(action.target_price)} 이하가 되면" if action.target_price else "최저가가 갱신되면"
            return f"'{action.title}' {condition} 알려 드릴게요."
        if action.watch_id is not None and self.store.delete(action.watch_id):
            return f"'{action.title}' 최저가 알림을 해제했어요."
        return "이미 없는 알림이에요."
