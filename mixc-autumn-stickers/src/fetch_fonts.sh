#!/usr/bin/env bash
# Downloads the (OFL) fonts used to outline the text. Usage: fetch_fonts.sh <dir>
set -euo pipefail
dir=${1:?font dir}
mkdir -p "$dir"
get() { [ -s "$dir/$1" ] || curl -sSfL -o "$dir/$1" "$2"; }
get Outfit-700.ttf     https://fonts.gstatic.com/s/outfit/v15/QGYyz_MVcBeNP4NjuGObqx1XmO1I4deyC4E.ttf
get Outfit-600.ttf     https://fonts.gstatic.com/s/outfit/v15/QGYyz_MVcBeNP4NjuGObqx1XmO1I4e6yC4E.ttf
get NotoSansSC-700.ttf https://fonts.gstatic.com/s/notosanssc/v41/k3kCo84MPvpLmixcA63oeAL7Iqp5IZJF9bmaGzjCnYw.ttf
get NotoSansSC-500.ttf https://fonts.gstatic.com/s/notosanssc/v41/k3kCo84MPvpLmixcA63oeAL7Iqp5IZJF9bmaG-3FnYw.ttf
