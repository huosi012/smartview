# 提示音

- `L1.wav` / `L2.wav` / `L3.wav`：由 `scripts/make_sounds.py` 生成的三级提示音（16 kHz 单声道）。
- 中文语音提示：自备 `voice_L1.wav`（"前方发现异物，请注意"）、`voice_L2.wav`（"前方有异物，请减速"）、
  `voice_L3.wav`（"前方有异物，请立即停车"），放在本目录后 `SoundSink` 会优先播放。
  可用 edge-tts、espeak-ng、讯飞等生成，建议 16 kHz / 16 bit / 单声道。
- 驾驶室噪音大，**蜂鸣器（GPIO）为主报警**，声音文件只是辅助；部分 Jetson 载板没有音频编解码器。
