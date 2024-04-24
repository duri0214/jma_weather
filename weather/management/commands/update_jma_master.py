import sys
from io import StringIO

import pandas as pd
import requests
from django.core.management.base import BaseCommand

from weather.models import JmaAreas1, JmaAreas2, JmaAreas3, JmaAreas4, JmaAmedas


class Command(BaseCommand):
    help = "master update"

    def handle(self, *args, **options):
        url = "https://www.jma.go.jp/bosai/common/const/area.json"
        try:
            # URLからデータを取得します
            response = requests.get(url)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(
                f"データの取得でエラーが発生しました。URL: {url} エラー詳細: {e}",
                file=sys.stderr,
            )
            sys.exit(1)

        raw_data = pd.read_json(StringIO(response.text))
        df_areas = pd.DataFrame({"area_name": []})
        for code, item in raw_data["centers"].dropna().items():
            df_areas.loc[f"{code:06}"] = [item["name"]]

        df_prefs = pd.DataFrame({"area_code": [], "pref_name": []})
        for code, item in raw_data["offices"].dropna().items():
            df_prefs.loc[f"{code:06}"] = [item["parent"], item["name"]]

        df_regions = pd.DataFrame({"pref_code": [], "region_name": []})
        for code, item in raw_data["class10s"].dropna().items():
            df_regions.loc[f"{code:06}"] = [item["parent"], item["name"]]

        df_class15s = pd.DataFrame({"region_code": [], "class15_name": []})
        for code, item in raw_data["class15s"].dropna().items():
            df_class15s.loc[f"{code:06}"] = [item["parent"], item["name"]]

        df_cities = pd.DataFrame({"class15_code": [], "city_name": []})
        for code, item in raw_data["class20s"].dropna().items():
            df_cities.loc[f"{code:07}"] = [item["parent"], item["name"]]

        df_cities = (
            df_cities.merge(
                df_class15s, left_on="class15_code", right_index=True, how="outer"
            )
            .merge(df_regions, left_on="region_code", right_index=True)
            .merge(df_prefs, left_on="pref_code", right_index=True)
            .merge(df_areas, left_on="area_code", right_index=True)
        )
        df_cities.drop(
            ["area_code", "area_name", "class15_code", "class15_name"],
            axis=1,
            inplace=True,
        )

        # jma_areas1: 010600 近畿地方
        df_areas.index.name = "id"
        df_areas.rename(columns={"area_name": "name"}, inplace=True)
        dict_centers = df_areas.reset_index().to_dict("records")
        JmaAreas1.objects.all().delete()
        JmaAreas1.objects.bulk_create(
            [JmaAreas1(id=item["id"], name=item["name"]) for item in dict_centers]
        )

        # jma_areas2: 280000 兵庫県
        df_prefs.index.name = "id"
        df_prefs.rename(
            columns={"area_code": "jmaAreas1Id", "pref_name": "name"}, inplace=True
        )
        dict_prefs = df_prefs.reset_index().to_dict("records")
        JmaAreas2.objects.all().delete()
        JmaAreas2.objects.bulk_create(
            [
                JmaAreas2(
                    id=item["id"], jma_area1_id=item["jmaAreas1Id"], name=item["name"]
                )
                for item in dict_prefs
            ]
        )

        # jma_areas3: 280010 南部
        df_regions.index.name = "id"
        df_regions.rename(
            columns={"pref_code": "jmaAreas2Id", "region_name": "name"}, inplace=True
        )
        dict_regions = df_regions.reset_index().to_dict("records")
        JmaAreas3.objects.all().delete()
        JmaAreas3.objects.bulk_create(
            [
                JmaAreas3(
                    id=item["id"], jma_area2_id=item["jmaAreas2Id"], name=item["name"]
                )
                for item in dict_regions
            ]
        )

        # jma_areas4: 2820100 姫路市
        df_cities.index.name = "id"
        df_cities.drop(["pref_name"], axis=1, inplace=True)
        df_cities.rename(
            columns={
                "pref_code": "jmaAreas2Id",
                "region_code": "jmaAreas3Id",
                "region_name": "regionName",
                "city_name": "name",
            },
            inplace=True,
        )
        df_cities = df_cities.reindex(["jmaAreas2Id", "jmaAreas3Id", "name"], axis=1)
        dict_cities = df_cities.reset_index().to_dict("records")
        JmaAreas4.objects.all().delete()
        JmaAreas4.objects.bulk_create(
            [
                JmaAreas4(
                    id=item["id"],
                    jma_area2_id=item["jmaAreas2Id"],
                    jma_area3_id=item["jmaAreas3Id"],
                    name=item["name"],
                )
                for item in dict_cities
            ]
        )

        # 2: from forecast_area.json
        url = "https://www.jma.go.jp/bosai/forecast/const/forecast_area.json"
        try:
            # URLからデータを取得します
            response = requests.get(url)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(
                f"データの取得でエラーが発生しました。URL: {url} エラー詳細: {e}",
                file=sys.stderr,
            )
            sys.exit(1)

        try:
            raw_data = response.json()  # response.text から JSON データを直接取得します
        except ValueError:
            print("JSONデコードエラー", file=sys.stderr)
            sys.exit(1)

        forecast_areas = []
        for key, value in raw_data.items():
            for item in value:
                for amedas in item["amedas"]:
                    forecast_areas.append(
                        {
                            "id": amedas,
                            "class10_code": item["class10"],
                            "class20_code": item["class20"],
                        }
                    )

        df_amedas = pd.DataFrame(forecast_areas).set_index("id")
        df_amedas = df_amedas.merge(df_cities, left_on="class20_code", right_index=True)
        df_amedas.drop(
            ["class10_code", "class20_code", "jmaAreas2Id", "name"],
            axis=1,
            inplace=True,
        )
        dict_amedas = df_amedas.reset_index().to_dict("records")
        JmaAmedas.objects.all().delete()
        JmaAmedas.objects.bulk_create(
            [
                JmaAmedas(
                    id=item["id"],
                    jma_area3_id=item["jmaAreas3Id"],
                )
                for item in dict_amedas
            ]
        )

        self.stdout.write(
            self.style.SUCCESS("The master data update has been completed.")
        )
