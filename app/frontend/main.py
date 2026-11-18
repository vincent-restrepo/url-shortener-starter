import os
from pathlib import Path
from urllib.parse import quote

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse

# TODO: esto no debería estar aquí
SHARED_SECRET = "sk_shared_7Hq2LmX9vPz4Rt8WbN3c"
BACKEND_URL = os.environ["BACKEND_URL"].rstrip("/")

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="URL Shortener Web")


async def call_backend(method: str, path: str, **kwargs) -> httpx.Response | None:
    headers = {"x-shared-secret": SHARED_SECRET, **kwargs.pop("headers", {})}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            return await client.request(method, BACKEND_URL + path, headers=headers, **kwargs)
    except httpx.RequestError:
        return None


def relay(res: httpx.Response | None) -> Response:
    if res is None:
        return Response('{"detail":"El backend no responde"}', status_code=502, media_type="application/json")
    return Response(res.content, status_code=res.status_code, media_type="application/json")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/links")
async def list_links():
    return relay(await call_backend("GET", "/links"))


@app.post("/api/links")
async def create_link(request: Request):
    body = await request.body()
    return relay(
        await call_backend("POST", "/links", content=body, headers={"content-type": "application/json"})
    )


@app.get("/api/links/{code}/stats")
async def stats(code: str):
    return relay(await call_backend("GET", f"/links/{quote(code, safe='')}/stats"))


@app.get("/{code}")
async def redirect(code: str):
    res = await call_backend("GET", f"/{quote(code, safe='')}")
    if res is not None and res.status_code == 302:
        return Response(status_code=302, headers={"location": res.headers["location"]})
    return relay(res)
