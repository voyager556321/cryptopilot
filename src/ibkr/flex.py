"""IBKR Flex Web Service client — pull open positions into local snapshot."""

from __future__ import annotations

import os
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

import requests

from src.ibkr.portfolio import SYMBOL_TAGS, build_snapshot

# IB documents both hosts; try in order
SEND_URLS = [
    "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService/SendRequest",
    "https://gdcdyn.interactivebrokers.com/AccountManagement/FlexWebService/SendRequest",
    "https://www.interactivebrokers.com/Universal/servlet/FlexStatementService.SendRequest",
]
GET_URLS = [
    "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService/GetStatement",
    "https://gdcdyn.interactivebrokers.com/AccountManagement/FlexWebService/GetStatement",
    "https://www.interactivebrokers.com/Universal/servlet/FlexStatementService.GetStatement",
]

USER_AGENT = "TradingBot/1.0 (IBKR Flex sync; local dashboard)"


class FlexError(Exception):
    def __init__(self, message: str, *, code: Optional[str] = None):
        super().__init__(message)
        self.code = code


def flex_credentials_from_env() -> Dict[str, Optional[str]]:
    return {
        "token": (os.getenv("IBKR_FLEX_TOKEN") or "").strip() or None,
        "query_id": (
            os.getenv("IBKR_FLEX_QUERY_ID")
            or os.getenv("IBKR_FLEX_QUERY")
            or ""
        ).strip()
        or None,
        "account_id": (os.getenv("IBKR_ACCOUNT_ID") or "").strip() or None,
    }


def flex_configured() -> bool:
    c = flex_credentials_from_env()
    return bool(c["token"] and c["query_id"])


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    return s


def _parse_flex_error(root: ET.Element) -> Optional[Tuple[str, str]]:
    """Return (code, message) if this XML is a Flex error/status envelope."""
    status = (root.findtext("Status") or root.get("status") or "").strip()
    code = (root.findtext("ErrorCode") or root.findtext("Code") or "").strip()
    msg = (
        root.findtext("ErrorMessage")
        or root.findtext("Message")
        or root.findtext("errorMessage")
        or ""
    ).strip()
    tag = (root.tag or "").lower()
    if "flex" in tag and status.lower() in {"fail", "warn", "warning"}:
        return code or "fail", msg or status
    if code and status.lower() != "success":
        # 1019 = still generating; 1018 = rate limit — callers may retry
        return code, msg or status or "Flex error"
    if status.lower() == "fail":
        return code or "fail", msg or "Flex request failed"
    return None


def _send_request(token: str, query_id: str) -> Tuple[str, str]:
    """Returns (reference_code, get_url_hint)."""
    sess = _session()
    last_err: Optional[Exception] = None
    for base in SEND_URLS:
        try:
            r = sess.get(base, params={"t": token, "q": query_id, "v": "3"}, timeout=30)
            r.raise_for_status()
            root = ET.fromstring(r.content)
            err = _parse_flex_error(root)
            if err:
                code, msg = err
                raise FlexError(msg or "SendRequest failed", code=code)
            ref = (root.findtext("ReferenceCode") or "").strip()
            url_hint = (root.findtext("Url") or "").strip()
            status = (root.findtext("Status") or "").strip()
            if status.lower() != "success" or not ref:
                raise FlexError(
                    f"SendRequest unexpected response (status={status!r})",
                    code=status or None,
                )
            return ref, url_hint
        except FlexError:
            raise
        except Exception as e:
            last_err = e
            continue
    raise FlexError(f"SendRequest failed on all hosts: {last_err}")


def _get_statement(token: str, reference_code: str, url_hint: str = "") -> str:
    """Poll GetStatement until XML report (not status envelope) is ready."""
    sess = _session()
    bases = []
    if url_hint:
        bases.append(url_hint.split("?")[0])
    bases.extend(GET_URLS)

    last_err: Optional[Exception] = None
    for attempt in range(12):
        for base in bases:
            try:
                r = sess.get(
                    base,
                    params={"t": token, "q": reference_code, "v": "3"},
                    timeout=60,
                )
                r.raise_for_status()
                text = r.text
                # Try parse as status envelope first
                try:
                    root = ET.fromstring(r.content)
                except ET.ParseError:
                    return text  # raw non-xml? unlikely
                err = _parse_flex_error(root)
                if err:
                    code, msg = err
                    if code in {"1019", "1018"} or "generation in progress" in msg.lower():
                        last_err = FlexError(msg, code=code)
                        time.sleep(min(2 + attempt * 2, 15))
                        break  # retry outer attempt
                    raise FlexError(msg or "GetStatement failed", code=code)
                # Success path: FlexQueryResponse / FlexStatement with positions
                if root.find(".//OpenPosition") is not None or root.tag.endswith(
                    ("FlexQueryResponse", "FlexStatement")
                ):
                    return text
                # Some responses wrap deeper
                if "OpenPosition" in text or "CashReportCurrency" in text:
                    return text
                last_err = FlexError("Unexpected GetStatement XML shape")
            except FlexError as e:
                if e.code in {"1019", "1018"}:
                    last_err = e
                    time.sleep(min(2 + attempt * 2, 15))
                    break
                raise
            except Exception as e:
                last_err = e
                continue
        else:
            continue
    raise FlexError(f"GetStatement timed out / failed: {last_err}")


def _f(val: Any, default: float = 0.0) -> float:
    try:
        if val is None or val == "":
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def _clean_symbol(raw: str) -> str:
    s = (raw or "").strip().upper()
    # Strip exchange suffixes like CSPX.L / BRK B weirdness — keep primary token
    if " " in s:
        s = s.split()[0]
    if "." in s and not s.startswith("."):
        # Keep BRK.B style; strip .L/.AS listing suffixes of length 1-3
        left, right = s.rsplit(".", 1)
        if len(right) <= 3 and right.isalpha():
            s = left
    return s


