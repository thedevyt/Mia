import os

def feature_enabled(name: str, default=True) -> bool:
    return os.getenv(name, "1" if default else "0") == "1"