from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Frame,
    Page,
    Playwright,
    sync_playwright,
)

from app.config import settings


@dataclass
class RecorderSession:
    site_id: int
    url: str
    state: str = "starting"
    error: str = ""
    actions: list[dict[str, Any]] = field(default_factory=list)
    playwright: Playwright | None = None
    browser: Browser | None = None
    context: BrowserContext | None = None
    page: Page | None = None
    thread: threading.Thread | None = None
    stop_event: threading.Event = field(default_factory=threading.Event)
    injected_frames: int = 0


class MacroRecorder:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._session: RecorderSession | None = None

    @staticmethod
    def _record_dir() -> Path:
        path = settings.data_dir / "macro_recorder"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _record_path(self, site_id: int) -> Path:
        return self._record_dir() / f"site-{site_id}.jsonl"

    def _reset_record_file(self, site_id: int) -> None:
        self._record_path(site_id).write_text("", encoding="utf-8")

    def _persist_action(self, site_id: int, action: dict[str, Any]) -> None:
        with self._record_path(site_id).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(action, ensure_ascii=False) + "\n")
            handle.flush()

    def _read_persisted_actions(self, site_id: int) -> list[dict[str, Any]]:
        path = self._record_path(site_id)
        if not path.exists():
            return []

        actions: list[dict[str, Any]] = []

        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                action = json.loads(line)
            except json.JSONDecodeError:
                continue

            if isinstance(action, dict):
                self._append_deduplicated(actions, action)

        return actions

    def start(self, site_id: int, url: str) -> None:
        with self._lock:
            if self._session and self._session.state in {
                "starting",
                "recording",
                "stopping",
            }:
                raise RuntimeError("Es läuft bereits eine Makro-Aufnahme.")

            self._reset_record_file(site_id)

            session = RecorderSession(
                site_id=site_id,
                url=url,
            )
            self._session = session

            session.thread = threading.Thread(
                target=self._run,
                args=(session,),
                daemon=True,
                name=f"macro-recorder-{site_id}",
            )
            session.thread.start()

    def _run(self, session: RecorderSession) -> None:
        try:
            session.playwright = sync_playwright().start()

            session.browser = session.playwright.chromium.launch(
                headless=False,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--start-maximized",
                ],
            )

            session.context = session.browser.new_context(
                viewport=None,
                ignore_https_errors=True,
                locale="de-DE",
                timezone_id="Europe/Berlin",
            )

            def record_binding(source: dict[str, Any], payload: Any) -> bool:
                if not isinstance(payload, dict):
                    return False

                action = self._normalize(payload)
                if not action:
                    return False

                with self._lock:
                    if self._session is not session:
                        return False

                    if session.state not in {
                        "starting",
                        "recording",
                        "stopping",
                    }:
                        return False

                    self._append_deduplicated(
                        session.actions,
                        action,
                    )
                    self._persist_action(
                        session.site_id,
                        action,
                    )

                return True

            session.context.expose_binding(
                "wmRecordAction",
                record_binding,
            )

            script = self._recorder_script()

            # Für neue Dokumente und Navigationen.
            session.context.add_init_script(script)

            session.page = session.context.new_page()

            def reinject(frame: Frame) -> None:
                try:
                    frame.evaluate(script)
                    with self._lock:
                        session.injected_frames += 1
                except Exception:
                    # Cross-Origin-, PDF- oder noch nicht fertige Frames
                    # dürfen die Aufnahme nicht abbrechen.
                    pass

            session.page.on(
                "framenavigated",
                reinject,
            )

            session.page.goto(
                session.url,
                wait_until="domcontentloaded",
                timeout=60000,
            )

            # Explizite Injektion nach dem ersten Laden. Dies ist der
            # entscheidende Fallback, falls add_init_script auf einer
            # speziellen Webseite nicht gegriffen hat.
            for frame in session.page.frames:
                reinject(frame)

            session.state = "recording"

            while not session.stop_event.wait(0.20):
                if not session.browser or not session.browser.is_connected():
                    break

                # Dynamisch erzeugte Frames regelmäßig nachinjizieren.
                if session.page:
                    for frame in session.page.frames:
                        try:
                            installed = frame.evaluate(
                                "() => Boolean(window.__wmRecorderInstalled)"
                            )
                        except Exception:
                            installed = True

                        if not installed:
                            reinject(frame)

        except Exception as exc:
            session.error = str(exc)
            session.state = "error"

        finally:
            self._close_session_resources(session)

            if session.state not in {
                "error",
                "finished",
                "cancelled",
            }:
                session.state = "finished"

    @staticmethod
    def _normalize(payload: dict[str, Any]) -> dict[str, Any] | None:
        kind = str(payload.get("action_type", "")).strip()

        if kind not in {
            "select",
            "fill",
            "click",
            "check",
            "press",
            "scroll",
        }:
            return None

        selector_type = (
            str(payload.get("selector_type", "css")).strip()
            or "css"
        )
        selector = str(payload.get("selector", "")).strip()
        value = str(payload.get("value", ""))

        return {
            "action_type": kind,
            "selector_type": selector_type[:30],
            "selector": selector[:2000],
            "value": value[:2000],
            "timeout_ms": 15000,
        }

    @staticmethod
    def _append_deduplicated(
        actions: list[dict[str, Any]],
        action: dict[str, Any],
    ) -> None:
        if actions and action["action_type"] == "fill":
            previous = actions[-1]

            if (
                previous["action_type"] == "fill"
                and previous["selector_type"] == action["selector_type"]
                and previous["selector"] == action["selector"]
            ):
                actions[-1] = action
                return

        if actions and action == actions[-1]:
            return

        actions.append(action)

    def status(self, site_id: int) -> dict[str, Any]:
        with self._lock:
            if not self._session or self._session.site_id != site_id:
                persisted = self._read_persisted_actions(site_id)

                return {
                    "state": "idle",
                    "count": len(persisted),
                    "error": "",
                    "injected_frames": 0,
                }

            persisted = self._read_persisted_actions(site_id)
            count = max(
                len(self._session.actions),
                len(persisted),
            )

            return {
                "state": self._session.state,
                "count": count,
                "error": self._session.error,
                "injected_frames": self._session.injected_frames,
            }

    def stop(self, site_id: int) -> list[dict[str, Any]]:
        with self._lock:
            session = self._require_session(site_id)
            session.state = "stopping"

        # Debounce-Timer aus Eingabefeldern und letzte Browserereignisse.
        time.sleep(1.2)

        with self._lock:
            session.stop_event.set()
            thread = session.thread

        if thread:
            thread.join(timeout=15)

        persisted = self._read_persisted_actions(site_id)

        with self._lock:
            actions = list(session.actions)

            for action in persisted:
                self._append_deduplicated(
                    actions,
                    action,
                )

            session.state = "finished"
            self._session = None

            return actions

    def cancel(self, site_id: int) -> None:
        with self._lock:
            session = self._require_session(site_id)
            session.state = "cancelled"
            session.stop_event.set()
            thread = session.thread

        if thread:
            thread.join(timeout=10)

        self._record_path(site_id).unlink(
            missing_ok=True,
        )

        with self._lock:
            self._session = None

    def cancel_active(self) -> None:
        with self._lock:
            session = self._session

        if not session:
            return

        try:
            self.cancel(session.site_id)
        except RuntimeError:
            pass

    def _require_session(
        self,
        site_id: int,
    ) -> RecorderSession:
        if (
            not self._session
            or self._session.site_id != site_id
        ):
            raise RuntimeError(
                "Keine laufende Aufnahme für diesen Monitor."
            )

        return self._session

    @staticmethod
    def _close_session_resources(
        session: RecorderSession,
    ) -> None:
        for resource in (
            session.context,
            session.browser,
        ):
            try:
                if resource:
                    resource.close()
            except Exception:
                pass

        try:
            if session.playwright:
                session.playwright.stop()
        except Exception:
            pass

    @staticmethod
    def _recorder_script() -> str:
        return r"""
(() => {
  if (window.__wmRecorderInstalled) {
    return true;
  }

  window.__wmRecorderInstalled = true;

  function report(payload) {
    try {
      if (typeof window.wmRecordAction !== "function") {
        return;
      }

      const result = window.wmRecordAction(payload);

      if (result && typeof result.catch === "function") {
        result.catch(() => {});
      }
    } catch (_) {}
  }

  const cssEscape = (value) => {
    if (window.CSS && CSS.escape) {
      return CSS.escape(value);
    }

    return String(value).replace(
      /[^a-zA-Z0-9_-]/g,
      "\\$&"
    );
  };

  function selectorFor(element) {
    if (!element || !(element instanceof Element)) {
      return {
        selector_type: "css",
        selector: ""
      };
    }

    if (element.id) {
      return {
        selector_type: "css",
        selector: "#" + cssEscape(element.id)
      };
    }

    const ariaLabel = element.getAttribute("aria-label");

    if (ariaLabel) {
      return {
        selector_type: "label",
        selector: ariaLabel
      };
    }

    if (element.labels && element.labels.length) {
      const label = (
        element.labels[0].innerText
        || element.labels[0].textContent
        || ""
      ).trim();

      if (label) {
        return {
          selector_type: "label",
          selector: label
        };
      }
    }

    const placeholder = element.getAttribute("placeholder");

    if (placeholder) {
      return {
        selector_type: "placeholder",
        selector: placeholder
      };
    }

    const name = element.getAttribute("name");

    if (name) {
      return {
        selector_type: "css",
        selector: `[name="${String(name).replace(/"/g, '\\"')}"]`
      };
    }

    if (
      element.tagName === "BUTTON"
      || element.getAttribute("role") === "button"
    ) {
      const text = (
        element.innerText
        || element.textContent
        || ""
      ).trim();

      if (text) {
        return {
          selector_type: "role_button",
          selector: text
        };
      }
    }

    const parts = [];
    let node = element;

    while (
      node
      && node.nodeType === 1
      && parts.length < 6
    ) {
      let part = node.tagName.toLowerCase();

      const classes = [...node.classList]
        .filter((value) =>
          value
          && !/active|focus|hover|selected|open/i.test(value)
        )
        .slice(0, 2);

      if (classes.length) {
        part += "."
          + classes.map(cssEscape).join(".");
      }

      const parent = node.parentElement;

      if (parent) {
        const same = [...parent.children]
          .filter((child) =>
            child.tagName === node.tagName
          );

        if (same.length > 1) {
          part += `:nth-of-type(${same.indexOf(node) + 1})`;
        }
      }

      parts.unshift(part);
      node = parent;
    }

    return {
      selector_type: "css",
      selector: parts.join(" > ")
    };
  }

  function send(
    actionType,
    element,
    value = ""
  ) {
    const target = selectorFor(element);

    report({
      action_type: actionType,
      ...target,
      value: String(value ?? "")
    });
  }

  document.addEventListener(
    "change",
    (event) => {
      const element = event.target;

      if (!(element instanceof Element)) {
        return;
      }

      if (element.tagName === "SELECT") {
        const option = element.options[
          element.selectedIndex
        ];

        send(
          "select",
          element,
          option ? option.text : element.value
        );
        return;
      }

      if (
        element.matches(
          'input[type="checkbox"], input[type="radio"]'
        )
      ) {
        send(
          "check",
          element,
          element.checked ? "true" : "false"
        );
        return;
      }

      if (element.matches("input, textarea")) {
        send(
          "fill",
          element,
          element.value
        );
      }
    },
    true
  );

  document.addEventListener(
    "input",
    (event) => {
      const element = event.target;

      if (
        !(element instanceof Element)
        || !element.matches(
          'input:not([type="checkbox"]):not([type="radio"]), textarea'
        )
      ) {
        return;
      }

      clearTimeout(element.__wmRecorderTimer);

      element.__wmRecorderTimer = setTimeout(
        () => send(
          "fill",
          element,
          element.value
        ),
        350
      );
    },
    true
  );

  document.addEventListener(
    "click",
    (event) => {
      if (!(event.target instanceof Element)) {
        return;
      }

      const clickable = event.target.closest(
        'button, a, [role="button"], '
        + 'input[type="submit"], input[type="button"]'
      );

      if (clickable) {
        send(
          "click",
          clickable,
          ""
        );
      }
    },
    true
  );

  document.addEventListener(
    "keydown",
    (event) => {
      if (
        ["Enter", "Tab", "Escape"].includes(event.key)
      ) {
        report({
          action_type: "press",
          selector_type: "css",
          selector: "",
          value: event.key
        });
      }
    },
    true
  );

  let lastScrollY = window.scrollY;
  let scrollTimer = null;

  window.addEventListener(
    "scroll",
    () => {
      clearTimeout(scrollTimer);

      scrollTimer = setTimeout(
        () => {
          const delta = window.scrollY - lastScrollY;
          lastScrollY = window.scrollY;

          if (Math.abs(delta) >= 20) {
            report({
              action_type: "scroll",
              selector_type: "css",
              selector: "",
              value: String(delta)
            });
          }
        },
        400
      );
    },
    { passive: true }
  );

  return true;
})();
"""


macro_recorder = MacroRecorder()
