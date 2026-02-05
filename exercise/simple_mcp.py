from mcp.server.fastmcp import FastMCP

mcp = FastMCP("add")

@mcp.tool()
def add(a: int, b: int) -> int:
    return a + b

@mcp.tool()
def subtract(a: int, b: int) -> int:
    return a - b

if __name__ == "__main__":
    mcp.run(transport="stdio")