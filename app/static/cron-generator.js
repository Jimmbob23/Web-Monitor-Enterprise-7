function intValue(el, min, max, fallback) {
  const n = parseInt(el.value, 10);
  return Number.isNaN(n) ? fallback : Math.max(min, Math.min(max, n));
}

function csvNumbers(value, min, max) {
  return [...new Set(value.split(",")
    .map(v => parseInt(v.trim(), 10))
    .filter(v => Number.isInteger(v) && v >= min && v <= max))]
    .sort((a,b) => a-b);
}

function selectedDays(helper) {
  return [...helper.querySelectorAll(".cron-weekday:checked")].map(el => el.value);
}

function buildCron(helper) {
  const preset = helper.querySelector(".cron-preset").value;
  const every = intValue(helper.querySelector(".cron-every"), 1, 59, 10);
  const hour = intValue(helper.querySelector(".cron-hour"), 0, 23, 8);
  const minute = intValue(helper.querySelector(".cron-minute"), 0, 59, 0);
  const end = intValue(helper.querySelector(".cron-hour-end"), 0, 23, 18);
  const days = selectedDays(helper);
  const hours = csvNumbers(helper.querySelector(".cron-hours").value, 0, 23);
  const monthDays = csvNumbers(helper.querySelector(".cron-month-days").value, 1, 31);

  if (preset === "every_minutes") return `*/${every} * * * *`;
  if (preset === "daily") return `${minute} ${hour} * * *`;
  if (preset === "hour_range") return `${minute} ${hour}-${end} * * *`;
  if (preset === "weekly") return `${minute} ${hour} * * ${days[0] || 1}`;
  if (preset === "weekdays") return days.length ? `${minute} ${hour} * * ${days.join(",")}` : "";
  if (preset === "weekdays_hours") return days.length && hours.length ? `${minute} ${hours.join(",")} * * ${days.join(",")}` : "";
  if (preset === "monthly") return monthDays.length ? `${minute} ${hour} ${monthDays.join(",")} * *` : "";
  return "";
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".cron-helper").forEach(helper => {
    const form = helper.closest("form");
    const output = form.querySelector(".cron-expression");
    const schedule = form.querySelector(".schedule-type");
    const preview = helper.querySelector(".cron-preview");

    const refresh = () => {
      const cron = buildCron(helper);
      preview.textContent = cron || "Bitte Auswahl vervollständigen";
      return cron;
    };

    helper.querySelectorAll("input,select").forEach(el => el.addEventListener("change", refresh));
    helper.querySelector(".cron-apply").addEventListener("click", () => {
      const cron = refresh();
      if (!cron) {
        alert("Bitte die benötigten Tage oder Uhrzeiten auswählen.");
        return;
      }
      output.value = cron;
      schedule.value = "cron";
    });

    refresh();
  });
});
