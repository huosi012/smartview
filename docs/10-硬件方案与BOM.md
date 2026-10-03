# 10 · 硬件方案与 BOM

> 平台：NVIDIA Jetson Orin NX 16GB 车规整机 + GMSL2 车规相机。本篇给出选型、安装几何、镜头吹扫、报警与供电、线缆、标定流程与 BOM。
> 价格为 2026-10 检索到的公开渠道参考价（海外报价按 1 USD ≈ 7.1 CNY 折算，国内渠道通常低 30~40 %），用于预算量级判断，采购前以报价为准；标注"估"者为无公开报价的经验估计。各条目来源见第 8 节。

## 1. 系统组成

```mermaid
flowchart LR
  subgraph 驾驶室
    ORIN[Jetson Orin NX 16GB<br/>车规整机 9~36 V]
    DISP[10.1" 触摸屏<br/>HDMI + USB 触摸]
    BZ[蜂鸣器 ≥95 dB]
    LAMP[红 / 黄 LED 灯条]
    RLY[8 路光耦继电器模块]
    PWR[隔离 DC-DC + 浪涌/反接保护<br/>延时关机]
    GNSS[GNSS 模块（可选）<br/>NMEA 车速]
  end
  subgraph 车顶
    C1[前视 GMSL2 相机<br/>IMX390 2 MP HDR<br/>HFOV 60°]
    AK1[环形气幕喷嘴]
  end
  subgraph 割台
    C2[近场 GMSL2 相机 ×2/3<br/>HFOV 100° IP67]
    AK2[环形气幕喷嘴 ×2/3]
    SV[电磁阀组 24 V]
    AIR[24 V 无油气泵 + 储气罐<br/>+ 过滤减压（或外接车载气源）]
  end
  C1 & C2 -- FAKRA 同轴 GMSL2 ≤15 m --> ORIN
  ORIN -- HDMI/USB --> DISP
  ORIN -- GPIO 3.3 V --> RLY
  RLY --> BZ & LAMP & SV
  SV --> AK1 & AK2
  AIR --> SV
  GNSS -- UART --> ORIN
  PWR --> ORIN & DISP & RLY
```

## 2. 主要部件选型

### 2.1 计算单元
| 项 | 选择 | 说明 |
|---|---|---|
| 模组 | **Jetson Orin NX 16GB**：Super 模式 157 TOPS 稀疏 / 78 TOPS 稠密 INT8（标准模式 100/50），1024 CUDA + 32 Tensor Core，8 核 Cortex-A78AE，16 GB LPDDR5，10~40 W（40 W 由 JetPack 6.1/6.2 解锁） | 实测 YOLOv8s@640 TensorRT FP16 7.2 ms、INT8 5.5 ms（见 §2.7）；4 路 1080p 合计 ≈65 fps 时 GPU 占用约一半 |
| 降本备选 | Orin Nano Super 8GB：67/33 TOPS，6 核 A78AE，7~25 W，模组 ≈289 USD | 3 路可行；6 行机建议 NX |
| 整机 | 车规级无风扇整机：≥4 路 GMSL2（MAX9296A/MAX96712）、9~36 V 宽压、−25~70 ℃、CAN、UART、NVMe；防护等级尽量 IP67（多数产品为 IP5X，需装驾驶室内） | 候选见 §6 BOM：米文 APEX ORIN NX（8 路 GMSL2，9~36 V，−25~70 ℃，IP5X）、Seeed reComputer Robotics J4012 + GMSL 板（4 路 MAX96712，12~24 V）、Connect Tech Rudi-NX（4 路，9~36 V，−20~80 ℃）、研华 MIC-713S-OX4A1（选配 2 路 GMSL2，9~36 V） |
| 存储 | NVMe 512 GB 工业级（−40~85 ℃） | 事件片段 + 数据采集；`max_disk_gb` 控制占用 |
| 软件平台 | JetPack 6.x（Ubuntu 22.04、Python 3.10） | 6.0 为 TensorRT 8.6，6.1+ 为 TensorRT 10（`yolo_trt.py` 按 10 编写） |

