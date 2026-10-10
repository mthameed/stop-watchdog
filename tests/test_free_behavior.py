"""Unit tests for Stop Watchdog Free's specific restrictions: the hard
single-position cap, the hard paper-account-only enforcement, and
confirming the "no re-arm capability" guarantee is architectural, not just
behavioral. No real IBKR connection involved -- a FakeBroker stands in."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stop_watchdog.watchdog import Watchdog, WatchdogConfig
from stop_watchdog.state import StopSnapshot
from stop_watchdog.broker import Broker


def snap(price=95.0, qty=100):
    return StopSnapshot(order_type="STP", aux_price=price, lmt_price=None, qty=qty, outside_rth=False)


class FakeBroker:
    def __init__(self, paper=True, positions=None, live_stops=None):
        self._paper = paper
        self._positions = positions or {}
        self._live_stops = live_stops or {}

    def connect(self, host, port):
        pass

    def disconnect(self):
        pass

    def is_paper_account(self):
        return self._paper

    def open_positions(self):
        return dict(self._positions)

    def live_stop_orders(self):
        return dict(self._live_stops)


def _watchdog(paper=True, positions=None, live_stops=None):
    cfg = WatchdogConfig(state_file=Path(tempfile.mktemp()))
    wd = Watchdog(cfg)
    wd.broker = FakeBroker(paper=paper, positions=positions, live_stops=live_stops)
    return wd


def test_broker_has_no_rearm_method_at_all():
    """The real guarantee this whole package relies on: not a permission
    check, an actual absence. If this test ever fails, someone added
    order-placement capability back into the free tier by mistake."""
    assert not hasattr(Broker, "rearm"), "Free tier Broker must never have a rearm() method"


def test_refuses_a_live_account():
    wd = _watchdog(paper=False)
    try:
        wd.connect()
        assert False, "should have raised RuntimeError for a non-paper account"
    except RuntimeError as e:
        assert "paper" in str(e).lower()


def test_allows_a_paper_account():
    wd = _watchdog(paper=True)
    wd.connect()  # must not raise


def test_only_learns_one_symbol_preferring_already_known_one():
    wd = _watchdog(positions={"AAPL": 100, "MSFT": 50},
                    live_stops={"AAPL": snap(), "MSFT": snap()})
    wd.state.set("MSFT", snap())  # MSFT already being tracked from a prior cycle
    wd.run_once()
    # MSFT was already known, so it stays the watched symbol even though
    # AAPL is alphabetically first -- AAPL must not get learned instead.
    assert wd.state.get("MSFT") is not None
    assert wd.state.get("AAPL") is None


def test_fresh_start_picks_the_symbol_with_a_live_stop_to_actually_learn():
    # Nothing known yet. AAPL has no live stop (nothing learnable there
    # this cycle); MSFT does. Must pick MSFT, not just alphabetical AAPL,
    # or it would learn nothing at all this cycle.
    wd = _watchdog(positions={"AAPL": 100, "MSFT": 50},
                    live_stops={"MSFT": snap()})
    wd.run_once()
    assert wd.state.get("MSFT") is not None
    assert wd.state.get("AAPL") is None


def test_vanished_stop_on_watched_symbol_is_detected_but_not_fixed():
    wd = _watchdog(positions={"AAPL": 100}, live_stops={})
    wd.state.set("AAPL", snap())  # previously seen protected, now gone
    # Must not raise even though there is no way to act on it -- free tier
    # can only detect and log, never place an order.
    wd.run_once()
    # Nothing about AAPL's tracked state should be touched by a detection
    # that can't be acted on.
    assert wd.state.get("AAPL") == snap()


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{passed}/{len(tests)} passed")
