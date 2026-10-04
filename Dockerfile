# 在任意 x86_64 / arm64 Linux 主机或虚拟机上跑 smartview 演示与 HMI（CPU，无需相机/GPU）。
#   docker build -t smartview .
#   docker run --rm -p 8080:8080 smartview            # 浏览器打开 http://localhost:8080/
# 回放自己的视频：docker run --rm -p 8080:8080 -v $PWD/my.yaml:/app/my.yaml -v $PWD/videos:/videos smartview \
#   smartview replay -c /app/my.yaml --hmi --realtime --loop
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 OMP_NUM_THREADS=2 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY configs ./configs
COPY assets ./assets
RUN pip install -e ".[hmi,onnx]"
EXPOSE 8080
VOLUME ["/app/data"]
CMD ["smartview", "demo", "--out", "/app/data/demo", "--hmi", "--realtime", "--loop", "--scenario", "mixed_forward"]
