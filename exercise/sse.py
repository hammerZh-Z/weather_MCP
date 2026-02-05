# sse_server.py
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import time

app = FastAPI()

@app.get("/sse")
def sse():
    def gen():
        for ch in "Hello MCP":
            yield f"data: {ch}\n\n"
            time.sleep(0.5)

    return StreamingResponse(gen(), media_type="text/event-stream")
