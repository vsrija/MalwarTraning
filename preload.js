const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
  runCommand: (command, args = []) => ipcRenderer.send("run-command", command, args),
  openDeleteWindow: () => ipcRenderer.send("open-delete-window"),
  performDelete: (path) => ipcRenderer.send("perform-delete", path),
  onLog: (callback) => ipcRenderer.on("log-message", (event, message) => callback(message)),
});
