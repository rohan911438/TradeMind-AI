from app.riskguard.engine import Limits, evaluate, reward_multiple, risk_level

L = Limits(risk_per_trade=0.01, max_symbol=0.20, max_total=0.60, min_rr=1.2, daily_loss=0.03, stop_atr=1.5)


def pf(cash=1_000_000, positions=None, realised_today=0.0):
    positions = positions or {}
    mv = sum(p["market_value"] for p in positions.values())
    return {"cash": cash, "equity": cash + mv, "starting_cash": 1_000_000, "positions": positions,
            "realised_today": realised_today}


BUY = {"signal": "BUY", "confidence": 0.65}


def run(side="BUY", qty=None, signal=BUY, portfolio=None, atr=3.0):
    return evaluate("RELIANCE", side, qty, bid=1450.0, ask=1450.5, atr=atr, ann_vol=0.25,
                    signal=signal, portfolio=portfolio or pf(), limits=L)


def test_sizing_is_capped_by_single_stock_exposure():
    v = run()
    # risk sizing: 10,000 / 4.5 = 2222 shares, but 20% cap = 200,000 / 1450.5 = 137
    assert v["status"] == "APPROVED"
    assert v["approved_qty"] == 137
    assert v["exposure_symbol_after"] <= 0.20


def test_large_order_is_reduced():
    v = run(qty=2000)
    assert v["status"] == "REDUCED"
    assert v["approved_qty"] == 137
    assert any("reduced" in r for r in v["reasons"])


def test_small_order_approved_unchanged():
    v = run(qty=50)
    assert v["status"] == "APPROVED" and v["approved_qty"] == 50
    assert v["stop_loss"] < v["entry"] < v["target"]


def test_risk_budget_binds_with_wide_stop():
    v = run(atr=100.0)   # stop distance 150 -> 10,000 / 150 = 66 shares
    assert v["approved_qty"] == 66


def test_no_trade_signal_rejected():
    v = run(signal={"signal": "NO_TRADE", "confidence": 0.3})
    assert v["status"] == "REJECTED" and v["approved_qty"] == 0


def test_opposite_signal_rejected():
    assert run(signal={"signal": "SELL", "confidence": 0.7})["status"] == "REJECTED"


def test_low_confidence_fails_risk_reward():
    v = run(signal={"signal": "BUY", "confidence": 0.335})
    assert reward_multiple(0.335) / 1.5 < 1.2
    assert v["status"] == "REJECTED"


def test_hold_halves_size():
    full = run(atr=100.0)["approved_qty"]
    half = run(atr=100.0, signal={"signal": "HOLD", "confidence": 0.65})["approved_qty"]
    assert half == full // 2


def test_daily_loss_limit():
    v = run(portfolio=pf(realised_today=-31_000))
    assert v["status"] == "REJECTED"


def test_total_exposure_cap():
    held = {s: {"qty": 100, "avg_price": 2000, "market_value": 200_000} for s in ("TCS", "INFY", "HDFCBANK")}
    v = run(portfolio=pf(cash=400_000, positions=held))  # 600k of 1M already invested = 60%
    assert v["status"] == "REJECTED"


def test_sell_without_position_rejected_and_sell_capped():
    assert run(side="SELL", qty=10)["status"] == "REJECTED"
    held = {"RELIANCE": {"qty": 40, "avg_price": 1400, "market_value": 58_000}}
    v = run(side="SELL", qty=100, portfolio=pf(cash=942_000, positions=held))
    assert v["status"] == "REDUCED" and v["approved_qty"] == 40


def test_risk_level():
    assert risk_level(0.1, 0.1) == "LOW"
    assert risk_level(0.3, 0.1) == "MODERATE"
    assert risk_level(0.5, 0.1) == "HIGH"
    assert risk_level(0.1, 0.5) == "MODERATE"
