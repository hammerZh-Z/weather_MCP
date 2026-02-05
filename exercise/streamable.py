# stream_http_server.py
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import time

app = FastAPI()

@app.post("/stream")
async def stream(data: dict):
    text = data.get("text", "Hello MCP")

    def gen():
        for ch in text:
            yield ch
            time.sleep(0.5)

    return StreamingResponse(gen(), media_type="text/plain")
