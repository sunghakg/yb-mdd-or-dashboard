"""
순풍 — Phase 2/3 MVP 통합 백테스트
===============================================================
position_t = regime_ON × target_lev  (변동성 타겟 × 레짐 필터)

핵심 원칙
  - **No lookahead**: t일 종가까지 계산한 비중을 t+1일 수익에 적용(position.shift(1)).
  - **거래비용**: 비중 변경분에 슬리피지+수수료 반영.
  - margin 미사용: position ∈ [0, lev_max=1.0].

리포트
  - 전체 성과: CAGR / MDD / Sharpe / Calmar  (순풍 vs SOXL 단순보유)
  - ★ 국면별 성과 분해(상승/하락/횡보) — 본 전략의 목적이므로 필수.
  - 상승 포획률 / 하락 방어율.

실행:
    python soonpung/data_pipeline.py        # 먼저 데이터 생성
    python soonpung/backtest_mvp.py         # 백테스트 + 리포트
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from regime_filter import regime_on
from vol_target import target_leverage

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "soonpung"
TRADING_DAYS = 252

# ── 백테스트 파라미터 (MVP — 최소) ──────────────────────────
SIGMA_TARGET = 0.35     # 목표 연변동성
VOL_WINDOW = 60         # 실현변동성 lookback
LEV_MAX = 1.0           # margin 미사용
MA_WINDOW = 200
TSM_LOOKBACK = 252
DWELL = 5
COMBINE = "and"
COST_BPS = 5.0          # 비중 변경 1.0당 5bps (슬리피지+수수료)


# ── 메트릭 ──────────────────────────────────────────────────
def cagr(equity: pd.Series) -> float:
    yrs = (equity.index[-1] - equity.index[0]).days / 365.25
    return float(equity.iloc[-1] / equity.iloc[0]) ** (1 / yrs) - 1 if yrs > 0 else np.nan


def mdd(equity: pd.Series) -> float:
    return float((equity / equity.cummax() - 1).min())


def sharpe(returns: pd.Series) -> float:
    s = returns.std()
    return float(returns.mean() / s * np.sqrt(TRADING_DAYS)) if s > 0 else np.nan


def metrics(returns: pd.Series) -> dict:
    eq = (1 + returns.fillna(0)).cumprod()
    m = mdd(eq)
    c = cagr(eq)
    return {
        "CAGR": round(c, 4),
        "MDD": round(m, 4),
        "Sharpe": round(sharpe(returns), 3),
        "Calmar": round(c / abs(m), 3) if m < 0 else np.nan,
        "final_mult": round(float(eq.iloc[-1]), 2),
    }


# ── 국면 라벨 (분해 리포트용 — 디스크립티브, 매매 시그널 아님) ──
def market_regime(base: pd.Series, window: int = 200, band: float = 0.02) -> pd.Series:
    sma = base.rolling(window, min_periods=window).mean()
    ratio = base / sma - 1.0
    lab = pd.Series("sideways", index=base.index)
    lab[ratio > band] = "bull"
    lab[ratio < -band] = "bear"
    return lab


def run(sigma_target: float = SIGMA_TARGET, combine: str = COMBINE,
        lev_max: float = LEV_MAX, vol_window: int = VOL_WINDOW,
        dwell: int = DWELL, save: bool = True, verbose: bool = True) -> dict:
    spliced = pd.read_csv(DATA / "soxl_spliced.csv", index_col=0, parse_dates=True)
    aux = pd.read_csv(DATA / "aux_series.csv", index_col=0, parse_dates=True)

    soxl = spliced["soxl_spliced"].dropna()
    r_soxl = soxl.pct_change()
    all_real = bool((spliced.get("source", "real") == "real").all())

    # 기초지수(MA 필터용): SOXX 우선, 없으면 SOX, 없으면 SOXL 자기참조
    base = None
    for c in ("SOXX", "SOX"):
        if c in aux.columns and aux[c].notna().sum() > MA_WINDOW:
            base = aux[c].reindex(soxl.index).ffill()
            break
    if base is None:
        base = soxl

    # ── 시그널 (모두 t일까지 정보) ──
    reg = regime_on(soxl, base_price=base, combine=combine,
                    ma_window=MA_WINDOW, tsm_lookback=TSM_LOOKBACK, dwell=dwell)
    lev = target_leverage(r_soxl, sigma_target=sigma_target,
                          method="realized", window=vol_window, lev_max=lev_max)
    raw_pos = (reg.astype(float) * lev).reindex(soxl.index).fillna(0.0)

    # ── No lookahead: t 비중은 t+1 수익에 적용 ──
    pos = raw_pos.shift(1).fillna(0.0)
    turnover = pos.diff().abs().fillna(0.0)
    cost = turnover * (COST_BPS / 1e4)
    strat_r = (pos * r_soxl - cost).dropna()

    # 워밍업(시그널 NaN 구간) 제거: 첫 유효 시점부터
    start = raw_pos[raw_pos > 0].index.min()
    if pd.notna(start):
        strat_r = strat_r.loc[start:]
    bh_r = r_soxl.reindex(strat_r.index).fillna(0.0)

    # ── 전체 성과 ──
    overall = {
        "순풍_MVP": metrics(strat_r),
        "SOXL_buyhold": metrics(bh_r),
        "period": [str(strat_r.index[0].date()), str(strat_r.index[-1].date())],
        "n_days": int(len(strat_r)),
        "avg_exposure": round(float(pos.reindex(strat_r.index).mean()), 3),
        "annual_turnover": round(float(turnover.reindex(strat_r.index).mean() * TRADING_DAYS), 1),
    }

    # ── ★ 국면별 분해 ──
    # capture는 누적(기하)이 아니라 **연율화 수익**으로 비교한다.
    # (비연속 국면 일자를 곱셈 누적하면 복리로 왜곡됨 — annualize가 해석가능)
    lab = market_regime(base).reindex(strat_r.index).fillna("sideways")

    def annualize(r: pd.Series) -> float:
        n = len(r)
        if n == 0:
            return float("nan")
        return float((1 + r).prod()) ** (TRADING_DAYS / n) - 1

    decomp = {}
    for state in ("bull", "bear", "sideways"):
        mask = lab == state
        if mask.sum() < 5:
            continue
        sr, br = strat_r[mask], bh_r[mask]
        ann_s, ann_b = annualize(sr), annualize(br)
        # 상승 포획률(capture): 상승장은 strat/bh, 하락장은 '손실 방어율'(1-strat/bh)
        cap = (ann_s / ann_b) if abs(ann_b) > 1e-9 else None
        decomp[state] = {
            "days": int(mask.sum()),
            "순풍_ann_ret": round(ann_s, 4),
            "SOXL_ann_ret": round(ann_b, 4),
            "순풍_mdd": round(mdd((1 + sr).cumprod()), 4),
            "SOXL_mdd": round(mdd((1 + br).cumprod()), 4),
            "capture_ratio": round(cap, 3) if cap is not None else None,
        }

    summary = {
        "strategy": "순풍(順風) MVP — regime filter × vol targeting",
        "params": {
            "sigma_target": sigma_target, "vol_window": vol_window, "lev_max": lev_max,
            "ma_window": MA_WINDOW, "tsm_lookback": TSM_LOOKBACK, "dwell": dwell,
            "combine": combine, "cost_bps": COST_BPS,
        },
        "overall": overall,
        "regime_decomposition": decomp,
        "note": ("전 구간 실제 SOXL (합성 역연장 미포함)." if all_real
                 else "합성 SOXL 역연장 포함 — 역사 구간은 참고용(과신 금지)."),
    }

    if save:
        (DATA / "mvp_summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        eq = pd.DataFrame({
            "순풍_equity": (1 + strat_r).cumprod(),
            "SOXL_equity": (1 + bh_r).cumprod(),
            "position": pos.reindex(strat_r.index),
            "regime": lab,
        })
        eq.to_csv(DATA / "mvp_equity.csv")
    if verbose:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        if save:
            print("\n✓ 저장: mvp_summary.json, mvp_equity.csv")
    return summary


if __name__ == "__main__":
    run()
