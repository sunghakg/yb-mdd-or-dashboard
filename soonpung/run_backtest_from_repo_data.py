"""
순풍 — 리포 내장 데이터로 MVP 백테스트 실행
===============================================================
원격 세션은 Yahoo/Stooq/Alpaca 아웃바운드가 모두 차단(403)되어 라이브 다운로드 불가.
대신 이 저장소가 이미 보유한 **실제 SOXL 일별 시리즈**를 재사용한다.

소스: data/v2_final/equity_paths.csv 의 `SOXL_buy_hold` 컬럼
  = SOXL 단순보유 equity (2010-05-25~). pct_change() = 실제 SOXL 일별수익률.
  → 가격 시리즈로 그대로 사용(수익률 기반 메트릭은 스케일 불변).

기초지수(200MA 필터용)는 라이브로 못 받으므로 de-lever 근사:
  R_base ≈ R_soxl / 3  → cumprod → 무레버리지 반도체 지수 프록시.
  (Faber 200MA 설계 의도가 '무레버리지 지수'이므로 3x 노이즈 제거)

VIX/VVIX는 data/v2_final/signal_diagnostics.csv 에서 보조로 병합(MVP 미사용, 기록용).

생성: data/soonpung/{soxl_spliced.csv, aux_series.csv} → backtest_mvp.run() 호출.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import backtest_mvp as bt  # noqa: E402

OUT = ROOT / "data" / "soonpung"
OUT.mkdir(parents=True, exist_ok=True)
LEVERAGE = 3.0


def build_inputs() -> None:
    ep = pd.read_csv(ROOT / "data" / "v2_final" / "equity_paths.csv",
                     index_col=0, parse_dates=True)
    soxl = ep["SOXL_buy_hold"].astype(float).dropna()
    soxl.name = "soxl"

    # de-lever 근사 기초지수(무레버리지 반도체 프록시)
    r = soxl.pct_change()
    base = (1.0 + r / LEVERAGE).cumprod()
    base.iloc[0] = 1.0

    spliced = pd.DataFrame(index=soxl.index)
    spliced["soxl_real"] = soxl
    spliced["soxl_synth"] = np.nan
    spliced["soxl_spliced"] = soxl
    spliced["source"] = "real"
    spliced.to_csv(OUT / "soxl_spliced.csv")

    aux = pd.DataFrame({"SOX": base})
    sd_path = ROOT / "data" / "v2_final" / "signal_diagnostics.csv"
    if sd_path.exists():
        sd = pd.read_csv(sd_path, index_col=0, parse_dates=True)
        for c in ("VIX", "VVIX"):
            if c in sd.columns:
                aux[c] = sd[c].reindex(aux.index)
    aux.to_csv(OUT / "aux_series.csv")

    print(f"입력 생성: SOXL {soxl.index[0].date()}~{soxl.index[-1].date()} "
          f"({len(soxl)}일), 기초지수 de-lever 프록시 + VIX/VVIX 병합")


if __name__ == "__main__":
    build_inputs()
    print("=" * 60)
    bt.run()
