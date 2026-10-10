"""Thin, READ-ONLY wrapper around IBKR's own native `ibapi` package.

This is the free tier's broker interface -- deliberately, architecturally
incapable of placing an order. There is no rearm() method, no Order import,
nothing here a user could re-enable by flipping a config value: the
capability to act simply does not exist in this codebase. Stop Watchdog
Pro (a separate, paid package) is what actually re-arms a vanished stop --
this free tier only detects and logs one, the same way a smoke detector
doesn't put out the fire itself.
"""
from __future__ import annotations
import logging
import threading
from typing import Optional

from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from .state import StopSnapshot

log = logging.getLogger("stop_watchdog")

STOP_ORDER_TYPES = {"STP", "STP LMT"}
DONE_STATES = {"Filled", "Cancelled", "ApiCancelled", "Inactive"}

# Informational "farm connection OK" style notices ibapi reports through
# the same error() callback as real problems -- not worth logging loudly.
_BENIGN_CODES = {2104, 2106, 2107, 2108, 2119, 2158, 10167}


class _App(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.connected_event = threading.Event()
        self.positions_done = threading.Event()
        self.orders_done = threading.Event()
        self.positions: dict[str, float] = {}
        self.open_orders: dict[int, dict] = {}  # orderId -> {contract, order, status}
        self.account_ids: list[str] = []

    # --- connection lifecycle ----------------------------------------------
    def nextValidId(self, orderId: int):
        self.connected_event.set()

    def managedAccounts(self, accountsList: str):
        # Fires once, shortly after connect -- the standard ibapi way to
        # learn which account(s) this client is authorized for. IBKR paper
        # accounts are always "DU"-prefixed; live accounts never are -- a
        # real, documented signal, not a guess.
        self.account_ids = [a.strip() for a in accountsList.split(",") if a.strip()]

    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        if errorCode not in _BENIGN_CODES:
            log.warning("IBKR error reqId=%s code=%s msg=%s", reqId, errorCode, errorString)

    # --- positions -----------------------------------------------------------
    def position(self, account, contract, position, avgCost):
        if position != 0:
            self.positions[contract.symbol] = position
        elif contract.symbol in self.positions:
            del self.positions[contract.symbol]

    def positionEnd(self):
        self.positions_done.set()

    # --- open orders -----------------------------------------------------------
    def openOrder(self, orderId, contract, order, orderState):
        self.open_orders[orderId] = {"contract": contract, "order": order, "status": orderState.status}

    def orderStatus(self, orderId, status, filled, remaining, avgFillPrice,
                     permId, parentId, lastFillPrice, clientId, whyHeld, mktCapPrice):
        if orderId in self.open_orders:
            self.open_orders[orderId]["status"] = status

    def openOrderEnd(self):
        self.orders_done.set()


class Broker:
    def __init__(self, client_id: int):
        self.client_id = client_id
        self.app = _App()

    def connect(self, host: str, port: int, timeout: float = 15.0) -> None:
        self.app.connect(host, port, self.client_id)
        thread = threading.Thread(target=self.app.run, daemon=True)
        thread.start()
        if not self.app.connected_event.wait(timeout):
            raise TimeoutError(f"Could not connect to IBKR at {host}:{port} (clientId={self.client_id})")

    def disconnect(self) -> None:
        self.app.disconnect()

    def is_paper_account(self) -> bool:
        """IBKR paper accounts are always "DU"-prefixed (e.g. DUQ356263);
        live accounts never are. Treated as NOT paper if nothing has
        arrived yet (fail closed, never fail open on a safety check)."""
        return bool(self.app.account_ids) and all(
            a.startswith("DU") for a in self.app.account_ids)

    def open_positions(self) -> dict[str, int]:
        """Long-share positions only -- matches the sell-stop-only scope
        this tool covers, see README's known limitations."""
        self.app.positions.clear()
        self.app.positions_done.clear()
        self.app.reqPositions()
        self.app.positions_done.wait(10)
        self.app.cancelPositions()
        return {sym: int(qty) for sym, qty in self.app.positions.items() if qty > 0}

    def live_stop_orders(self) -> dict[str, StopSnapshot]:
        """CLIENT-ID SCOPED, deliberately. reqAllOpenOrders() returns every
        client's open orders on a shared IBKR account, so filtering to
        self.client_id here is what stops this tool from ever reporting on
        a stop that's actually protecting a different bot's position."""
        self.app.open_orders.clear()
        self.app.orders_done.clear()
        self.app.reqAllOpenOrders()
        self.app.orders_done.wait(10)

        result: dict[str, StopSnapshot] = {}
        for entry in self.app.open_orders.values():
            order = entry["order"]
            contract = entry["contract"]
            if order.clientId != self.client_id:
                continue
            if order.action != "SELL" or order.orderType not in STOP_ORDER_TYPES:
                continue
            if entry["status"] in DONE_STATES:
                continue
            result[contract.symbol] = StopSnapshot(
                order_type=order.orderType,
                aux_price=order.auxPrice,
                lmt_price=order.lmtPrice if order.orderType == "STP LMT" else None,
                qty=int(order.totalQuantity),
                outside_rth=bool(order.outsideRth),
            )
        return result
