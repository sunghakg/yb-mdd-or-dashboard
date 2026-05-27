# BUBE V1 CHAMP_NOMARGIN — Cloud Dashboard

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://bear-upper-bound-escape-valve.streamlit.app/)

Streamlit Community Cloud로 배포된 BUBE V1 CHAMP_NOMARGIN 백테스트 + Alpaca paper 실시간 모니터링 대시보드.
휴대폰·태블릿에서 어디서나 접근 가능.

**2026-05-26 전환**: T2 GOLD_ESCAPE bm=90 → **V1 CHAMP_NOMARGIN** (BASE × VIX dynamic-k overlay, alloc cap 1.0).

## V1 CHAMP_NOMARGIN spec

```
k_today    = 0.65 × clip(20.0 / VIX_today, 0.5, 2.0)
alloc_today = min(k_today × strategy_alloc, 1.0)   # margin 사용 X
```

| VIX | scale | k_today | alloc 동향 |
|---|---|---|---|
| 10 | 2.0 | 1.30 | cap 1.0 (저변동성 풀로딩) |
| 20 | 1.0 | 0.65 | base 중립 |
| 40 | 0.5 | 0.325 | 디리스킹 |
| 80 | 0.5 | 0.325 | lo clip (극한 변동성) |

BASE BUBE rotation:

| Regime | Sub-strategy |
|---|---|
| BULL / NEUTRAL | 롱변기 (SOXL +1.5% stop, -8% close stop) |
| BEAR | 양변기 v5 F1_A6 (SOXL+SOXS, win 0% / loss 25% LOC) |
| **GOLD_ESCAPE** (BEAR streak > 90d) | 황금변기 (SOXL K-vol breakout 0.25) |

Regime: Consensus 3-SMA200 (QQQ/SPY/SMH ±2%) + Fast BEAR OR (VIX9D/VIX>1.05 OR SOXL 5d mom<-10%), dwell=5d.

## 16년 in-sample 결과 (2010-05-25 ~ 2026-05-22)

| Metric | BASE (k=0.65 정적) | CHAMP_NOMARGIN | Δ |
|---|---|---|---|
| CAGR | +53.4% | **+77.2%** | +23.8pp |
| MDD | −30.88% | **−28.13%** | +2.75pp 개선 |
| Sharpe | 1.50 | **1.81** | +0.31 |
| Calmar | 1.73 | **2.75** | +1.02 |
| $100K → Final | $90.7M | **$926M** | ×10.2 |

Bootstrap 5,000 paths: p50 Cal **2.16** / MDD **−34.9%** / P(MDD<-30%) = **82.0%** / P(MDD<-40%) = 22.7%.

VIX shuffle test에서 alpha 소실 → VIX-conditioning이 진짜 시그널 ✓.

## 7 탭

1. **📊 Overview** — V1 CHAMP_NOMARGIN spec + BASE 대비 알파
2. **📋 거래 내역** — CHAMP_NOMARGIN trades + equity curve (자유 시드/기간)
3. **📈 Stress Tests** — 8개 crisis × BASE vs CHAMP
4. **🎲 Bootstrap** — 5,000 paths 신뢰구간
5. **📅 Year-by-Year** — 17년 BASE vs CHAMP 연도별
6. **🔄 Multi-window OOS** — 1y/2y/3y/4y/5y/8y/10y/15y/16y rolling
7. **💰 BUBE Live** — Alpaca paper 실잔고 + 실시간 regime + V1 k_today 계산

## 데이터 갱신

`data/champ_nomargin/` 폴더 업데이트:
1. `python local/strategies/regime_rotation_validation/bube_champ_nomargin_16yr.py`
2. 산출물 7개 파일을 `data/champ_nomargin/`로 복사
3. `git push` → Streamlit Cloud 자동 reload

## 모바일 사용

iPhone Safari / Android Chrome에서 URL 열고 "홈 화면에 추가" — PWA로 앱처럼 사용.

## Secrets (Streamlit Cloud → App Settings)

| Key | Value |
|---|---|
| `ALPACA_API_KEY` | BUBE paper key (PK로 시작) |
| `ALPACA_SECRET_KEY` | BUBE paper secret |

## 로컬 실행

```bash
pip install -r requirements.txt
streamlit run app.py
```

## ⚠️ 운영 상태

- **백테**: V1 CHAMP_NOMARGIN (이 대시보드)
- **Alpaca paper 봇**: 현재 `bube_trader.py`는 k=1.0 BASE 운영 — CHAMP_NOMARGIN overlay deploy 별도 작업 대기
- **메모리**: `project_bube_overlays.md` (BUBE V1 CHAMP_NOMARGIN 검증), `feedback_idealized_models.md` (returns-stream 환상 라벨)
