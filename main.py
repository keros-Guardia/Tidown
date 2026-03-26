import os
import sqlite3
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from database import init_db
from routers import auth_router, search, artists, feed, recommendations
from routers import tidal as tidal_router
from routers import admin as admin_router

app = FastAPI(title="Resonance", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _auto_migrate():
    from config import settings
    raw = settings.database_url.replace("sqlite+aiosqlite:///", "")
    db_path = raw if raw.startswith("/") else os.path.join(os.path.dirname(__file__), raw.lstrip("./"))

    if not os.path.exists(db_path):
        return

    migrations = [
        ("lastfm_api_key",      "ALTER TABLE users ADD COLUMN lastfm_api_key TEXT"),
        ("lastfm_api_secret",   "ALTER TABLE users ADD COLUMN lastfm_api_secret TEXT"),
        ("tidal_user_id",       "ALTER TABLE users ADD COLUMN tidal_user_id TEXT"),
        ("tidal_token_type",    "ALTER TABLE users ADD COLUMN tidal_token_type TEXT"),
        ("tidal_access_token",  "ALTER TABLE users ADD COLUMN tidal_access_token TEXT"),
        ("tidal_refresh_token", "ALTER TABLE users ADD COLUMN tidal_refresh_token TEXT"),
        ("tidal_expiry_time",   "ALTER TABLE users ADD COLUMN tidal_expiry_time DATETIME"),
        ("tidal_quality",       "ALTER TABLE users ADD COLUMN tidal_quality TEXT DEFAULT 'LOSSLESS'"),
        ("is_admin",            "ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0"),
    ]
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        cur.execute("PRAGMA table_info(users)")
        existing = {row[1] for row in cur.fetchall()}
        for col, sql in migrations:
            if col not in existing:
                cur.execute(sql)
                print(f"[migrate] +{col}")

        # Si un seul utilisateur existe et is_admin=0, le passer admin
        cur.execute("SELECT COUNT(*) FROM users")
        total = cur.fetchone()[0]
        if total == 1:
            cur.execute("UPDATE users SET is_admin=1 WHERE is_admin=0")
            print("[migrate] Premier utilisateur promu admin")
    except Exception as e:
        print(f"[migrate] Erreur : {e}")
    finally:
        conn.commit()
        conn.close()


@app.on_event("startup")
async def startup():
    _auto_migrate()
    await init_db()


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=404, content={"detail": "Route introuvable"})
    frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
    return FileResponse(os.path.join(frontend_dir, "index.html"))


@app.exception_handler(500)
async def server_error_handler(request: Request, exc):
    return JSONResponse(status_code=500, content={"detail": "Erreur interne du serveur"})


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router.router)
app.include_router(search.router)
app.include_router(artists.router)
app.include_router(feed.router)
app.include_router(recommendations.router)
app.include_router(tidal_router.router)
app.include_router(admin_router.router)


# ── Frontend ──────────────────────────────────────────────────────────────────
frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.isdir(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_frontend():
        return FileResponse(os.path.join(frontend_dir, "index.html"))

    @app.get("/{full_path:path}", include_in_schema=False)
    async def catch_all(request: Request, full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": f"Route introuvable : /{full_path}"})
        return FileResponse(os.path.join(frontend_dir, "index.html"))
