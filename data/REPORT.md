# 매매법 라이브러리 trade-level 백테 통합 검증 (2026-05-26)

> 모든 결과는 https://bear-upper-bound-escape-valve.streamlit.app/ 와 동일한 잣대 ─
> **trade-level OHLC, slippage 0.05%, commission 0.035% 편도, 실제 MOC·MOO·LOC·STOP 가격** ─ 으로 정렬했다.
>
> 사용자의 문제 제기: "여태까지 보여준 백테가 streamlit 대시보드 수준의 사실성을 갖추고 있는가, 허상은 아닌가?"

---

## TL;DR

- **운영중인 BUBE 16년**은 streamlit summary와 100% 일치 (5,203 trades, Cal 1.86, MDD −45.9%) — **신뢰 가능**
- **CHAMP alloc sweep k=0.72 (Cal 4.32), Slot rotation N7_H7 (Cal 3.53), V_bear_cap escape valve (Cal 6.52)** 는 모두 **returns-stream 합성 모델의 환상**. trade-level로 재시뮬하면 Cal 1.7~1.9 박스. → 운영 의사결정에서 제외
- 단독 매매법은 모두 trade-level 검증 완료: 양변기 v5 단독 (8y Cal 2.55)이 단독으론 가장 우수
- Legacy 매매법 (soxl_rsi/synthesis_nq/meta_pro)은 베이스라인 패배 또는 alpha 음수 → 운영 후보 X

---

## 1. ✅ 운영 가능 (trade-level OHLC, 검증 완료)

| 매매법 | 기간 | CAGR | MDD | Calmar | n_trades | win_rate | 운영 |
|---|---|---|---|---|---|---|---|
| **BUBE 통합** (T2 GOLD_ESCAPE bm=90) | 16.0y | 85.3% | **−45.9%** | **1.86** | 5,203 | — | ✅ 현재 운영중 |
| 양변기 v5 단독 (F1_A6) | 7.96y | 52.9% | −20.7% | **2.55** | 2,122 | — | BUBE 내 BEAR regime |
| 황금변기 단독 (RSI alloc) | 15.6y | 82.9% | −40.5% | **2.05** | 2,267 | 58.1% | BUBE 내 BEAR streak >90d (16년 0회 발동) |
| 롱변기 단독 (breakout 0.5%) | 15.6y | 119.7% | **−75.1%** | 1.59 | 3,238 | 54.9% | BUBE 내 BULL/NEUTRAL regime |

**핵심 인사이트**:
- 롱변기 단독은 MDD −75%로 거침. BUBE가 BEAR regime에서 양변기로 스위칭해서 MDD 30pp 완화
- 황금변기는 단독으론 Calmar 가장 높지만 (2.05), BUBE 16년 동안 BEAR streak >90일 조건 0번 → **dead code**
- 양변기 v5 8년 단독 Cal 2.55가 가장 높음 — BUBE 16년 통합 Cal 1.86보다 우월. 16년 확장 시 어떤 분포 나올지 별도 백테 필요

**검증 산출물**:
- BUBE 16년 사유 컬럼 추가본: [validation_2026_05/bube_trades_enriched.csv](local/strategies/validation_2026_05/bube_trades_enriched.csv) (5,203 rows × 16 cols)
  - 컬럼: date, strategy, leg, ticker, action, qty, price, pnl, side, **regime_today, active_today, bear_streak, equity_eod, cash_eod, reason_short, reason_detail**
- 검증 일치 확인: [validation_2026_05/bube_summary_check.json](local/strategies/validation_2026_05/bube_summary_check.json)
- 전체 분류: [validation_2026_05/all_strategies_classified.json](local/strategies/validation_2026_05/all_strategies_classified.json)

---

## 2. 🚨 환상 (returns-stream idealized) — 운영 사용 금지

이 항목들은 모두 **일별 returns 곱셈/슬롯 합성**으로 만들어진 합성 백테이고, trade-level OHLC path dependency (intraday stop, gap-through, MOO/LOC 슬리피지)를 무시한다.

### 2.1 CHAMP alloc sweep k=0.72

| 모델 | 데이터 | Calmar | MDD | CAGR |
|---|---|---|---|---|
| **memory 권고치** (returns-stream) | 8-slot 합성 × cash sleeve k=0.72 | **4.32** | −20.0% | 86.6% |
| **trade-level 재시뮬** (BUBE eq × k=0.72) | 16y BUBE equity × k overlay | **1.77** | −34% | 60% |

- 코드 출처: [slot_rotation_alloc_sweep.py](local/strategies/regime_rotation_validation/slot_rotation_alloc_sweep.py) (returns-stream) vs [bube_alloc_sweep_tradelevel.py](local/strategies/regime_rotation_validation/bube_alloc_sweep_tradelevel.py) (trade-level)
- **갭의 원인**: 8개 슬롯이 독립적으로 회복한다는 가정. 실제로는 SOXL/SOXS 단일자산이라 슬롯 분산 0
- **MDD −20% 목표 (trade-level 운영 추정)**: k≈0.43, CAGR ~34%, Cal ~1.70

### 2.2 Slot rotation N7_H7

| 메모리 권고치 (returns-stream) | Cal **3.53**, MDD −11pp 개선, CAGR +7pp |
|---|---|
| trade-level | 동일자산 SOXL에서 슬롯 분산 효과 = 0 |

