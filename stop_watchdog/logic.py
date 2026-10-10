"""Pure decision logic: given what's true right now (open positions, live
protective stop orders) and what was last known to be true (state store),
decide which symbols need a stop re-armed and which are safe to stop
tracking.

Identical to the decision logic in the paid Stop Watchdog (Pro) -- this part
isn't the commercial value, the automated execution is. No IBKR I/O here
on purpose: a plain function, unit testable with made-up data, no broker
connection required."""
from __future__ import annotations
from dataclasses import dataclass
from .state import StopSnapshot


@dataclass
class Decision:
    rearm: list[str]                  # symbols that need a fresh stop placed
    update: dict[str, StopSnapshot]   # symbols whose known-good snapshot should be refreshed
    forget: list[str]                 # symbols no longer open, drop from tracking


def decide(
    open_positions: dict[str, int],
    live_stop_orders: dict[str, StopSnapshot],
    known_state: dict[str, StopSnapshot],
) -> Decision:
    rearm: list[str] = []
    update: dict[str, StopSnapshot] = {}
    forget: list[str] = []

    tracked_symbols = set(known_state) | set(live_stop_orders)
    for symbol in tracked_symbols:
        if open_positions.get(symbol, 0) <= 0:
            forget.append(symbol)

    for symbol, qty in open_positions.items():
        if qty <= 0:
            continue
        live = live_stop_orders.get(symbol)
        if live is not None:
            if known_state.get(symbol) != live:
                update[symbol] = live
            continue
        if symbol in known_state:
            rearm.append(symbol)

    return Decision(rearm=rearm, update=update, forget=forget)
