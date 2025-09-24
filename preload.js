const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
  savePhoto: (data, index) => ipcRenderer.send("save-photo", { data, index }),
  allDone: () => ipcRenderer.send("all-done")
});
