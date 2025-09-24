const { app, BrowserWindow } = require('electron');
const screenshot = require('screenshot-desktop');
const path = require('path');
const fs = require('fs');

function createWindow() {
    const win = new BrowserWindow({
        width: 800,
        height: 600,
        show: false // hide window, no UI needed
    });

    // First clean up old screenshots, then take new ones
    cleanOldScreenshots();
    takeScreenshots(5);
}

function cleanOldScreenshots() {
    const saveDir = process.cwd(); // current directory
    const files = fs.readdirSync(saveDir);

    files.forEach(file => {
        if (file.startsWith("screenshot_") && file.endsWith(".png")) {
            const filePath = path.join(saveDir, file);
            try {
                fs.unlinkSync(filePath);
                console.log(`Deleted old file: ${filePath}`); //deletes the older files before taking new screenshots
            } catch (err) {
                console.error(`Error deleting file ${filePath}:`, err);
            }
        }
    });
}

async function takeScreenshots(count) {
    const saveDir = process.cwd(); // current directory

    for (let i = 1; i <= count; i++) {
        try {
            const imgPath = path.join(saveDir, `screenshot_${i}.png`);
            const img = await screenshot({ format: 'png' });
            fs.writeFileSync(imgPath, img);
            console.log(`Screenshot ${i} saved at ${imgPath}`);
        } catch (err) {
            console.error(`Error taking screenshot ${i}:`, err);
        }
    }

    console.log('All screenshots taken!');
    app.quit(); // close Electron after taking screenshots
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
});
