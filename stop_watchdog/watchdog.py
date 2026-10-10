"""The run loop: poll IBKR, run the pure decision logic, report what it
finds. This is Stop Watchdog FREE -- it watches one position and tells you
when its protective stop has vanished. It does not, and architecturally
cannot, place an order to fix it -- Broker in this package has no rearm()
method at all. See README.md for the full free-vs-pro comparison.

Synchronous throughout -- ibapi's own client is callback/thread-based, not
asyncio-based."""
from __future__ import annotations
import logging
import time
from dataclasses import dataclass
from pathlib import Path

from .broker import Broker
from .state import StateStore
from .logic import decide

log = logging.getLogger("stop_watchdog")

PRO_INFO = "Stop Watchdog (Pro) re-arms this automatically and watches your whole portfolio: https://algovigil.gumroad.com/l/stop-watchdog"


@dataclass
class WatchdogConfig:
    host: str = "127.0.0.1"
    port: int = 7497
    client_id: int = 99
    poll_interval_sec: int = 30
    state_file: Path = Path("stop_watchdog_state.json")


class Watchdog:
    def __init__(self, cfg: WatchdogConfig):
        self.cfg = cfg
        self.broker = Broker(cfg.client_id)
        self.state = StateStore(cfg.state_file)

    def connect(self) -> None:
        self.broker.connect(self.cfg.host, self.cfg.port)
        log.info("Connected to IBKR at %s:%d as clientId=%d",
                 self.cfg.host, self.cfg.port, self.cfg.client_id)
        if not self.broker.is_paper_account():
            # Fails loud and immediately, before reading any real positions.
            # Free tier is paper-only -- not a soft suggestion, a hard
            # requirement, since this package can't act on what it finds
            # even on paper, let alone be trusted unverified on a live
            # account.
            self.broker.disconnect()
            raise RuntimeError(
                "Stop Watchdog (Free) only runs against IBKR paper trading accounts "
                f"(account must start with 'DU'). {PRO_INFO}")

    def run_forever(self) -> None:
        self.connect()
        while True:
            try:
                self.run_once()
            except Exception:
                log.exception("Watchdog cycle failed -- will retry next interval.")
            time.sleep(self.cfg.poll_interval_sec)

    def run_once(self) -> None:
        positions = self.broker.open_positions()
        live_stops = self.broker.live_stop_orders()
        known = {sym: snap for sym in self.state.symbols()
                 if (snap := self.state.get(sym)) is not None}

        # Hard single-position cap -- not a config option, this build only
        # ever watches one symbol. decide() still sees the FULL real
        # position picture so forget/close-detection stays accurate for
        # the watched symbol; the cap only decides which one gets learned.
        result = decide(positions, live_stops, known)

        for symbol in result.forget:
            log.info("[%s] position closed -- no longer tracking.", symbol)
            self.state.clear(symbol)

        watched = self._watched_symbol(positions, known, live_stops)

        for symbol, snapshot in result.update.items():
            if symbol != watched:
                continue
            self.state.set(symbol, snapshot)

        for symbol in result.rearm:
            if symbol != watched:
                log.warning("[%s] also needs attention but Free only watches one "
                            "position at a time (currently %s). %s", symbol, watched, PRO_INFO)
                continue
            log.warning("[%s] OPEN POSITION WITH NO LIVE STOP. Free tier cannot "
                        "re-arm it automatically -- you need to do this yourself. %s",
                        symbol, PRO_INFO)

    def _watched_symbol(self, positions: dict[str, int], known: dict,
                         live_stops: dict) -> str | None:
        """Deterministic choice (sorted), not dict-iteration order, so which
        single symbol is covered doesn't silently shift cycle to cycle.
        Priority: (1) a symbol already being tracked, so it doesn't keep
        hopping to a different one every cycle; (2) failing that, a symbol
        with a live stop right now, so there's actually something to learn
        this cycle rather than picking an arbitrary position with nothing
        to do yet; (3) failing that, just the first open position."""
        in_scope_known = sorted(set(positions) & set(known))
        if in_scope_known:
            return in_scope_known[0]
        learnable = sorted(set(positions) & set(live_stops))
        if learnable:
            return learnable[0]
        return sorted(positions)[0] if positions else None
