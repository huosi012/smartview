"""旺店通开放平台客户端，支持企业版（openapi2）和旗舰版（openapi）。

两个版本的签名、分页和返回结构都不一样，这里统一成：
  iter_refunds(start, end) -> 逐条返回退换单原始 dict
  get_trade(trade_no)      -> 返回订单原始 dict（找不到为 None）
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterator, List, Mapping, Optional

from .config import ENTERPRISE, Config

log = logging.getLogger(__name__)

# 旺店通的时间参数都是北京时间，跟运行机器的时区无关
CST = timezone(timedelta(hours=8))
# 旗舰版 timestamp = 当前秒数 - 2012-01-01 00:00:00(+08:00)
ULTIMATE_EPOCH = 1325347200

# (url, body, headers) -> 响应体
Transport = Callable[[str, bytes, Dict[str, str]], bytes]


class WdtError(RuntimeError):
    pass


def http_post(url: str, body: bytes, headers: Dict[str, str], timeout: float = 30) -> bytes:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def format_wdt_time(dt: datetime) -> str:
    return dt.astimezone(CST).strftime("%Y-%m-%d %H:%M:%S")


def sign_enterprise(params: Mapping[str, Any], appsecret: str) -> str:
    """企业版签名：键名正序，每项拼成 `键长(2位)-键:值长(4位)-值`，用 ; 连接，末尾拼 appsecret 后 md5。"""
    parts = []
    for key in sorted(params):
        if key == "sign":
            continue
        value = str(params[key])
        parts.append("%02d-%s:%04d-%s" % (len(key), key, len(value), value))
    return hashlib.md5((";".join(parts) + appsecret).encode("utf-8")).hexdigest()


def sign_ultimate(params: Mapping[str, Any], secret: str) -> str:
    """旗舰版签名：md5(secret + 键名正序拼接的 键值键值... + secret)，body 参与签名。"""
    content = "".join(key + str(params[key]) for key in sorted(params) if key != "sign")
    return hashlib.md5((secret + content + secret).encode("utf-8")).hexdigest()


def _is_rate_limited(message: str) -> bool:
    return any(word in message for word in ("频率", "频繁", "too many", "Too Many"))


class _BaseClient:
    max_attempts = 3

    def __init__(
        self,
        sid: str,
        appkey: str,
        appsecret: str,
        base_url: str,
        page_size: int = 50,
        transport: Optional[Transport] = None,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.sid = sid
        self.appkey = appkey
        self.appsecret = appsecret
        self.base_url = base_url
        self.page_size = page_size
        self.transport = transport or http_post
        self.clock = clock
        self.sleep = sleep

    def _post_json(self, url: str, body: bytes, headers: Dict[str, str]) -> Dict[str, Any]:
        last_error: Optional[Exception] = None
        for attempt in range(self.max_attempts):
            if attempt:
                self.sleep(2 ** attempt)
            try:
                raw = self.transport(url, body, headers)
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                last_error = e
                log.warning("请求旺店通失败（第 %d 次）：%s", attempt + 1, e)
                continue
            try:
                return json.loads(raw.decode("utf-8"))
            except ValueError:
                raise WdtError("旺店通返回的不是 JSON：%r" % raw[:200]) from None
        raise WdtError("请求旺店通失败：%s" % last_error)

    def iter_refunds(self, start: datetime, end: datetime) -> Iterator[Dict[str, Any]]:
        raise NotImplementedError

    def get_trade(self, trade_no: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError


class EnterpriseClient(_BaseClient):
    """旺店通·企业版：POST 表单到 {base}/{接口}.php，返回 {"code": 0, ...}。"""

    def call(self, endpoint: str, params: Mapping[str, Any]) -> Dict[str, Any]:
        url = self.base_url.rstrip("/") + "/" + endpoint
        for attempt in range(self.max_attempts):
            data = {key: str(value) for key, value in params.items()}
            data["sid"] = self.sid
            data["appkey"] = self.appkey
            data["timestamp"] = str(int(self.clock()))
            data["sign"] = sign_enterprise(data, self.appsecret)
            resp = self._post_json(
                url,
                urllib.parse.urlencode(data).encode("utf-8"),
                {"Content-Type": "application/x-www-form-urlencoded; charset=utf-8"},
            )
            code = resp.get("code")
            if str(code) == "0":
                return resp
            message = str(resp.get("message", ""))
            if _is_rate_limited(message) and attempt + 1 < self.max_attempts:
                log.warning("旺店通限流，稍后重试：%s", message)
                self.sleep(3 * (attempt + 1))
                continue
            raise WdtError("%s 返回错误 code=%s message=%s" % (endpoint, code, message))
        raise AssertionError("unreachable")

    def iter_refunds(self, start: datetime, end: datetime) -> Iterator[Dict[str, Any]]:
        page_no = 0
        while True:
            resp = self.call(
                "refund_query.php",
                {
                    "start_time": format_wdt_time(start),
                    "end_time": format_wdt_time(end),
                    "page_size": self.page_size,
                    "page_no": page_no,
                },
            )
            refunds = resp.get("refunds") or []
            yield from refunds
            total = int(resp.get("total_count") or 0)
            page_no += 1
            if len(refunds) < self.page_size or (total and page_no * self.page_size >= total):
                return

    def get_trade(self, trade_no: str) -> Optional[Dict[str, Any]]:
        resp = self.call("trade_query.php", {"trade_no": trade_no, "page_size": 1, "page_no": 0})
        trades = resp.get("trades") or []
        return trades[0] if trades else None


class UltimateClient(_BaseClient):
    """旺店通·旗舰版：业务参数放 JSON body，公共参数放 URL，返回 {"status": 0, "data": {...}}。"""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.secret, _, self.salt = self.appsecret.partition(":")

    def call(
        self, method: str, body: Mapping[str, Any], page_no: Optional[int] = None
    ) -> Dict[str, Any]:
        body_json = json.dumps([body], ensure_ascii=False, separators=(",", ":"))
        sep = "&" if "?" in self.base_url else "?"
        for attempt in range(self.max_attempts):
            params = {
                "sid": self.sid,
                "key": self.appkey,
                "salt": self.salt,
                "method": method,
                "v": "1.0",
                "timestamp": str(int(self.clock()) - ULTIMATE_EPOCH),
            }
            if page_no is not None:
                params.update(page_size=str(self.page_size), page_no=str(page_no), calc_total="1")
            params["sign"] = sign_ultimate(dict(params, body=body_json), self.secret)
            resp = self._post_json(
                self.base_url + sep + urllib.parse.urlencode(params),
                body_json.encode("utf-8"),
                {"Content-Type": "application/json; charset=utf-8"},
            )
            status = resp.get("status")
            if str(status) == "0":
                return resp
            message = str(resp.get("message", ""))
            if _is_rate_limited(message) and attempt + 1 < self.max_attempts:
                log.warning("旺店通限流，稍后重试：%s", message)
                self.sleep(3 * (attempt + 1))
                continue
            raise WdtError("%s 返回错误 status=%s message=%s" % (method, status, message))
        raise AssertionError("unreachable")

    def iter_refunds(self, start: datetime, end: datetime) -> Iterator[Dict[str, Any]]:
        body = {"modified_from": format_wdt_time(start), "modified_to": format_wdt_time(end)}
        page_no = 0
        while True:
            resp = self.call("aftersales.refund.Refund.search", body, page_no=page_no)
            data = resp.get("data") or {}
            refunds: List[Dict[str, Any]] = data.get("order") or []
            yield from refunds
            total = int(data.get("total_count") or 0)
            page_no += 1
            if len(refunds) < self.page_size or (total and page_no * self.page_size >= total):
                return

    def get_trade(self, trade_no: str) -> Optional[Dict[str, Any]]:
        resp = self.call("sales.TradeQuery.queryWithDetail", {"trade_no": trade_no}, page_no=0)
        trades = (resp.get("data") or {}).get("order") or []
        return trades[0] if trades else None


def make_client(cfg: Config, **kwargs: Any) -> _BaseClient:
    cls = EnterpriseClient if cfg.wdt_edition == ENTERPRISE else UltimateClient
    return cls(
        cfg.wdt_sid,
        cfg.wdt_appkey,
        cfg.wdt_appsecret,
        cfg.wdt_base_url,
        page_size=cfg.wdt_page_size,
        **kwargs,
    )
