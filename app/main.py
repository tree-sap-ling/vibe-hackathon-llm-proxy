import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse


def get_upstream_base_url():
    return os.getenv(
        "UPSTREAM_BASE_URL",
        "http://127.0.0.1:9000",
    ).rstrip("/")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(5.0)
    )

    yield

    await app.state.http_client.aclose()


app = FastAPI(
    title="LLM Proxy",
    lifespan=lifespan,
)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/readyz")
async def readyz(request: Request):
    upstream_url = f"{get_upstream_base_url()}/healthz"

    try:
        upstream_response = await request.app.state.http_client.get(
            upstream_url,
            timeout=1.0,
        )
        upstream_response.raise_for_status()
    except httpx.HTTPError:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready"},
        )

    return {"status": "ready"}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    payload = await request.json()

    upstream_url = (
        f"{get_upstream_base_url()}/v1/chat/completions"
    )

    try:
        upstream_response = await request.app.state.http_client.post(
            upstream_url,
            json=payload,
        )
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=504,
            detail="Upstream provider timed out",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail="Upstream provider is unavailable",
        ) from exc

    return JSONResponse(
        status_code=upstream_response.status_code,
        content=upstream_response.json(),
    )