### 2.2 相机（GMSL2 车规）
| 位置 | 规格 | 候选 | 备注 |
|---|---|---|---|
| 前视 ×1 | 2 MP 1/2.7" Sony IMX390，1920×1080@30，HDR（传感器 120 dB）+ LFM，YUV422，PoC 供电，IP67，HFOV 60° | 森云 SG2-IMX390C-5200-GMSL2F-H60 | 逆光 / 黄昏依赖 HDR |
| 割台 ×2（6 行 ×3） | 同系列 HFOV 100°（H100）镜头版本，IP67 | 森云 SG2-IMX390C-5200-GMSL2F-H100 | 近距大视场；镜头前加气幕喷嘴 |
| 备选 | onsemi AR0233 2.6 MP HDR（SG2-AR0233C-5200-GMSL2F，60/100/118°）；Leopard LI-IMX390-GMSL2；e-con STURDeCAM21（IP67，批量价低） | | |
| 解串 | MAX96712 4 入（Seeed Robotics GMSL 板 / 整机自带）、MAX9296A 2 入（Waveshare HAT） | 同轴供电 PoC 9~16 V，线长 ≤15 m | |
| 补光（可选） | 24 V LED 工作灯 ×2，与割台相机同向 | 夜间作业 | 避免直射前视相机 |

分辨率必要性：前视 1920 px / 60° 时 15 m 处 ≈0.9 cm/px，Ø219 mm 井管宽 ≈24 px、0.5 m 高 ≈55 px；15 cm 石块高 ≈17 px —— 已接近模型稳定检出下限，因此 **前视必须以 1080p 中心裁剪方式推理**（见 [30 §2](30-感知算法与数据方案.md)），不能整帧缩到 640。

### 2.3 镜头吹扫（气幕 / 风刀）
| 项 | 选择 | 说明 |
|---|---|---|
| 喷嘴 | 环形气幕喷嘴（参考 EXAIR Super Air Wipe：360° 环形、30° 向心气幕；国产/自制环形喷嘴 + 快插接头即可） | 低流量持续气幕防尘 + 脉冲吹扫除污；喷嘴不进入视场 |
| 阀 | 24 V DC 二位二通常闭电磁阀（如 2V025-08，1/4"，0~1.0 MPa，响应 ≤0.05 s），每通道 1 只 | `alarm.purge.channels` 一一对应，继电器驱动 |
| 气源 | **国内玉米收获机（雷沃/中联等）产品页未见空压机标配**（Fendt IDEAL 标配、约翰迪尔 S 系列选装），因此系统自带 24 V 无油活塞气泵（≥30 L/min，130 psi 级）+ 5~10 L 储气罐 + 油水分离/减压阀（0.3~0.5 MPa）；有车载气源的机型外接 | 单次脉冲 1.5 s、每 60 s 一次、占空比 ≤10 %（软件限制） |
| 保护玻璃 | 相机前可更换疏水疏油镀膜玻璃 | 消耗件 |
| 控制 | 定时 / 镜头脏污检测触发 / HMI 手动；吹扫窗口内该相机检测暂停提交 | 见 [20 §8](20-软件架构.md) |

### 2.4 报警与人机
| 项 | 规格 | 说明 |
|---|---|---|
| 蜂鸣器 | 24 V 压电报警器 ≥95 dB@1 m（SFM-27 类），IP65 | 驾驶室噪声 80~90 dB，须明显高于 |
| 灯条 | 红色 + 黄色 12~24 V LED 警示灯条，安装于 A 柱视线内 | 红 = L2/L3，黄 = L1 |
| 继电器 | 8 路光耦隔离继电器模块（3.3 V 触发，高/低电平可选，10 A），分配：蜂鸣、红灯、黄灯、吹扫 ×2、二期预留 ×3 | `active_high: false` |
| 触摸屏 | 10.1" 1280×800 车载屏，HDMI + USB 电容触摸，≥1000 nit 防眩光，9~36 V（Xenarc 1022TSH/1029CNH 级；国产同规格明显便宜） | 浏览器 kiosk 全屏打开 HMI |
| 音频（可选） | 整机 3.5 mm/USB 声卡 + 小功放喇叭 | 中文语音提示；部分载板无音频编解码，蜂鸣器为主 |

