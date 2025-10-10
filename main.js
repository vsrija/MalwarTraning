const { app, BrowserWindow, ipcMain, dialog } = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const fs = require("fs");
const os = require("os");

// ---------------- Firebase Setup (v9+ compatible) ----------------
const { initializeApp } = require("firebase/app");
const { getDatabase, ref, push, update } = require("firebase/database");

const firebaseConfig = {
  apiKey: "AIzaSyBpKUW9G9XMleeLLnW0F7PFdoEOZc0zLgA",
  authDomain: "projectmanagement-c7883.firebaseapp.com",
  databaseURL: "https://projectmanagement-c7883-default-rtdb.firebaseio.com",
  projectId: "projectmanagement-c7883",
  storageBucket: "projectmanagement-c7883.firebasestorage.app",
  messagingSenderId: "907908963007",
  appId: "1:907908963007:web:310717b4b8d2b839f0840a",
  measurementId: "G-6YTNV66123",
};

const appFB = initializeApp(firebaseConfig);
const db = getDatabase(appFB);

// ---------------- Electron Windows ----------------
let win;
let deleteWin;
const py = path.join(__dirname, "agent", "agent.py");

function createWindow() {
  win = new BrowserWindow({
    width: 1000,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  win.loadFile(path.join(__dirname, "renderer", "index.html"));
}

app.whenReady().then(createWindow);

// ---------------- Python Command Runner ----------------
ipcMain.handle("run-agent-command", async (event, cmd, args) => {
  return new Promise((resolve) => {
    const child = spawn("python", ["-u", py, cmd, ...(args || [])], {
      cwd: path.join(__dirname, "agent"),
      env: process.env,
    });

    let out = "";
    let err = "";

    child.stdout.on("data", (d) => (out += d.toString()));
    child.stderr.on("data", (d) => (err += d.toString()));

    child.on("close", (code) => {
      const result = out.trim() || err.trim() || "No output";

      // Push log to Firebase
      const logEntry = {
        command: cmd,
        result: result,
        status: code === 0 ? "success" : "error",
        triggered_by: "dashboard",
        timestamp: new Date().toISOString(),
        device: os.hostname(),
      };

      push(ref(db, "logs"), logEntry);

      // Update "task" node for UI visibility
      update(ref(db, "task"), {
        last_result: result,
        last_executed: new Date().toISOString(),
        command: "",
        triggered_by: "dashboard",
        device: os.hostname(),
      });

      resolve({ code, stdout: out.trim(), stderr: err.trim() });
    });
  });
});

// ---------------- Confirm Dialog ----------------
ipcMain.handle("show-confirm", async (event, message) => {
  const res = await dialog.showMessageBox(win, {
    type: "question",
    buttons: ["Yes", "No"],
    defaultId: 1,
    message,
  });
  return res.response === 0;
});

// ---------------- Location JSON Reader ----------------
ipcMain.handle("get-location-json", async () => {
  const file = path.join(__dirname, "agent", "location.json");
  try {
    if (fs.existsSync(file)) {
      const content = fs.readFileSync(file, "utf-8");
      return JSON.parse(content);
    } else {
      return [];
    }
  } catch (err) {
    return { error: err.message };
  }
});

// ---------------- Open Delete Window ----------------
ipcMain.on("open-delete-window", () => {
  if (deleteWin) {
    deleteWin.focus();
    return;
  }
  deleteWin = new BrowserWindow({
    width: 500,
    height: 200,
    parent: win,
    modal: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  deleteWin.loadFile(path.join(__dirname, "renderer", "delete.html"));

  deleteWin.on("closed", () => {
    deleteWin = null;
  });
});

// ---------------- Handle Delete Request ----------------
ipcMain.on("perform-delete", async (event, targetPath) => {
  if (!targetPath) return;

  const res = await (async () => {
    return new Promise((resolve) => {
      const child = spawn("python", ["-u", py, "delete", targetPath], {
        cwd: path.join(__dirname, "agent"),
        env: process.env,
      });
      let out = "";
      child.stdout.on("data", (d) => (out += d.toString()));
      child.on("close", () => resolve(out.trim()));
    });
  })();

  // Send result back to both windows
  if (deleteWin) deleteWin.webContents.send("delete-result", res);
  if (win) win.webContents.send("delete-result", res);

  // Log to Firebase
  const logEntry = {
    command: `delete ${targetPath}`,
    result: res,
    status: "done",
    triggered_by: "dashboard",
    timestamp: new Date().toISOString(),
    device: os.hostname(),
  };
  push(ref(db, "logs"), logEntry);

  update(ref(db, "task"), {
    last_result: res,
    last_executed: new Date().toISOString(),
    command: "",
    triggered_by: "dashboard",
    device: os.hostname(),
  });
});

// ---------------- Quit when all windows closed ----------------
app.on("window-all-closed", () => app.quit());
