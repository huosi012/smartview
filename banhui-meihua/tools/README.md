# 生成脚本

重新出图、出文档用（需要先把字体放进 ~/.fonts：站酷快乐体 ZCOOLKuaiLe-Regular.ttf、站酷庆科黄油体 QingKe.ttf（只用于印章字）、Noto Sans SC、Noto Serif SC、LXGW WenKai）。

1. `python3 cutout.py <参考人物图> ../assets/char_full.png /tmp/head.png`：人物抠图
   AI 生成的人物图（纯白背景）用 `rmbg.py` 抠图（需要 `pip install "rembg[cpu]"`）：`python rmbg.py isnet-general-use '[{"src":"in.png","dst":"../assets/char_A.png"}]'`；`keep` 可指定要补回的道具区域（地上的虚线、骨牌）
2. `python3 assets.py ../assets`：封面标题横幅、小图标
3. `python3 design3.py ../assets`：点阵纸页面、栏目标签、环节档案夹、报纸图标
4. `python3 content_imgs.py ../assets`：班会过程台阶图、课前小调查、板书设计
   `python3 activity_imgs.py ../assets`：活动配图（奇怪线条线索卡、骨牌实验示意、排队承诺卡，以及对掌、小火车两张场景图的底板）
5. `node build.js items.json ../assets raw.docx && python3 fixup.py raw.docx out.docx`：生成 Word
6. `python3 verify.py items.json out.docx`：逐段核对文字和原文一致

`items.json` 是从原文档逐段提取出的文字，`build.js` 只从这里取文字。
