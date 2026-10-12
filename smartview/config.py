"""配置：全部从环境变量读取，可选从 .env 文件加载。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Mapping, Optional

ENTERPRISE = "enterprise"  # 旺店通·企业版（openapi2，接口名如 refund_query.php）
ULTIMATE = "ultimate"  # 旺店通·旗舰版（openapi，接口名如 aftersales.refund.Refund.search）

DEFAULT_BASE_URLS = {
    ENTERPRISE: "https://api.wangdian.cn/openapi2/",
    ULTIMATE: "http://wdt.wangdian.cn/openapi",
}


class ConfigError(ValueError):
    pass


def load_dotenv(path: str = ".env") -> None:
    """极简 .env 解析：KEY=VALUE，忽略注释和空行；已存在的环境变量优先。"""
    p = Path(path)
    if not p.is_file():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _bool(value: Optional[str], default: bool) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "y", "on")


def _int(env: Mapping[str, str], key: str, default: int) -> int:
    value = env.get(key, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        raise ConfigError(f"{key} 必须是整数，当前为 {value!r}") from None


def _list(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.replace("，", ",").split(",") if item.strip()]


@dataclass
class Config:
    wdt_edition: str
    wdt_sid: str
    wdt_appkey: str
    wdt_appsecret: str
    wdt_base_url: str
    feishu_webhook: str
    feishu_secret: str = ""
    feishu_at: List[str] = field(default_factory=list)
    wdt_page_size: int = 50
    wdt_window_minutes: int = 60
    refund_types: List[int] = field(default_factory=lambda: [2, 4])
    check_presale_shipped: bool = False
    shop_nos: List[str] = field(default_factory=list)
    skip_cancelled: bool = True
    max_refund_age_hours: int = 72
    poll_interval_seconds: int = 300
    initial_lookback_minutes: int = 60
    overlap_minutes: int = 10
    state_db: str = "data/state.db"

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "Config":
        env = os.environ if env is None else env
        edition = env.get("WDT_EDITION", ENTERPRISE).strip().lower() or ENTERPRISE
        if edition not in DEFAULT_BASE_URLS:
            raise ConfigError("WDT_EDITION 只能是 enterprise（企业版）或 ultimate（旗舰版）")

        try:
            refund_types = [int(t) for t in _list(env.get("REFUND_TYPES") or "2,4")]
        except ValueError:
            raise ConfigError("REFUND_TYPES 必须是逗号分隔的数字，例如 2,4") from None

        cfg = cls(
            wdt_edition=edition,
            wdt_sid=env.get("WDT_SID", "").strip(),
            wdt_appkey=env.get("WDT_APPKEY", "").strip(),
            wdt_appsecret=env.get("WDT_APPSECRET", "").strip(),
            wdt_base_url=env.get("WDT_BASE_URL", "").strip() or DEFAULT_BASE_URLS[edition],
            feishu_webhook=env.get("FEISHU_WEBHOOK", "").strip(),
            feishu_secret=env.get("FEISHU_SECRET", "").strip(),
            feishu_at=_list(env.get("FEISHU_AT")),
            wdt_page_size=_int(env, "WDT_PAGE_SIZE", 50),
            wdt_window_minutes=_int(env, "WDT_WINDOW_MINUTES", 60),
            refund_types=refund_types,
            check_presale_shipped=_bool(env.get("CHECK_PRESALE_SHIPPED"), False),
            shop_nos=_list(env.get("SHOP_NOS")),
            skip_cancelled=_bool(env.get("SKIP_CANCELLED"), True),
            max_refund_age_hours=_int(env, "MAX_REFUND_AGE_HOURS", 72),
            poll_interval_seconds=_int(env, "POLL_INTERVAL_SECONDS", 300),
            initial_lookback_minutes=_int(env, "INITIAL_LOOKBACK_MINUTES", 60),
            overlap_minutes=_int(env, "OVERLAP_MINUTES", 10),
            state_db=env.get("STATE_DB", "").strip() or "data/state.db",
        )
        if cfg.wdt_window_minutes <= 0:
            raise ConfigError("WDT_WINDOW_MINUTES 必须大于 0")
        if cfg.wdt_page_size <= 0:
            raise ConfigError("WDT_PAGE_SIZE 必须大于 0")
        return cfg

    def require_wdt(self) -> None:
        missing = [
            name
            for name, value in (
                ("WDT_SID", self.wdt_sid),
                ("WDT_APPKEY", self.wdt_appkey),
                ("WDT_APPSECRET", self.wdt_appsecret),
            )
            if not value
        ]
        if missing:
            raise ConfigError("缺少旺店通配置：" + ", ".join(missing))
        if self.wdt_edition == ULTIMATE and ":" not in self.wdt_appsecret:
            raise ConfigError("旗舰版 WDT_APPSECRET 格式应为 secret:salt")

    def require_feishu(self) -> None:
        if not self.feishu_webhook:
            raise ConfigError("缺少飞书配置：FEISHU_WEBHOOK")
