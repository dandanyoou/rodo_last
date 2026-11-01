from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from apps.api.core.config import settings
from apps.api.core.database import init_db
from apps.api.routers import layouts, scans, simruns, venues


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="Rodo API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

upload_dir = Path(settings.UPLOAD_DIR)
upload_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")

app.include_router(venues.router)
app.include_router(layouts.router)
app.include_router(simruns.router)
app.include_router(scans.router)


@app.get("/")
def health():
    return {"status": "ok", "service": "rodo-api"}
