// preload.js
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("agentAPI", {
  runCommand: (cmd, args = []) =>
    ipcRenderer.invoke("run-agent-command", cmd, args),

  confirm: (msg) => ipcRenderer.invoke("show-confirm", msg),

  getLocationJson: () => ipcRenderer.invoke("get-location-json"),

  saveLocation: (locObj) => ipcRenderer.invoke("save-location", locObj),

  openDeleteWindow: () => ipcRenderer.send("open-delete-window"),

  performDelete: (path) => ipcRenderer.send("perform-delete", path),

  onDeleteResult: (cb) =>
    ipcRenderer.on("delete-result", (event, data) => cb(data)),
});
