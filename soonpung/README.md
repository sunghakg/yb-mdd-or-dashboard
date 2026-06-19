# 순풍(順風) — SOXL 추세추종 신규 엔진

> 상승은 끝까지 끌고, 하락은 돛을 미리 접는다.
> 기존 평균회귀 계열(BUBE·떨사오팔·그리드·동파법·양변기)과 **상호보완**되는 추세추종 축.

기존 엔진은 박스권에 강하나 ① 강한 상승장 조기 청산, ② 급락 시 물타기 손실 확대의 구조적 약점이 있다.
**순풍**은 이를 메우는 별도 엔진 — 단독 운용이 아니라 평균회귀 엔진과 **국면 분산**으로 묶어 전체 포트 변동성을 낮추는 게 본질.

```
순풍 = 레짐 필터(언제 탈지) × 변동성 타겟팅(얼마나 탈지) × 헤지 오버레이(어떻게 막을지)
```

## 진행 상태 (마일스톤)

| Phase | 내용 | 산출물 | 상태 |
|---|---|---|---|
| **0** | 리서치·노트 정리 | `research_notes.md`, `module_candidates.md` | ✅ 완료 |
| **1** | 데이터 파이프라인 + 합성 SOXL (GFC 포함) | `data_pipeline.py`, `build_gfc_inputs.py` | ✅ 완료 |
| **2** | 모듈 프로토타입 (레짐 / vol target) | `regime_filter.py`, `vol_target.py` | ✅ MVP 완료 |
| **3** | 통합 백테스트 + 국면별 분해 + 스윕 | `backtest_mvp.py` | ✅ MVP 백테스트 실행 완료 · 정식 검증(WF/PBO/DSR) 대기 |
| **4** | 페이퍼 트레이딩 (BUBE V2처럼 병렬) | — | ⬜ 예정 |
| **5** | 소액 실거래 → 확대 (IBKR 통합) | — | ⬜ 예정 |

## 백테스트 결과 (실데이터, 2009-05 ~ 2026-06)

데이터 출처: 사용자 Google Drive — 실제 SOXL OHLC(2010-03~) + USD(2x 반도체 ETF, 2008-01~)를
de-lever→3x 재구성한 **GFC 포함 합성 SOXL**(2008~2010 구간). 합성 vs 실제 일별수익률 상관 0.95.

**추천 구성: ma_only(Faber 200MA), σ_target=0.35, lev_max=1.0(margin 미사용)**

| | 순풍 MVP | SOXL 단순보유 |
|---|---|---|
| CAGR | +22.4% | +45.6% |
| **MDD** | **−52.1%** | **−90.5%** |
| Sharpe | 0.78 | 0.87 |
| Calmar | 0.43 | 0.50 |
| 평균 노출 | 0.40 | 1.00 |

위기 구간 방어 (★ 본 전략의 목적):

| 위기 | 순풍 | SOXL 단순보유 |
|---|---|---|
| **2008 GFC** | 레짐 OFF로 **전구간 현금 회피** (200MA 이탈) | −95%+ |
| **COVID 2020** (2/19~3/23) | −33% | −79% |
| **2022 베어** | −26% | −90% |

**해석**: lev_max=1.0이라 노출이 항상 단순보유 이하 → 메가 불장에서 raw 수익은 뒤지지만,
**MDD를 반토막내고 위기 낙폭을 1/2~1/3로 압축**. 즉 단독 알파가 아니라 **하락 방어 + 국면 분산용**.
기존 평균회귀 엔진과 묶었을 때의 합성 포트 효과 측정이 다음 단계.

스윕(combine × σ_target) 전체는 `data/soonpung/mvp_sweep.csv`. AND-게이트는 과보수적,
ma_only(200MA 단독)이 Calmar 최고 — TSM AND-게이트는 MVP에서 오히려 수익을 깎음.

## MVP 사양

```
position_t = regime_ON × clip(σ_target / σ̂_60d, 0, lev_max)

regime_ON  = (SOX > SMA200)  AND/OR  (sign(R_252d) > 0)   [dwell=5]
σ̂          = SOXL 실현변동성(60일, 연율화)
σ_target   = 0.35 (연)
lev_max    = 1.0  (margin 미사용 — CHAMP_NOMARGIN 정책 정합)
```

학술 근거: Cooper(2010) managed volatility ★, Cheng-Madhavan(2009) 경로의존성/비용,
Moskowitz-Ooi-Pedersen(2012) TSM, Harvey(2018) vol-targeting 실증, Faber(2007) 200MA, Antonacci dual momentum.
상세 → `research_notes.md`.

## 실행

```bash
pip install -r ../requirements.txt          # yfinance·pandas·numpy

python soonpung/data_pipeline.py            # 시세 다운로드 + 합성 SOXL + splice → data/soonpung/
python soonpung/backtest_mvp.py             # MVP 백테스트 + 국면별 분해 → data/soonpung/mvp_*.{json,csv}
```

> ⚠️ 이 저장소의 원격 세션 환경은 Yahoo Finance 아웃바운드가 막혀 있어 데이터 생성이 안 된다.
> 네트워크가 열린 로컬에서 위 명령을 실행하면 `data/soonpung/`에 산출물이 생성된다.
> (모듈/백테스트 로직은 합성 가격으로 end-to-end 자체검증 완료.)

## 파일

| 파일 | 역할 |
|---|---|
| `research_notes.md` | Phase 0 — 6개 논문 + CPPI 3열(메커니즘/수식/적용) 정리 |
| `module_candidates.md` | Phase 0 — 6개 모듈별 후보 비교 + MVP 확정 |
| `data_pipeline.py` | Phase 1 — 시세 다운로드 + 합성 SOXL 역연장(2001~) + splice + 검증 |
| `regime_filter.py` | 모듈 1 — Faber 200MA × MOP TSM 부호 + dwell |
| `vol_target.py` | 모듈 2 — Cooper 변동성 타겟(실현/EWMA) ★ |
| `backtest_mvp.py` | Phase 2/3 — no-lookahead 통합 백테스트 + **국면별 성과 분해(필수)** |

## 남은 작업 (Phase 3 정식 검증)

- Walk-forward · CSCV/PBO · Deflated Sharpe(DSR)+PSR
- Lookahead 자동 탐지(현재는 `position.shift(1)`로 구조적 방지)
- 기존 평균회귀 엔진과 상관계수 · 합성 포트 효과 측정
- 합격 기준: 하락 국면 MDD가 단순보유 대비 유의 개선 + 상승 포획률 충분 + PBO 낮음
- 검증 통과 후 헤지 오버레이(조건부 SOXS/현금) · 수익 플로어(CPPI) 추가
- 대시보드(`app.py`) 탭 편입 검토 — `data/soonpung/` 산출물 소비

## 리스크

- 횡보장 휩쏘 → 평균회귀 엔진과 **반드시 묶어** 운용
- 실현변동성 후행 → VVIX 선행 보조(Phase 2.5)
- 합성 데이터 한계 → 역연장 구간 과신 금지
- 과최적화 → MVP는 최소 파라미터, 모듈 추가 시 PBO 모니터링
