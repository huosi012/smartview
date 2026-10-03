# 自身区域遮罩

用 `smartview calib-mask --video <割台相机行驶视频> --out configs/masks/hdr_l.png` 生成，白色 = 需剔除的割台 / 分禾器 / 机身区域。
真机配置通过 `exclude_mask_png` 引用（相对配置文件目录），与 `exclude_polygons` 取并集。
