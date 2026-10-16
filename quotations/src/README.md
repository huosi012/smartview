# CS881-TG 热风循环烘箱报价单 — 生成脚本

`../1200x1500x1500热风循环烘箱_CS881-TG_报价单.pdf` 由以下脚本生成，所有文字均直接读取自原始
`1200×1500×1500热风循环烘箱.docx`，未改写。

| 文件 | 作用 |
| --- | --- |
| `prep.py` | 处理客户提供的 logo、合同章、照片（旋转纠正、缩放、去白底） |
| `cut.py` | 用 rembg（BiRefNet）对关键设备照片抠图，每次处理一张以控制内存 |
| `cutprep.py` | 清理抠图边缘杂物（线缆等）并裁切 |
| `build.py` | 读取 docx 文本，生成 A4 分页 HTML（`build.py <docx> <out.html> <总页数> <style.css>`） |
| `style.css` | 版式与配色（品牌青 #2E94A6，字体 Noto Sans SC / Noto Serif SC / Inter） |
| `render.js` | Playwright + Chromium 导出 PDF，并报告每页是否溢出 |
| `verify.py` | 校验 docx 中每一段文字均出现在 PDF 中 |

字体与图片素材体积较大，未提交到仓库；字体可从 Google Fonts 下载（Noto Sans SC、Noto Serif SC、Inter）。