### 2.5 定位与车速（可选但推荐）
| 方案 | 选择 | 用途 |
|---|---|---|
| 米级 GNSS | u-blox NEO-M9N（≈15 USD）或国产同级模块，UART NMEA 1~10 Hz | 车速（TTC）、事件打点、"同一位置复发预警" |
| RTK | u-blox ZED-F9P（≈125 USD）/ 和芯星通 UM982（双天线定向，≈160 USD）+ 网络 RTK 账号 | 三期无人机建图联动、厘米级事件地图 |

### 2.6 供电与保护
| 项 | 规格 |
|---|---|
| 电源 | 车载 24 V → 隔离 DC-DC（Mean Well SD-25B-12 / SD-50B-12：19~36 V 入、12 V 出、1500 VAC 隔离，短路/过载/过压保护；**无反接与 ISO 7637 浪涌保护**，前级须加熔断器 + 理想二极管/反接二极管 + TVS 如 5KP36A），或整机直接 9~36 V 宽压输入 |
| 延时关机 | 点火信号（ACC）检测，熄火后维持 ≥10 s 让服务落盘后再切断（或小型 UPS 模块） |
| 接地 | 整机与屏单点接地，GMSL2 同轴屏蔽层随机身 |

### 2.7 推理性能参考（Ultralytics 官方基准，Orin NX 16GB，JetPack 6.0，640 输入，batch 1，TensorRT 引擎时间，不含前后处理）
| 模型 | FP32 | FP16 | INT8 |
|---|---|---|---|
| YOLOv8n | 8.0 ms | 4.6 ms | 4.1 ms |
| YOLOv8s | 14.0 ms | 7.2 ms | 5.5 ms |
| YOLO26n | 7.0 ms | 4.1 ms | 3.5 ms |
| YOLO26s | 12.6 ms | 6.4 ms | 4.8 ms |

整管线按每帧再加 2~4 ms 前后处理预留。1 路前视 20 fps + 3 路割台 15 fps = 65 fps × 7.2 ms ≈ 0.47 GPU 时间占用（FP16，YOLOv8s）。

## 3. 安装几何

| 相机 | 安装 | 几何结果（由 `smartview.geometry.PinholeCamera` 计算） |
|---|---|---|
| 前视 fwd | 驾驶室顶中线前沿，离地 3.2 m，俯角 15°，HFOV 60°，位于割台前缘后方 ≈2.5 m | 可见地面从相机前 ≈4.9 m（距割台前缘 ≈2.4 m）到地平线；关注区 5~20 m；地平线在画面上方约 1/3 处 |
| 割台 hdr_l / hdr_r | 分禾器尖端后上方横梁，离地 0.5 m（作业时分禾器尖贴地 5~15 cm），横向 ±0.6 m（6 行机 ±1.2 m 与 0），俯角 25°，HFOV 100°，位于割台前缘前方 ≈0.3 m | 可见地面从 ≈0.3 m 起；3 m 处 ≈0.37 cm/px；画面下沿必然看到分禾器 → 必须配置排除区 |

机型参数参考：雷沃谷神 CP04（4YZ-4C）割台幅宽 2.6 m、行距 650 mm（适应 630~700）；6 行机幅宽 3.6~3.9 m（行距 550~650 可选）。农业农村部黄淮海玉米技术意见：60 cm 等行距，收获行距偏差 ±5 cm；机收作业速度一般 4~6 km/h。**配置中的 `row_spacing_m` / `header_width_m` 按实车填写。**

