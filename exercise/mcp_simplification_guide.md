# MCP 低级 API 简化写法指南

## 📊 四种方案对比

| 方案 | 代码行数 | 简洁度 | 可读性 | 推荐指数 |
|------|---------|--------|--------|----------|
| **方案 1**: 标准写法 | 41 行 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **方案 2**: 短变量名 | 37 行 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **方案 3**: 辅助函数 | 40 行 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **方案 4**: FastMCP | 13 行 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

---

## 方案 1: 标准写法（已应用）

**适用场景**: 需要清晰的代码结构，团队协作

```python
async def main():
    # ✅ 标准写法：清晰明了
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
```

**优点**:
- ✅ 代码意图清晰
- ✅ 变量名见名知意
- ✅ 适合团队协作

**缺点**:
- ❌ 代码略显冗长
- ❌ 需要多行书写

---

## 方案 2: 短变量名

**适用场景**: 个人项目，熟悉代码后

```python
async def main():
    # 🎯 简化变量名
    async with stdio_server() as (r, w):
        await server.run(r, w, server.create_initialization_options())
```

**优点**:
- ✅ 代码更紧凑
- ✅ 仍然保持可读性
- ✅ 一行搞定

**缺点**:
- ❌ `r`, `w` 不如全拼直观
- ❌ 新手可能需要思考

**文件**: `lower_server_simple.py`

---

## 方案 3: 辅助函数（推荐！）

**适用场景**: 经常使用低级 API，希望代码优雅

```python
# 🎯 定义辅助函数
async def run_server(server: Server):
    """运行低级 MCP 服务器的简化函数"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

# 使用时超级简单
if __name__ == "__main__":
    asyncio.run(run_server(server))
```

**优点**:
- ✅ main() 函数极简
- ✅ 复杂逻辑封装在辅助函数中
- ✅ 可复用，多个项目共用
- ✅ 保持完整变量名，可读性好

**缺点**:
- ❌ 需要额外定义辅助函数
- ❌ 多了一层抽象

**文件**: `lower_server_helper.py`

---

## 方案 4: FastMCP（最简单！）

**适用场景**: 快速开发，不需要低级 API 的特殊功能

```python
from fastmcp import FastMCP

mcp = FastMCP("lower_server")

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b

if __name__ == "__main__":
    mcp.run()
```

**优点**:
- ✅ 代码最少（13 行 vs 41 行）
- ✅ 类型提示自动生成
- ✅ 支持 `mcp dev` 工具
- ✅ 最易维护

**缺点**:
- ❌ 不再是低级 API
- ❌ 灵活性较低
- ❌ 无法精细控制

**文件**: `fastmcp_version.py`

---

## 🎯 推荐选择指南

### 选择方案 1（标准写法），如果：
- ✅ 团队协作项目
- ✅ 需要清晰的代码注释
- ✅ 新手学习低级 API
- ✅ 未来可能需要扩展功能

### 选择方案 2（短变量名），如果：
- ✅ 个人项目
- ✅ 已经熟悉低级 API
- ✅ 追求代码简洁
- ✅ 不想引入额外抽象

### 选择方案 3（辅助函数），如果：
- ✅ **强烈推荐！**
- ✅ 经常使用低级 API
- ✅ 希望代码优雅且可读
- ✅ 想要复用代码
- ✅ 既想简单又想保持低级 API 的灵活性

### 选择方案 4（FastMCP），如果：
- ✅ 快速原型开发
- ✅ 不需要低级 API 特殊功能
- ✅ 想使用 `mcp dev` 工具
- ✅ 简单工具定义

---

## 📝 完整示例对比

### 低级 API（方案 3 - 辅助函数版）

```python
import asyncio
from mcp.server.lowlevel.server import Server
from mcp.types import TextContent, Tool
from mcp.server.stdio import stdio_server

async def run_server(server: Server):
    """运行低级 MCP 服务器的简化函数"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

server = Server("lower_server")

@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="add",
            description="add two numbers",
            inputSchema={
                "type": "object",
                "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
                "required": ["a", "b"],
            },
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "add":
        return [TextContent(type="text", text=str(arguments["a"] + arguments["b"]))]

if __name__ == "__main__":
    asyncio.run(run_server(server))  # 👈 只需一行！
```

### FastMCP

```python
from fastmcp import FastMCP

mcp = FastMCP("lower_server")

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b

if __name__ == "__main__":
    mcp.run()  # 👈 只需一行！
```

---

## 🚀 进阶技巧：可复用的辅助模块

创建一个 `mcp_helper.py` 文件：

```python
# mcp_helper.py
from mcp.server.lowlevel.server import Server
from mcp.server.stdio import stdio_server

async def run_server(server: Server):
    """运行低级 MCP 服务器的简化函数"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
```

然后在所有项目中使用：

```python
# your_server.py
import asyncio
from mcp.server.lowlevel.server import Server
from mcp_helper import run_server  # 导入辅助函数

server = Server("my_server")

# ... 定义工具 ...

if __name__ == "__main__":
    asyncio.run(run_server(server))
```

---

## 总结

| 需求 | 推荐方案 |
|------|----------|
| **最简单** | FastMCP |
| **最优雅的低级 API** | 方案 3（辅助函数） |
| **最简洁的低级 API** | 方案 2（短变量名） |
| **团队协作** | 方案 1（标准写法） |

**个人建议**：
- 学习阶段 → 方案 1（标准写法）
- 熟悉后 → 方案 3（辅助函数）
- 生产环境 → 根据需求选择方案 3 或方案 4
