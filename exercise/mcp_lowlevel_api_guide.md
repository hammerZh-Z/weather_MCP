# MCP 低级 API 完全指南：从创建到配置 Cherry Studio(附快速调试MCP函数方法)

## 目录
- [什么是 MCP 低级 API](#什么是-mcp-低级-api)
- [创建第一个低级 MCP 服务器](#创建第一个低级-mcp-服务器)
  - [深入理解 read_stream 和 write_stream](#深入理解-read_stream-和-write_stream)
- [常见错误与解决方案](#常见错误与解决方案)
- [使用 MCP Inspector 测试](#使用-mcp-inspector-测试)
- [在 Cherry Studio 中配置](#在-cherry-studio-中配置)
- [低级 API vs FastMCP](#低级-api-vs-fastmcp)

---


## 什么是 MCP 低级 API

MCP (Model Context Protocol) 提供了两套 API：
- **FastMCP**: 高级 API，简单易用，推荐新手使用
- **Low-level Server**: 低级 API，更灵活，适合需要精细控制的场景

**低级 API 的优势：**
- 更精细的控制能力
- 更好的性能优化空间
- 可以处理复杂的业务逻辑

**低级 API 的劣势：**
- 需要手动管理更多细节
- `mcp dev` 工具不支持（仅支持 FastMCP）
- 代码相对复杂

---

![MCP服务示意图](https://coze-hotel-1257853985.cos.ap-guangzhou.myqcloud.com/wx_articles/20260204/mcp%E7%A4%BA%E6%84%8F%E5%9B%BE.avif)

## 创建第一个低级 MCP 服务器

### 完整代码示例

```python
import asyncio
from mcp.server.lowlevel.server import Server
from mcp.types import TextContent, Tool
from mcp.server.stdio import stdio_server

# 创建服务器实例
server = Server(name="lower_server")

# 定义工具列表
@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="add",
            description="add two numbers",
            inputSchema={
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
                "required": ["a", "b"],
            },
        )
    ]

# 定义工具调用处理
@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "add":
        return [TextContent(
            type="text",  # ⚠️ 重要：必须指定 type 字段
            text=str(arguments["a"] + arguments["b"])
        )]

# 主函数
async def main():
    # 低级 API 的正确用法
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())
```

### 关键点解析

#### 1. 导入正确的模块
```python
from mcp.server.lowlevel.server import Server  # 低级 API
from mcp.server.stdio import stdio_server       # STDIO 传输
from mcp.types import TextContent, Tool        # 类型定义
```

#### 2. stdio_server 的正确用法
```python
# ❌ 错误写法
async with stdio_server(server):
    await asyncio.Event().wait()

# ✅ 正确写法
async with stdio_server() as (read_stream, write_stream):
    await server.run(read_stream, write_stream, server.create_initialization_options())
```

**为什么？** `stdio_server()` 是一个异步上下文管理器，它会：
1. 创建 STDIO 输入输出流
2. 返回 `(read_stream, write_stream)` 元组
3. 需要将这些流传给 `server.run()`

#### 3. 深入理解 read_stream 和 write_stream

很多初学者会困惑：**"这两个变量是从哪里冒出来的？"**

让我们深入解析这个过程：

##### 📖 read_stream 和 write_stream 的来源

`stdio_server()` 是一个**异步上下文管理器**（使用 `@asynccontextmanager` 装饰器），它的工作原理如下：

```python
async def stdio_server(...):
    """简化版源码"""

    # 1️⃣ 创建内存流对象
    read_stream_writer, read_stream = anyio.create_memory_object_stream(0)
    write_stream, write_stream_reader = anyio.create_memory_object_stream(0)

    # 2️⃣ 启动后台任务
    async def stdin_reader():
        """从 stdin 读取数据 → 写入 read_stream"""
        async for line in stdin:
            message = parse_json(line)
            await read_stream_writer.send(message)

    async def stdout_writer():
        """从 write_stream 读取数据 → 写入 stdout"""
        async for message in write_stream_reader:
            json_data = message.model_dump_json()
            await stdout.write(json_data + "\n")

    # 3️⃣ 启动后台读写任务
    async with anyio.create_task_group() as tg:
        tg.start_soon(stdin_reader)
        tg.start_soon(stdout_writer)

        # 4️⃣ 把流的"另一端"返回给你 ← 这就是"冒出来"的地方！
        yield read_stream, write_stream
```

##### 🎯 使用流程

```python
# 您的代码
async with stdio_server() as (read_stream, write_stream):
    #        ↑ 调用函数         ↑ 接收返回的两个值
    await server.run(read_stream, write_stream, ...)
```

这等价于：
```python
# 伪代码
result = stdio_server()
read_stream, write_stream = result  # Python 的解包语法
```

##### 🔄 数据流向图

```
┌─────────────────┐                    ┌──────────────────┐
│   Cherry Studio │                    │  您的 MCP 服务器  │
│   (MCP 客户端)   │                    │                  │
└────────┬────────┘                    └────────┬─────────┘
         │                                      │
         │  JSON-RPC 请求                       │
         │  {"method": "tools/call", ...}      │
         ├─────────────────────────────────────>│
         │                              read_stream
         │                              (接收请求的"耳朵")
         │                                      │
         │                        ┌────────────┴────────────┐
         │                        │  server.run() 处理逻辑  │
         │                        │  - 解析请求              │
         │                        │  - 调用工具              │
         │                        │  - 生成响应              │
         │                        └────────────┬────────────┘
         │                                      │
         │  JSON-RPC 响应                       │
         │  {"result": 12, ...}                │
         │<─────────────────────────────────────┤
         │                             write_stream
         │                             (发送响应的"嘴巴")
         │                                      │
```

**类比理解：**
- `read_stream` = 🎧 **耳朵**（听客户端说什么）
- `write_stream` = 🗣️ **嘴巴**（对客户端说什么）

##### 🤔 为什么要这样设计？

**问题：** 为什么不直接读写 `stdin` 和 `stdout`？

**答案：** `stdio_server()` 为我们处理了所有繁琐的细节：

1. **平台兼容性**：Windows 的 stdin/stdout 编码问题
2. **协议转换**：JSON-RPC 字符串 ↔ Python 对象
3. **异步处理**：非阻塞的读写操作
4. **错误处理**：自动处理连接断开等情况

您只需要关注**业务逻辑**，通信层完全由 `stdio_server()` 负责！

##### 📝 完整时序图

```
时间线 →

您的代码                      stdio_server()              server.run()
   │                              │                            │
   │  async with stdio_server()   │                            │
   ├────────────────────────────>│                            │
   │                              │  创建 read_stream          │
   │                              │  创建 write_stream         │
   │                              │  启动 stdin_reader 任务    │
   │                              │  启动 stdout_writer 任务   │
   │                              │                            │
   │  返回 (read_stream,          │                            │
   │         write_stream)        │                            │
   │<─────────────────────────────┤                            │
   │                              │                            │
   │  调用 server.run(            │                            │
   │    read_stream,              │                            │
   │    write_stream)             │                            │
   ├─────────────────────────────────────────────────────────>│
   │                              │                            │
   │                              │  后台任务持续运行:           │
   │                              │                            │
   │ Cherry Studio → stdin        │                            │
   │                              │ stdin_reader              │
   │                              │ → read_stream ───────────>│  server.run()
   │                              │                            │  读取并处理
   │                              │                            │
   │                              │                            │  write_stream
   │                              │ stdout_writer <───────────│  写入响应
   │                              │ → stdout                  │
   │                              │                            │
   │ stdout ← Cherry Studio       │                            │
```

##### ✨ 总结

`read_stream` 和 `write_stream` **不是凭空出现的**，而是经过了一个精心设计的过程：

1. **`stdio_server()` 创建**它们（内存流对象）
2. **通过 `yield` 返回**出来
3. **用 `as (...)` 接收**它们（Python 解包语法）
4. **传给 `server.run()`** 使用

这种设计的优雅之处：
- **繁琐的 stdin/stdout 处理** → `stdio_server()` 负责 ✅
- **业务逻辑处理** → 您的代码负责 ✅
- 两者通过**流对象**干净地分离 ✅

#### 4. TextContent 必须包含 type 字段
```python
# ❌ 错误写法
TextContent(text="result")

# ✅ 正确写法
TextContent(type="text", text="result")
```

---

## 常见错误与解决方案

### 错误 1: TypeError - 'async for' requires an object with __aiter__ method

**错误信息：**
```
TypeError: 'async for' requires an object with __aiter__ method, got Server
```

**原因：** 直接将 Server 对象传给 `stdio_server()`

**解决方案：**
```python
# 错误代码
async with stdio_server(server):  # ❌ stdio_server 不接受 server 参数
    await asyncio.Event().wait()

# 正确代码
async with stdio_server() as (read_stream, write_stream):  # ✅ 获取流对象
    await server.run(read_stream, write_stream, server.create_initialization_options())
```

### 错误 2: Pydantic Validation Error - Field required

**错误信息：**
```
1 validation error for TextContent
type
  Field required [type=missing, input_value={'text': '12'}, input_type=dict]
```

**原因：** `TextContent` 缺少必需的 `type` 字段

**解决方案：**
```python
# 错误代码
return [TextContent(text=str(arguments["a"] + arguments["b"]))]

# 正确代码
return [TextContent(type="text", text=str(arguments["a"] + arguments["b"]))]
```

### 错误 3: mcp dev 不支持低级 API

**错误信息：**
```
The server object is of type <class 'mcp.server.lowlevel.server.Server'>
(expecting <class 'mcp.server.fastmcp.server.FastMCP'>)
Note that only FastMCP server is supported.
```

**原因：** `mcp dev` 工具仅支持 FastMCP

**解决方案：** 使用 MCP Inspector 替代（见下节）

---

## 使用 MCP Inspector 测试

由于 `mcp dev` 不支持低级 API，我们使用 **MCP Inspector** 进行测试。

### 启动 Inspector

```bash
npx -y @modelcontextprotocol/inspector python exercise/lower_server.py
```

### Inspector 功能

启动后会自动：
1. 打开浏览器访问 `http://localhost:6274`
2. 加载您的 MCP 服务器
3. 显示可用的工具列表

### 测试工具调用

在 Inspector 界面中：
1. 查看可用工具（如 `add`）
2. 输入参数：`{"a": 5, "b": 7}`
3. 点击调用
4. 查看返回结果：`12`

**优点：**
- 支持低级 API
- 可视化界面
- 实时测试
- 自动重新加载

![测试页面](https://coze-hotel-1257853985.cos.ap-guangzhou.myqcloud.com/wx_articles/20260204/MCP%E8%B0%83%E8%AF%95%E6%88%AA%E5%9B%BE.png)

---

## 在 Cherry Studio 中配置

Cherry Studio 是一个支持 MCP 的 AI 客户端，可以轻松集成您的 MCP 服务器。

### 配置 JSON

```json
{
  "mcpServers": {
    "lower_server": {
      "command": "F:\\python学习资料\\3mcp\\first_own\\npx_weather\\.venv\\Scripts\\python.exe",
      "args": [
        "F:\\python学习资料\\3mcp\\first_own\\npx_weather\\exercise\\lower_server.py"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

### 配置步骤

1. **找到 Cherry Studio 配置文件**
   - Windows: `%APPDATA%\CherryStudio\mcp_config.json`
   - macOS: `~/Library/Application Support/CherryStudio/mcp_config.json`
   - Linux: `~/.config/CherryStudio/mcp_config.json`

2. **添加服务器配置**
   - 将上述 JSON 合并到配置文件中
   - 或在 Cherry Studio 设置界面中手动添加

3. **重启 Cherry Studio**

4. **验证配置**
   - 在 Cherry Studio 中查看 MCP 服务器列表
   - 应该能看到 `lower_server`
   - 可以在对话中调用 `add` 工具

### 配置字段说明

| 字段 | 说明 |
|------|------|
| `command` | Python 解释器完整路径 |
| `args` | 服务器脚本路径数组 |
| `env.PYTHONUNBUFFERED` | 禁用输出缓冲，实时显示日志 |

---

## 低级 API vs FastMCP

### 对比表

| 特性 | 低级 API | FastMCP |
|------|----------|---------|
| 易用性 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 灵活性 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| 性能优化空间 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| mcp dev 支持 | ❌ | ✅ |
| 代码复杂度 | 较高 | 较低 |
| 适用场景 | 复杂业务逻辑 | 快速开发 |

### FastMCP 示例

```python
from fastmcp import FastMCP

mcp = FastMCP("my_server")

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b

if __name__ == "__main__":
    mcp.run()
```

### 低级 API 示例

```python
from mcp.server.lowlevel.server import Server
from mcp.types import TextContent, Tool
from mcp.server.stdio import stdio_server
import asyncio

server = Server(name="my_server")

@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="add",
            description="Add two numbers",
            inputSchema={
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
                "required": ["a", "b"],
            },
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "add":
        return [TextContent(type="text", text=str(arguments["a"] + arguments["b"]))]

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
```

### 如何选择？

**选择 FastMCP，如果：**
- 快速开发原型
- 简单的工具定义
- 需要使用 `mcp dev` 工具
- 新手入门

**选择低级 API，如果：**
- 需要精细控制服务器行为
- 复杂的业务逻辑
- 性能要求高
- 需要自定义流处理

---

## 总结

本文介绍了：
1. ✅ MCP 低级 API 的基本概念
2. ✅ 创建低级 MCP 服务器的完整步骤
3. ✅ 常见错误及解决方案
4. ✅ 使用 MCP Inspector 测试服务器
5. ✅ 在 Cherry Studio 中集成配置
6. ✅ 低级 API 与 FastMCP 的对比

**下一步建议：**
- 尝试扩展 `add` 工具，添加更多功能
- 探索 `@server.list_resources()` 等其他装饰器
- 学习 MCP 的资源和提示(Prompt)功能
- 阅读官方文档了解更多高级特性

---

## 参考资源

- [MCP 官方文档](https://modelcontextprotocol.io)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Cherry Studio GitHub](https://github.com/kangfenmao/cherry-studio)
- [示例代码仓库](https://github.com/modelcontextprotocol/servers)

---

**作者备注：** 如有问题或建议，欢迎在评论区讨论！
