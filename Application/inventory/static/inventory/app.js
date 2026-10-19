document.addEventListener("click", (event) => {
  const row = event.target.closest(".clickable-row");
  if (!row || event.target.closest("a, button, input, select, textarea, form, summary, details, label")) {
    return;
  }
  window.location.assign(row.dataset.href);
});

document.addEventListener("keydown", (event) => {
  const row = event.target.closest(".clickable-row");
  if (!row || (event.key !== "Enter" && event.key !== " ")) {
    return;
  }
  event.preventDefault();
  window.location.assign(row.dataset.href);
});
