# Stop Watchdog (Free)

Watches one Interactive Brokers paper-trading position and tells you the
moment its protective stop order has silently vanished.

Built out of a real production incident: IBKR's own extended-hours price
collar can reject a stop order's trailing update and silently cancel the
entire resting order, server-side, with no warning delivered to your code.
If your strategy only checks stops when it decides to move them, a position
can sit completely unprotected — real shares, zero downside protection —
until something else happens to notice. This free tool proves that detection
actually works, on your own account, before you trust anything to fix it
automatically.

## What Free does

1. On a timer (default every 30 seconds), it asks IBKR for your current
   positions and open orders.
2. It watches **one position** — if you have several, it picks the one it's
   already tracking, or the first one with a live stop to learn, so it
   doesn't arbitrarily hop between positions cycle to cycle.
3. If that position has a live protective stop (STP or STP LMT), it
   remembers the current level — this is how it learns what "normal" looks
   like, no manual configuration needed.
4. If the position is open but its stop has disappeared, and this tool has
   previously seen a real stop for it, it logs a clear warning. **It does
   not place an order to fix it** — this build has no order-placement
   capability at all, by design (see "Free vs Pro" below).

What that looks like in the log when it fires:

```
2026-10-10 09:43:11 INFO Connected to IBKR at 127.0.0.1:7497 as clientId=99
2026-10-10 10:15:42 WARNING [AAPL] OPEN POSITION WITH NO LIVE STOP. Free tier cannot re-arm it automatically -- you need to do this yourself.
```

## Free vs Pro

|                                      | Free | Pro |
|--------------------------------------|:---:|:---:|
| Detect a vanished protective stop    | ✅  | ✅  |
| Watch more than one position at once | ❌  | ✅  |
| Automatically re-arm the stop        | ❌  | ✅  |
| Live trading accounts                | ❌ (paper only) | ✅  |

This isn't a feature flag — the free build's `Broker` class has no
order-placement code in it at all. There's nothing to unlock by editing a
config file; the capability genuinely isn't present in this package.

**[Stop Watchdog (Pro) →](https://algovigil.gumroad.com/l/stop-watchdog)** —
one-time purchase, not a subscription.

## Requirements

- Python 3.10+
- TWS or IB Gateway running and logged in to a **paper trading account**
- IBKR's own native TWS API client (`ibapi`)

## Known limitations

- Watches exactly one long position's sell-side stop. No short-side
  support, no multi-position coverage — that's what Pro is for.
- Paper trading accounts only (checked and enforced at connect time,
  account must start with `DU`).
- No email/SMS/webhook alerting — detection events are logged only.

## Support

support@algovigil.com
