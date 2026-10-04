# stop-watchdog

A small utility that watches your Interactive Brokers positions and puts a
vanished protective stop back before you notice it's gone.

Built out of a live, real-money automated trading operation that hit this
exact failure mode in production — this isn't a hypothetical problem, it's
the fix for one that actually happened.

## The problem this solves

IBKR's own extended-hours price collar can reject a stop order's trailing
update and silently cancel the entire resting order, server-side, with no
warning delivered to your code. If your strategy only checks stops when it
decides to move them, a position can sit completely unprotected — real
shares, zero downside protection — until something else happens to notice.

This tool doesn't replace your strategy's exit logic. It runs alongside it
and does exactly one job: if a position you're holding ever loses its
protective stop unexpectedly, put an equivalent one back within seconds.

## How it works

1. On a timer (default every 30 seconds), it asks IBKR for your current
   positions and open orders.
2. If a position has a live protective stop (STP or STP LMT), it just
   remembers the current level — this is how it learns what "normal" looks
   like for that position, no manual configuration needed.
3. If a position is open but its stop has disappeared, and this tool has
   previously seen a real stop for it, it re-places one immediately at the
   last known price, quantity, and order type.
4. It never invents a stop for a position it has never seen protected —
   that might be intentional.
5. It only ever looks at orders under its own IBKR API client ID, so it
   can't interfere with another bot running on the same account.

What that looks like in the log when it actually fires:

```
2026-09-26 09:43:11 INFO Connected to IBKR at 127.0.0.1:7497 as clientId=99
2026-09-26 10:15:42 WARNING [AAPL] OPEN POSITION WITH NO LIVE STOP -- re-arming.
2026-09-26 10:15:42 WARNING [AAPL] RE-ARMED STP qty=100 stop=182.40 orderId=1057
```

## What it does NOT do

- It does not decide where your stop should be, or trail it. It only
  remembers the last stop level your own strategy placed, and re-uses that
  level if the order disappears.
- It does not manage entries or targets.
- It only watches long positions and their sell-side stop orders in v1.
- It only works with Interactive Brokers (TWS / IB Gateway).

## Requirements

- Python 3.10+
- TWS or IB Gateway running and logged in (paper or live)
- IBKR's own native TWS API client (`ibapi`)

## Known limitations (v1)

- Long positions / sell-side stops only — no short-side support yet.
- IBKR only.
- No email/SMS/webhook alerting yet — re-arm events are logged only.

## Status

**Available now:** [algovigil.gumroad.com/l/stop-watchdog](https://algovigil.gumroad.com/l/stop-watchdog) — $249, one-time purchase (not a subscription), 7-day refund. This repository is documentation only — the product itself (full source, license, setup instructions) is delivered as part of the purchase. Questions before buying: support@algovigil.com.

## Support

support@algovigil.com
