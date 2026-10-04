from __future__ import annotations

from abc import ABC, abstractmethod

from smartview.types import Frame


class FrameSource(ABC):
    """帧源接口。``read()`` 返回 None 表示结束（文件）或暂时无帧（直播，调用方应继续）。"""

    cam_id: str
    fps: float
    is_live: bool = False
    width: int = 0
    height: int = 0
    ts_offset: float = 0.0  # 回放源时间戳偏移（循环回放时保证时钟单调）

    @abstractmethod
    def open(self) -> None: ...

    @abstractmethod
    def read(self) -> Frame | None: ...

    @abstractmethod
    def close(self) -> None: ...

    @property
    def finished(self) -> bool:
        return False

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *exc):
        self.close()
