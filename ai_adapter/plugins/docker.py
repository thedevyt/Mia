import os

def ps():
    os.system("docker ps --format 'table {{.ID}}\t{{.Image}}\t{{.Status}}'")