安装要点：
1. 前视相机沿机器中线对准垄沟，俯角用水平仪校到 15°±1°；支架刚性固定于驾驶室骨架，避免悬臂。
2. 割台相机避开拨禾链甩出的秸秆轨迹，镜头朝前下；支架 M8 以上螺栓 + 弹垫；线缆沿割台横梁走拖链，在割台升降铰链处留 ≥300 mm 弯曲余量。
3. 所有相机前方加气幕喷嘴，喷嘴不进入视场；排除区标定在喷嘴安装后进行。
4. 灯条 / 蜂鸣器安装在驾驶员正前视线 30° 内且不遮挡仪表。

## 4. 接线与引脚（示例，按整机手册核对）

| 信号 | Orin 40 pin（BOARD 编号） | 连接 | 配置键 |
|---|---|---|---|
| 蜂鸣器 | 12 | 继电器 IN1 → 24 V 蜂鸣器 | `alarm.gpio.buzzer_pin` |
| 红灯 | 16 | IN2 → 红灯条 | `alarm.gpio.lamp_pin` |
| 黄灯 | 18 | IN3 → 黄灯条 | `alarm.gpio.lamp_yellow_pin` |
| 吹扫-前视 | 22 | IN4 → 电磁阀 1 | `alarm.purge.channels.forward` |
| 吹扫-割台 | 24 | IN5 → 电磁阀 2 | `alarm.purge.channels.header` |
| GNSS | UART1（/dev/ttyTHS1）3.3 V TTL | NMEA 9600/115200 | `speed.nmea_port` |
| 二期 CAN | can0 | 车辆 CAN/ISOBUS（经隔离收发器） | — |

继电器模块 VCC 接 5 V、JD-VCC 接 24 V（去掉光耦隔离跳线）；GPIO 低电平吸合时 `active_high: false`。

## 5. 标定流程

1. **内参 / 畸变**（可选）：棋盘格 20 张，`cv2.calibrateCamera`；前视 60° 可省略，割台 100° 建议去畸变。
2. **地面单应性**：地面放 ≥4 个标志物（5/10/15/20 m，左右各 ±2 m），卷尺或 RTK 量 (x_fwd, y_lat)，`python scripts/calibrate_homography.py --image fwd.jpg` 点选 → 写入 `homography`；重投影 RMS 应 <0.2 m。割台相机用 0.5/1/2/3 m 标志物同法。
3. **垄道 ROI 与中心裁剪**：在 HMI 画面中确认 ROI 覆盖机器路径 ±1.5 m 及 5~20 m，`detect_crop` 包含 ROI。
4. **割台排除区**：空地行驶 30 s 录像，`smartview calib-mask --video hdr_l.mp4 --out /etc/smartview/masks/hdr_l.png`，核对预览图后写入配置；也可手工给 `exclude_polygons`。
5. **自检**：`smartview selftest`；HMI"测试报警"确认蜂鸣/灯/语音；手动吹扫确认阀动作。
6. **复标定触发**：更换/碰撞相机、更换割台、季前检查发现外参漂移 >1°。

## 6. BOM（4 行机原型，1 套）

