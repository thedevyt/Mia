import os

def playpause():
    os.system("playerctl play-pause")

def volume(percent:int):
    os.system(f"pactl set-sink-volume @DEFAULT_SINK@ {percent}%")