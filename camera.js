const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs');

function createWindow() {
  const win = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    }
  });

  win.loadFile('index.html');
}

app.whenReady().then(() => createWindow());

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

// Save photo buffers from renderer
ipcMain.on('save-photo', (event, { buffer, index }) => {
  const filePath = path.join(__dirname, `photo_${index + 1}.png`);
  fs.writeFile(filePath, buffer, err => {
    if (err) console.error("Error saving photo:", err);
    else console.log("✅ Saved:", filePath);
  });
});
