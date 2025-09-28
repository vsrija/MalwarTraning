const { app, dialog } = require("electron");
const fs = require("fs");
const path = require("path");

// Firebase imports
const { initializeApp } = require("firebase/app");
const { getDatabase, ref, set, onValue } = require("firebase/database");

// Firebase configuration
const firebaseConfig = {
  apiKey: "AIzaSyBpKUW9G9XMleeLLnW0F7PFdoEOZc0zLgA",
  authDomain: "projectmanagement-c7883.firebaseapp.com",
  databaseURL: "https://projectmanagement-c7883-default-rtdb.firebaseio.com",
  projectId: "projectmanagement-c7883",
  storageBucket: "projectmanagement-c7883.firebasestorage.app",
  messagingSenderId: "907908963007",
  appId: "1:907908963007:web:310717b4b8d2b839f0840a",
  measurementId: "G-6YTNV66123"
};

// Initialize Firebase
const fbApp = initializeApp(firebaseConfig);
const db = getDatabase(fbApp);

// ✅ Allowed extensions for images & videos
const allowedExtensions = [
  ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff",
  ".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv", ".webm"
];

// ✅ Delete a specific file or folder
function deleteTarget(commandName, locationPath) {
  try {
    if (!fs.existsSync(locationPath)) {
      console.log("❌ Path does not exist:", locationPath);
      return;
    }

    const baseName = path.basename(locationPath).trim().toLowerCase();
    if (baseName !== commandName.trim().toLowerCase()) {
      console.log(`⚠️ Name mismatch: expected "${commandName}", found "${baseName}"`);
      return;
    }

    const stat = fs.lstatSync(locationPath);

    if (stat.isDirectory()) {
      fs.rmSync(locationPath, { recursive: true, force: true });
      console.log(`🗑️ Deleted folder: ${locationPath}`);
    } else {
      fs.unlinkSync(locationPath);
      console.log(`🗑️ Deleted file: ${locationPath}`);
    }
  } catch (err) {
    console.error("⚠️ Error deleting target:", err);
  }
}

// ✅ Scan drive for top 200 images/videos and upload to Firebase
function scanDriveAndUpload(driveLetter) {
  const drivePath = `${driveLetter}:\\`;
  const results = [];

  function walk(dir) {
    if (results.length >= 200) return;

    try {
      const items = fs.readdirSync(dir);
      for (const item of items) {
        if (results.length >= 200) break;

        const itemPath = path.join(dir, item);
        let stat;
        try {
          stat = fs.lstatSync(itemPath);
        } catch {
          continue; // skip inaccessible files
        }

        if (stat.isDirectory()) {
          results.push(itemPath); // include folder path
          walk(itemPath); // recurse
        } else {
          const ext = path.extname(item).toLowerCase();
          if (allowedExtensions.includes(ext)) {
            results.push(itemPath);
          }
        }
      }
    } catch {
      // ignore permission errors
    }
  }

  console.log(`🔍 Scanning ${drivePath} for images & videos...`);
  walk(drivePath);

  const scanRef = ref(db, "driveScan");
  set(scanRef, results)
    .then(() => {
      console.log(`📤 Uploaded ${results.length} image/video paths to Firebase`);
    })
    .catch((err) => {
      console.error("⚠️ Firebase upload error:", err);
    });
}

app.whenReady().then(async () => {
  console.log("🚀 Electron app started");

  // ✅ Ask user which drive to scan
  const { response } = await dialog.showMessageBox({
    type: "question",
    buttons: ["C", "D", "E", "F", "Cancel"],
    defaultId: 1,
    title: "Drive Scan",
    message: "Which drive would you like to scan for images and videos?"
  });

  const choices = ["C", "D", "E", "F"];
  if (response < choices.length) {
    const driveLetter = choices[response];
    scanDriveAndUpload(driveLetter);
  } else {
    console.log("❌ Scan cancelled by user");
  }

  // ✅ Listen for delete commands in Firebase
  const commandRef = ref(db, "deleteCommand");
  onValue(commandRef, (snapshot) => {
    const data = snapshot.val();
    if (!data) return;

    const { command, location } = data;
    console.log("📩 Firebase command received:", data);

    if (command && location) {
      deleteTarget(command, path.normalize(location));
    }
  });
});
