# cmdctl.py
import time, json
import pyrebase

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

def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def send_command(cmd_payload):
    task = {
        "command": cmd_payload,
        "timestamp": now()
    }
    db.child("task").set(task)

if __name__ == "__main__":
    print("=== Firebase Command Control ===")
    while True:
        try:
            cmd = input("Enter command or JSON payload (or 'exit'): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break

        if cmd.lower() in ["exit", "quit"]:
            break
        if not cmd:
            continue

        # If looks like JSON, validate
        try:
            payload_to_send = cmd
            if (cmd.startswith("{") and cmd.endswith("}")):
                parsed = json.loads(cmd)
                payload_to_send = json.dumps(parsed)
        except Exception as e:
            print("JSON parse error:", e)
            continue

        send_command(payload_to_send)
        print(f"[✓] Sent command.")
        print("Waiting for execution...")
        executed = False
        start = time.time()
        while not executed and time.time() - start < 30:
            task_data = db.child("task").get().val()
            last_result = task_data.get("last_result") if task_data else None
            if last_result:
                print(f"[Result] {last_result}")
                executed = True
            else:
                time.sleep(1)
        if not executed:
            print("No result within timeout (30s). Check agent logs/outputs.")
        print("")