def parse_flex_positions_xml(xml_text: str) -> Tuple[List[dict], float, Dict[str, Any]]:
    """
    Parse Flex Query XML → (positions[], cash_usd, meta).
    Expects an Activity/Open Positions style query with OpenPosition rows.
    """
    root = ET.fromstring(xml_text)
    positions: List[dict] = []
    meta: Dict[str, Any] = {
        "account_id": None,
        "from_date": None,
        "to_date": None,
        "open_position_count": 0,
    }

    # Account / statement meta
    for stmt in root.iter():
        if stmt.tag.endswith("FlexStatement"):
            meta["account_id"] = stmt.get("accountId") or meta["account_id"]
            meta["from_date"] = stmt.get("fromDate") or meta["from_date"]
            meta["to_date"] = stmt.get("toDate") or meta["to_date"]

    for el in root.iter():
        if not el.tag.endswith("OpenPosition"):
            continue
        # Skip options / futures for this stocks UI (assetCategory STK / ETF)
        cat = (el.get("assetCategory") or el.get("assetCategory") or "").upper()
        if cat and cat not in {"STK", "ETF", "FUND", ""}:
            # Still allow empty; skip OPT/FUT/CFD
            if cat in {"OPT", "FUT", "CFD", "CASH", "FX", "BILL", "BOND"}:
                continue

        sym = _clean_symbol(el.get("symbol") or el.get("underlyingSymbol") or "")
        if not sym:
            continue
        qty = _f(el.get("position") or el.get("quantity"))
        if abs(qty) < 1e-12:
            continue

        last = _f(
            el.get("markPrice")
            or el.get("closePrice")
            or el.get("marketPrice")
        )
        mv = _f(el.get("positionValue") or el.get("marketValue"))
        if not mv and last and qty:
            mv = abs(qty) * last
        cost_money = _f(el.get("costBasisMoney") or el.get("costBasis"))
        cost_price = _f(el.get("costBasisPrice") or el.get("averageCost"))
        if not cost_price and qty and cost_money:
            cost_price = abs(cost_money / qty)
        if not cost_money and cost_price and qty:
            cost_money = abs(qty) * cost_price

        unr = el.get("fifoPnlUnrealized") or el.get("unrealizedPnL")
        unr_f = _f(unr, default=mv - cost_money if cost_money else 0.0)

        name = el.get("description") or el.get("issuer") or sym
        positions.append({
            "symbol": sym,
            "name": name,
            "qty": abs(qty),
            "last": last,
            "avg_price": cost_price,
            "cost_basis": abs(cost_money),
            "market_value": abs(mv),
            "daily_pnl": 0.0,  # not in OpenPosition; leave 0
            "unrealized_pnl": unr_f,
            "tag": SYMBOL_TAGS.get(sym, "other"),
            "side": "short" if qty < 0 else "long",
        })

    meta["open_position_count"] = len(positions)

    # Cash: prefer BASE summary
    cash = 0.0
    cash_candidates: List[float] = []
    for el in root.iter():
        tag = el.tag
        if tag.endswith("CashReportCurrency") or tag.endswith("EquitySummaryByReportDateInBase"):
            cur = (el.get("currency") or el.get("currencyPrimary") or "").upper()
            ending = el.get("endingCash") or el.get("cash") or el.get("total")
            # EquitySummary uses total
            if tag.endswith("EquitySummaryByReportDateInBase"):
                # cash ≈ total - stock; skip here
                continue
            if ending is not None and ending != "":
                if cur in {"BASE", "USD", ""}:
                    cash_candidates.append(_f(ending))
        if tag.endswith("EquitySummaryInBase") or tag.endswith("AccountInformation"):
            pass

    if cash_candidates:
        cash = cash_candidates[-1]
    else:
        # Fallback: CashReport endingCash any USD row
        for el in root.iter():
            if el.tag.endswith("CashReportCurrency"):
                if (el.get("currency") or "").upper() == "USD":
                    cash = _f(el.get("endingCash"))
                    break

    return positions, cash, meta


def fetch_flex_snapshot(
    *,
    token: Optional[str] = None,
    query_id: Optional[str] = None,
) -> dict:
    """
    Full Flex pull → build_snapshot dict ready to save.
    Raises FlexError on config / API / parse failures.
    """
    creds = flex_credentials_from_env()
    token = (token or creds["token"] or "").strip()
    query_id = (query_id or creds["query_id"] or "").strip()
    if not token or not query_id:
        raise FlexError(
            "Set IBKR_FLEX_TOKEN and IBKR_FLEX_QUERY_ID in .env "
            "(Account Management → Reports → Flex Queries → Flex Web Service)."
        )

    ref, url_hint = _send_request(token, query_id)
    xml_text = _get_statement(token, ref, url_hint=url_hint)
    positions, cash, meta = parse_flex_positions_xml(xml_text)

    if not positions:
        raise FlexError(
            "Flex XML returned no OpenPosition rows. "
            "Check that your Flex Query includes Open Positions (STK/ETF) "
            "and date period covers today."
        )

    snap = build_snapshot(positions, cash_usd=cash, source="ibkr_flex")
    snap["flex"] = {
        "query_id": query_id,
        "reference_code": ref,
        "account_id": meta.get("account_id") or creds.get("account_id"),
        "from_date": meta.get("from_date"),
        "to_date": meta.get("to_date"),
        "positions_parsed": len(positions),
        "cash_usd": round(cash, 2),
    }
    snap["message"] = (
        f"Flex sync ok · {len(positions)} positions · cash ${cash:,.2f}"
    )
    return snap
