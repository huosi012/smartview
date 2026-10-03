#!/usr/bin/env python3
"""地面单应性标定工具。

交互模式（需显示器）::

    python scripts/calibrate_homography.py --image frame.jpg
    # 在窗口中依次左键点击标志物，终端输入其地面坐标 "x_fwd y_lat"（米），≥4 点后按 q 求解

非交互模式::

    python scripts/calibrate_homography.py --points "960,900,5,0;300,700,10,-2;1600,700,10,2;960,560,20,0"

输出可直接粘贴到相机配置 ``homography:`` 的 3x3 列表，并给出重投影误差。
"""

from __future__ import annotations

import argparse
import json

from smartview.tools.homography import parse_points, solve_homography


def interactive(image_path: str):
    import cv2

    img = cv2.imread(image_path)
    if img is None:
        raise SystemExit(f"无法读取 {image_path}")
    pixels, ground = [], []

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            print(f"像素 ({x}, {y}) → 请输入地面坐标 x_fwd y_lat（米）：", end="", flush=True)
            try:
                xf, yl = (float(t) for t in input().split())
            except ValueError:
                print("格式错误，忽略该点")
                return
            pixels.append((float(x), float(y)))
            ground.append((xf, yl))
            cv2.circle(img, (x, y), 6, (0, 0, 255), 2)
            cv2.putText(img, f"({xf:g},{yl:g})", (x + 8, y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

    cv2.namedWindow("calib", cv2.WINDOW_NORMAL)
    cv2.setMouseCallback("calib", on_mouse)
    print("左键点击标志物；≥4 点后按 q 求解")
    while True:
        cv2.imshow("calib", img)
        if cv2.waitKey(30) & 0xFF == ord("q"):
            break
    cv2.destroyAllWindows()
    return pixels, ground


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--image", default=None)
    ap.add_argument("--points", default=None, help='"u,v,x,y;..."')
    args = ap.parse_args()
    if args.points:
        px, gd = parse_points(args.points)
    elif args.image:
        px, gd = interactive(args.image)
    else:
        ap.error("需要 --image 或 --points")
    H, rms = solve_homography(px, gd)
    print(f"重投影 RMS 误差: {rms:.3f} m（建议 < 0.2 m；偏大请检查量距或增加点数）")
    print("homography:")
    print(json.dumps([[round(float(v), 8) for v in row] for row in H]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
