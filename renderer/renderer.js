const logDiv = document.getElementById("log");

function appendLog(text) {
  logDiv.textContent = new Date().toISOString() + " - " + text + "\n\n" + logDiv.textContent;
}

window.electronAPI.onLog((msg) => appendLog(msg));

document.getElementById("screenshot").onclick = () => window.electronAPI.runCommand("screenshot");
document.getElementById("webcam").onclick = () => window.electronAPI.runCommand("webcam_photo");
document.getElementById("video").onclick = () => window.electronAPI.runCommand("record_video", ["--duration", "5"]);
document.getElementById("audio").onclick = () => window.electronAPI.runCommand("record_audio", ["--duration", "5"]);
document.getElementById("info").onclick = () => window.electronAPI.runCommand("device_info");
document.getElementById("loc").onclick = () => window.electronAPI.runCommand("location_snapshot", ["--method", "ip"]);
document.getElementById("delete").onclick = () => window.electronAPI.openDeleteWindow();
