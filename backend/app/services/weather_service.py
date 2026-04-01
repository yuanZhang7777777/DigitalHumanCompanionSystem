"""
天气查询服务模块
核心功能：
  1. 通过高德天气 API 获取城市天气预报
  2. 从用户消息中智能提取城市名
  3. 独立检测面试出行意图（任何场景下可触发）
  4. 降级策略：API 不可用时静默跳过，不影响正常对话
"""
import httpx
import re
import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


class WeatherService:
    """天气查询服务，封装高德天气 API"""

    # ── 支持的城市列表（省会 + 主要城市）──────────────────────────────────────
    SUPPORTED_CITIES = [
        # 直辖市
        "北京", "上海", "天津", "重庆",
        # 省会及主要城市
        "广州", "深圳", "杭州", "成都", "武汉", "南京", "西安", "苏州",
        "郑州", "长沙", "宁波", "青岛", "合肥", "无锡", "济南", "大连",
        "厦门", "福州", "昆明", "贵阳", "南宁", "海口", "三亚",
        "哈尔滨", "长春", "沈阳", "石家庄", "太原", "呼和浩特",
        "乌鲁木齐", "兰州", "西宁", "银川", "拉萨",
        "珠海", "东莞", "佛山", "中山", "惠州", "温州", "绍兴",
        "常州", "南通", "扬州", "徐州", "烟台", "潍坊", "泉州",
        "洛阳", "襄阳", "宜昌", "岳阳", "株洲", "秦皇岛", "唐山",
        # 新一线及热门城市
        "东莞", "佛山", "嘉兴", "金华", "台州", "威海", "湖州",
    ]

    # ── 面试出行关键词模式 ─────────────────────────────────────────────────
    _TRIP_PATTERN = re.compile(
        r"(明天|后天|下周|过两天|这周|周末|大后天)?"
        r".{0,6}"
        r"(去|到|飞|赶|出发去|动身去|前往)?"
        r".{0,4}"
        r"(面试|笔试|参加面试|复试|终面|现场面)"
    )

    def __init__(self):
        self.api_key = settings.amap_api_key
        self.weather_url = settings.amap_weather_url
        self.geocode_url = settings.amap_geocode_url

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
            logger.warning("高德天气 API Key 未配置，跳过天气查询")
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
                    forecast = data["forecasts"][0]["casts"][1]  # 获取明天的数据

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
                        f"【系统附加提醒：天气情报】\n"
                        f"用户即将前往{city_name}。根据高德天气预报，明天{city_name}白天天气为：{weather}，"
                        f"气温 {temp_night}\u2103 ~ {temp_day}\u2103"
                    )
                    if wind:
                        result += f"，{wind}风{wind_power}级"
                    result += f"。\n{suggestion}"
                    if clothing:
                        result += f" {clothing}"
                    result += "\n请在你的回复中自然地带入天气关怀，不要生硬地罗列数据。"
                    return result

        except Exception as e:
            logger.error(f"获取天气失败 (adcode: {adcode}): {str(e)}")
        return None

    def extract_city(self, text: str) -> Optional[str]:
        """
        从用户文本中提取目标城市
        支持多种表达：
          - "去北京面试" / "到上海参加面试"
          - "明天要去深圳" / "后天飞杭州面试"
          - "在广州有个面试"
        """
        # 模式1：去/到/飞 + 城市 + 面试相关
        cities_pattern = "|".join(self.SUPPORTED_CITIES)
        match = re.search(
            rf'(?:去|到|飞|赶|前往|出发去)\s*({cities_pattern})',
            text
        )
        if match:
            return match.group(1)

        # 模式2：在 + 城市 + 面试相关
        match = re.search(
            rf'在\s*({cities_pattern})\s*(?:面试|笔试|复试|终面|有个面|有面试)',
            text
        )
        if match:
            return match.group(1)

        # 模式3：城市 + 面试
        match = re.search(
            rf'({cities_pattern})\s*(?:的|那边|那里)?\s*(?:面试|笔试|复试)',
            text
        )
        if match:
            return match.group(1)

        return None

    def detect_interview_trip(self, message: str) -> bool:
        """
        独立检测用户消息中是否包含面试出行意图
        与场景检测解耦——即使不在 interview 场景下，也能触发天气查询
        """
        return bool(self._TRIP_PATTERN.search(message))
