"""RiskGuard: decides whether a simulated order may go ahead, and at what size.

Rules (all limits configurable in config.py):
 1. Signal check   - the AI advises, the user decides: HOLD -> size halved; buying against a SELL or
                     NO_TRADE signal is allowed with a warning, at 25 % size and the minimum R:R target
 2. Daily loss     - realised loss today >= 3 % of starting capital -> REJECTED
 3. Stop / target  - stop = entry - 1.5 x ATR; reward multiple grows with AI confidence
 4. Risk/reward    - R:R below MIN_RR -> REJECTED
 5. Position size  - risk 1 % of equity: qty = (equity x 1 %) / stop distance
 6. Exposure caps  - one stock <= 20 % of equity, all stocks <= 60 %, and never more than cash
                     -> quantity REDUCED to fit
Long-only: SELL closes an existing position (risk-reducing), so it is always allowed up to the held qty.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from ..config import settings


@dataclass
class Limits:
    risk_per_trade: float = settings.RISK_PER_TRADE
    max_symbol: float = settings.MAX_SYMBOL_EXPOSURE
    max_total: float = settings.MAX_TOTAL_EXPOSURE
    min_rr: float = settings.MIN_RR
    daily_loss: float = settings.DAILY_LOSS_LIMIT
    stop_atr: float = settings.STOP_ATR_MULT


def reward_multiple(confidence: float) -> float:
    """Target distance in ATRs. It grows with the model's edge over an uninformed 3-class guess (1/3).

    The model's probabilities are compressed (about 0.33-0.45), so every +1 percentage point of edge
    adds 0.3 ATR of expected reward. Below ~0.34 confidence the R:R fails the minimum.
    """
    return float(min(4.5, max(1.0, 1.5 + 30.0 * (confidence - 1 / 3))))


def risk_level(ann_vol: float, exposure_after: float) -> str:
    level = 0 if ann_vol < 0.20 else 1 if ann_vol < 0.40 else 2
    if exposure_after > 0.45:
        level += 1
    return ["LOW", "MODERATE", "HIGH", "HIGH"][level]


def evaluate(symbol: str, side: str, qty: int | None, *, bid: float, ask: float, atr: float,
             ann_vol: float, signal: dict, portfolio: dict, limits: Limits | None = None) -> dict:
    L = limits or Limits()
    side = side.upper()
    equity = portfolio["equity"]
    cash = portfolio["cash"]
    positions = portfolio["positions"]           # {sym: {"qty", "avg_price", "market_value"}}
    held = positions.get(symbol, {}).get("qty", 0)
    exposure_now = sum(p["market_value"] for p in positions.values())
    reasons: list[str] = []

    def verdict(status: str, approved: int, entry: float, stop=None, target=None, rr=None, risk_amt=0.0):
        sym_val_after = (held + (approved if side == "BUY" else -approved)) * entry
        tot_after = exposure_now + (approved * entry if side == "BUY" else -approved * entry)
        return {
            "status": status, "symbol": symbol, "side": side,
            "requested_qty": qty, "approved_qty": int(approved), "entry": round(entry, 2),
            "stop_loss": None if stop is None else round(stop, 2),
            "target": None if target is None else round(target, 2),
            "risk_reward": None if rr is None else round(rr, 2),
            "risk_amount": round(risk_amt, 2),
            "annualised_volatility": round(ann_vol, 4),
            "risk_level": risk_level(ann_vol, tot_after / equity if equity else 0),
            "exposure_symbol_after": round(sym_val_after / equity, 4) if equity else 0,
            "exposure_total_after": round(tot_after / equity, 4) if equity else 0,
            "signal": signal.get("signal"), "confidence": signal.get("confidence"),
            "against_ai": side == "BUY" and signal.get("signal") in ("SELL", "NO_TRADE"),
            "reasons": reasons,
        }

    if qty is not None and qty <= 0:
        reasons.append("Quantity must be positive")
        return verdict("REJECTED", 0, ask)

    # ---------- SELL: closing a long position ----------
    if side == "SELL":
        if held <= 0:
            reasons.append("No open position to sell (paper account is long-only)")
            return verdict("REJECTED", 0, bid)
        want = qty if qty is not None else held
        approved = min(want, held)
        if approved < want:
            reasons.append(f"Only {held} shares held - quantity reduced to {held}")
            return verdict("REDUCED", approved, bid)
        reasons.append("Closing/reducing a position lowers portfolio risk")
        return verdict("APPROVED", approved, bid)

    # ---------- BUY ----------
    entry = ask
    sig = signal.get("signal", "NO_TRADE")
    conf = float(signal.get("confidence", 0) or 0)

    loss_today = -min(0.0, portfolio.get("realised_today", 0.0))
    if loss_today >= L.daily_loss * portfolio["starting_cash"]:
        reasons.append(f"Daily loss limit hit ({loss_today:,.0f} >= {L.daily_loss:.0%} of capital)")
        return verdict("REJECTED", 0, entry)

    stop_dist = max(L.stop_atr * atr, entry * 0.002)      # floor: 0.2 % of price
    stop = entry - stop_dist
    against_ai = sig in ("SELL", "NO_TRADE")
    if against_ai:
        # The user decides; RiskGuard does not veto. With no model edge behind the trade, the target is
        # the minimum acceptable R:R and the risk-based size is cut to a quarter.
        rr = L.min_rr
    else:
        rr = reward_multiple(conf) / L.stop_atr
    target = entry + stop_dist * rr
    if rr < L.min_rr:
        reasons.append(f"Risk/reward {rr:.2f} is below the minimum {L.min_rr:.2f} (confidence {conf:.0%} too low)")
        return verdict("REJECTED", 0, entry, stop, target, rr)

    sized = math.floor(equity * L.risk_per_trade / stop_dist)
    if against_ai:
        sized //= 4
        why = "the AI signal is SELL" if sig == "SELL" else "the AI signal is NO TRADE (no confident view)"
        reasons.append(f"Warning: buying although {why} - allowed, but risk-based size cut to 25%")
    elif sig == "HOLD":
        sized //= 2
        reasons.append("AI signal is HOLD (no clear edge) - risk-based size halved")
    caps = {
        "risk budget (1% of equity)": sized,
        f"single-stock cap ({L.max_symbol:.0%})": math.floor(max(0.0, L.max_symbol * equity - held * entry) / entry),
        f"total exposure cap ({L.max_total:.0%})": math.floor(max(0.0, L.max_total * equity - exposure_now) / entry),
        "available cash": math.floor(cash / entry),
    }
    allowed = max(0, min(caps.values()))
    binding = min(caps, key=caps.get)
    if allowed <= 0:
        reasons.append(f"No room left: limited by {binding}")
        return verdict("REJECTED", 0, entry, stop, target, rr)

    want = qty if qty is not None else allowed
    approved = min(want, allowed)
    status = "APPROVED"
    if approved < want:
        status = "REDUCED"
        reasons.append(f"Quantity reduced from {want} to {approved}: limited by {binding}")
    reasons.append(f"Stop {stop:.2f} ({L.stop_atr}x ATR), target {target:.2f}, R:R {rr:.2f}")
    return verdict(status, approved, entry, stop, target, rr, approved * stop_dist)
