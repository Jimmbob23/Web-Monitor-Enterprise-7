#!/usr/bin/env bash
set -e

rm -f /tmp/.X99-lock
Xvfb :99 -screen 0 1600x1000x24 -ac +extension RANDR &
sleep 1
fluxbox >/tmp/fluxbox.log 2>&1 &
x11vnc -display :99 -forever -shared -nopw -rfbport 5900 >/tmp/x11vnc.log 2>&1 &
websockify --web=/usr/share/novnc/ 6080 localhost:5900 >/tmp/novnc.log 2>&1 &

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
