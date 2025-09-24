const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const { deleteAllFiles } = require('./deleteFiles');

function createWindow() {
  const win = new BrowserWindow({
    width: 600,
    height: 400,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: true,   // for simplicity
      contextIsolation: false
    }
  });

  win.loadFile('index.html');
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

// Listen for delete request from renderer
ipcMain.handle('delete-files', async () => {
  try {
    await deleteAllFiles("D:\\Photos");
    return { success: true, message: "All files deleted successfully!" };
  } catch (err) {
    return { success: false, message: err.message };
  }
});
