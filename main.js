const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const fs = require("fs");

let mainWindow;
let deleteWindow;

// Python command candidates
const pythonCandidates = [
  "python",
  "python3",
  "py",
  "C:\\Users\\User\\AppData\\Local\\Programs\\Python\\Python311\\python.exe" // adjust if needed
];

// Find first working Python
function findPython() {
  return new Promise((resolve, reject) => {
    let checked = 0;
    pythonCandidates.forEach(cmd => {
      const test = spawn(cmd, ["--version"]);
      test.on("error", () => {
        checked++;
        if (checked === pythonCandidates.length) reject(new Error("No working Python found"));
      });
      test.stdout.on("data", () => resolve(cmd));
    });
  });
}

// Run Python agent.py
async function runPython(command, args = []) {
  try {
    const pythonCmd = await findPython();

    const script = path.join(__dirname, "agent.py");
    if (!fs.existsSync(script)) {
      sendToRenderer("❌ agent.py not found at " + script);
      return;
    }

    const py = spawn(pythonCmd, [script, command, ...args]);

    py.stdout.on("data", data => sendToRenderer(data.toString()));
    py.stderr.on("data", data => sendToRenderer("ERR: " + data.toString()));
    py.on("close", code => sendToRenderer(`Python exited with code ${code}`));
  } catch (err) {
    sendToRenderer("❌ Could not start Python: " + err.message);
  }
}

// Send logs to renderer
function sendToRenderer(message) {
  if (mainWindow && mainWindow.webContents) {
    mainWindow.webContents.send("log-message", message);
  }
  if (deleteWindow && deleteWindow.webContents) {
    deleteWindow.webContents.send("log-message", message);
  }
}

// Create main window
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1000,
    height: 700,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, "preload.js"),
    },
  });

  mainWindow.loadFile(path.join(__dirname, "renderer", "index.html"));
}

// Open Delete modal window
function openDeleteWindow() {
  if (deleteWindow) {
    deleteWindow.focus();
    return;
  }

  deleteWindow = new BrowserWindow({
    width: 500,
    height: 200,
    parent: mainWindow,
    modal: true,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, "preload.js"),
    },
  });

  deleteWindow.loadFile(path.join(__dirname, "renderer", "delete.html"));

  deleteWindow.on("closed", () => {
    deleteWindow = null;
  });
}

app.whenReady().then(() => {
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

// IPC from renderer
ipcMain.on("run-command", (event, command, args) => {
  sendToRenderer(`➡️ Running: ${command} ${args.join(" ")}`);
  runPython(command, args);
});

// IPC for opening delete window
ipcMain.on("open-delete-window", () => {
  openDeleteWindow();
});

// IPC for performing delete from modal
ipcMain.on("perform-delete", (event, targetPath) => {
  if (!targetPath) return;
  runPython("delete", [targetPath]);
});
