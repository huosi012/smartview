"""把企业版 / 旗舰版退换单的原始字段统一成 Refund，并判断是否属于"发货后退款"。

两个版本字段名不完全一致，这里每个字段按候选键名依次取第一个有值的。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional

from .config import Config
from .wdt import CST

TYPE_NAMES = {1: "售前退款", 2: "退货", 3: "换货", 4: "退款不退货", 6: "保价退款", 7: "批发退货退款"}
# 推送卡片标题用的叫法
TYPE_LABELS = {1: "售前退款", 2: "退货退款", 3: "换货", 4: "已发货仅退款", 6: "保价退款", 7: "批发退货退款"}
PRESALE_SHIPPED_LABEL = "退款时订单已发货"
# 只收录确认过的处理状态，其他状态直接显示数字
PROCESS_STATUS_NAMES = {"10": "已取消", "20": "待审核", "30": "已同意", "90": "已完成"}
CANCELLED_STATUS = "10"
# 订单状态 >= 95 表示已发货（95已发货 100已签收 105部分打款 110已完成）
TRADE_SHIPPED_STATUS = 95


def _first(data: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def _text(data: Mapping[str, Any], *keys: str) -> str:
    value = _first(data, *keys)
    return "" if value is None else str(value).strip()


def _number(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_time(value: Any) -> Optional[datetime]:
    """支持 '2024-01-01 12:00:00'、秒级或毫秒级时间戳，统一成北京时间。"""
    if value in (None, ""):
        return None
    number = _number(value)
    if number is not None and number > 0:
        if number > 1e12:
            number /= 1000
        return datetime.fromtimestamp(number, CST)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value).strip(), fmt).replace(tzinfo=CST)
        except ValueError:
            continue
    return None


def format_time(value: Any) -> str:
    dt = parse_time(value)
    if dt is None:
        return "" if value in (None, "") else str(value)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class RefundItem:
    name: str
    spec: str
    sku: str
    num: Optional[float]


@dataclass
class Refund:
    refund_no: str
    type_code: Optional[int]
    shop_no: str
    shop_name: str
    tid: str
    trade_no: str
    buyer: str
    amount: Optional[float]
    reason: str
    remark: str
    process_status: str
    return_logistics: str
    created: str
    modified: str
    created_at: Optional[datetime]
    items: List[RefundItem] = field(default_factory=list)

    @property
    def type_name(self) -> str:
        if self.type_code is None:
            return "未知"
        return TYPE_NAMES.get(self.type_code, "类型%d" % self.type_code)

    @property
    def status_name(self) -> str:
        if not self.process_status:
            return ""
        name = PROCESS_STATUS_NAMES.get(self.process_status)
        return "%s(%s)" % (name, self.process_status) if name else self.process_status

    @property
    def first_trade_no(self) -> str:
        return self.trade_no.replace("，", ",").split(",")[0].strip()


def _items(raw: Mapping[str, Any]) -> List[RefundItem]:
    rows = _first(raw, "refund_order_list", "detail_list", "order_list", "goods_list") or []
    items = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, Mapping):
            continue
        items.append(
            RefundItem(
                name=_text(row, "goods_name", "api_goods_name", "suite_name"),
                spec=_text(row, "spec_name", "api_spec_name"),
                sku=_text(row, "spec_no", "merchant_no", "goods_no"),
                num=_number(_first(row, "refund_num", "num")),
            )
        )
    return items


def _amount(raw: Mapping[str, Any]) -> Optional[float]:
    for key in ("refund_amount", "guarantee_refund_amount", "actual_refund_amount", "refund_total_amount"):
        number = _number(raw.get(key))
        if number:
            return number
    return None


def normalize(raw: Mapping[str, Any]) -> Refund:
    type_code = _number(_first(raw, "type", "refund_type"))
    created_raw = _first(raw, "created", "refund_time", "create_time")
    return Refund(
        refund_no=_text(raw, "refund_no"),
        type_code=int(type_code) if type_code is not None else None,
        shop_no=_text(raw, "shop_no"),
        shop_name=_text(raw, "shop_name", "shop_no"),
        tid=_text(raw, "tid", "src_tids", "tid_list", "src_tid"),
        trade_no=_text(raw, "trade_no", "trade_no_list", "sales_trade_no"),
        buyer=_text(raw, "buyer_nick", "customer_name", "receiver_name"),
        amount=_amount(raw),
        reason=_text(raw, "refund_reason", "reason_name", "reason"),
        remark=_text(raw, "remark"),
        process_status=_text(raw, "process_status"),
        return_logistics=" ".join(
            part
            for part in (
                _text(raw, "return_logistics_name", "logistics_name"),
                _text(raw, "return_logistics_no", "logistics_no"),
            )
            if part
        ),
        created=format_time(created_raw),
        modified=format_time(_first(raw, "modified_date", "modified")),
        created_at=parse_time(created_raw),
        items=_items(raw),
    )


def is_trade_shipped(trade: Optional[Mapping[str, Any]]) -> bool:
    if not trade:
        return False
    status = _number(_first(trade, "trade_status", "status"))
    return status is not None and status >= TRADE_SHIPPED_STATUS


class RefundFilter:
    """决定一张退换单要不要推送，要推送时返回卡片标题用的分类名。"""

    def __init__(
        self,
        cfg: Config,
        trade_lookup: Optional[Callable[[str], Optional[Mapping[str, Any]]]] = None,
        now: Callable[[], datetime] = lambda: datetime.now(CST),
    ):
        self.cfg = cfg
        self.trade_lookup = trade_lookup
        self.now = now

    def classify(self, refund: Refund) -> Optional[str]:
        cfg = self.cfg
        if cfg.shop_nos and refund.shop_no not in cfg.shop_nos:
            return None
        if cfg.skip_cancelled and refund.process_status == CANCELLED_STATUS:
            return None
        if cfg.max_refund_age_hours > 0 and refund.created_at is not None:
            if self.now() - refund.created_at > timedelta(hours=cfg.max_refund_age_hours):
                return None
        if refund.type_code in cfg.refund_types:
            return TYPE_LABELS.get(refund.type_code, refund.type_name)
        if (
            cfg.check_presale_shipped
            and refund.type_code == 1
            and self.trade_lookup is not None
            and refund.first_trade_no
            and is_trade_shipped(self.trade_lookup(refund.first_trade_no))
        ):
            return PRESALE_SHIPPED_LABEL
        return None


def summarize(refunds: Iterable[Refund]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for refund in refunds:
        counts[refund.type_name] = counts.get(refund.type_name, 0) + 1
    return counts
