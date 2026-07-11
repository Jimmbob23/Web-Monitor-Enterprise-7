document.addEventListener("DOMContentLoaded", () => {
  const link = document.getElementById("novnc-link");
  if (link) {
    const protocol = window.location.protocol === "https:" ? "https:" : "http:";
    link.href = `${protocol}//${window.location.hostname}:6080/vnc.html?autoconnect=true&resize=scale&reconnect=true`;
  }

  const box = document.querySelector(".recorder-status");
  if (!box) return;
  const siteId = box.dataset.siteId;
  const state = box.querySelector(".recorder-state");
  const count = box.querySelector(".recorder-count");

  async function refresh() {
    try {
      const response = await fetch(`/sites/${siteId}/recorder/status`, {credentials: "same-origin"});
      const data = await response.json();
      state.textContent = data.error ? `${data.state}: ${data.error}` : data.state;
      count.textContent = data.count ?? 0;
    } catch (error) {
      state.textContent = "nicht erreichbar";
    }
  }
  refresh();
  setInterval(refresh, 2000);
});
