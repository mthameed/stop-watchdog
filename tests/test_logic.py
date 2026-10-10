"""Unit tests for the pure decision logic — no IBKR connection involved.
These are the tests that actually matter: get this wrong and the tool either
re-arms a stop it shouldn't (touching another bot's order) or fails to
re-arm one it should (the exact failure this tool exists to prevent)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stop_watchdog.logic import decide
from stop_watchdog.state import StopSnapshot


def snap(price=95.0, qty=100, order_type="STP", lmt=None, outside_rth=False):
    return StopSnapshot(order_type=order_type, aux_price=price, lmt_price=lmt,
                         qty=qty, outside_rth=outside_rth)


def test_no_position_no_state_does_nothing():
    result = decide(open_positions={}, live_stop_orders={}, known_state={})
    assert result.rearm == []
    assert result.update == {}
    assert result.forget == []


def test_open_position_with_live_stop_learns_it():
    """First time this tool ever sees a stop for a position, it should just
    remember it (update), not re-arm anything — nothing is wrong yet."""
    result = decide(
        open_positions={"AAPL": 100},
        live_stop_orders={"AAPL": snap(95.0)},
        known_state={},
    )
    assert result.rearm == []
    assert result.update == {"AAPL": snap(95.0)}
    assert result.forget == []


def test_open_position_no_live_stop_never_seen_before_does_not_invent_one():
    """No live stop AND no prior known-good snapshot — must NOT re-arm.
    Could be a strategy that intentionally doesn't use stops."""
    result = decide(
        open_positions={"AAPL": 100},
        live_stop_orders={},
        known_state={},
    )
    assert result.rearm == []


def test_stop_vanished_while_position_still_open_triggers_rearm():
    """The core scenario this whole tool exists for: a stop that was
    previously seen live has disappeared while the position is still open."""
    result = decide(
        open_positions={"AAPL": 100},
        live_stop_orders={},
        known_state={"AAPL": snap(95.0)},
    )
    assert result.rearm == ["AAPL"]
    assert result.forget == []


def test_position_closed_forgets_tracking_without_rearm():
    result = decide(
        open_positions={},
        live_stop_orders={},
        known_state={"AAPL": snap(95.0)},
    )
    assert result.rearm == []
    assert result.forget == ["AAPL"]


def test_trailed_stop_price_change_updates_known_snapshot():
    """The user's own bot trails the stop up over time — the watchdog should
    just track the new level, not treat a moved (but still live) stop as
    anything wrong."""
    result = decide(
        open_positions={"AAPL": 100},
        live_stop_orders={"AAPL": snap(97.0)},
        known_state={"AAPL": snap(95.0)},
    )
    assert result.rearm == []
    assert result.update == {"AAPL": snap(97.0)}


def test_unchanged_live_stop_produces_no_update_noise():
    result = decide(
        open_positions={"AAPL": 100},
        live_stop_orders={"AAPL": snap(95.0)},
        known_state={"AAPL": snap(95.0)},
    )
    assert result.update == {}
    assert result.rearm == []
    assert result.forget == []


def test_multiple_symbols_handled_independently():
    """AAPL has a live stop never seen before (gets learned), MSFT's known
    stop has vanished (gets re-armed), TSLA is flat (gets forgotten) — three
    symbols, three different outcomes, none should bleed into another."""
    result = decide(
        open_positions={"AAPL": 100, "MSFT": 50, "TSLA": 0},
        live_stop_orders={"AAPL": snap(95.0)},
        known_state={"MSFT": snap(300.0), "TSLA": snap(200.0)},
    )
    assert result.rearm == ["MSFT"]
    assert result.forget == ["TSLA"]
    assert result.update == {"AAPL": snap(95.0)}


def test_stop_limit_snapshot_round_trips_through_equality():
    a = snap(order_type="STP LMT", price=95.0, lmt=93.1)
    b = snap(order_type="STP LMT", price=95.0, lmt=93.1)
    assert a == b
    result = decide(
        open_positions={"AAPL": 100},
        live_stop_orders={"AAPL": b},
        known_state={"AAPL": a},
    )
    assert result.update == {}


def run_all():
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    run_all()