- 코드: [slot_rotation_position.py:36-55](local/strategies/regime_rotation_validation/slot_rotation_position.py:36) — `bube_equity.csv`의 일별 returns만으로 슬롯별 곱셈
- cross_asset_validation에서 18 자산 0/4 통과 ([[project_bear_cap_cross_asset]]) — 다자산 확장도 reject

### 2.3 V_bear_cap escape valve

| 모델 | 결과 |
|---|---|
| returns-stream (memory의 Cal 6.52) | 8년 idealized cherry-pick |
| **trade-level (streamlit)** | 8y Cal **2.40** / 16y Cal **1.87** / MDD −45.9% |
| trade-level 발동 횟수 | 16년 **0회** → dead code |

- 코드: [V_bear_cap_comprehensive.py](local/strategies/regime_rotation_validation/V_bear_cap_comprehensive.py)
- 이미 [[project_bube_critique]] 메모리에 명시되어 있던 내용을 ★환상★ 라벨로 명시화

**메모리 업데이트 완료**: [feedback_idealized_models.md](C:\Users\sungh\.claude\projects\C--Users-sungh\memory\feedback_idealized_models.md) — returns-stream 결과로 운영 권고 금지.

---

## 3. ❌ Legacy — 베이스라인 패배 / 운영 후보 X

| 매매법 | 기간 | CAGR | MDD | Calmar | 벤치 CAGR | Alpha | 운영 |
|---|---|---|---|---|---|---|---|
| soxl_rsi (떨사오팔) | 5y | 7.81% | −37.8% | 0.21 | SOXL B&H ~8% | ≈0 | ❌ B&H에도 못 이김 |
| synthesis_nq_v5base | 16.3y | 3.5% | −12.8% | 0.27 | NQ 18.3% | **−14.76** | ❌ 베이스라인 압도적 패배 |
| meta_pro | 16.1y | 17.5% | −19.4% | 0.90 | 42.1% | **−24.56** | ❌ B&H 1/2.4 |
| soxl_dip / soxl_dip_v3 | — | — | — | — | — | — | trade_log만 있고 summary 없음 → 미완 |
| dongpa | — | — | — | — | — | — | 메모리상 재현 실패 ([[project_strategies]]) |
| regime_rotation P5.5 | — | — | — | — | — | — | output 없음, code 분류 불확실 |

---

## 4. 모델 라벨 가이드 (앞으로 모든 보고)

| 라벨 | 의미 | 운영 사용 |
|---|---|---|
| **trade-level OHLC** | 실제 일/분봉 OHLC + slippage + commission + MOC/MOO/LOC/STOP 실제 가격 | ✅ 가능 |
| **returns-stream (idealized)** | 일별 returns 곱셈 / 슬롯 합성 / cash sleeve overlay만 | ❌ idealized 라벨 필수 |
| **trade-level overlay** | trade-level equity 위에 k 같은 단순 선형 sleeve | ⚠️ Calmar 거의 보존, MDD 선형 — 운영 가능 |

**규칙** (메모리 [[feedback-idealized-models]]):
- 보고 시 라벨 항상 명시
- returns-stream 결과로 alloc·slot 수·진입 빈도 같은 운영 파라미터 권고 금지
- 운영 추정치는 trade-level OHLC 백테 또는 trade-level overlay만 사용

---

## 5. 다음 작업 후보 (사용자 결정 필요)

1. **양변기 v5 단독 16년 확장 백테** — 8년 Cal 2.55가 16년에선 어떻게 변하는지. jongsajongpal_backtest.py를 2010-05-25 시작으로 재실행
2. **dashboard에 enriched 거래내역 노출** — yb-mdd-or-dashboard `app.py`의 거래내역 탭이 현재 bube_full/trades.csv를 보여주는데, validation_2026_05/bube_trades_enriched.csv로 교체하면 한 줄씩 사유 + regime + bear_streak 컬럼 노출
3. **regime_rotation P5.5 / dongpa output 생성** — code는 있으니 한 번 돌려서 trade-level 결과 확보 → 분류 확정
4. **bube_trades_enriched에 trigger_value / alloc_mode 추가** — multi_strategy_paper.simulate_day를 fork해서 reason 컬럼 풍부화 (운영 코드 안 건드림)

---

## 6. 사용한 코드

- 검증 스크립트: [validation_2026_05/enrich_bube_trades.py](local/strategies/validation_2026_05/enrich_bube_trades.py)
- 분류 스크립트: [validation_2026_05/classify_strategies.py](local/strategies/validation_2026_05/classify_strategies.py)
- BUBE 운영 백테: [regime_rotation_validation/bube_full_backtest.py](local/strategies/regime_rotation_validation/bube_full_backtest.py)
- alloc sweep 비교: [regime_rotation_validation/bube_alloc_sweep_tradelevel.py](local/strategies/regime_rotation_validation/bube_alloc_sweep_tradelevel.py)
- 단독 백테: [jongsajongpal_backtest.py](local/strategies/jongsajongpal_backtest.py), [longbyungi_backtest.py](local/strategies/longbyungi_backtest.py), [goldenbyungi_backtest.py](local/strategies/goldenbyungi_backtest.py)
