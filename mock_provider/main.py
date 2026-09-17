from fastapi import FastAPI

app = FastAPI(title="Mock LLM Provider")


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.post("/v1/chat/completions")
async def chat_completions(payload: dict):
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
