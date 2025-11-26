import subprocess

def top20():
    subprocess.run("bash -lc 'ps -eo pid,comm,%cpu,%mem --sort=-%cpu | head -n 20'", shell=True)

def uptime():
    subprocess.run(["uptime","-p"])

def sensors():
    subprocess.run(["bash","-lc","which sensors && sensors || echo 'lm-sensors not installed'"], shell=False)