# 职业健康检查一览表（附件8）排版工具

把原始“职业健康检查一览表”xlsx 整理成可打印的 Excel + PDF：

- A4 横向；上下边距 1 cm，左右 0.5 cm；无页眉页脚、无页码。
- 首页保留附件名称、标题（16 号）、受检单位/体检单位及日期（12 号，日期居右、上下对齐，
  两行信息完整外框、中间横线、日期左侧无竖线）。
- 第 2 页起只重复表头（10 号加粗、水平垂直居中，“接害/工龄”两行）。
- 短字段居中；“体检结果”“临床建议及处理意见”靠左。
- 文字整理：删除多余空格、空行；每个编号条目一行，条目内各检查项目用句号连接；
  原文内容和医学结论不改动。
- 行高按每人实际内容确定；按原顺序每页 1–2 人，同一人不跨页，页数最少。
- PDF 由同一份 Excel 导出，行高、分页与 Excel 一致；导出时启用中文避头尾规则。

## 使用

```bash
# 一次性准备（Ubuntu）
sudo apt-get install -y libreoffice-calc fonts-arphic-uming
pip install openpyxl pdfplumber fonttools
mkdir -p ~/.local/share/fonts ~/.config/fontconfig
python3 make_song_font.py ~/.local/share/fonts/UMingSongXL.ttf
cp fonts.conf ~/.config/fontconfig/fonts.conf && fc-cache -f

# 生成
python3 build_report.py 原始一览表.xlsx 输出目录
# 核对（人数、编号、姓名、正文、表头、页数、避头尾、文字越界、数字拆行）
python3 verify_report.py 原始一览表.xlsx 输出目录/*.xlsx 输出目录/*.pdf 输出目录/layout_plan.json
```

> 本仓库为公开仓库，含个人体检信息的 xlsx/pdf 及 `layout_plan.json` 已在 `.gitignore` 中排除，请勿提交。

## 关键做法

| 问题 | 处理 |
| --- | --- |
| Excel 与 LibreOffice 列宽换算不同 | 工作簿“常规”字体设为宋体 12（数字宽恰为 6 pt），两者列宽一致 |
| 环境中没有 Windows 宋体 | 用字宽与宋体相同的 AR PL UMing，行距调为 1.25 em，与 Excel 屏幕上宋体的行距一致 |
| 行高既要适合 PDF 也要适合 Excel | 取 LibreOffice 实测最适行高与 Excel 屏幕保守估算的较大值，按 0.75 pt 取整 |
| Excel 单行行高上限 409 pt | 超限的人员长文本字号由 8 号降为 7.5 号 |
| xlsx 导入后避头尾规则被关闭 | 通过 UNO 重新启用，并补充 %、～、↑↓ 等不得出现在行首的符号 |