| # | 部件 | 候选型号 / 规格 | 数量 | 参考单价（CNY） | 小计 | 来源 / 备注 |
|---|---|---|---|---|---|---|
| 1 | Orin NX 16GB 车规整机（含模组、载板、≥4 路 GMSL2） | 米文 APEX ORIN NX（8 路 GMSL2，9~36 V，−25~70 ℃） | 1 | 15,000~25,000（估） | 18,000 | 米文官网无公开报价；替代：Seeed Robotics J4012 + GMSL 板 ≈11,600（1,639 USD，美国站含关税）、Connect Tech Rudi-NX ≈24,200（3,412 USD）、研华 MIC-713S-OX4A1 ≈17,700（2,492 USD） |
| 2 | NVMe 512 GB 工业级 | — | 1 | 500 | 500 | 估 |
| 3 | 前视 GMSL2 相机 2 MP HDR H60 IP67 | 森云 SG2-IMX390C-5200-GMSL2F | 1 | 1,500~2,500（国内估）；海外 2,500~3,500 | 2,000 | gmslcam 358 USD、D3 499 USD |
| 4 | 割台 GMSL2 相机 2 MP H100 IP67 | 森云 SG2-IMX390C-5200-GMSL2F | 2 | 1,500~2,500 | 4,000 | 6 行机 ×3 |
| 5 | GMSL2 解串板（整机未含时） | Seeed Robotics GMSL 板（MAX96712 4 路） | 1 | 350 | 0 | 49 USD；整机含则为 0 |
| 6 | FAKRA 同轴线 5~12 m + 防水接头 | — | 3 | 200 | 600 | 估 |
| 7 | 10.1" 车载触摸屏 HDMI/USB 9~36 V | 国产 1280×800 ≥900 nit | 1 | 600~1,800（估）；Xenarc 1022TSH ≈4,700 | 1,500 | Xenarc 659 USD |
| 8 | 蜂鸣器 ≥95 dB 24 V | SFM-27 类压电 | 1 | 10~20 | 20 | eBay/SunFounder |
| 9 | LED 警示灯条 红/黄 12~24 V | — | 2 | 130~460 | 400 | Amazon |
| 10 | 8 路光耦继电器模块 3.3 V | — | 1 | 28~65 | 60 | Amazon/Sharvi |
| 11 | 环形气幕喷嘴 + 保护玻璃 | 自制/国产环形喷嘴（EXAIR Super Air Wipe ≈2,850 为参考上限） | 3 | 100~400（估） | 750 | EXAIR 401 USD |
| 12 | 24 V 电磁阀 1/4" 二位二通 | 2V025-08 DC24V | 2 | 15~35（亚德客正品 40~70） | 100 | Alibaba/ElectroPeak |
| 13 | 24 V 无油气泵 + 储气罐 + 过滤减压 | 国产 24 V 车载气泵 / VIAIR 96C（≈1,330） | 1 | 500~1,500 | 1,000 | 国内收获机多无空压机，需自带 |
| 14 | 气管、快插接头 | PU 6 mm | 1 | 150 | 150 | 估 |
| 15 | 隔离 DC-DC + 保护 | Mean Well SD-50B-12（≈225）+ 熔断/反接/TVS（20~40）+ 延时模块 | 1 | 400 | 400 | DigiKey/Jameco |
| 16 | GNSS 模块（米级，可选） | u-blox NEO-M9N | 1 | 110（模组）+ 天线/板 ≈200 | 300 | DigiKey 15.44 USD；RTK：ZED-F9P ≈885 / UM982 ≈1,150 |
| 17 | 支架、护罩、拖链、线束、接插件 | 定制 | 1 | 2,000 | 2,000 | 估 |
| 18 | 近场 LED 工作灯（可选） | 24 V | 2 | 100 | 200 | 估 |
| | **合计（原型，不含人工与安装）** | | | | **≈32,000** | 区间约 2.5~4.0 万；用 Seeed J4012 方案可降至 ≈2.5 万 |

量产降本路径：整机改用 Orin Nano Super 8GB（模组 ≈289 USD）或 RK3588 国产平台（需重做模型适配）、相机改用国产 1080p GMSL2 模组（e-con STURDeCAM21 批量 129 USD 级）、屏幕复用主机原厂显示器（以太网 HMI）、取消 RTK；6 行机量产 BOM 目标 ≈1.5 万元以内。

## 7. 环境与可靠性要求

