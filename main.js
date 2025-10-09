const { app, BrowserWindow, ipcMain, dialog } = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const fs = require("fs");

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

// ---- Python agent command runner ----
ipcMain.handle("run-agent-command", async (event, cmd, args) => {
  return new Promise((resolve) => {
    const child = spawn("python", ["-u", py, cmd, ...args], {
      cwd: path.join(__dirname, "agent"),
      env: process.env,
    });

    let out = "";
    let err = "";
    child.stdout.on("data", (d) => (out += d.toString()));
    child.stderr.on("data", (d) => (err += d.toString()));

    child.on("close", (code) => {
      resolve({ code, stdout: out.trim(), stderr: err.trim() });
    });
  });
});

// ---- Confirmation dialog ----
ipcMain.handle("show-confirm", async (event, message) => {
  const res = await dialog.showMessageBox(win, {
    type: "question",
    buttons: ["Yes", "No"],
    defaultId: 1,
    message,
  });
  return res.response === 0;
});

// ---- Location JSON reader ----
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

// ---- Open Delete Window ----
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

// ---- Perform delete from Electron ----
ipcMain.on("perform-delete", async (event, targetPath) => {
  if (!targetPath) return;
  console.log("Attempting to delete:", targetPath);

  const res = await new Promise((resolve) => {
    const child = spawn("python", ["-u", py, "delete", targetPath], {
      cwd: path.join(__dirname, "agent"),
      env: process.env,
    });
    let out = "";
    child.stdout.on("data", (d) => (out += d.toString()));
    child.on("close", () => resolve(out.trim()));
  });

  if (deleteWin) deleteWin.webContents.send("delete-result", res);
  if (win) win.webContents.send("delete-result", res);
});

app.on("window-all-closed", () => app.quit());
