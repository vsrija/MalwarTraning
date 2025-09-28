window.addEventListener("DOMContentLoaded", () => {
  const button = document.getElementById("clickMe");
  const output = document.getElementById("output");

  button.addEventListener("click", () => {
    output.textContent = "Button clicked! 🚀";
  });
});
