from datetime import date, timedelta, datetime

import requests
from django.core.management.base import BaseCommand

from weather.models import JmaAmedas, JmaWeather

FORECASTS_3DAYS = 0
FORECASTS_OVERVIEW = 0
FORECASTS_TEMPERATURE = 2
PROBABILITY_MAX_WIND_SPEED = 3
PROBABILITY_LAND = 0


class RegionWeather:
    def __init__(self, region_code: str, region_name: str, weather_code: str):
        self.region_code = region_code
        self.region_name = region_name
        self.weather_code = weather_code

    def __str__(self):
        return f"Region {self.region_name}({self.region_code}), Weather: {self.weather_code}"


class AmedasTemperature:
    def __init__(
        self, amedas_code: str, amedas_name: str, min_temps: int, max_temps: int
    ):
        self.amedas_code = amedas_code
        self.amedas_name = amedas_name
        self.min_temps = min_temps
        self.max_temps = max_temps

    def __str__(self):
        return f"  {self.amedas_name}({self.amedas_code} の朝の最低気温: {self.min_temps}, 日中の最高気温: {self.max_temps})"


class RegionTemperature:
    def __init__(
        self, region_code: str, region_name: str, data: dict, target_date: date
    ):
        self.region_code = region_code
        self.region_name = region_name
        self.data = data
        amedas_ids = [
            amedas.id for amedas in JmaAmedas.objects.filter(jma_area3_id=region_code)
        ]
        min_temps_idx, max_temps_idx = self.get_indexes_from_time_defines(
            data["timeDefines"], target_date
        )
        min_temps_list, max_temps_list = self.get_temps_list(
            data["areas"], amedas_ids, min_temps_idx, max_temps_idx
        )
        self.avg_min_temps = round(sum(min_temps_list) / len(min_temps_list), 1)
        self.avg_max_temps = round(sum(max_temps_list) / len(max_temps_list), 1)

    @staticmethod
    def get_indexes_from_time_defines(time_defines: list[str], target_date: date):
        time_defines = [
            datetime.fromisoformat(date_str).date() for date_str in time_defines
        ]

        return [
            i
            for i, time_define in enumerate(time_defines)
            if time_define == target_date
        ]

    @staticmethod
    def get_temps_list(
        amedas_data,
        target_amedas_ids: list[str],
        min_temps_idx: int,
        max_temps_idx: int,
    ):
        min_temps_list, max_temps_list = [], []
        for amedas in amedas_data:
            amedas_temperature = AmedasTemperature(
                amedas["area"]["code"],
                amedas["area"]["name"],
                int(amedas["temps"][min_temps_idx]),
                int(amedas["temps"][max_temps_idx]),
            )
            if amedas_temperature.amedas_code not in target_amedas_ids:
                continue
            min_temps_list.append(amedas_temperature.min_temps)
            max_temps_list.append(amedas_temperature.max_temps)

        return min_temps_list, max_temps_list

    def __str__(self):
        return f"Avg Min: {self.avg_min_temps}℃, Avg Max: {self.avg_max_temps}℃"


class RegionWindSpeed:
    def __init__(self, region_code: str, data: dict, target_indexes: list[int]):
        self.region_code = region_code
        self.data = data
        self.avg_wind_speed = self.calc_wind_speed(data, target_indexes)

    @staticmethod
    def calc_wind_speed(wind_data, target_indexes):
        wind_values = [
            int(time_cell["locals"][PROBABILITY_LAND]["value"])
            for i, time_cell in enumerate(wind_data)
            if i in target_indexes
        ]

        return round(sum(wind_values) / len(wind_values), 1)

    def __str__(self):
        return f"{self.region_code} の最大風速（日中平均）は {self.avg_wind_speed}"


