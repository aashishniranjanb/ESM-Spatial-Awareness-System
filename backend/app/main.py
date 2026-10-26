from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core_config import settings
from app.database.session import init_db
from app.api.sessions_router import router as sessions_router
from app.websocket.ws_router import router as ws_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize database tables
    await init_db()
    yield
    # Shutdown

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health & Readiness Endpoints
@app.get("/health", tags=["system"])
async def health_check():
    return {"status": "ok", "version": settings.VERSION}

@app.get("/ready", tags=["system"])
async def readiness_check():
    return {"status": "ready", "env": settings.ENV}

# Include API Routers
app.include_router(sessions_router, prefix=settings.API_V1_STR)
app.include_router(ws_router)
