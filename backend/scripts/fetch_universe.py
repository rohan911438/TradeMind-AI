"""Download and cache real NSE 5-minute bars for the blue-chip (Nifty 50) universe.

    python -m scripts.fetch_universe            # only symbols without a cached CSV
    python -m scripts.fetch_universe --refresh  # re-download everything

Prints the symbols that downloaded successfully, ready to paste into config.NIFTY50.
"""
from __future__ import annotations

import argparse
import time

from app.config import NIFTY50
from app.predictx.data import _cache_path, load_history


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    ok, failed = [], []
    for sym in NIFTY50:
        if _cache_path(sym).exists() and not args.refresh:
            ok.append(sym)
            continue
        df, src = load_history(sym, refresh=True)
        (ok if src.startswith("yfinance") else failed).append(sym)
        print(f"{sym:12s} {len(df):5d} bars  {src}")
        time.sleep(0.5)  # be polite to the data provider
    print(f"\n{len(ok)} ok, {len(failed)} failed: {failed}")


if __name__ == "__main__":
    main()
