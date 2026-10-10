"""Command-line entry point for Stop Watchdog Free."""
from __future__ import annotations
import argparse
import json
import logging
from pathlib import Path

from .watchdog import Watchdog, WatchdogConfig


def load_config(path: Path) -> WatchdogConfig:
    raw = json.loads(path.read_text()) if path.exists() else {}
    return WatchdogConfig(
        host=raw.get("host", "127.0.0.1"),
        port=raw.get("port", 7497),
        client_id=raw.get("client_id", 99),
        poll_interval_sec=raw.get("poll_interval_sec", 30),
        state_file=Path(raw.get("state_file", "stop_watchdog_state.json")),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="stop-watchdog",
        description="Stop Watchdog Free -- watches one IBKR paper-trading position and tells you "
                    "when its protective stop has vanished. Does not re-arm it for you; "
                    "see Stop Watchdog Pro for that.")
    parser.add_argument("--config", type=Path, default=Path("config.json"),
                         help="Path to a JSON config file (see config.example.json).")
    parser.add_argument("--log-file", type=Path, default=None)
    args = parser.parse_args()

    handlers = [logging.StreamHandler()]
    if args.log_file:
        handlers.append(logging.FileHandler(args.log_file))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=handlers)

    cfg = load_config(args.config)
    watchdog = Watchdog(cfg)
    watchdog.run_forever()


if __name__ == "__main__":
    main()
