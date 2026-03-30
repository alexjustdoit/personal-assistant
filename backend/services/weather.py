import httpx
from backend.config import config


class WeatherService:
    def __init__(self):
        cfg = config.get("weather", {})
        self.enabled = cfg.get("enabled", False)
        self.api_key = cfg.get("api_key", "")
        self.city = cfg.get("city", "")
        self.units = cfg.get("units", "imperial")

    async def get(self) -> dict | None:
        if not self.enabled or not self.api_key or not self.city:
            return None
        url = "https://api.openweathermap.org/data/2.5/weather"
        async with httpx.AsyncClient() as client:
            res = await client.get(url, params={
                "q": self.city,
                "appid": self.api_key,
                "units": self.units,
            })
            res.raise_for_status()
            data = res.json()
        unit_symbol = "°F" if self.units == "imperial" else "°C"
        return {
            "city": data["name"],
            "description": data["weather"][0]["description"].capitalize(),
            "temp": round(data["main"]["temp"]),
            "feels_like": round(data["main"]["feels_like"]),
            "humidity": data["main"]["humidity"],
            "unit": unit_symbol,
        }

    def format(self, weather: dict) -> str:
        return (
            f"{weather['description']}, {weather['temp']}{weather['unit']} "
            f"(feels like {weather['feels_like']}{weather['unit']}) in {weather['city']}"
        )


weather_service = WeatherService()
