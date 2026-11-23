import numpy as np

from app.paper.broker import PaperAccount, new_state
from app.predictx.data import synthetic
from app.predictx.features import FEATURES, build_features, make_labels


def test_features_have_no_lookahead():
    df = synthetic("RELIANCE", n=300)
    before = build_features(df).iloc[:200]
    df2 = df.copy()
    df2.loc[250:, ["open", "high", "low", "close"]] *= 1.5   # change the FUTURE
    after = build_features(df2).iloc[:200]
    assert np.allclose(before[FEATURES].fillna(0).values, after[FEATURES].fillna(0).values)


def test_features_complete_after_warmup():
    f = build_features(synthetic("TCS", n=300))
    assert not f[FEATURES].iloc[40:].isna().any().any()


def test_labels():
    df = synthetic("INFY", n=100)
    y = make_labels(df, horizon=6, threshold=0.0025)
    assert y.iloc[-6:].isna().all()
    assert set(y.dropna().unique()) <= {0.0, 1.0, 2.0}


class _NoSave(PaperAccount):
    def save(self):
        pass


def _verdict(qty, status="APPROVED"):
    return {"approved_qty": qty, "status": status, "reasons": [], "stop_loss": None, "target": None}


def test_broker_buy_sell_pnl():
    acc = _NoSave("t", new_state(1_000_000))
    acc.record("TCS", "BUY", 10, _verdict(10), 100.0, {})
    acc.record("TCS", "BUY", 10, _verdict(10), 120.0, {})
    assert acc.s["positions"]["TCS"]["avg_price"] == 110.0
    o = acc.record("TCS", "SELL", 20, _verdict(20), 130.0, {})
    assert o["realised_pnl"] == 400.0
    assert acc.s["cash"] == 1_000_000 + 400
    assert "TCS" not in acc.s["positions"]


def test_rejected_order_changes_nothing():
    acc = _NoSave("t", new_state(1_000_000))
    o = acc.record("TCS", "BUY", 10, _verdict(0, "REJECTED"), 100.0, {})
    assert o["status"] == "REJECTED" and acc.s["cash"] == 1_000_000
