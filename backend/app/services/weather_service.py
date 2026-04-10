"""
天气查询服务模块
使用高德地图 Web 开放接口获取天气（基于用户提供的 API Key）。
支持从聊天记录中自动抽取城市名称并进行天气和出行提示。
"""
import httpx
import re
import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

class WeatherService:
    """天气查询服务，封装高德天气 API"""

    def __init__(self):
        self.api_key = settings.amap_api_key
        self.weather_url = settings.amap_weather_url
        self.geocode_url = settings.amap_geocode_url

    def extract_city(self, text: str) -> Optional[str]:
        """
        从用户文本中提取目标城市
        """
        # 简单正则匹配：“XX天气”、“去XX”、“在XX”
        cities = ["北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "南京", "西安", "苏州", "长沙", "重庆", "天津", "青岛", "厦门"]
        for city in cities:
            if city in text:
                return city
        
        # 模糊匹配：(.*?)(天气|下雨|温度|大概几度|多热|冷吗)
        match = re.search(r'([\u4e00-\u9fa5]{2,4})(?:市|省)?(?:的)?(?:天气|气温|温度|下雨|冷吗|热吗)', text)
        if match:
            return match.group(1)
            
        return None

    async def get_city_adcode(self, city_name: str) -> Optional[str]:
        """通过高德地理编码获取城市 adcode"""
        if not self.api_key:
            return None

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                params = {
                    "key": self.api_key,
                    "address": city_name,
                    "output": "JSON"
                }
                response = await client.get(self.geocode_url, params=params)
                data = response.json()
                if data.get("status") == "1" and int(data.get("count", 0)) > 0:
                    return data["geocodes"][0]["adcode"]
        except Exception as e:
            logger.error(f"获取城市 adcode 失败 ({city_name}): {str(e)}")
        return None

    async def get_weather(self, city_name: str) -> Optional[str]:
        """获取目标城市天气并格式化为提示词片段"""
        if not self.api_key:
            logger.warning("高德天气 API Key 未配置，跳过高德天气查询")
            return None

        adcode = await self.get_city_adcode(city_name)
        if not adcode:
            logger.info(f"无法获取 {city_name} 的 adcode，跳过天气")
            return None

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # 获取预报天气（extensions=all）
                params = {
                    "key": self.api_key,
                    "city": adcode,
                    "extensions": "all",
                    "output": "JSON"
                }
                response = await client.get(self.weather_url, params=params)
                data = response.json()

                if data.get("status") == "1" and data.get("forecasts"):
                    forecast = data["forecasts"][0]["casts"][0]  # 获取当天或明天的数据

                    weather = forecast.get("dayweather", "未知")
                    temp_day = forecast.get("daytemp", "")
                    temp_night = forecast.get("nighttemp", "")
                    wind = forecast.get("daywind", "")
                    wind_power = forecast.get("daypower", "")

                    # 生成穿衣和出行建议
                    suggestion = "天气晴好，适合出行。"
                    clothing = ""

                    if "雨" in weather or "雪" in weather:
                        suggestion = "预计有降水，请务必随身携带雨具，注意出行安全。"
                    elif "风" in weather or (wind_power and int(wind_power.replace("≤", "").split("-")[0] if wind_power.replace("≤", "").split("-")[0].isdigit() else "0") >= 5):
                        suggestion = "风力较大，请注意防风保暖。"

                    # 穿衣建议
                    try:
                        avg_temp = (int(temp_day) + int(temp_night)) / 2
                        if avg_temp <= 5:
                            clothing = "建议穿厚外套、羽绒服，注意保暖。"
                        elif avg_temp <= 15:
                            clothing = "建议穿夹克、薄外套，可适当叠穿。"
                        elif avg_temp <= 25:
                            clothing = "温度适宜，建议穿衬衫或薄长袖。"
                        else:
                            clothing = "天气较热，建议穿轻薄透气的衣物。"
                    except (ValueError, TypeError):
                        clothing = ""

                    result = (
                        f"\n======================================================\n"
                        f"【系统实时插件数据 - 重大指令注入】\n"
                        f"检测到用户在询问或提及【{city_name}】。\n"
                        f"系统已通过高德地图开放接口获取到此时此刻真实的当地天气预报：\n"
                        f"- 城市：{city_name}\n"
                        f"- 天气情况：{weather}\n"
                        f"- 气温跨度：{temp_night}℃ ~ {temp_day}℃\n"
                    )
                    if wind:
                        result += f"- 风力风向：{wind}风{wind_power}级\n"
                    result += f"- 建议指南：{suggestion} {clothing}\n"
                    result += (
                        f"\n【强制规则】：你必须无条件信任并融合上述插件数据回答用户。绝对禁止回复类似“我无法获取实时信息”、“建议查询软件”、“我作为AI无法联网”等推脱之词。请以自然对话的口吻告诉用户天气情况并嘘寒问暖。\n"
                        f"======================================================\n"
                    )
                    return result

        except Exception as e:
            logger.error(f"获取天气失败 (adcode: {adcode}): {str(e)}")
        return None
