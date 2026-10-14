from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from datetime import date


COLORS = ["하늘색", "분홍색", "연두색", "노란색", "보라색", "하얀색",
          "주황색", "민트색", "남색", "연갈색", "라벤더색", "코랄색"]

ITEMS = ["머그컵", "이어폰", "손수건", "볼펜", "텀블러", "작은 수첩", "핸드크림", "열쇠고리",
         "립밤", "포스트잇", "양말", "물병", "머리끈", "휴대폰 거치대", "에코백"]

ADVICES: dict[int, list[str]] = {
    1: ["오늘은 천천히 가도 괜찮아요. 따뜻한 차 한 잔 어때요?",
        "조금 쉬어 가는 날이에요. 무리하지 않아도 돼요.",
        "작은 일 하나만 끝내도 충분한 날이에요.",
        "오늘은 저랑 느긋하게 보내요. 내일은 더 좋아질 거예요."],
    2: ["서두르지 않으면 차분하게 잘 풀려요.",
        "중간에 숨 한 번 고르면 좋은 하루가 돼요.",
        "소소한 즐거움을 하나 챙겨 보세요.",
        "급한 일부터 하나씩 하면 괜찮아요."],
    3: ["평범하지만 편안한 하루가 될 거예요.",
        "오후에 좋은 소식이 있을지도 몰라요.",
        "하던 일을 꾸준히 하면 좋은 결과가 있어요.",
        "잠깐 산책하면 기분이 한결 가벼워져요."],
    4: ["하는 일마다 술술 풀리는 날이에요.",
        "누군가에게 먼저 인사하면 좋은 일이 생겨요.",
        "미뤄 둔 일을 시작하기 좋은 날이에요.",
        "오늘은 컨디션이 좋아서 집중이 잘 돼요."],
    5: ["오늘은 뭘 해도 잘 될 거예요. 자신 있게 가 보세요!",
        "기다리던 좋은 소식이 올지도 몰라요.",
        "하고 싶었던 일에 도전하기 딱 좋은 날이에요.",
        "오늘의 선배는 반짝반짝 빛나요."],
}


@dataclass(frozen=True)
class Fortune:
    stars: int
    color: str
    item: str
    advice: str


def today_fortune(day: date, persona_id: str) -> Fortune:
    digest = hashlib.sha256(f"{day.isoformat()}:{persona_id}".encode("utf-8")).digest()
    rng = random.Random(int.from_bytes(digest[:8], "big"))
    stars = rng.randint(1, 5)
    return Fortune(stars, rng.choice(COLORS), rng.choice(ITEMS), rng.choice(ADVICES[stars]))


def fortune_text(f: Fortune) -> str:
    bar = "★" * f.stars + "☆" * (5 - f.stars)
    return f"운세 {bar} · 행운의 색 {f.color} · 행운의 물건 {f.item}\n{f.advice}"
