"""
순풍(順風) — Phase 1 데이터 파이프라인 + 합성 SOXL
===============================================================
SOXL 추세추종 전략 "순풍"의 데이터 레이어.

핵심 산출물
  1. 실제 시세 다운로드: SOXL / SOXX(또는 ^SOX) / SOXS / EWY / ^VIX / ^VVIX
  2. **합성 SOXL 역연장**: SOXX(2001-) 지수에 일일 3x 시뮬레이션(보수+금융비)을 적용해
     2008 금융위기·2000 닷컴 구간까지 SOXL 가격 경로를 재구성 → 하락 대비 전략 스트레스 검증용.
  3. 합성(역사) + 실제(상장 이후) splice → 단일 연속 SOXL 시리즈.
  4. 검증: 겹치는 구간에서 합성 vs 실제 일일수익률 상관(목표 ≥ 0.99) 리포트.

근거
  - Cheng & Madhavan (2009): LETF 경로 의존성 / 변동성 드래그 / 비용 모델.
      LETF_daily ≈ L·R_index − (보수 + 금융비)/252.  변동성 드래그 −½L(L−1)σ² 는
      일일 3x 복리에서 **자동 발생**하므로 별도로 빼지 않는다(이중계산 방지).
  - 일일 리셋 3x ETF는 매일 재계산해야 장기 경로가 정확.

⚠️ 역연장 구간은 실제 SOXL이 아님 — 참고용. 과신 금지.

실행:
    python soonpung/data_pipeline.py            # 전체 다운로드 + 합성 + 캐시
    python soonpung/data_pipeline.py --no-net   # 캐시만 사용(오프라인)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ── 경로 ────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent          # repo root
OUT = ROOT / "data" / "soonpung"
OUT.mkdir(parents=True, exist_ok=True)

# ── 파라미터 (Cheng-Madhavan 비용 모델) ─────────────────────
LEVERAGE = 3.0                 # SOXL = 일일 3x
EXPENSE_RATIO = 0.0089         # SOXL 운용보수 0.89%/yr
# 금융비: 3x는 자기자본의 2배를 차입 → 차입분에 단기금리+스프레드.
# 단순화: 연 (L-1) × (단기금리 + 스프레드). 무위험금리 시계열이 없으면 상수 폴백.
FINANCING_SPREAD = 0.005       # 스왑/차입 스프레드 연 0.5%
RF_FALLBACK = 0.02             # 무위험금리 폴백 연 2% (역사 평균 근사)

# 합성 기초지수 우선순위: SOXX(ETF, 배당 포함 근사) → ^SOX(지수)
BASE_TICKERS = ["SOXX", "^SOX"]
AUX_TICKERS = ["SOXL", "SOXS", "EWY", "^VIX", "^VVIX"]
RF_TICKER = "^IRX"             # 13주 T-bill 수익률(%), 금융비 추정용


def _download(tickers: list[str]) -> dict[str, pd.DataFrame]:
    """yfinance 일봉 다운로드. 실패 티커는 건너뛴다."""
    import yfinance as yf
    out: dict[str, pd.DataFrame] = {}
    for t in tickers:
        try:
            df = yf.download(t, period="max", auto_adjust=True, progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if df is None or df.empty:
                print(f"  ! {t}: 빈 데이터 — skip")
                continue
            out[t] = df
            print(f"  ✓ {t}: {len(df)} rows  {df.index[0].date()} → {df.index[-1].date()}")
        except Exception as e:  # noqa: BLE001
            print(f"  ! {t}: 다운로드 실패 ({e}) — skip")
    return out


def _close(df: pd.DataFrame) -> pd.Series:
    col = "Close" if "Close" in df.columns else df.columns[0]
    return df[col].astype(float).dropna()


def build_synthetic_soxl(base_close: pd.Series,
                         rf_annual: pd.Series | None) -> pd.Series:
    """기초지수 종가로부터 합성 SOXL 가격 경로 재구성.

    R_base_t  = base_close.pct_change()
    cost_t    = (EXPENSE_RATIO + (L-1)*(rf_t + spread)) / 252        # 일일 비용 드래그
    R_soxl_t  = L * R_base_t - cost_t
    price_t   = (1 + R_soxl_t).cumprod()  (시작 1.0; 이후 실제 SOXL 레벨로 splice)
    """
    r_base = base_close.pct_change()

    if rf_annual is not None and not rf_annual.empty:
        rf = rf_annual.reindex(r_base.index).ffill().fillna(RF_FALLBACK) / 100.0
    else:
        rf = pd.Series(RF_FALLBACK, index=r_base.index)

    daily_cost = (EXPENSE_RATIO + (LEVERAGE - 1.0) * (rf + FINANCING_SPREAD)) / 252.0
    r_soxl = LEVERAGE * r_base - daily_cost
    price = (1.0 + r_soxl).cumprod()
    price.iloc[0] = 1.0
    return price.dropna()


def splice(synth: pd.Series, real: pd.Series) -> pd.DataFrame:
    """합성(역사) + 실제(상장 이후)를 splice.

    실제 SOXL 첫날에서 합성 레벨을 실제 레벨에 맞춰 스케일.
    반환: columns = [soxl_real, soxl_synth, soxl_spliced, source]
    """
    real = real.dropna()
    first_real = real.index[0]
    # 합성을 실제 첫날 레벨에 맞추는 스케일 팩터
    if first_real in synth.index:
        scale = real.loc[first_real] / synth.loc[first_real]
    else:
        # 가장 가까운 이전 합성 포인트 사용
        prior = synth.loc[:first_real]
        scale = real.loc[first_real] / prior.iloc[-1] if len(prior) else 1.0
    synth_scaled = synth * scale

    idx = synth_scaled.index.union(real.index)
    df = pd.DataFrame(index=idx)
    df["soxl_real"] = real.reindex(idx)
    df["soxl_synth"] = synth_scaled.reindex(idx)
    # splice: 실제가 있으면 실제, 없으면 합성
    df["soxl_spliced"] = df["soxl_real"].where(df["soxl_real"].notna(), df["soxl_synth"])
    df["source"] = np.where(df["soxl_real"].notna(), "real", "synth")
    return df.dropna(subset=["soxl_spliced"])


def validate_overlap(df: pd.DataFrame) -> dict:
    """겹치는 구간(실제 & 합성 모두 존재)에서 일일수익률 상관 검증."""
    both = df.dropna(subset=["soxl_real", "soxl_synth"])
    if len(both) < 30:
        return {"overlap_days": int(len(both)), "corr": None,
                "note": "겹치는 구간 부족 — 검증 불가"}
    r_real = both["soxl_real"].pct_change().dropna()
    r_synth = both["soxl_synth"].pct_change().dropna()
    j = r_real.index.intersection(r_synth.index)
    corr = float(np.corrcoef(r_real.loc[j], r_synth.loc[j])[0, 1])
    te = float((r_real.loc[j] - r_synth.loc[j]).std() * np.sqrt(252))   # tracking error annual
    return {
        "overlap_days": int(len(j)),
        "overlap_start": str(j[0].date()),
        "overlap_end": str(j[-1].date()),
        "daily_return_corr": round(corr, 4),
        "tracking_error_annual": round(te, 4),
        "pass_corr_099": bool(corr >= 0.99),
    }


def run(use_net: bool = True) -> None:
    print("순풍 데이터 파이프라인 시작\n" + "=" * 50)

    if use_net:
        print("[1/4] 시세 다운로드")
        downloaded = _download(BASE_TICKERS + AUX_TICKERS + [RF_TICKER])
        # 원시 종가 캐시 저장
        for t, df in downloaded.items():
            safe = t.replace("^", "").lower()
            _close(df).rename(t).to_csv(OUT / f"raw_{safe}.csv")
    else:
        print("[1/4] --no-net: 캐시 raw_*.csv 로드")
        downloaded = {}
        for t in BASE_TICKERS + AUX_TICKERS + [RF_TICKER]:
            safe = t.replace("^", "").lower()
            p = OUT / f"raw_{safe}.csv"
            if p.exists():
                s = pd.read_csv(p, index_col=0, parse_dates=True).iloc[:, 0]
                downloaded[t] = s.to_frame("Close")

    if "SOXL" not in downloaded:
        print("✗ SOXL 데이터 없음 — 합성/splice 불가. 네트워크 또는 캐시 확인.")
        sys.exit(1)

    # 기초지수 선택
    base_t = next((t for t in BASE_TICKERS if t in downloaded), None)
    if base_t is None:
        print("✗ 기초지수(SOXX/^SOX) 없음 — 합성 불가.")
        sys.exit(1)

    print(f"\n[2/4] 합성 SOXL 재구성 (기초={base_t}, L={LEVERAGE}, 보수={EXPENSE_RATIO:.2%})")
    base_close = _close(downloaded[base_t])
    rf = _close(downloaded["^IRX"]) if "^IRX" in downloaded else None
    synth = build_synthetic_soxl(base_close, rf)

    print("[3/4] 합성 + 실제 splice")
    real = _close(downloaded["SOXL"])
    spliced = splice(synth, real)
    spliced.to_csv(OUT / "soxl_spliced.csv")
    print(f"  splice 결과: {spliced.index[0].date()} → {spliced.index[-1].date()} "
          f"({len(spliced)} rows, synth {int((spliced['source']=='synth').sum())}d)")

    # 보조 시리즈 한 파일로 병합
    aux = {}
    for t in AUX_TICKERS + BASE_TICKERS:
        if t in downloaded:
            aux[t.replace("^", "")] = _close(downloaded[t])
    aux_df = pd.DataFrame(aux)
    aux_df.to_csv(OUT / "aux_series.csv")

    print("\n[4/4] 합성 검증 (겹치는 구간 상관)")
    v = validate_overlap(spliced)
    for k, val in v.items():
        print(f"  {k}: {val}")
    import json
    (OUT / "synth_validation.json").write_text(
        json.dumps(v, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n✓ 완료. 산출물 →", OUT)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-net", action="store_true", help="네트워크 없이 캐시만 사용")
    args = ap.parse_args()
    run(use_net=not args.no_net)
