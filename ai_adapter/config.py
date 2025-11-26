from __future__ import annotations
import os
from dataclasses import dataclass


@dataclass
class Settings:
    engine: str = os.getenv("ENGINE", "auto")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3")
    voice_engine: str = os.getenv("VOICE_ENGINE", "vosk")
    vosk_model_path: str = os.getenv("VOSK_MODEL_PATH", "./models/vosk-model-en-us-0.22-lgraph")
    confirmation: str = os.getenv("CONFIRMATION", "ask")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_file: str = os.getenv("LOG_FILE", "./adapter.log")
    allow_docker: bool = os.getenv("ALLOW_DOCKER", "1") == "1"
    allow_apt: bool = os.getenv("ALLOW_APT", "1") == "1"
    allow_playerctl: bool = os.getenv("ALLOW_PLAYERCTL", "1") == "1"


settings = Settings()