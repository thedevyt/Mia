import os

def ping(host:str="8.8.8.8"):
    os.system(f"ping -c 4 {host}")