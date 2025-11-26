import os

def kill_by_name(name:str):
    os.system(f"pkill -f '{name}'")