| 项目 | 要求 |
|---|---|
| 工作温度 | −20~60 ℃（整机 −25~70 ℃） |
| 防护 | 相机 IP67/IP69K；整机若为 IP5X 须置于驾驶室内防尘盒，继电器/电源同盒 |
| 振动冲击 | ISO 16750-3 / GB/T 28046.3 农机级；相机支架一阶固有频率 >30 Hz |
| EMC | GB/T 18655（车辆 EMC）；GMSL2 同轴屏蔽、电源隔离 |
| 电源 | 9~36 V，抗 ISO 7637 浪涌（外加 TVS）；熄火延时 ≥10 s |
| 寿命 | 电磁阀 ≥100 万次；按每 60 s 一次吹扫、每季 300 h 计约 1.8 万次/季 |

## 8. 数据来源（2026-10-03 检索）

- Orin NX Super 模式与 JetPack 6.2：Connect Tech `connecttech.com/jetson-orin-nx-nano-super-mode/`；NVIDIA 开发者博客 "JetPack 6.2 brings Super Mode"。Orin NX 发布价 599 USD（1KU+），零售 699~829 USD（ThinkRobotics 评测）。Orin Nano Super 模组 289 USD（Arrow 900-13767-0030-000）。
- 整机：米文 APEX ORIN NX 产品页；Seeed reComputer Industrial J4012 1,813.99 USD、Robotics J4012 含 GMSL 1,639 USD、GMSL 板 49 USD（seeedstudio.com）；Connect Tech Rudi-NX 16GB+1TB 3,412 USD（WDL Systems）与规格 PDF CTIX-00198；研华 MIC-713S-OX4A1 2,491.73 USD（buy.advantech.com）。
- 相机：森云 SG2-IMX390C 数据手册（files.seeedstudio.com）；gmslcam 358 USD、ndcomputingtech 408 USD、D3 Embedded 499 USD；AR0233 版 459~529 USD（openelab / sgwrd）；Leopard LI-IMX390-GMSL2 429 USD；e-con STURDeCAM21 批量 129 USD；Waveshare MAX9296 HAT 89.99 USD。
- 推理基准：Ultralytics 文档 "NVIDIA Jetson" 指南（v8.2.100 存档与当前版）。
- 气幕：EXAIR Super Air Wipe 博客与 Amazon 价（401 USD）；SAMCON air.Blade；MOS Pneumatics AIR SCREEN；电磁阀 2V025-08 2.09~4.95 USD（Alibaba / ElectroPeak）；VIAIR 96C 24 V 187.97 USD；收获机空压机：Fendt IDEAL 10 标配、约翰迪尔 S760~S790 手册 "If Equipped"。
- 显示与声光：Xenarc 1022TSH 659 USD、1029CNH；Industrial Monitor Direct 车载 10.1" 起 447 USD；压电蜂鸣器 1.63 USD/只；LED 灯条 17.88~63.99 USD；继电器模块 3.97/8.85 USD。
- GNSS：ZED-F9P-05B 124.62 USD（DigiKey）；UM982 162.81 USD（gnss.store）；NEO-M9N-00B 15.44 USD（DigiKey）。
- 电源：Mean Well SD-25B-12 25.50 USD（DigiKey）、SD-50B-12 31.70 USD（Jameco）；数据手册未列反接/ISO 7637。
- 机型与农艺：农业农村部《黄淮海夏播玉米生产技术指导意见》（60 cm 等行距、收获行距偏差 ±5 cm）、《玉米机械化收获减损技术指导意见》（4~6 km/h、分禾器贴地）；雷沃谷神 CP04 参数（农机通）；6 行机幅宽（天人 4YZL-6 3900、牧神 4YZT-6 3860/3610）；雷沃 CB6P 行距选项。
- 机井：8 寸（NPS 8）钢管外径 219.1 mm（Engineering ToolBox）；江苏高标准农田工程质量整治方案要求井台高出地面 0.3~0.8 m；山东 DB37/T 3488-2019、GB/T 50625-2023（正文未核）。

> 注：Seeed / Connect Tech / 研华 / 米文 / Arrow 页面在本次环境中由搜索摘要获取，正式报价前请人工复核。
