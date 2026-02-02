#!/usr/bin/env python3
'''
MCP Server for Weather Forecast.

This server provides tools to query weather forecasts using Open-Meteo API,
supporting queries for specific cities and future dates.
'''

from typing import Dict, Any
from enum import Enum
import httpx
from pydantic import BaseModel, Field, field_validator, ConfigDict
from mcp.server.fastmcp import FastMCP
from datetime import datetime, timedelta

# Initialize the MCP server
mcp = FastMCP("weather_mcp")

# Constants
OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1"
GEOCODING_API = "https://geocoding-api.open-meteo.com/v1"

# Enums
class ResponseFormat(str, Enum):
    '''Output format for tool responses.'''
    MARKDOWN = "markdown"
    JSON = "json"

# Pydantic Models for Input Validation
class WeatherQueryInput(BaseModel):
    '''Input model for weather forecast queries.'''
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    city: str = Field(
        ...,
        description="City name (e.g., '北京', '上海', 'New York', 'London')",
        min_length=1,
        max_length=100
    )
    days_later: int = Field(
        ...,
        description="Number of days in the future to query (e.g., 1 for tomorrow, 2 for day after tomorrow)",
        ge=0,
        le=16
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )

    @field_validator('city')
    @classmethod
    def validate_city(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("City name cannot be empty")
        return v.strip()

class WeekdayQueryInput(BaseModel):
    '''Input model for weekday-based weather queries.'''
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    city: str = Field(
        ...,
        description="City name (e.g., '北京', '上海', 'New York', 'London')",
        min_length=1,
        max_length=100
    )
    target_weekday: str = Field(
        ...,
        description="Target weekday in English (e.g., 'Saturday', 'Sunday', 'Monday')",
        min_length=1,
        max_length=20
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )

    @field_validator('target_weekday')
    @classmethod
    def validate_weekday(cls, v: str) -> str:
        valid_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        v_lower = v.strip().lower()
        if v_lower not in valid_days:
            raise ValueError(f"Invalid weekday. Must be one of: {', '.join(valid_days)}")
        return v.strip()

# Shared utility functions
async def _get_city_coordinates(city: str) -> Dict[str, float]:
    '''Get latitude and longitude for a city using geocoding API.'''
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{GEOCODING_API}/search",
                params={"name": city, "count": 1, "language": "zh", "format": "json"},
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()

            if not data.get("results"):
                raise ValueError(f"City '{city}' not found. Please check the city name.")

            result = data["results"][0]
            return {"latitude": result["latitude"], "longitude": result["longitude"],
                   "name": result.get("name", city), "country": result.get("country", "")}
        except httpx.HTTPStatusError as e:
            raise ValueError(f"Geocoding API error: {e.response.status_code}")
        except Exception as e:
            raise ValueError(f"Failed to get city coordinates: {str(e)}")

def _handle_api_error(e: Exception) -> str:
    '''Consistent error formatting across all tools.'''
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code == 404:
            return "Error: Weather data not found. Please check the location and try again."
        elif e.response.status_code == 429:
            return "Error: Rate limit exceeded. Please wait before making more requests."
        return f"Error: API request failed with status {e.response.status_code}"
    elif isinstance(e, httpx.TimeoutException):
        return "Error: Request timed out. Please try again."
    return f"Error: {str(e)}"

def _format_weather_markdown(data: Dict[str, Any], city_info: Dict[str, str], target_date: str) -> str:
    '''Format weather data as human-readable markdown.'''
    daily = data.get("daily", {})

    # Find the index for the target date
    dates = daily.get("time", [])
    try:
        date_index = dates.index(target_date)
    except ValueError:
        return f"Error: Weather data not available for {target_date}"

    lines = [
        f"# 天气预报 - {city_info['name']}",
        "",
        f"**日期**: {target_date}",
        f"**位置**: {city_info['name']}, {city_info['country']}",
        "",
        "## 天气概况",
        ""
    ]

    # Weather codes description
    weather_code = daily.get("weathercode", [])[date_index]
    weather_desc = _get_weather_description(weather_code)
    lines.append(f"- **天气状况**: {weather_desc}")

    # Temperature
    if daily.get("temperature_2m_max"):
        temp_max = daily["temperature_2m_max"][date_index]
        temp_min = daily["temperature_2m_min"][date_index]
        lines.append(f"- **温度**: {temp_min:.1f}°C ~ {temp_max:.1f}°C")

    # Apparent temperature
    if daily.get("apparent_temperature_max"):
        app_temp_max = daily["apparent_temperature_max"][date_index]
        app_temp_min = daily["apparent_temperature_min"][date_index]
        lines.append(f"- **体感温度**: {app_temp_min:.1f}°C ~ {app_temp_max:.1f}°C")

    # Precipitation
    if daily.get("precipitation_sum"):
        precip = daily["precipitation_sum"][date_index]
        lines.append(f"- **降水量**: {precip:.1f} mm")

    # Precipitation probability
    if daily.get("precipitation_probability_max"):
        precip_prob = daily["precipitation_probability_max"][date_index]
        lines.append(f"- **降水概率**: {precip_prob:.0f}%")

    # Wind
    if daily.get("windspeed_10m_max"):
        wind = daily["windspeed_10m_max"][date_index]
        lines.append(f"- **风速**: {wind:.1f} km/h")

    # Humidity
    if daily.get("relative_humidity_2m_max"):
        humidity_max = daily["relative_humidity_2m_max"][date_index]
        humidity_min = daily["relative_humidity_2m_min"][date_index]
        lines.append(f"- **湿度**: {humidity_min:.0f}% ~ {humidity_max:.0f}%")

    # UV Index
    if daily.get("uv_index_max"):
        uv = daily["uv_index_max"][date_index]
        uv_desc = _get_uv_description(uv)
        lines.append(f"- **紫外线指数**: {uv:.1f} ({uv_desc})")

    # Sunrise/Sunset
    if daily.get("sunrise") and daily.get("sunset"):
        sunrise = daily["sunrise"][date_index].split('T')[1]
        sunset = daily["sunset"][date_index].split('T')[1]
        lines.append(f"- **日出**: {sunrise}")
        lines.append(f"- **日落**: {sunset}")

    lines.append("")
    lines.append("---")
    lines.append("*数据来源: Open-Meteo API*")

    return "\n".join(lines)

def _format_weather_json(data: Dict[str, Any], city_info: Dict[str, str], target_date: str) -> str:
    '''Format weather data as JSON.'''
    import json

    daily = data.get("daily", {})
    dates = daily.get("time", [])

    try:
        date_index = dates.index(target_date)
    except ValueError:
        return json.dumps({"error": f"Weather data not available for {target_date}"}, indent=2)

    result = {
        "city": city_info["name"],
        "country": city_info["country"],
        "date": target_date,
        "latitude": city_info["latitude"],
        "longitude": city_info["longitude"],
        "weather": {}
    }

    # Extract all available daily data
    for key, values in daily.items():
        if date_index < len(values):
            result["weather"][key] = values[date_index]

    return json.dumps(result, indent=2)

def _get_weather_description(code: int) -> str:
    '''Get weather description from WMO weather code.'''
    weather_codes = {
        0: "晴朗",
        1: "大部分晴朗",
        2: "部分多云",
        3: "阴天",
        45: "雾",
        48: "雾凇",
        51: "毛毛雨（轻度）",
        53: "毛毛雨（中度）",
        55: "毛毛雨（重度）",
        61: "小雨",
        63: "中雨",
        65: "大雨",
        71: "小雪",
        73: "中雪",
        75: "大雪",
        77: "雪粒",
        80: "阵雨（轻度）",
        81: "阵雨（中度）",
        82: "阵雨（重度）",
        85: "小阵雪",
        86: "大阵雪",
        95: "雷暴",
        96: "雷暴伴冰雹（轻度）",
        99: "雷暴伴冰雹（重度）"
    }
    return weather_codes.get(code, f"未知天气状况 (代码: {code})")

def _get_uv_description(uv_index: float) -> str:
    '''Get UV index description.'''
    if uv_index <= 2:
        return "低"
    elif uv_index <= 5:
        return "中等"
    elif uv_index <= 7:
        return "高"
    elif uv_index <= 10:
        return "很高"
    else:
        return "极高"

async def _fetch_weather_data(latitude: float, longitude: float, start_date: str, end_date: str) -> Dict[str, Any]:
    '''Fetch weather data from Open-Meteo API.'''
    async with httpx.AsyncClient() as client:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": "weathercode,temperature_2m_max,temperature_2m_min,apparent_temperature_max,apparent_temperature_min,precipitation_sum,precipitation_probability_max,windspeed_10m_max,relative_humidity_2m_max,relative_humidity_2m_min,uv_index_max,sunrise,sunset",
            "timezone": "auto",
            "start_date": start_date,
            "end_date": end_date
        }

        response = await client.get(
            f"{OPEN_METEO_BASE_URL}/forecast",
            params=params,
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()

# Tool definitions
@mcp.tool(
    name="weather_query_by_days",
    annotations={
        "title": "查询指定天数后的天气",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def weather_query_by_days(params: WeatherQueryInput) -> str:
    '''查询指定城市在指定天数后的天气情况。

    这个工具可以查询未来16天内任意一天的天气预报，包括温度、降水、风力等信息。

    Args:
        params (WeatherQueryInput): 已验证的输入参数，包含:
            - city (str): 城市名称（例如：'北京', '上海', 'New York', 'London'）
            - days_later (int): 未来的天数（0=今天, 1=明天, 2=后天, 范围：0-16）
            - response_format (ResponseFormat): 输出格式，默认为markdown

    Returns:
        str: 格式化的天气信息

        成功响应包含：
        - 天气状况（晴朗、多云、雨等）
        - 温度范围（最低/最高温度）
        - 体感温度
        - 降水量和降水概率
        - 风速
        - 湿度
        - 紫外线指数
        - 日出日落时间

        错误响应：
        "Error: <错误信息>"

    Examples:
        - 查询明天的天气: city="北京", days_later=1
        - 查询后天的天气: city="上海", days_later=2
        - 查询7天后的天气: city="New York", days_later=7

    Error Handling:
        - 如果城市名称无效，返回城市未找到错误
        - 如果天数超出范围（0-16），返回验证错误
        - 如果API请求失败，返回相应的错误信息
    '''
    try:
        # Get city coordinates
        city_info = await _get_city_coordinates(params.city)

        # Calculate target date
        target_date = (datetime.now() + timedelta(days=params.days_later)).strftime("%Y-%m-%d")

        # Fetch weather data (get a range to ensure we include the target date)
        start_date = (datetime.now() + timedelta(days=params.days_later)).strftime("%Y-%m-%d")
        end_date = start_date

        weather_data = await _fetch_weather_data(
            city_info["latitude"],
            city_info["longitude"],
            start_date,
            end_date
        )

        # Format response
        if params.response_format == ResponseFormat.MARKDOWN:
            return _format_weather_markdown(weather_data, city_info, target_date)
        else:
            return _format_weather_json(weather_data, city_info, target_date)

    except Exception as e:
        return _handle_api_error(e)

@mcp.tool(
    name="weather_query_by_weekday",
    annotations={
        "title": "查询指定星期几的天气",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def weather_query_by_weekday(params: WeekdayQueryInput) -> str:
    '''查询指定城市在下一个指定星期几的天气情况。

    这个工具可以查询下一个指定星期几（如本周六、本周日）的天气预报。

    Args:
        params (WeekdayQueryInput): 已验证的输入参数，包含:
            - city (str): 城市名称（例如：'北京', '上海', 'New York'）
            - target_weekday (str): 目标星期几（例如：'Saturday', 'Sunday', 'Monday'）
            - response_format (ResponseFormat): 输出格式，默认为markdown

    Returns:
        str: 格式化的天气信息，包含与weather_query_by_days相同的详细信息

    Examples:
        - 查询本周六的天气: city="北京", target_weekday="Saturday"
        - 查询本周日的天气: city="上海", target_weekday="Sunday"
        - 查询下周一的天气: city="Guangzhou", target_weekday="Monday"

    Error Handling:
        - 如果城市名称或星期几无效，返回相应的验证错误
        - 如果API请求失败，返回相应的错误信息
    '''
    try:
        # Get city coordinates
        city_info = await _get_city_coordinates(params.city)

        # Find the next occurrence of the target weekday
        target_weekday_lower = params.target_weekday.lower()
        weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        target_index = weekdays.index(target_weekday_lower)

        today = datetime.now()
        current_weekday = today.weekday()  # Monday=0, Sunday=6

        # Calculate days to add
        days_until_target = (target_index - current_weekday) % 7
        if days_until_target == 0:
            # If today is the target day, check if we want today or next week
            # For simplicity, we'll use next week's occurrence if today is the target
            days_until_target = 7

        target_date = (today + timedelta(days=days_until_target)).strftime("%Y-%m-%d")

        # Fetch weather data
        weather_data = await _fetch_weather_data(
            city_info["latitude"],
            city_info["longitude"],
            target_date,
            target_date
        )

        # Format response
        if params.response_format == ResponseFormat.MARKDOWN:
            return _format_weather_markdown(weather_data, city_info, target_date)
        else:
            return _format_weather_json(weather_data, city_info, target_date)

    except Exception as e:
        return _handle_api_error(e)

if __name__ == "__main__":
    mcp.run(transport="stdio")
