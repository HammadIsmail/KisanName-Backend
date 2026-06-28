import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from database import init_db
from routers import auth, query, tts, admin, health

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables if they don't exist
    init_db()
    yield
    # Shutdown: nothing to clean up

app = FastAPI(
    title="KisanNama API",
    description="AI-powered crop advisory system for Pakistani farmers",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow frontend origins
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "https://kisan-nama.vercel.app",
    os.getenv("FRONTEND_URL", ""),
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in ALLOWED_ORIGINS if o],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(query.router)
app.include_router(tts.router)
app.include_router(admin.router)
app.include_router(health.router)


@app.get("/")
def root():
    return {"message": "KisanNama API is running", "docs": "/docs"}
