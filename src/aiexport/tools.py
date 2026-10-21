"""Locating the external programs the pipeline can use (Inkscape, Ghostscript, Chromium)."""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path


class ToolMissing(RuntimeError):
    """A required external program or library is not installed."""


def _first_existing(candidates: list[str]) -> str | None:
    for candidate in candidates:
        for match in sorted(glob.glob(candidate), reverse=True):
            if Path(match).is_file():
                return match
    return None


@lru_cache(maxsize=None)
def find_inkscape() -> str | None:
    """Inkscape 1.x executable, or None."""
    override = os.environ.get("AIEXPORT_INKSCAPE")
    if override:
        return override
    found = shutil.which("inkscape") or _first_existing([
        "/Applications/Inkscape.app/Contents/MacOS/inkscape",
        r"C:\Program Files\Inkscape\bin\inkscape.exe",
        r"C:\Program Files (x86)\Inkscape\bin\inkscape.exe",
    ])
    if found and not inkscape_version(found).startswith("Inkscape 1"):
        return None  # 0.92 uses a different command line
    return found


@lru_cache(maxsize=None)
def inkscape_version(exe: str) -> str:
    try:
        out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return out.stdout.strip().splitlines()[0] if out.stdout.strip() else ""


@lru_cache(maxsize=None)
def find_ghostscript() -> str | None:
    override = os.environ.get("AIEXPORT_GS")
    if override:
        return override
    for name in ("gs", "gswin64c", "gswin32c"):
        found = shutil.which(name)
        if found:
            return found
    return _first_existing([
        r"C:\Program Files\gs\gs*\bin\gswin64c.exe",
        r"C:\Program Files (x86)\gs\gs*\bin\gswin32c.exe",
        "/opt/homebrew/bin/gs",
        "/usr/local/bin/gs",
    ])


@lru_cache(maxsize=None)
def ghostscript_version(exe: str) -> str:
    try:
        out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return out.stdout.strip()


def cairosvg_available() -> bool:
    try:
        import cairosvg  # noqa: F401
    except (ImportError, OSError):  # OSError: the cairo C library is missing
        return False
    return True


def playwright_available() -> bool:
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        return False
    return True


def chromium_launch_options() -> list[dict]:
    """Ways to start a browser, tried in order: explicit path, Playwright's own build, Chrome, Edge."""
    options: list[dict] = []
    override = os.environ.get("AIEXPORT_CHROMIUM")
    if override:
        options.append({"executable_path": override})
    options += [{}, {"channel": "chrome"}, {"channel": "msedge"}]
    return options


def run(cmd: list[str], *, what: str, timeout: int = 300) -> None:
    """Run an external program and raise with its stderr when it fails."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"{what} 超时（{timeout}s）") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()[-2000:]
        raise RuntimeError(f"{what} 失败（退出码 {proc.returncode}）：{detail}")


def environment_report() -> str:
    """What this machine can do, with install hints for what is missing."""
    from .cmyk import find_cmyk_profile

    inkscape, gs, profile = find_inkscape(), find_ghostscript(), find_cmyk_profile()
    lines = [
        "SVG 渲染：",
        f"  Inkscape 1.x   {'✓ ' + inkscape_version(inkscape) if inkscape else '✗ 未找到（推荐安装：inkscape.org，SVG 还原度最高，自带转曲）'}",
        f"  Chromium       {'✓ playwright 已安装（实际能否启动浏览器在渲染时确认）' if playwright_available() else '✗ pip install playwright 后可用（也用于 HTML 源文件）'}",
        f"  cairosvg       {'✓' if cairosvg_available() else '✗ pip install cairosvg（需要系统 cairo 库）'}",
        "文字转曲：",
        f"  Ghostscript    {'✓ ' + ghostscript_version(gs) + '（' + gs + '）' if gs else '✗ 未找到（brew/apt install ghostscript，Windows 去 ghostscript.com 下载）'}",
        "CMYK 配置文件：",
        f"  {profile if profile else '✗ 未找到，将用简单公式换算；建议设置 AIEXPORT_CMYK_PROFILE 指向 Japan Color 2001 Coated 等 .icc 文件'}",
    ]
    return "\n".join(lines)
