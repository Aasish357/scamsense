# syntax=docker/dockerfile:1
#
# ScamSense backend image.
#
# Why a container: Tesseract is a *system* binary. Render's native Python
# runtime cannot install system packages, so screenshot OCR is only possible
# with an image. Everything else runs the same code as the native runtime.

FROM python:3.11-slim

# tesseract-ocr      : reads text out of uploaded screenshots
# libgl1/libglib2.0-0: runtime libraries OpenCV needs to import cv2 (QR decoding)
# curl               : used by the container healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first so code edits do not invalidate the pip layer.
COPY apps/web/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt

# The FastAPI app lives in the web app at apps/web/src/app/main.py.
COPY apps/web/src /app/src

ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]