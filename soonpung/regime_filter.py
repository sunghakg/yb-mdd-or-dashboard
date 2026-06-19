"""
순풍 — 모듈 1: 레짐 필터 (상승/하락 국면 판별)
===============================================================
"언제 탈지" 결정. Faber(2007) 200MA + Moskowitz-Ooi-Pedersen(2012) 12개월 TSM 부호.

regime_ON = (price > SMA200)  COMBINE  (sign(R_252) > 0)
  COMBINE ∈ {"and", "or", "ma_only", "tsm_only"}   # 검증 단계에서 비교

dwell(이력관성): 상태 전환을 N일 연속 충족해야 확정 → 횡보장 휩쏘 완화.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma_signal(price: pd.Series, window: int = 200) -> pd.Series:
    """price > SMA(window) → True. (Faber 10개월 ≈ 200일 일봉 변환)"""
    sma = price.rolling(window, min_periods=window).mean()
    return (price > sma)


def tsm_signal(price: pd.Series, lookback: int = 252) -> pd.Series:
    """12개월(252일) 시계열 모멘텀 부호 > 0 → True. (MOP 2012)"""
    mom = price.pct_change(lookback)
    return (mom > 0)


def _apply_dwell(raw: pd.Series, dwell: int) -> pd.Series:
    """상태가 dwell일 연속 유지될 때만 전환을 확정(관성 필터)."""
    if dwell <= 1:
        return raw.fillna(False)
    raw = raw.fillna(False).astype(int)
    out = np.zeros(len(raw), dtype=int)
    state = 0
    run_val, run_len = raw.iloc[0], 0
    for i, v in enumerate(raw.to_numpy()):
        if v == run_val:
            run_len += 1
        else:
            run_val, run_len = v, 1
        if run_len >= dwell:
            state = run_val
        out[i] = state
    return pd.Series(out.astype(bool), index=raw.index)


def regime_on(price: pd.Series,
              base_price: pd.Series | None = None,
              combine: str = "and",
              ma_window: int = 200,
              tsm_lookback: int = 252,
              dwell: int = 5) -> pd.Series:
    """레짐 ON/OFF 시리즈 반환.

    price       : 모멘텀(TSM) 계산용 — 통상 (합성)SOXL.
    base_price  : MA 필터 계산용 기초지수(SOX/SOXX). None이면 price 사용.
    combine     : and / or / ma_only / tsm_only.
    """
    base_price = price if base_price is None else base_price.reindex(price.index).ffill()
    ma = sma_signal(base_price, ma_window).reindex(price.index)
    tsm = tsm_signal(price, tsm_lookback)

    if combine == "ma_only":
        raw = ma
    elif combine == "tsm_only":
        raw = tsm
    elif combine == "or":
        raw = ma | tsm
    else:  # "and"
        raw = ma & tsm

    return _apply_dwell(raw, dwell)
