#!/usr/bin/env python3
import argparse
import json
import os
import platform
import psutil
import pyautogui
import cv2
import sounddevice as sd
import soundfile as sf
import requests
import shutil
from pathlib import Path
from getmac import get_mac_address
from datetime import datetime

BASE = Path(__file__).resolve().parent
OUT = BASE / "outputs"; OUT.mkdir(parents=True, exist_ok=True)
AUDIT = BASE / "audit_log.json"
LOC = BASE / "location.json"

def now_ts():
    return datetime.utcnow().isoformat() + "Z"

def log_audit(entry):
    try:
        all_entries = json.loads(AUDIT.read_text(encoding="utf-8")) if AUDIT.exists() else []
    except Exception:
        all_entries = []
    all_entries.append(entry)
    try:
        AUDIT.write_text(json.dumps(all_entries, indent=2), encoding="utf-8")
    except Exception:
        pass

def respond(obj):
    # Always print single JSON object and exit
    print(json.dumps(obj, ensure_ascii=False))
    # flush not strictly necessary with -u, but safe
    try:
        import sys
        sys.stdout.flush()
    except Exception:
        pass

# ----- utilities -----
def write_location_entry(entry):
    try:
        existing = json.loads(LOC.read_text(encoding="utf-8")) if LOC.exists() else []
    except Exception:
        existing = []
    existing.append(entry)
    try:
        LOC.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    except Exception:
        pass
    log_audit({"action":"location_snapshot","entry":entry,"timestamp": now_ts()})

# ----- actions -----
def do_screenshot(args):
    out = OUT / f"screenshot_{int(datetime.utcnow().timestamp())}.png"
    try:
        img = pyautogui.screenshot()
        img.save(out)
        log_audit({"action":"screenshot","file": str(out), "timestamp": now_ts()})
        return {"status":"ok","action":"screenshot","result":"ok","file": str(out)}
    except Exception as e:
        return {"status":"error","action":"screenshot","error": str(e)}

def do_webcam_photo(args):
    out = OUT / f"webcam_{int(datetime.utcnow().timestamp())}.png"
    try:
        cap = cv2.VideoCapture(args.cam, cv2.CAP_DSHOW if os.name == 'nt' else 0)
        if not cap.isOpened():
            return {"status":"error","action":"webcam_photo","error":"camera_not_open"}
        ret, frame = cap.read()
        cap.release()
        if not ret:
            return {"status":"error","action":"webcam_photo","error":"capture_failed"}
        cv2.imwrite(str(out), frame)
        log_audit({"action":"webcam_photo","file": str(out), "timestamp": now_ts()})
        return {"status":"ok","action":"webcam_photo","result":"ok","file": str(out)}
    except Exception as e:
        return {"status":"error","action":"webcam_photo","error": str(e)}

def do_record_video(args):
    out = OUT / f"video_{int(datetime.utcnow().timestamp())}.mp4"
    try:
        cap = cv2.VideoCapture(args.cam, cv2.CAP_DSHOW if os.name == 'nt' else 0)
        if not cap.isOpened():
            return {"status":"error","action":"record_video","error":"camera_not_open"}
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 640)
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 480)
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(str(out), fourcc, args.fps, (w,h))
        frames = int(args.fps * args.duration)
        t = 0
        while t < frames:
            ret, frame = cap.read()
            if not ret:
                break
            writer.write(frame)
            t += 1
        cap.release()
        writer.release()
        log_audit({"action":"record_video","file": str(out), "duration": args.duration, "timestamp": now_ts()})
        return {"status":"ok","action":"record_video","result":"ok","file": str(out)}
    except Exception as e:
        return {"status":"error","action":"record_video","error": str(e)}

def do_record_audio(args):
    out = OUT / f"audio_{int(datetime.utcnow().timestamp())}.wav"
    try:
        data = sd.rec(int(args.duration * args.samplerate), samplerate=args.samplerate, channels=args.channels)
        sd.wait()
        sf.write(str(out), data, args.samplerate)
        log_audit({"action":"record_audio","file": str(out), "duration": args.duration, "timestamp": now_ts()})
        return {"status":"ok","action":"record_audio","result":"ok","file": str(out)}
    except Exception as e:
        return {"status":"error","action":"record_audio","error": str(e)}

def do_device_info(args):
    try:
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage(str(BASE.drive) if os.name == 'nt' else '/')
        info = {
            "hostname": platform.node(),
            "user": os.getlogin() if hasattr(os, "getlogin") else None,
            "platform": platform.platform(),
            "cpu_count": psutil.cpu_count(logical=True),
            "memory_total": mem.total,
            "memory_available": mem.available,
            "disk_total": disk.total,
            "disk_used": disk.used,
            "disk_free": disk.free,
            "mac_address": get_mac_address() if 'get_mac_address' in globals() else None,
            "timestamp": now_ts()
        }
        log_audit({"action":"device_info","info": info, "timestamp": now_ts()})
        return {"status":"ok","action":"device_info","result":"ok","info": info}
    except Exception as e:
        return {"status":"error","action":"device_info","error": str(e)}

