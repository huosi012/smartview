#!/usr/bin/env bash
# 下载海报用到的开源字体（Google Fonts / SIL OFL）到 fonts/ 目录
set -euo pipefail
cd "$(dirname "$0")/fonts"
dl() { [ -s "$1" ] || curl -fsSL -o "$1" "$2"; }
dl ZCOOLQingKeHuangYou.ttf https://fonts.gstatic.com/s/zcoolqingkehuangyou/v16/2Eb5L_R5IXJEWhD3AOhSvFC554MOOahI4mRIiw.ttf
dl MaShanZheng.ttf         https://fonts.gstatic.com/s/mashanzheng/v18/NaPecZTRCLxvwo41b4gvzkXaRMQ.ttf
dl NotoSansSC-500.ttf      https://fonts.gstatic.com/s/notosanssc/v41/k3kCo84MPvpLmixcA63oeAL7Iqp5IZJF9bmaG-3FnYw.ttf
dl NotoSansSC-700.ttf      https://fonts.gstatic.com/s/notosanssc/v41/k3kCo84MPvpLmixcA63oeAL7Iqp5IZJF9bmaGzjCnYw.ttf
dl NotoSansSC-900.ttf      https://fonts.gstatic.com/s/notosanssc/v41/k3kCo84MPvpLmixcA63oeAL7Iqp5IZJF9bmaG3bCnYw.ttf
dl NotoSerifSC-900.ttf     https://fonts.gstatic.com/s/notoserifsc/v36/H4cyBXePl9DZ0Xe7gG9cyOj7uK2-n-D2rd4FY7QrrCWv.ttf
dl Anton.ttf               https://fonts.gstatic.com/s/anton/v27/1Ptgg87LROyAm0K0.ttf
dl Oswald-700.ttf          https://fonts.gstatic.com/s/oswald/v57/TK3_WkUHHAIjg75cFRf3bXL8LICs1xZogUE.ttf