class RegionForecastResults:
    def __init__(
        self,
        region_weather: RegionWeather,
        region_temperature: RegionTemperature,
        region_wind_speed: RegionWindSpeed,
    ):
        self.region_weather = region_weather
        self.region_temperature = region_temperature
        self.region_wind_speed = region_wind_speed

    def __str__(self):
        region_code = self.region_weather.region_code
        region_name = self.region_weather.region_name
        forecast = {
            "weather_code": self.region_weather.weather_code,
            "temperature": (
                self.region_temperature.avg_min_temps,
                self.region_temperature.avg_max_temps,
            ),
            "wind_speed": self.region_wind_speed.avg_wind_speed,
        }

        return f"{region_code}({region_name}): {forecast}"


class Command(BaseCommand):
    help = "get weather forecast"

    def handle(self, *args, **options):
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)

        # TODO: facilityテーブルから areas2_ids を取得
        jma_areas2_ids = ["280000", "050000", "130000"]

        if not jma_areas2_ids:
            raise Exception("facility is empty")

        JmaWeather.objects.all().delete()
        for prefecture_id in jma_areas2_ids:
            forecasts_by_region = {}

            forecasts = requests.get(
                f"https://www.jma.go.jp/bosai/forecast/data/forecast/{prefecture_id}.json"
            ).json()
            overview = forecasts[FORECASTS_3DAYS]["timeSeries"][FORECASTS_OVERVIEW]
            time_defines = [
                datetime.fromisoformat(date_str).date()
                for date_str in overview["timeDefines"]
            ]
            try:
                tomorrow_idx = time_defines.index(tomorrow)
                for a_region in overview["areas"]:
                    region_code = a_region["area"]["code"]
                    region_weather = RegionWeather(
                        region_code,
                        a_region["area"]["name"],
                        a_region["weatherCodes"][tomorrow_idx],
                    )
                    forecasts_by_region.setdefault(region_code, {})[
                        "weather"
                    ] = region_weather
                    region_temperature = RegionTemperature(
                        region_code,
                        a_region["area"]["name"],
                        forecasts[FORECASTS_3DAYS]["timeSeries"][FORECASTS_TEMPERATURE],
                        tomorrow,
                    )
                    forecasts_by_region.setdefault(region_code, {})[
                        "temperature"
                    ] = region_temperature

            except ValueError:
                print(f"{prefecture_id}: no forecast")

            probabilities = requests.get(
                f"https://www.jma.go.jp/bosai/probability/data/probability/{prefecture_id}.json"
            ).json()
            tomorrow_indexes = [
                i
                for i, date_str in enumerate(
                    probabilities[0]["timeSeries"][1]["timeDefines"]
                )
                if datetime.fromisoformat(date_str).date() == tomorrow
            ]
            for a_region in probabilities[0]["timeSeries"][1]["areas"]:
                region_code = a_region["code"]
                region_wind_speed = RegionWindSpeed(
                    region_code,
                    a_region["properties"][PROBABILITY_MAX_WIND_SPEED]["timeCells"],
                    tomorrow_indexes,
                )
                forecasts_by_region.setdefault(region_code, {})[
                    "wind_speed"
                ] = region_wind_speed

            region_forecast_results_list: list[RegionForecastResults] = []
            for region_code, forecast in forecasts_by_region.items():
                region_forecast_results = RegionForecastResults(
                    forecast["weather"],
                    forecast["temperature"],
                    forecast["wind_speed"],
                )
                print(region_forecast_results)
                region_forecast_results_list.append(region_forecast_results)

            JmaWeather.objects.bulk_create(
                [
                    JmaWeather(
                        jma_areas3_id=item.region_weather.region_code,
                        weather_code=item.region_weather.weather_code,
                        temperature_min=item.region_temperature.avg_min_temps,
                        temperature_max=item.region_temperature.avg_max_temps,
                        wind_speed=item.region_wind_speed.avg_wind_speed,
                    )
                    for item in region_forecast_results_list
                ]
            )

        self.stdout.write(
            self.style.SUCCESS("weather forecast data retrieve has been completed.")
        )
