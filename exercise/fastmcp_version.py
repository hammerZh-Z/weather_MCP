from fastmcp import FastMCP

# 🚀 FastMCP 版本 - 代码最少！
mcp = FastMCP("lower_server")

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b

if __name__ == "__main__":
    # ✅ 只需一行！
    mcp.run()
