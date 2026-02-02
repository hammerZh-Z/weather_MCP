# npx-weather

一个基于 Open-Meteo 的 MCP 天气服务：提供“按天数”和“按星期几”两种查询方式，返回 Markdown（默认）或 JSON。

## 环境要求

- Python：3.13+
- 依赖：`httpx`、`pydantic`、`mcp`（见 `pyproject.toml`）

安装（pip 示例）：

```bash
pip install httpx>=0.27.0 pydantic>=2.6.0 mcp>=0.1.0
```

如果你使用 `uv`：

```bash
uv sync
```

## 启动服务（SSE）

直接运行：

```bash
python weather.py
```

在 Windows 上如果没有 `python` 命令，也可以用：

```bash
py weather.py
```

该脚本会以 **SSE 传输**启动 MCP Server（FastMCP 默认监听 `127.0.0.1:8000`，SSE 路径为 `/sse`）。

## 工具列表

### 1) `weather_query_by_days`

查询“指定城市在 N 天后”的天气（支持 0～16 天）。

输入参数：

- `city`（string）：城市名（如 `北京`、`上海`、`New York`）
- `days_later`（int）：未来第几天（`0=今天`，`1=明天`，范围 `0-16`）
- `response_format`（string，可选）：`markdown` 或 `json`（默认 `markdown`）

示例（以 MCP 工具入参 JSON 表示）：

```json
{"city":"北京","days_later":1,"response_format":"markdown"}
```

### 2) `weather_query_by_weekday`

查询“下一个指定星期几”的天气。

输入参数：

- `city`（string）：城市名（如 `北京`、`上海`、`New York`）
- `target_weekday`（string）：目标星期（英文，大小写不敏感）：`Monday`/`Tuesday`/`Wednesday`/`Thursday`/`Friday`/`Saturday`/`Sunday`
- `response_format`（string，可选）：`markdown` 或 `json`（默认 `markdown`）

说明：

- 如果今天刚好是 `target_weekday`，为了避免歧义，本工具会查询“下周同一天”（即 +7 天）。

示例：

```json
{"city":"上海","target_weekday":"Saturday","response_format":"json"}
```

## 返回内容

### Markdown（默认）

包含（如有数据）：

- 天气状况（WMO code 映射的中文描述）
- 最高/最低温、最高/最低体感温
- 降水量、最大降水概率
- 最大风速
- 最大/最小湿度
- 最大紫外线指数（含等级：低/中等/高/很高/极高）
- 日出/日落时间

### JSON

工具会返回一个 JSON 字符串，结构类似：

- 顶层：`city`、`country`、`date`、`latitude`、`longitude`
- `weather`：包含 Open-Meteo `daily` 下的各字段在目标日期对应的值（例如 `weathercode`、`temperature_2m_max`、`precipitation_sum`、`sunrise`、`sunset` 等）

## MCP 服务配置

本服务支持 **SSE (Server-Sent Events)** 传输方式，可以远程托管部署。

### 快速启动配置

**方式 1：使用 Python 直接运行**

```json
{
  "command": "python",
  "args": ["weather.py"],
  "env": {}
}
```

**方式 2：使用 uv 运行（推荐）**

```json
{
  "command": "uv",
  "args": ["--directory", "/path/to/npx_weather", "run", "python", "weather.py"],
  "env": {}
}
```

**方式 3：使用 Windows 的 py 命令**

```json
{
  "command": "py",
  "args": ["weather.py"],
  "env": {}
}
```

### 配置说明

- **传输方式**：SSE (Server-Sent Events)
- **默认监听地址**：`127.0.0.1:8000`
- **SSE 路径**：`/sse`
- **环境变量**：无需额外环境变量配置
- **托管类型**：可托管部署（不依赖本地资源）
- **网络要求**：需要能访问 Open-Meteo API (`api.open-meteo.com` 和 `geocoding-api.open-meteo.com`)

### Claude Desktop 配置示例

在 Claude Desktop 的配置文件中添加：

```json
{
  "mcpServers": {
    "weather": {
        "type": "sse",
        "url": "http://127.0.0.1:8000/sse"
    }
  }
}
```

## 备注与限制

- 预报范围：Open-Meteo 日级预报限制为 `0-16` 天。
- 城市解析：先通过 Open-Meteo Geocoding 获取经纬度，再拉取预报（需要可访问外网）。
- 错误返回：出错时返回以 `Error:` 开头的字符串（例如城市不存在、参数校验失败、请求超时/限流等）。
- 托管部署：本服务不依赖本地资源，适合在 ModelScope 平台进行远程托管部署。
