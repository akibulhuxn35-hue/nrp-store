document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".alert").forEach(el => {
    setTimeout(() => { el.style.opacity = "0"; el.style.transform = "translateY(-5px)"; }, 4500);
    setTimeout(() => el.remove(), 5000);
  });
});
