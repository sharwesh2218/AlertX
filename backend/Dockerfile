FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 \
    PORT=7860 TF_CPP_MIN_LOG_LEVEL=2 TF_USE_LEGACY_KERAS=1 YOLO_CONFIG_DIR=/tmp/Ultralytics
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 git && (apt-get install -y --no-install-recommends libglib2.0-0t64 || apt-get install -y --no-install-recommends libglib2.0-0) \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /tmp/build
COPY requirements.txt .
RUN pip install "setuptools<81" wheel \
    && pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-build-isolation -r requirements.txt
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user
WORKDIR /home/user/app
COPY --chown=user:user . .
RUN mkdir -p uploads logs && (python -c "import clip; clip.load('ViT-B/32', device='cpu')" || true)
EXPOSE 7860
CMD ["python", "run.py"]
