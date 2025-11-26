from __future__ import annotations
import os
import json
import httpx
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"))

# ------------------------------------------------------------
# Base engine
# ------------------------------------------------------------

class Engine:
    async def parse(self, prompt: str, system: str) -> Dict[str, Any]:
        raise NotImplementedError("No backend AI engine selected or misconfigured.")

# ------------------------------------------------------------
# OpenAI backend
# ------------------------------------------------------------

class OpenAIEngine(Engine):
    def __init__(self, model: str, api_key: str):
        self.api_key = api_key
        self.model = model

    async def parse(self, prompt: str, system: str) -> Dict[str, Any]:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=self.api_key)  # create new client each time

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ]
        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=messages,
            )
            content = response.choices[0].message.content.strip()
            return json.loads(content)
        except Exception as e:
            print(f"[OpenAIEngine] Connection error: {e}")
            raise


# ------------------------------------------------------------
# Ollama backend (local)
# ------------------------------------------------------------

class OllamaEngine(Engine):
    def __init__(self, model: str):
        self.model = model
        self.url = "http://127.0.0.1:11434/api/chat"

    async def parse(self, prompt: str, system: str) -> Dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt}
            ],
            "format": "json"
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(self.url, json=payload, timeout=120)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict) and "message" in data:
                try:
                    return json.loads(data["message"]["content"])
                except Exception:
                    return {"intent": "unknown", "params": {"raw": data}}
            return data

# ------------------------------------------------------------
# Factory selector
# ------------------------------------------------------------

def make_engine() -> Engine:
    eng = os.getenv("ENGINE", "auto").lower()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    ollama_model = os.getenv("OLLAMA_MODEL", "llama3")
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    if eng == "openai" or (eng == "auto" and api_key):
        print("[AI Adapter] ✅ Using OpenAI backend")
        return OpenAIEngine(model=openai_model, api_key=api_key)

    elif eng == "ollama" or (eng == "auto" and not api_key):
        print("[AI Adapter] ✅ Using Ollama backend")
        return OllamaEngine(model=ollama_model)

    raise RuntimeError(
        "❌ No AI backend configured. Set ENGINE=openai and OPENAI_API_KEY in .env "
        "or start `ollama serve` with ENGINE=ollama."
    )

