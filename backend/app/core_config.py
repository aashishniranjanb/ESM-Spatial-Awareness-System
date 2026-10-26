from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    PROJECT_NAME: str = "EchoMap Spatial Awareness API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Environment
    ENV: str = "development"
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./echomap.db"
    
    # Security / CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001"
    ]
    
    # WebSocket settings
    WS_HEARTBEAT_INTERVAL_SEC: float = 15.0
    WS_TIMEOUT_SEC: float = 60.0
    
    # Spatial filter bounds (cm)
    MIN_DISTANCE_CM: float = 2.0
    MAX_DISTANCE_CM: float = 400.0

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
