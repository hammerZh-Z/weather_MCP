import asyncio
from mcp.server.lowlevel.server import Server
from mcp.types import TextContent, Tool
from mcp.server.stdio import stdio_server

# 🎯 辅助函数：让低级 API 像 FastMCP 一样简单
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
    # ✅ 现在超级简单了！
    asyncio.run(run_server(server))
