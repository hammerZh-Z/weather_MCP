import asyncio
from mcp.server.lowlevel.server import Server
from mcp.types import TextContent, Tool
from mcp.server.stdio import stdio_server

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

async def main():
    # 🎯 最简洁写法
    async with stdio_server() as (r, w):
        await server.run(r, w, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
