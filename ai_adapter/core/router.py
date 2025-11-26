from __future__ import annotations
import yaml, os
from typing import Dict, Any


class Router:
    def __init__(self, intents_dir: str):
        self.templates: Dict[str, Dict[str, Any]] = {}
        for fn in sorted(os.listdir(intents_dir)):
            if fn.endswith('.yaml'):
                with open(os.path.join(intents_dir, fn), 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f) or {}
                    self.templates.update(data)
    def get(self, intent: str) -> Dict[str, Any]:
        if intent not in self.templates:
            raise KeyError(f"Unknown intent: {intent}")
        return self.templates[intent]