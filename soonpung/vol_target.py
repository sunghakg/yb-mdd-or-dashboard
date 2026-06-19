"""
순풍 — 모듈 2: 변동성 타겟팅 (비중 동적 조절) ★ 순풍의 심장
===============================================================
"얼마나 탈지" 결정. Cooper(2010) managed volatility + Harvey(2018) 실증.

target_lev_t = clip(σ_target / σ̂_t, 0, lev_max)
  σ̂_t      = SOXL 실현변동성(연율화). realized(rolling std) 또는 EWMA.
  σ_target = 목표 연변동성 (예: 0.35)
  lev_max  = 1.0 (margin 미사용 — CHAMP_NOMARGIN 정책 정합)

SOXL은 일일 3x 리셋 → 고변동 구간에서 decay가 구조적. σ̂↑ 시 비중을 선제 축소해 decay/꼬리위험 방어.
실현변동성은 후행 → 급변 시 한 박자 늦음(VVIX 선행 보조는 Phase 2.5).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def realized_vol(returns: pd.Series, window: int = 60) -> pd.Series:
    """롤링 실현변동성(연율화)."""
    return returns.rolling(window, min_periods=max(5, window // 3)).std() * np.sqrt(TRADING_DAYS)


def ewma_vol(returns: pd.Series, lam: float = 0.94) -> pd.Series:
    """EWMA 변동성(연율화). RiskMetrics λ=0.94 기본 — 실현변동성보다 반응 빠름."""
    var = returns.pow(2).ewm(alpha=1 - lam, adjust=False).mean()
    return np.sqrt(var) * np.sqrt(TRADING_DAYS)


def target_leverage(returns: pd.Series,
                    sigma_target: float = 0.35,
                    method: str = "realized",
                    window: int = 60,
                    lam: float = 0.94,
                    lev_max: float = 1.0,
                    band: float | None = None) -> pd.Series:
    """변동성 타겟 비중 시리즈(0..lev_max) 반환.

    band: None이면 매일 조정. 값(예: 0.1)이면 직전 비중 대비 |Δ|>band 일 때만 갱신(거래 절감).
    """
    sig = ewma_vol(returns, lam) if method == "ewma" else realized_vol(returns, window)
    lev = (sigma_target / sig).clip(lower=0.0, upper=lev_max)
    lev = lev.replace([np.inf, -np.inf], np.nan)

    if band is not None and band > 0:
        out = lev.copy()
        last = np.nan
        vals = lev.to_numpy()
        for i, v in enumerate(vals):
            if np.isnan(v):
                out.iloc[i] = last
                continue
            if np.isnan(last) or abs(v - last) > band:
                last = v
            out.iloc[i] = last
        lev = out
    return lev
