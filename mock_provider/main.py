import asyncio

from fastapi import FastAPI

app = FastAPI(title="Mock LLM Provider")


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.post("/v1/chat/completions")
async def chat_completions(payload: dict):
    delay_ms = payload.get("mock_delay_ms", 0)

    try:
        delay_ms = float(delay_ms)
    except (TypeError, ValueError):
        delay_ms = 0

    delay_ms = max(0, min(delay_ms, 30_000))

    if delay_ms:
        await asyncio.sleep(delay_ms / 1000)

    messages = payload.get("messages", [])

    last_user_message = ""

    for message in reversed(messages):
        if message.get("role") == "user":
            last_user_message = str(message.get("content", ""))
            break

    reply = f"Mock reply: {last_user_message}"

    return {
        "id": "mock-chat-completion",
        "object": "chat.completion",
        "model": payload.get("model", "mock-model"),
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": reply,
                },
                "finish_reason": "stop",
            }
        ],
    }
