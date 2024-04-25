import requests
from django.core.management.base import BaseCommand

WARNING_REGION_BASED = 0

M_TARGET_WARNINGS = {
    "03": "大雨警報",
    "24": "霜注意報",
    "10": "大雨注意報",
    "21": "乾燥注意報",
    "14": "雷注意報",
    "18": "洪水注意報",
    "20": "濃霧注意報",
    "15": "強風注意報",
    "16": "波浪注意報",
}


class RegionWarning:
    def __init__(self, region_code: str, data: dict):
        self.code = region_code
        self.data = data
        warning_target_codes = M_TARGET_WARNINGS.keys()
        self.warnings = [
            M_TARGET_WARNINGS[code]
            for code in self.get_warnings(data["warnings"], warning_target_codes)
        ]

    @staticmethod
    def get_warnings(warning_data, warning_target_codes):
        warnings = []
        try:
            for x in warning_data:
                if x["code"] in warning_target_codes:
                    warnings.append(x["code"])
        except KeyError:
            warnings = []
        return list(set(warnings))

    def __str__(self):
        return f"{self.code} の保持する警報は {self.warnings}"


class RegionWarningResults:
    def __init__(self, region_warnings: RegionWarning):
        self.warnings = region_warnings

    def __str__(self):
        region_code = self.warnings.code
        forecast = {"warnings": self.warnings.warnings}
        return f"{region_code}: {forecast}"


class Command(BaseCommand):
    help = "get weather warning"

    def handle(self, *args, **options):
        # TODO: facilityテーブルから areas2_ids を取得
        jma_areas2_ids = ["280000", "050000", "130000"]

        if not jma_areas2_ids:
            raise Exception("facility is empty")
        for prefecture_id in jma_areas2_ids:
            warnings_by_region = {}

            warnings = requests.get(
                f"https://www.jma.go.jp/bosai/warning/data/warning/{prefecture_id}.json"
            ).json()
            for a_region in warnings["areaTypes"][WARNING_REGION_BASED]["areas"]:
                region_code = a_region["code"]
                region_warning = RegionWarning(region_code, a_region)
                warnings_by_region.setdefault(region_code, {})[
                    "warnings"
                ] = region_warning

            for region_code, forecast in warnings_by_region.items():
                region_warning_results = RegionWarningResults(forecast["warnings"])
                print(region_warning_results)

            # TODO: dbに保存
            # JmaAmedas.objects.all().delete()
            # JmaAmedas.objects.bulk_create(
            #     [
            #         JmaAmedas(
            #             id=item["id"],
            #             jma_area3_id=item["jmaAreas3Id"],
            #         )
            #         for item in dict_amedas
            #     ]
            # )

        self.stdout.write(
            self.style.SUCCESS("weather warning data retrieve has been completed.")
        )
