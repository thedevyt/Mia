import os

def apt_install(pkg:str):
    os.system(f"sudo apt-get update && sudo apt-get install -y {pkg}")

def flatpak_install(ref:str):
    os.system(f"flatpak install -y {ref}")