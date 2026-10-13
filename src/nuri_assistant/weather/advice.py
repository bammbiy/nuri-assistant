from __future__ import annotations

from .forecast import DayForecast


def _hour_text(hour: int) -> str:
    if hour == 0:
        return "자정"
    if hour == 12:
        return "낮 12시"
    return f"오전 {hour}시" if hour < 12 else f"오후 {hour - 12}시"


def _clothing(high: float) -> str:
    for limit, text in (
        (28, "반팔에 얇은 옷이면 충분해요."),
        (23, "반팔이면 돼요."),
        (20, "얇은 긴팔이 좋아요."),
        (17, "가디건 하나 챙겨요."),
        (12, "자켓 입고 나가요."),
        (9, "트렌치코트 날씨예요."),
        (5, "코트 입어요."),
    ):
        if high >= limit:
            return text
    return "패딩 꼭 입어요!"


def weather_line(place_name: str, day: DayForecast) -> str:
    high, low = round(day.high), round(day.low)
    head = f"{place_name} 오늘 최고 {high}도·최저 {low}도, 비 올 확률 {day.rain_chance}%예요"
    umbrella = ""
    if day.rain_chance >= 60:
        umbrella = "우산 꼭 챙기세요!"
    elif day.rain_chance >= 40:
        umbrella = "작은 우산 있으면 좋아요."
    if umbrella and day.rain_from is not None:
        head += f"({_hour_text(day.rain_from)}쯤부터)"
    parts = [head + ".", umbrella, _clothing(day.high)]
    if day.high - day.low >= 10:
        parts.append("일교차가 커요.")
    return " ".join(p for p in parts if p)
