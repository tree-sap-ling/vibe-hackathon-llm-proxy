import asyncio
import json

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI(title="Mock LLM Provider")


def get_delay_ms(payload, key, default=0):
    value = payload.get(key, default)

    try:
        value = float(value)
    except (TypeError, ValueError):
        value = default

    return max(0, min(value, 30_000))


def get_last_user_message(messages):
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content", ""))

    return ""


async def stream_chat_completion(
    reply,
    model,
    first_chunk_delay_ms,
    chunk_delay_ms,
):
    if first_chunk_delay_ms:
        await asyncio.sleep(first_chunk_delay_ms / 1000)

    words = reply.split()

    for index, word in enumerate(words):
        content = word

        if index < len(words) - 1:
            content += " "

        chunk = {
            "id": "mock-chat-completion",
            "object": "chat.completion.chunk",
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "content": content,
                    },
                    "finish_reason": None,
                }
            ],
        }

        yield f"data: {json.dumps(chunk)}\n\n"

        if chunk_delay_ms and index < len(words) - 1:
            await asyncio.sleep(chunk_delay_ms / 1000)

    final_chunk = {
        "id": "mock-chat-completion",
        "object": "chat.completion.chunk",
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {},
                "finish_reason": "stop",
            }
        ],
    }

    yield f"data: {json.dumps(final_chunk)}\n\n"
    yield "data: [DONE]\n\n"


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.post("/v1/chat/completions")
async def chat_completions(payload: dict):
    delay_ms = get_delay_ms(
        payload,
        "mock_delay_ms",
    )

    messages = payload.get("messages", [])
    last_user_message = get_last_user_message(messages)

    reply = f"Mock reply: {last_user_message}"
    model = payload.get("model", "mock-model")

    if payload.get("stream") is True:
        chunk_delay_ms = get_delay_ms(
            payload,
            "mock_chunk_delay_ms",
            100,
        )

        return StreamingResponse(
            stream_chat_completion(
                reply=reply,
                model=model,
                first_chunk_delay_ms=delay_ms,
                chunk_delay_ms=chunk_delay_ms,
            ),
            media_type="text/event-stream",
        )

    if delay_ms:
        await asyncio.sleep(delay_ms / 1000)

    return {
        "id": "mock-chat-completion",
        "object": "chat.completion",
        "model": model,
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
