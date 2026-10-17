# CS881-TG 热风循环烘箱报价单 — 生成脚本

`../1200x1500x1500热风循环烘箱_CS881-TG_报价单.pdf` 由以下脚本生成，所有文字均直接读取自原始
`1200×1500×1500热风循环烘箱.docx`；仅原文中明显的错别字/标点按 `fixes.py` 中的清单逐条更正。

| 文件 | 作用 |
| --- | --- |
| `prep.py` | 处理客户提供的 logo、合同章、照片（旋转纠正、缩放、去白底） |
| `cut.py` | 用 rembg（BiRefNet）对关键设备照片抠图，每次处理一张以控制内存 |
| `cutprep.py` | 清理抠图边缘杂物（线缆等）并裁切 |
| `edges.py` | 用 RANSAC 拟合设备轮廓的上下左右边线 |
| `rectify.py` | 透视矫正：把设备正面映射为正矩形（三分之四视角的设备只校正竖线） |
| `fixes.py` | 原文明显错误的更正清单（原文 → 更正） |
| `build.py` | 读取 docx 文本，生成 A4 分页 HTML（`build.py <docx> <out.html> <总页数> <style.css>`） |
| `style.css` | 版式与配色（品牌青 #2E94A6，字体 Noto Sans SC / Noto Serif SC / Inter） |
| `render.js` | Playwright + Chromium 导出 PDF，并报告每页是否溢出 |
| `verify.py` | 校验 docx 中每一段文字均出现在 PDF 中 |

字体与图片素材体积较大，未提交到仓库；字体可从 Google Fonts 下载（Noto Sans SC、Noto Serif SC、Inter）。

## Word 版（.docx）

`../1200x1500x1500热风循环烘箱_CS881-TG_报价单.docx` 与 PDF 内容一致（同一份文字、图片、8 页结构），所有文字、表格、图片均可编辑。

| 文件 | 作用 |
| --- | --- |
| `docx/content.py` | 从原 docx（含 `fixes.py` 更正）导出全部文字为 JSON，与 PDF 用同一来源 |
| `docx/assets_docx.js` | 从 PDF 的 HTML 渲染封面/内页背景（去掉文字）、图标、安装示意图，并记录封面文字位置 |
| `docx/build_docx.js` | 用 docx-js 生成 Word：每页一节（页眉标签不同），页码用 PAGE/NUMPAGES 字段，固定行距保证分页稳定 |
| `docx/tune.json` | 各页行高/间距微调参数，使每页内容排到页脚附近 |
| `docx/measure_docx.py` | 统计每页内容底部位置，用于调整 `tune.json` |

字体使用 Windows 常见的「微软雅黑」+ Arial。封面和内页的渐变、色带作为背景图放在页眉里（双击页眉可编辑或删除）。
