# server/main.py
"""Newsletter Portal FastAPI application.

Serves dist/ as static files and exposes /api/* routes.
API routes MUST be registered before the StaticFiles mount.
"""
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DIST_DIR  = REPO_ROOT / "dist"

app = FastAPI(title="Newsletter Portal", version="2.0.0")

# Import and register routers lazily to avoid circular imports
def _register_routers():
    from server.routers.generate   import router as generate_router
    from server.routers.topics     import router as topics_router
    from server.routers.jobs_router import router as jobs_router

    app.include_router(generate_router, prefix="/api/generate", tags=["generate"])
    app.include_router(topics_router,   prefix="/api/topics",   tags=["topics"])
    app.include_router(jobs_router,     prefix="/api/jobs",     tags=["jobs"])

_register_routers()

# Static files MUST be mounted after all /api/* routes
if DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=str(DIST_DIR), html=True), name="static")

if __name__ == "__main__":
    uvicorn.run("server.main:app", host="0.0.0.0", port=8787, reload=False)
