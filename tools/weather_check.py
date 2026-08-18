# 心知天气API工具类
import requests
from pydantic import Field
from configs.settings import TIME_OUT

class WeatherCheck:
    city: str = Field(description="City name,include city and county")

    def __init__(self, api_key):
        self.api_key = api_key

    def run(self, city):
        city = city.split('\n')[0]  # 清除多余的\n不然API会报错。
        url = f"https://api.seniverse.com/v3/weather/now.json?key={self.api_key}&location={city}&language=zh-Hans&unit=c"
        # 发送请求到心知天气API
        # print(url)
        response = requests.get(url, timeout=TIME_OUT)
        # print(response.status_code)
        # 如果请求成功，解析返回数据
        if response.status_code == 200:
            data = response.json()
            # 获取天气信息
            weather = data['results'][0]['now']['text']
            temperature = data['results'][0]['now']['temperature']
            return f"{city}的天气是{weather}，温度为{temperature}°C"
        else:
            return f"错误码: {response.status_code}, 无法获取{city}的天气信息"

weather_check = WeatherCheck("S1rGPZqLSGYCJZ8kS")
