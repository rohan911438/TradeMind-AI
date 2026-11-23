"""Paper trading broker: virtual capital, simulated fills at bid/ask, positions and P&L.

One PaperAccount per signed-in user, persisted to SQLite.
"""
from __future__ import annotations

import time
import uuid

from .. import db
from ..config import settings


def _today() -> str:
    return time.strftime("%Y-%m-%d")


def new_state(starting: float) -> dict:
    return {"starting_cash": starting, "cash": starting, "positions": {}, "realised_total": 0.0,
            "realised_by_day": {}, "orders": [], "equity_curve": [], "created_at": time.time()}


class PaperAccount:
    def __init__(self, user_id: str, state: dict | None = None) -> None:
        self.user_id = user_id
        self.s = state or new_state(settings.STARTING_CAPITAL)

    # ---------- views ----------
    def portfolio(self, marks: dict[str, float]) -> dict:
        positions, mv_total, unreal_total = {}, 0.0, 0.0
        for sym, p in self.s["positions"].items():
            if p["qty"] <= 0:
                continue
            mark = marks.get(sym, p["avg_price"])
            mv = p["qty"] * mark
            unreal = (mark - p["avg_price"]) * p["qty"]
            mv_total += mv
            unreal_total += unreal
            positions[sym] = {"qty": p["qty"], "avg_price": round(p["avg_price"], 2), "mark": round(mark, 2),
                              "market_value": round(mv, 2), "unrealised_pnl": round(unreal, 2),
                              "unrealised_pct": round((mark / p["avg_price"] - 1) * 100, 2)}
        equity = self.s["cash"] + mv_total
        for p in positions.values():
            p["weight"] = round(p["market_value"] / equity, 4) if equity else 0
        start = self.s["starting_cash"]
        return {"cash": round(self.s["cash"], 2), "equity": round(equity, 2), "starting_cash": start,
                "positions": positions, "exposure": round(mv_total / equity, 4) if equity else 0,
                "unrealised_pnl": round(unreal_total, 2), "realised_pnl": round(self.s["realised_total"], 2),
                "realised_today": round(self.s["realised_by_day"].get(_today(), 0.0), 2),
                "total_pnl": round(equity - start, 2), "total_return_pct": round((equity / start - 1) * 100, 3),
                "orders_count": len(self.s["orders"])}

    # ---------- actions ----------
    def record(self, symbol: str, side: str, qty: int | None, verdict: dict, fill_price: float | None,
               signal: dict) -> dict:
        approved = verdict["approved_qty"]
        filled = verdict["status"] != "REJECTED" and approved > 0 and fill_price is not None
        order = {"id": uuid.uuid4().hex[:10], "ts": time.time(), "symbol": symbol, "side": side,
                 "requested_qty": qty, "filled_qty": approved if filled else 0,
                 "fill_price": round(fill_price, 2) if filled else None,
                 "status": "FILLED" if filled else "REJECTED", "risk_status": verdict["status"],
                 "risk_reasons": verdict["reasons"], "stop_loss": verdict.get("stop_loss"),
                 "target": verdict.get("target"),
                 "signal": {k: signal.get(k) for k in ("signal", "confidence", "market_pressure")},
                 "realised_pnl": None}
        if filled:
            pos = self.s["positions"].setdefault(symbol, {"qty": 0, "avg_price": 0.0})
            if side == "BUY":
                cost = approved * fill_price
                pos["avg_price"] = (pos["avg_price"] * pos["qty"] + cost) / (pos["qty"] + approved)
                pos["qty"] += approved
                self.s["cash"] -= cost
            else:
                pnl = (fill_price - pos["avg_price"]) * approved
                pos["qty"] -= approved
                self.s["cash"] += approved * fill_price
                self.s["realised_total"] += pnl
                day = _today()
                self.s["realised_by_day"][day] = self.s["realised_by_day"].get(day, 0.0) + pnl
                order["realised_pnl"] = round(pnl, 2)
                if pos["qty"] == 0:
                    del self.s["positions"][symbol]
        self.s["orders"].insert(0, order)
        self.s["orders"] = self.s["orders"][:500]
        self.save()
        return order

    def snapshot_equity(self, marks: dict[str, float]) -> None:
        eq = self.portfolio(marks)["equity"]
        self.s["equity_curve"].append({"t": int(time.time()), "equity": round(eq, 2)})
        self.s["equity_curve"] = self.s["equity_curve"][-2000:]

    def reset(self) -> None:
        self.s = new_state(settings.STARTING_CAPITAL)
        self.save()

    def save(self) -> None:
        db.save_account(self.user_id, self.s)


class AccountManager:
    def __init__(self) -> None:
        self._cache: dict[str, PaperAccount] = {}

    def get(self, user_id: str) -> PaperAccount:
        acc = self._cache.get(user_id)
        if acc is None:
            acc = PaperAccount(user_id, db.load_account(user_id))
            self._cache[user_id] = acc
        return acc

    def active(self) -> list[PaperAccount]:
        return list(self._cache.values())
