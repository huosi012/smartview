# 生成脚本

重新出图、出文档用（需要先把字体放进 ~/.fonts：ZCOOL KuaiLe、Noto Sans SC、Noto Serif SC、LXGW WenKai）。

1. `python3 cutout.py <参考人物图> ../assets/char_full.png ../assets/char_head_src.png`：人物抠图
2. `python3 assets.py ../assets`：页面边框、标题、栏目标签、环节横幅、图标
3. `python3 content_imgs.py ../assets`：班会过程总览、课前小调查、板书设计
4. `node build.js items.json ../assets raw.docx && python3 fixup.py raw.docx out.docx`：生成 Word
5. `python3 verify.py items.json out.docx`：逐段核对文字和原文一致

`items.json` 是从原文档逐段提取出的文字，`build.js` 只从这里取文字。
