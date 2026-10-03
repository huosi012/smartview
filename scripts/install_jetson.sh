#!/usr/bin/env bash
# Jetson Orin（JetPack 6.x，Ubuntu 22.04）部署脚本。⚠ 需真机验证。
# 用法：sudo bash scripts/install_jetson.sh [安装目录=/opt/smartview]
set -euo pipefail
PREFIX="${1:-/opt/smartview}"
SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "== 1/6 系统依赖"
apt-get update
apt-get install -y python3-venv python3-pip python3-opencv \
  gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
  v4l-utils alsa-utils sqlite3 fonts-noto-cjk

echo "== 2/6 校验系统 OpenCV 带 GStreamer 支持（GMSL2 管线需要）"
python3 - <<'PY'
import cv2
info = cv2.getBuildInformation()
ok = "GStreamer:                   YES" in info or "GStreamer" in info and "YES" in info.split("GStreamer")[1][:40]
print("OpenCV", cv2.__version__, "GStreamer:", "YES" if ok else "NO")
if not ok:
    raise SystemExit("系统 cv2 不支持 GStreamer，请安装 JetPack 自带的 OpenCV 或自行编译")
PY

echo "== 3/6 创建用户与目录"
id -u smartview >/dev/null 2>&1 || useradd -r -m -s /usr/sbin/nologin smartview
usermod -aG gpio,video,dialout,audio smartview || true
mkdir -p "$PREFIX" /etc/smartview /var/lib/smartview/clips "$PREFIX/models"
rsync -a --exclude .venv --exclude data --exclude .git "$SRC_DIR/" "$PREFIX/"

echo "== 4/6 Python 虚拟环境（继承系统 site-packages 以使用自带 cv2 / tensorrt）"
python3 -m venv --system-site-packages "$PREFIX/.venv"
"$PREFIX/.venv/bin/pip" install --upgrade pip
"$PREFIX/.venv/bin/pip" install -e "$PREFIX[hmi,onnx,jetson]"

echo "== 5/6 配置与模型"
if [ ! -f /etc/smartview/config.yaml ]; then
  cp "$PREFIX/configs/jetson_4row.yaml" /etc/smartview/config.yaml
  mkdir -p /etc/smartview/masks
  echo "已生成 /etc/smartview/config.yaml（4 行机模板），请按实车修改相机管线 / 安装参数 / GPIO 引脚"
fi
echo "模型：把 training/export_trt.sh 生成的 *.engine 放到 $PREFIX/models/ 并在配置 detector.model_path 中引用"
chown -R smartview:smartview "$PREFIX" /var/lib/smartview /etc/smartview

echo "== 6/6 systemd 服务"
install -m 644 "$SRC_DIR/scripts/smartview.service" /etc/systemd/system/smartview.service
systemctl daemon-reload
systemctl enable smartview.service
echo "完成。先运行自检：sudo -u smartview $PREFIX/.venv/bin/smartview selftest -c /etc/smartview/config.yaml"
echo "再启动：systemctl start smartview；HMI：http://<本机IP>:8080/"
