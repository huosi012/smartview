#!/usr/bin/env python3
"""用 numpy 生成三级提示音 WAV（16 kHz 单声道 16 bit）。

L1：单声短促提示；L2：双声；L3：连续急促。中文语音提示请自备 ``voice_L{1,2,3}.wav``
（例如用 edge-tts / 讯飞 / espeak-ng 生成"前方有异物，请减速"等），SoundSink 会优先播放。
"""

from __future__ import annotations

import argparse
import wave
from pathlib import Path

import numpy as np

SR = 16000


def tone(freq: float, dur: float, amp: float = 0.6) -> np.ndarray:
    t = np.arange(int(SR * dur)) / SR
    env = np.minimum(1.0, np.minimum(t / 0.01, (dur - t) / 0.02)).clip(0, 1)
    return amp * env * np.sin(2 * np.pi * freq * t)


def silence(dur: float) -> np.ndarray:
    return np.zeros(int(SR * dur))


def write(path: Path, data: np.ndarray) -> None:
    pcm = (np.clip(data, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="assets/sounds")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write(out / "L1.wav", tone(880, 0.18))
    write(out / "L2.wav", np.concatenate([tone(1200, 0.15), silence(0.08), tone(1200, 0.15)]))
    write(out / "L3.wav", np.concatenate([tone(1600, 0.12, 0.8), silence(0.04)] * 5))
    print(f"写入 {out}/L1.wav L2.wav L3.wav")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
