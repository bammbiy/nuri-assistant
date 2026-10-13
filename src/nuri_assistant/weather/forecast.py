from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


USER_AGENT = "NuriAssistant/1.0 (+desktop weather)"
TIMEOUT = 15
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
RAIN_HOUR_PERCENT = 60


class WeatherError(Exception):
    pass


@dataclass(frozen=True)
class Place:
    name: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class DayForecast:
    high: float
    low: float
    rain_chance: int
    rain_from: int | None


Opener = Callable[[Request], Any]


def _default_opener(request: Request) -> Any:
    return urlopen(request, timeout=TIMEOUT)  # noqa: S310 - fixed https endpoints


def _read_json(opener: Opener, url: str) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with opener(request) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise WeatherError(f"날씨 서버 요청이 실패했어요. ({exc.code})") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise WeatherError("날씨 서버에 연결하지 못했어요.") from exc
    except ValueError as exc:
        raise WeatherError("날씨 응답을 읽지 못했어요.") from exc
    if not isinstance(data, dict):
        raise WeatherError("날씨 응답을 읽지 못했어요.")
    return data


def geocode(city: str, opener: Opener = _default_opener) -> Place:
    query = urlencode({"name": city.strip(), "count": 1, "language": "ko", "format": "json"})
    data = _read_json(opener, f"{GEOCODE_URL}?{query}")
    results = data.get("results")
    if not isinstance(results, list) or not results:
        raise WeatherError(f"'{city}' 위치를 찾지 못했어요.")
    first = results[0]
    try:
        return Place(str(first.get("name") or city), float(first["latitude"]), float(first["longitude"]))
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise WeatherError(f"'{city}' 위치를 찾지 못했어요.") from exc


def fetch_today(place: Place, now: datetime, opener: Opener = _default_opener) -> DayForecast:
    query = urlencode(
        {
            "latitude": place.latitude,
            "longitude": place.longitude,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "hourly": "precipitation_probability",
            "timezone": "auto",
            "forecast_days": 1,
        },
        safe=",",
    )
    data = _read_json(opener, f"{FORECAST_URL}?{query}")
    try:
        daily = data["daily"]
        high = daily["temperature_2m_max"][0]
        low = daily["temperature_2m_min"][0]
        chance = daily["precipitation_probability_max"][0]
        hourly = data["hourly"]["precipitation_probability"]
        if high is None or low is None or chance is None:
            raise ValueError
        rain_from = None
        for hour, value in enumerate(hourly[:24]):
            if hour >= now.hour and value is not None and value >= RAIN_HOUR_PERCENT:
                rain_from = hour
                break
        return DayForecast(float(high), float(low), int(round(chance)), rain_from)
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise WeatherError("날씨 정보를 읽지 못했어요.") from exc
