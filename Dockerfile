FROM mcr.microsoft.com/playwright/python:v1.54.0-jammy

ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=:99

RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb x11vnc fluxbox novnc websockify \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY start.sh /start.sh
RUN chmod +x /start.sh && mkdir -p /app/data/screenshots /app/data/diffs /app/data/backups /app/data/unread_changes

EXPOSE 8000 6080
CMD ["/start.sh"]
