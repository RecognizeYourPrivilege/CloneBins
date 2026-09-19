# syntax=docker/dockerfile:1
# Web UI + clonebins-api with YuNet/SFace ONNX weights baked in.
#   docker compose up --build
#   open http://127.0.0.1:8765

FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci
COPY apps/web/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CLONEBINS_MODELS_DIR=/models \
    CLONEBINS_WEB_DIST=/app/web/dist \
    CLONEBINS_API_HOST=0.0.0.0 \
    CLONEBINS_API_PORT=8765

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY packages/core packages/core
COPY packages/api packages/api
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e packages/core -e packages/api

# opencv_zoo YuNet ×3 + SFace ×3 (Hugging Face, GitHub LFS mirrors as fallback)
RUN mkdir -p /models \
    && python -m clonebins_core.models --all --dir /models

COPY --from=web /web/dist /app/web/dist

EXPOSE 8765
CMD ["clonebins-api"]
