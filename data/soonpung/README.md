# data/soonpung/ — 순풍 엔진 산출물 (생성물)

이 폴더는 `soonpung/` 파이프라인·백테스트의 **생성 산출물** 위치다.
저장소에는 비어 있으며(원격 세션은 Yahoo Finance 차단), 네트워크가 열린 로컬에서
아래 실행 시 채워진다.

```bash
python soonpung/data_pipeline.py    # raw_*.csv, soxl_spliced.csv, aux_series.csv, synth_validation.json
python soonpung/backtest_mvp.py     # mvp_summary.json, mvp_equity.csv
```

생성 후 다른 `data/*` 산출물처럼 커밋하면 대시보드/리뷰에서 소비 가능.
