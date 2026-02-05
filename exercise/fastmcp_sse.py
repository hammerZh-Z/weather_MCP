from mcp.server.fastmcp import FastMCP

app = FastMCP("WeatherMCP")

@app.tool()
def get_weather(city: str) -> dict:
    # 这是一个简单固定返回，你可以改成请求真实天气
    return {"city": city, "temp": 25}

if __name__ == "__main__":
    # 启动 SSE transport
    app.run(transport="sse")
