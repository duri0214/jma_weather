from django.db import models


class JmaAreas1(models.Model):
    """地方区分。生データでは center という名前で取り扱われている"""

    id = models.CharField(primary_key=True, max_length=6)
    name = models.CharField(max_length=100)


class JmaAreas2(models.Model):
    """都道府県。生データでは office という名前で取り扱われている"""

    id = models.CharField(primary_key=True, max_length=6)
    jma_area1 = models.ForeignKey(JmaAreas1, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)


class JmaAreas3(models.Model):
    """リージョン。生データでは class10 という名前で取り扱われている"""

    id = models.CharField(primary_key=True, max_length=6)
    jma_area2 = models.ForeignKey(JmaAreas2, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)


class JmaAreas4(models.Model):
    """市区町村。生データでは class20 という名前で取り扱われている"""

    id = models.CharField(primary_key=True, max_length=7)
    jma_area2 = models.ForeignKey(JmaAreas2, on_delete=models.CASCADE)
    jma_area3 = models.ForeignKey(JmaAreas3, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)


class JmaAmedas(models.Model):
    """気象観測所。生データでは amedas という名前で取り扱われている"""

    id = models.CharField(primary_key=True, max_length=5)
    jma_area3 = models.ForeignKey(JmaAreas3, on_delete=models.CASCADE)


class JmaWeather(models.Model):
    jma_areas3 = models.OneToOneField(
        JmaAreas3, primary_key=True, on_delete=models.CASCADE
    )
    weather_code = models.CharField(max_length=3)
    temperature_min = models.FloatField()
    temperature_max = models.FloatField()
    wind_speed = models.FloatField()


class JmaWarning(models.Model):
    jma_areas3 = models.OneToOneField(
        JmaAreas3, primary_key=True, on_delete=models.CASCADE
    )
    warnings = models.CharField(max_length=100)
