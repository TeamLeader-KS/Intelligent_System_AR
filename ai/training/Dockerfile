# Optional isolated CPU training image. The normal application does not build it.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
RUN --mount=type=cache,id=iv-training-pip,target=/root/.cache/pip \
    pip install --timeout 30 torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt /training-requirements.txt
RUN --mount=type=cache,id=iv-training-pip,target=/root/.cache/pip pip install --timeout 30 -r /training-requirements.txt
ENV YOLO_CONFIG_DIR=/tmp/ultralytics MPLCONFIGDIR=/tmp/matplotlib HOME=/tmp OMP_NUM_THREADS=4
WORKDIR /tmp
