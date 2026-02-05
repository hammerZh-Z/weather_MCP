import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
import anyio
from bs4 import BeautifulSoup
from mcp.server.lowlevel.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import TextContent, Tool
import os
from openai import OpenAI
from starlette.applications import Starlette
from starlette.routing import Mount


DEFAULT_URL = "https://mp.weixin.qq.com/s/8KiDOoosF4cMyOOEltq28g"
DEFAULT_PROMPT_PATH = Path(__file__).parent / "解析被投资公司.prompt"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)
OPENAI_BASE_URL = "https://api.xiaomimimo.com/v1"
OPENAI_MODEL = "mimo-v2-flash"
SYSTEM_PROMPT = (
    "You are MiMo, an AI assistant developed by Xiaomi. "
    "Today is date: Tuesday, December 16, 2025. "
    "Your knowledge cutoff date is December 2024."
)


def load_default_prompt() -> str:
    return DEFAULT_PROMPT_PATH.read_text(encoding="utf-8").strip()


DEFAULT_PROMPT = load_default_prompt()

server = Server(name="wechat_article_mcp")


@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="parse_wechat_article",
            description="获取并解析微信公众号文章",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "解析用提示词（可选）"},
                    "url": {"type": "string", "description": "微信公众号文章链接（可选）"},
                },
                "required": [],
            },
        )
    ]


def _first_text(*values: str | None) -> str:
    for value in values:
        if value:
            return value.strip()
    return ""


async def _fetch_html(url: str) -> str:
    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=20.0) as client:
        response = await client.get(url)
        if response.status_code != 200:
            raise RuntimeError(f"Fetch failed with status {response.status_code}")
        return response.text


def _parse_wechat_html(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")

    title = _first_text(
        (soup.find("meta", property="og:title") or {}).get("content"),
        soup.select_one("#activity-name").get_text(strip=True) if soup.select_one("#activity-name") else None,
    )

    author = _first_text(
        (soup.find("meta", attrs={"name": "author"}) or {}).get("content"),
        soup.select_one("#js_author_name").get_text(strip=True) if soup.select_one("#js_author_name") else None,
    )

    publish_time = _first_text(
        (soup.find("meta", property="article:published_time") or {}).get("content"),
        soup.select_one("#publish_time").get_text(strip=True) if soup.select_one("#publish_time") else None,
    )

    content_node = soup.select_one("#js_content")
    content = content_node.get_text("\n", strip=True) if content_node else ""

    return {
        "title": title,
        "author": author,
        "publish_time": publish_time,
        "content": content,
        "content_length": len(content),
    }


def _extract_api_key() -> str:
    ctx = server.request_context
    request = ctx.request
    if request is None:
        raise RuntimeError("Missing request context for authorization")

    auth_header = request.headers.get("authorization")
    if not auth_header:
        env_key = os.environ.get("MIMO_API_KEY")
        if env_key:
            return env_key
        raise RuntimeError("Missing Authorization header and MIMO_API_KEY env")

    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return auth_header.strip()


def _run_openai(prompt: str, content: str, api_key: str) -> str:
    client = OpenAI(api_key=api_key, base_url=OPENAI_BASE_URL)
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"{prompt}\n\n---\n\n{content}"},
        ],
        max_completion_tokens=1024,
        temperature=0.3,
        top_p=0.95,
        stream=False,
        stop=None,
        frequency_penalty=0,
        presence_penalty=0,
        extra_body={"thinking": {"type": "disabled"}},
    )
    if response.choices and response.choices[0].message:
        return response.choices[0].message.content or ""
    return ""


async def _parse_with_openai(prompt: str, content: str, api_key: str) -> str:
    return await anyio.to_thread.run_sync(_run_openai, prompt, content, api_key)


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name != "parse_wechat_article":
        raise RuntimeError(f"Unknown tool: {name}")

    prompt = (arguments.get("prompt") or "").strip() or DEFAULT_PROMPT
    url = (arguments.get("url") or "").strip() or DEFAULT_URL

    html = await _fetch_html(url)
    parsed = _parse_wechat_html(html)
    api_key = _extract_api_key()
    parsed_result = await _parse_with_openai(prompt, parsed["content"], api_key)
    payload = {"prompt": prompt, "parsed_result": parsed_result}

    return [
        TextContent(
            type="text",
            text=json.dumps(payload, ensure_ascii=False),
        )
    ]


session_manager = StreamableHTTPSessionManager(server)


async def mcp_asgi(scope, receive, send):
    await session_manager.handle_request(scope, receive, send)


@asynccontextmanager
async def lifespan(_: Starlette):
    async with session_manager.run():
        yield


app = Starlette(routes=[Mount("/mcp", app=mcp_asgi)], lifespan=lifespan)


def main():
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8523)


if __name__ == "__main__":
    main()
