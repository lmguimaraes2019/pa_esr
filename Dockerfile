FROM node:22-alpine AS web
WORKDIR /web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.13-slim
WORKDIR /srv
ENV PYTHONUNBUFFERED=1 ORC_DATA_DIR=/data ORC_COOKIE_SECURE=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ app/
COPY scripts/ scripts/
COPY --from=web /web/dist web/dist
RUN useradd -r -u 1000 orc && mkdir /data && chown orc /data
USER orc
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*", "--workers", "1"]
