# 星爵台球俱乐部 X展架（80 × 180 cm）

- `index.html`：海报源文件，画布 800 × 1800 px（1px = 1mm），文案直接在里面改
- `output/`：导出文件
  - `*-print.jpg`：3200 × 7200 px（约 100dpi），直接发图文店喷绘/写真
  - `*.pdf`：80 × 180 cm 矢量 PDF（文字为矢量）
  - `*-preview.png`：手机预览用小图
- 微信群二维码：把图片存为 `wechat-qr.png` 放在本目录，重新导出即可替换占位框

重新导出：

```bash
./fetch-fonts.sh                     # 下载字体（Google Fonts，开源可商用）
NODE_PATH=$(npm root -g) node render.js   # 需要 playwright + chromium
```