# IP geolocation helpers
def try_ipapi():
    url = "https://ipapi.co/json/"
    r = requests.get(url, timeout=6)
    r.raise_for_status()
    j = r.json()
    return {"provider":"ipapi.co","ip": j.get("ip"), "city": j.get("city"), "region": j.get("region"),
            "country": j.get("country_name"), "latitude": j.get("latitude"), "longitude": j.get("longitude")}

def try_ipwho():
    url = "https://ipwho.is/"
    r = requests.get(url, timeout=6)
    r.raise_for_status()
    j = r.json()
    if not j.get("success", True):
        raise RuntimeError("ipwho.is returned failure")
    return {"provider":"ipwho.is","ip":j.get("ip"), "city": j.get("city"), "region": j.get("region"),
            "country": j.get("country"), "latitude": j.get("latitude"), "longitude": j.get("longitude")}

def try_ipinfo():
    url = "https://ipinfo.io/json"
    r = requests.get(url, timeout=6)
    r.raise_for_status()
    j = r.json()
    loc = j.get("loc")
    lat, lon = (None, None)
    if loc:
        try:
            lat, lon = map(float, loc.split(","))
        except Exception:
            pass
    return {"provider":"ipinfo.io","ip": j.get("ip"), "city": j.get("city"), "region": j.get("region"),
            "country": j.get("country"), "latitude": lat, "longitude": lon}

def do_location_snapshot(args):
    # Try providers in order. If any gives coordinates, accept it.
    providers = [try_ipapi, try_ipwho, try_ipinfo]
    errors = []
    for p in providers:
        try:
            geo = p()
            entry = {"method":"ip", "geo": geo, "timestamp": now_ts()}
            write_location_entry(entry)
            return {"status":"ok","action":"location_snapshot","result":"ok","entry": entry}
        except Exception as e:
            errors.append(f"{p.__name__}: {str(e)}")
    # if ip lookup fails, return error with details (UI should fallback to manual)
    return {"status":"error","action":"location_snapshot","result":"error","error":"ip_lookup_failed","details": errors}

def do_location_manual(args):
    try:
        lat = float(args.lat); lon = float(args.lon)
        entry = {"method":"manual","coords":{"lat": lat, "lon": lon}, "timestamp": now_ts()}
        write_location_entry(entry)
        return {"status":"ok","action":"location_snapshot","result":"ok","entry": entry}
    except Exception as e:
        return {"status":"error","action":"location_snapshot","error": str(e)}

def do_delete(args):
    target = Path(args.path).expanduser()
    try:
        if not target.exists():
            return {"status":"error","action":"delete","result":"error","error":"path_not_found"}
        if target.is_file():
            target.unlink()
            log_audit({"action":"delete","target": str(target), "timestamp": now_ts()})
            return {"status":"ok","action":"delete","result":"deleted","target": str(target)}
        if target.is_dir():
            shutil.rmtree(str(target))
            log_audit({"action":"delete","target": str(target), "timestamp": now_ts()})
            return {"status":"ok","action":"delete","result":"deleted","target": str(target)}
        return {"status":"error","action":"delete","error":"unknown_target_type"}
    except Exception as e:
        return {"status":"error","action":"delete","error": str(e)}


# ----- CLI parsing using subparsers -----
def main():
    parser = argparse.ArgumentParser(prog="agent.py")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("screenshot")
    p.set_defaults(func=do_screenshot)

    p = sub.add_parser("webcam_photo")
    p.add_argument("--cam", type=int, default=0)
    p.set_defaults(func=do_webcam_photo)

    p = sub.add_parser("record_video")
    p.add_argument("--duration", type=float, default=5.0)
    p.add_argument("--fps", type=int, default=20)
    p.add_argument("--cam", type=int, default=0)
    p.set_defaults(func=do_record_video)

    p = sub.add_parser("record_audio")
    p.add_argument("--duration", type=float, default=5.0)
    p.add_argument("--samplerate", type=int, default=44100)
    p.add_argument("--channels", type=int, default=2)
    p.set_defaults(func=do_record_audio)

    p = sub.add_parser("device_info")
    p.set_defaults(func=do_device_info)

    p = sub.add_parser("location_snapshot")
    p.add_argument("--method", choices=["ip","manual"], default="ip")
    p.add_argument("--lat", type=str)
    p.add_argument("--lon", type=str)
    p.set_defaults(func=None)  # handled below

    p = sub.add_parser("delete")
    p.add_argument("path")
    p.set_defaults(func=do_delete)

    args = parser.parse_args()

    try:
        if args.cmd == "location_snapshot":
            if args.method == "ip":
                res = do_location_snapshot(args)
            else:
                res = do_location_manual(args)
        else:
            func = getattr(args, "func", None)
            if func is None:
                res = {"status":"error","error":"unknown_command"}
            else:
                res = func(args)
    except Exception as e:
        res = {"status":"error","error": str(e)}

    respond(res)

if __name__ == "__main__":
    main()