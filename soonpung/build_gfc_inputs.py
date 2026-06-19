"""
순풍 — GFC 포함 합성 SOXL 구축 (사용자 Drive 데이터 사용)
===============================================================
입력 (Google Drive에서 받아 data/soonpung/ 에 저장):
  - SOXL_2008.csv : 실제 SOXL OHLC (2010-03-11~, Adj Close)
  - USD_2008.csv  : ProShares Ultra Semiconductors 2x (2008-01-02~, Adj Close)
                    → 2008 GFC 포함하는 실제 '반도체 레버리지' 시계열

절차 (Cheng-Madhavan 비용모델):
  1. USD de-lever → 반도체 지수 프록시:  R_idx = (R_usd + cost2/252) / 2
  2. 합성 3x SOXL:  R_soxl_syn = 3·R_idx − cost3/252
  3. splice: 2008~2010 합성 + 2010~ 실제 SOXL (실제 첫날 레벨에 합성 스케일 정합)
  4. 검증: 겹치는 2010~2026 구간에서 합성 vs 실제 SOXL 일별수익률 상관

비용(연):
  cost2 = USD 보수(0.95%) + 1×(rf+spread)   ; 2x → 1배 차입
  cost3 = SOXL 보수(0.89%) + 2×(rf+spread)  ; 3x → 2배 차입
  rf+spread ≈ 3% (역사 평균 근사)

출력: data/soonpung/{soxl_spliced.csv, aux_series.csv, synth_validation.json}
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data" / "soonpung"

EXP_USD, EXP_SOXL = 0.0095, 0.0089
RF_SPREAD = 0.03
COST2 = EXP_USD + 1 * RF_SPREAD          # 2x de-lever 비용 add-back
COST3 = EXP_SOXL + 2 * RF_SPREAD         # 3x 합성 비용


def _adj(path: Path) -> pd.Series:
    df = pd.read_csv(path, parse_dates=["Date"]).set_index("Date")
    col = "Adj Close" if "Adj Close" in df.columns else "Close"
    return df[col].astype(float).dropna()


def build() -> dict:
    usd = _adj(DATA / "USD_2008.csv")
    soxl_real = _adj(DATA / "SOXL_2008.csv")

    # 1. USD → 반도체 지수 프록시 (de-lever ÷2, 비용 add-back)
    r_usd = usd.pct_change()
    r_idx = (r_usd + COST2 / 252) / 2.0
    index_proxy = (1 + r_idx).cumprod()
    index_proxy.iloc[0] = 1.0

    # 2. 합성 3x SOXL
    r_syn = 3 * r_idx - COST3 / 252
    synth = (1 + r_syn).cumprod()
    synth.iloc[0] = 1.0

    # 3. splice — 실제 SOXL 첫날 레벨에 합성 정합
    first = soxl_real.index[0]
    if first in synth.index:
        scale = soxl_real.loc[first] / synth.loc[first]
    else:
        scale = soxl_real.iloc[0] / synth.reindex([first], method="ffill").iloc[0]
    synth_scaled = synth * scale

    idx = synth_scaled.index.union(soxl_real.index)
    df = pd.DataFrame(index=idx)
    df["soxl_real"] = soxl_real.reindex(idx)
    df["soxl_synth"] = synth_scaled.reindex(idx)
    df["soxl_spliced"] = df["soxl_real"].where(df["soxl_real"].notna(), df["soxl_synth"])
    df["source"] = np.where(df["soxl_real"].notna(), "real", "synth")
    df = df.dropna(subset=["soxl_spliced"])
    df.to_csv(DATA / "soxl_spliced.csv")

    # aux: de-lever 지수 프록시(=SOX 대용, MA 필터용)
    pd.DataFrame({"SOX": index_proxy}).to_csv(DATA / "aux_series.csv")

    # 4. 검증
    both = df.dropna(subset=["soxl_real", "soxl_synth"])
    rr = both["soxl_real"].pct_change().dropna()
    rs = both["soxl_synth"].pct_change().dropna()
    j = rr.index.intersection(rs.index)
    corr = float(np.corrcoef(rr.loc[j], rs.loc[j])[0, 1])
    te = float((rr.loc[j] - rs.loc[j]).std() * np.sqrt(252))
    v = {
        "spliced_start": str(df.index[0].date()),
        "spliced_end": str(df.index[-1].date()),
        "synth_days": int((df["source"] == "synth").sum()),
        "real_days": int((df["source"] == "real").sum()),
        "overlap_days": int(len(j)),
        "daily_return_corr": round(corr, 4),
        "tracking_error_annual": round(te, 4),
        "pass_corr_098": bool(corr >= 0.98),
        "note": "합성 2008~2010 = USD(2x semis) de-lever→3x 재구성. 실제 아님, 참고용.",
    }
    (DATA / "synth_validation.json").write_text(
        json.dumps(v, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(v, indent=2, ensure_ascii=False))
    return v


if __name__ == "__main__":
    build()
