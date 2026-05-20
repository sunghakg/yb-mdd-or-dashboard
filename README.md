# YB MDD 60/40/20 OR — Cloud Dashboard

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://yb-mdd-or-dashboard.streamlit.app/)

Streamlit Community Cloud로 배포된 백테스트 + 페이퍼 트레이딩 대시보드.
휴대폰·태블릿에서 어디서나 접근 가능.

## 7 탭

1. **📊 Overview** — 매매법 spec + 6/6 검증 통과 요약
2. **📋 거래 내역** — 8년 분봉 풀백테 거래 로그 + 기간별 필터
3. **📈 Stress Tests** — 5+2 폭락 사이클 분석
4. **🎲 Bootstrap** — 5,000 paths 신뢰구간
5. **📅 Year-by-Year** — 16년 일봉 long-horizon + Cross-Asset
6. **🔄 Walk-Forward / OOS** — 동적 vs 정적
7. **📜 Paper Trading** — 자체 시뮬 journal (local만)
8. **💰 Alpaca Live** — Alpaca paper 실잔고 (실시간)

## 데이터 갱신

매일 11:00 HST (17:00 ET) 로컬 머신에서 `daily_update.bat`이:
1. IBKR 8년 캐시 + Alpaca 새 1-2일 append
2. 전체 8년 백테 재실행
3. `data/` 폴더 업데이트
4. `git push` → Streamlit Cloud 자동 reload

## 모바일 사용

iPhone Safari / Android Chrome에서 URL 열고 "홈 화면에 추가" — PWA로 앱처럼 사용.

## Secrets (Streamlit Cloud → App Settings)

| Key | Value |
|---|---|
| `ALPACA_API_KEY` | Alpaca paper API key (PK…) |
| `ALPACA_SECRET_KEY` | Alpaca paper secret |

## 로컬 실행

```bash
pip install -r requirements.txt
streamlit run app.py
```
