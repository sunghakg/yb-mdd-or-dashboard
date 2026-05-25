# Unified Trader — Cloud Dashboard

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://yb-mdd-or-dashboard.streamlit.app/)

Streamlit Community Cloud로 배포된 백테스트 + Alpaca paper 통합 봇 실시간 모니터링 대시보드.
휴대폰·태블릿에서 어디서나 접근 가능.

**2026-05-24 통합**: 기존 두 봇(YB MDD OR + Rotation P5.5) → unified_trader.py (Tier 2 GOLD_ESCAPE bm=90) 하나로 통합.

## 7 탭

1. **📊 Overview** — 매매법 spec 요약
2. **📋 거래 내역** — 8년 분봉 풀백테 거래 로그 + 기간별 필터
3. **📈 Stress Tests** — 5+2 폭락 사이클 분석
4. **🎲 Bootstrap** — 5,000 paths 신뢰구간
5. **📅 Year-by-Year** — 16년 일봉 long-horizon + Cross-Asset
6. **🔄 Walk-Forward / OOS** — 동적 vs 정적
7. **💰 Unified Live** — Alpaca paper 실잔고 + 실시간 regime 판정 + active sub-strategy 표시

## Tier 2 GOLD_ESCAPE bm=90 spec

| Regime | Sub-strategy |
|---|---|
| BULL / NEUTRAL | 롱변기 (SOXL 100%, +1.5% stop, -8% close stop) |
| BEAR | 양변기 v5 F1_A6 (SOXL+SOXS, win 0% / loss 25% LOC) |
| **GOLD_ESCAPE** (BEAR streak > 90d) | 황금변기 (SOXL K-vol breakout 0.25, RSI mode) |

Regime: Consensus 3-SMA200 (QQQ/SPY/SMH ±2%) + Fast BEAR OR (VIX9D/VIX>1.05 OR SOXL 5d mom<-10%), dwell=5d.

검증: V_bear_cap_comprehensive V1-V9 (2026-05-23). 8년 Cal 6.52, 닷컴 31m OOS +66.9%, V7 random p=0.0000, V9 longest UW 246d → 156d.

## 데이터 갱신

매일 11:00 HST (17:00 ET) 로컬 머신에서 `daily_update.bat`이:
1. IBKR 8년 캐시 + Alpaca 새 1-2일 append
2. 전체 8년 백테 재실행
3. `data/` 폴더 업데이트
4. `git push` → Streamlit Cloud 자동 reload

## 모바일 사용

iPhone Safari / Android Chrome에서 URL 열고 "홈 화면에 추가" — PWA로 앱처럼 사용.

## Secrets (Streamlit Cloud → App Settings)

2026-05-24 통합 후 새 paper 계정으로 갱신 필요:

| Key | Value |
|---|---|
| `ALPACA_API_KEY` | 신규 unified paper key (PK로 시작) |
| `ALPACA_SECRET_KEY` | 신규 unified paper secret |

기존 `ALPACA_ROT_API_KEY` / `ALPACA_ROT_SECRET_KEY`는 삭제.

## 로컬 실행

```bash
pip install -r requirements.txt
streamlit run app.py
```
