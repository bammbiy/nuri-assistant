import json
import unittest
from datetime import datetime
from urllib.error import HTTPError, URLError

from src.nuri_assistant.weather import DayForecast, Place, WeatherError, fetch_today, geocode, weather_line


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self.payload if isinstance(self.payload, bytes) else json.dumps(self.payload).encode("utf-8")


class FakeOpener:
    def __init__(self, payload=None, error=None):
        self.payload, self.error, self.urls = payload, error, []

    def __call__(self, request):
        self.urls.append(request.full_url)
        if self.error:
            raise self.error
        return FakeResponse(self.payload)


def forecast_payload(probs, high=28.4, low=19.2, chance=70):
    return {
        "daily": {"temperature_2m_max": [high], "temperature_2m_min": [low], "precipitation_probability_max": [chance]},
        "hourly": {"precipitation_probability": probs},
    }


class GeocodeTests(unittest.TestCase):
    def test_success_and_url(self):
        opener = FakeOpener({"results": [{"name": "서울", "latitude": 37.57, "longitude": 126.98}]})
        place = geocode("서울 시", opener)
        self.assertEqual(place, Place("서울", 37.57, 126.98))
        url = opener.urls[0]
        self.assertIn("geocoding-api.open-meteo.com", url)
        self.assertIn("count=1", url)
        self.assertIn("language=ko", url)
        self.assertNotIn("서울", url)
        self.assertIn("%EC%84%9C%EC%9A%B8", url)

    def test_no_result(self):
        with self.assertRaises(WeatherError) as ctx:
            geocode("없는곳", FakeOpener({}))
        self.assertIn("'없는곳' 위치를 찾지 못했어요.", str(ctx.exception))


class FetchTodayTests(unittest.TestCase):
    place = Place("서울", 37.57, 126.98)

    def test_parse_rain_from(self):
        probs = [0] * 15 + [60, 80, 90] + [20] * 6
        opener = FakeOpener(forecast_payload([10] * 5 + [70] + probs[6:]))
        day = fetch_today(self.place, datetime(2026, 10, 13, 10, 0), opener)
        self.assertEqual(day, DayForecast(28.4, 19.2, 70, 15))
        url = opener.urls[0]
        self.assertIn("latitude=37.57", url)
        self.assertIn("longitude=126.98", url)
        self.assertIn("forecast_days=1", url)
        self.assertIn("timezone=auto", url)

    def test_no_rain_later(self):
        opener = FakeOpener(forecast_payload([0] * 24, chance=10))
        self.assertIsNone(fetch_today(self.place, datetime(2026, 10, 13, 10), opener).rain_from)

    def test_missing_values(self):
        opener = FakeOpener(forecast_payload([0] * 24, high=None))
        with self.assertRaises(WeatherError) as ctx:
            fetch_today(self.place, datetime(2026, 10, 13, 10), opener)
        self.assertEqual(str(ctx.exception), "날씨 정보를 읽지 못했어요.")
        with self.assertRaises(WeatherError):
            fetch_today(self.place, datetime(2026, 10, 13, 10), FakeOpener({}))

    def test_network_errors(self):
        now = datetime(2026, 10, 13, 10)
        for error in (URLError("x"), HTTPError("u", 500, "e", {}, None), TimeoutError()):
            with self.assertRaises(WeatherError):
                fetch_today(self.place, now, FakeOpener(error=error))
        with self.assertRaises(WeatherError):
            geocode("서울", FakeOpener(error=URLError("x")))
        with self.assertRaises(WeatherError):
            geocode("서울", FakeOpener(b"not json"))


class AdviceTests(unittest.TestCase):
    def test_rain_with_time(self):
        line = weather_line("서울", DayForecast(28.4, 19.2, 70, 15))
        self.assertEqual(
            line,
            "서울 오늘 최고 28도·최저 19도, 비 올 확률 70%예요(오후 3시쯤부터). 우산 꼭 챙기세요! 반팔에 얇은 옷이면 충분해요.",
        )

    def test_morning_time(self):
        self.assertIn("(오전 7시쯤부터)", weather_line("서울", DayForecast(20, 15, 80, 7)))

    def test_medium_rain_and_dry(self):
        medium = weather_line("서울", DayForecast(21, 15, 45, 14))
        self.assertIn("작은 우산 있으면 좋아요.", medium)
        self.assertIn("(오후 2시쯤부터)", medium)
        dry = weather_line("서울", DayForecast(21, 15, 20, 14))
        self.assertNotIn("우산", dry)
        self.assertNotIn("쯤부터", dry)
        self.assertNotIn("일교차", dry)

    def test_clothing_bands(self):
        cases = [(28, "반팔에 얇은"), (27.9, "반팔이면 돼요"), (23, "반팔이면 돼요"), (22, "얇은 긴팔"), (20, "얇은 긴팔"),
                 (19, "가디건"), (17, "가디건"), (16, "자켓"), (12, "자켓"), (11, "트렌치코트"), (9, "트렌치코트"),
                 (8, "코트 입어요"), (5, "코트 입어요"), (4, "패딩")]
        for high, text in cases:
            with self.subTest(high=high):
                self.assertIn(text, weather_line("서울", DayForecast(high, high - 1, 0, None)))

    def test_daily_range(self):
        self.assertIn("일교차가 커요.", weather_line("서울", DayForecast(25, 15, 0, None)))
        self.assertNotIn("일교차", weather_line("서울", DayForecast(25, 16, 0, None)))


if __name__ == "__main__":
    unittest.main()
