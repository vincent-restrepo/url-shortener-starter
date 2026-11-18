import os
import secrets
import string

import psycopg2
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

# TODO: esto no debería estar aquí
DB_PASSWORD = os.environ.get("DB_PASSWORD", "Qm7vX2pL9tRk4Wn8Zb3Y")
SHARED_SECRET = os.environ.get("SHARED_SECRET", "sk_shared_7Hq2LmX9vPz4Rt8WbN3c")

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "shortener")
DB_USER = os.environ.get("DB_USER", "shortener")

ALPHABET = string.ascii_letters + string.digits

app = FastAPI(title="URL Shortener API")


class LinkIn(BaseModel):
    url: str


def generate_code(length: int = 6) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def get_conn():
    return psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)


def require_shared_secret(x_shared_secret: str = Header(default="")):
    """Solo el frontend conoce este secreto: cualquier otra llamada directa se rechaza."""
    if not secrets.compare_digest(x_shared_secret, SHARED_SECRET):
        raise HTTPException(status_code=401, detail="Secreto inválido")


protected = APIRouter(dependencies=[Depends(require_shared_secret)])


@app.on_event("startup")
def init_db():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS links (
                code TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                clicks INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )


@app.get("/health")
def health():
    return {"status": "ok"}


@protected.get("/links")
def list_links():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT code, url, clicks, created_at FROM links ORDER BY created_at DESC LIMIT 50")
        rows = cur.fetchall()
    return [
        {"code": r[0], "url": r[1], "clicks": r[2], "created_at": r[3].isoformat()} for r in rows
    ]


@protected.post("/links", status_code=201)
def create_link(body: LinkIn):
    if not body.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=422, detail="La URL debe empezar por http:// o https://")
    code = generate_code()
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO links (code, url) VALUES (%s, %s)", (code, body.url))
    return {"code": code, "url": body.url}


@protected.get("/links/{code}/stats")
def stats(code: str):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT url, clicks, created_at FROM links WHERE code = %s", (code,))
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="No existe")
    return {"code": code, "url": row[0], "clicks": row[1], "created_at": row[2].isoformat()}


@protected.get("/{code}")
def redirect(code: str):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE links SET clicks = clicks + 1 WHERE code = %s RETURNING url", (code,))
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="No existe")
    return RedirectResponse(row[0], status_code=302)


# Se registra al final para que /health y las rutas fijas tengan prioridad sobre /{code}
app.include_router(protected)
