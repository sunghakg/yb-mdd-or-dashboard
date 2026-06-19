# data/soonpung/ — 순풍 엔진 산출물

`soonpung/` 파이프라인·백테스트의 입력/산출물.

## 입력 (사용자 Google Drive에서 수집)
- `SOXL_2008.csv` — 실제 SOXL OHLC (2010-03-11~, Adj Close)
- `USD_2008.csv` — ProShares Ultra Semiconductors 2x (2008-01-02~, **2008 GFC 포함**)

## 생성물
- `soxl_spliced.csv` — GFC 포함 합성 SOXL (USD de-lever→3x 재구성 2008~2010 + 실제 2010~)
- `aux_series.csv` — de-lever 반도체 지수 프록시(SOX 대용, MA 필터용)
- `synth_validation.json` — 합성 vs 실제 일별수익률 상관(0.95)
- `mvp_summary.json` — 추천 구성(ma_only σ0.35) 전체 성과 + 국면별 분해
- `mvp_equity.csv` — 순풍/SOXL equity + position + regime 일별
- `mvp_sweep.csv` — combine × σ_target 파라미터 스윕

## 재생성
```bash
python soonpung/build_gfc_inputs.py   # Drive CSV → spliced/aux/validation
python soonpung/backtest_mvp.py       # mvp_summary.json, mvp_equity.csv
```
라이브 다운로드(yfinance)가 가능한 환경에서는 `soonpung/data_pipeline.py`로 갱신.
