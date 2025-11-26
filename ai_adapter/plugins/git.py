import os

def clone(url:str, dest:str=""):
    os.system(f"git clone {url} {dest}" if dest else f"git clone {url}")