import os
import sys
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "2")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:  # 允许未安装时直接运行 pytest
    sys.path.insert(0, str(SRC))

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def replay_config_path(repo_root: Path) -> Path:
    return repo_root / "configs" / "replay_synthetic.yaml"
