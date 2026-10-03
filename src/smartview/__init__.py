"""smartview — 玉米收获机垄内异物视觉预警系统（边缘端软件原型）。

包结构（数据流自上而下）::

    capture  →  detect  →  track  →  geometry  →  risk  →  alarm / hmi / storage
      ↑                                                      ↑
    synth（合成场景，用于离线测试与演示）                    health（相机健康 / 镜头脏污 / 吹扫）
"""

__version__ = "0.1.0"
