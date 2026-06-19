# 순풍(順風) — Phase 0 리서치 노트

> 상승은 끝까지 끌고, 하락은 돛을 미리 접는다.
> 기존 평균회귀 계열(BUBE·떨사오팔·그리드·동파법·양변기)과 **상호보완**되는 추세추종 축.

**원칙**: 각 소스에서 "우리 환경(SOXL · IBKR · 7계좌 · 일봉/분봉)에 맞는 메커니즘 1개"만 추출해 모듈로 편입. 통째 복제 금지.

---

## 3열 정리 (메커니즘 / 수식 / 우리 환경 적용)

### ① Tony Cooper (2010) — *Alpha Generation and Risk Smoothing Using Managed Volatility* ★ 순풍의 심장

NAAIM 2010 Wagner Award 수상작. 레버리지 ETF 변동성 타겟팅의 바이블.

| 메커니즘 | 수식 / 핵심 | 우리 환경 적용성 |
|---|---|---|
| **수익률을 예측하기 어려워도 변동성은 예측 가능** → 변동성으로 레버리지를 동적 조절하면 레버리지의 상방은 취하고 하방은 줄인다 | 목표 변동성 `σ_target` 대비 예측변동성 `σ̂_t` 역가중: `leverage_t = σ_target / σ̂_t` (Cooper는 EGARCH로 σ̂ 추정) | **★ 채택(MVP 핵심)**. SOXL은 일일 3x 리셋 → 변동성 감쇠(decay)가 구조적. Cooper식 변동성 타겟팅으로 고변동 구간 비중을 자동 축소 = decay 방어. EGARCH 대신 실현변동성(20/60d) 또는 EWMA로 단순화 |
| 부수효과: 일간 수익률 첨도(kurtosis)·MDD 감소, 보수/공격 자산 배분 타이밍 신호 제공 | — | 첨도·MDD 감소는 -3x 상품에서 특히 가치. "타이밍 신호" 역할은 레짐 필터와 결합 |

### ② Cheng & Madhavan (2009) — *The Dynamics of Leveraged and Inverse ETFs*

일일 리밸런싱·경로 의존성의 수학적 근거. **왜 급락장에서 -3x가 치명적인가**의 출처.

| 메커니즘 | 수식 / 핵심 | 우리 환경 적용성 |
|---|---|---|
| LETF 수익은 **경로 의존적**(path-dependent). 일일 리밸런싱이 추세장에선 우호적(복리 부스트), 횡보·고변동장에선 적대적(decay) | 변동성 드래그 근사: `LETF_return ≈ L·R_index − ½·L·(L−1)·σ²` (L=3 → −3σ² 드래그). 추가로 운용보수 + 스왑 금융비 + 리밸런싱 슬리피지 | **★ 채택(합성 SOXL + 비용 모델)**. 이 식이 `data_pipeline.py`의 합성 SOXL 재구성 코어. 비용 항(0.89% 보수 + 금융비)을 반드시 반영해야 역연장 데이터가 현실적 |
| LETF 리밸런싱은 지수 방향과 같은 방향(장 마감 부근 매수/매도 압력) → 급락장 변동성 증폭 | — | 급락장에서 -3x가 "치명적"인 메커니즘 이해 → 디레버리징을 **선제적**으로 해야 하는 이유 (후행하면 decay+갭에 노출) |

### ③ Moskowitz, Ooi & Pedersen (2012) — *Time Series Momentum* (JFE 104:228–250)

추세추종의 학술적 근거. 58개 선물 25년 검증.

| 메커니즘 | 수식 / 핵심 | 우리 환경 적용성 |
|---|---|---|
| **과거 12개월 초과수익의 부호가 미래 수익의 양의 예측자** (TSM). 모든 자산군에서 성립 | 시그널 = `sign(R_{t-12m → t})`. 포지션 = `sign × (σ_target / σ̂)` (TSM 논문 자체가 변동성 스케일링 내장) | **★ 채택(레짐 필터의 한 축)**. SOXL 12개월(252d) 모멘텀 부호를 ON/OFF 스위치로. TSM이 이미 vol-scaling을 쓴다는 점이 ①과 자연스럽게 결합 |
| 추세는 ~1년 지속 후 장기 부분 반전 | — | 횡보·반전 구간 휩쏘 경고 → 평균회귀 엔진과 묶어야 하는 학술적 근거. 타임스톱/dwell로 완화 |

### ④ Harvey et al. (2018) — *The Impact of Volatility Targeting* (JPM 45:1)

변동성 타겟팅의 샤프·꼬리위험 개선 실증.

| 메커니즘 | 수식 / 핵심 | 우리 환경 적용성 |
|---|---|---|
| 변동성 타겟팅은 **리스크 자산(주식·크레딧)**의 샤프를 개선(채권·통화·원자재는 효과 미미) | 일/포트폴리오 레벨 모두 vol-scaling 적용 | **★ 채택 근거**. SOXL=극단적 리스크 자산 → 변동성 타겟팅 효과가 큰 영역. ①을 우리 자산에 적용해도 된다는 실증 뒷받침 |
| **꼬리위험(좌측 꼬리) 완화는 전 자산군 공통** — 좌측 꼬리는 보통 고변동 시점에 발생, 그때 target-vol 포지션이 작아 충격이 작다 | MDD·극단수익 확률 감소 | **★ 본 전략 목적과 직결**. "하락 국면 MDD를 단순 보유 대비 개선" 합격 기준의 메커니즘 |

### ⑤ Faber (2007) — *A Quantitative Approach to Tactical Asset Allocation*

단순 MA 타이밍 모델 — 레짐 필터 베이스라인.

| 메커니즘 | 수식 / 핵심 | 우리 환경 적용성 |
|---|---|---|
| **월말 종가 > 10개월 SMA → 보유, 아니면 현금**. 월 1회 리밸런싱 | `signal = price_eom > SMA(price, 10m)`. 100년+ S&P에서 buy&hold 대비 변동성↓ | **★ 채택(레짐 필터 베이스라인)**. 10개월 ≈ 200일. SOX 지수 / EWY 200MA 필터(KORU 분석 R²=0.97 검증)와 동형. 일봉에선 200일 SMA로 변환. 가장 단순·강건한 ON/OFF |
| 자본 보존(하락장 현금화) + 상승장 참여 | — | "하락 선제 디레버리징"의 가장 단순한 버전. 200MA 이탈 = 디레버리징 트리거 |

### ⑥ Antonacci — *Dual Momentum Investing* (GEM)

절대·상대 모멘텀 결합 → ON/OFF 스위치 강화.

| 메커니즘 | 수식 / 핵심 | 우리 환경 적용성 |
|---|---|---|
| **절대 모멘텀**(자산 자체 12m 수익 부호: 약세장 회피) + **상대 모멘텀**(자산 간 상대강도: 승자 선택) 결합 | 매월: 상대강도 우위 자산 선택 → 그 자산의 절대모멘텀 양수면 매수, 음수면 채권/현금 | **△ 부분 채택**. 절대 모멘텀 = ③ TSM과 같은 ON/OFF 축으로 흡수. 상대 모멘텀(SOXL vs 현금/채권 vs SOXS 로테이션)은 헤지 오버레이 단계에서 고려. MVP에선 절대 모멘텀만 |

### ⑦ (보조) CPPI — Black & Jones (1987), Constant Proportion Portfolio Insurance

수익 플로어 모듈의 기법.

| 메커니즘 | 수식 / 핵심 | 우리 환경 적용성 |
|---|---|---|
| 플로어 `F` 위 쿠션 `C = P − F`에 비례해 위험자산 비중 결정 | 위험자산 = `m × C`, 나머지 안전자산. m=3~5, F=초기의 80~90% | **△ Phase 3+ 오버레이**. 누적 수익 보호(이익 잠금)에 사용. m·F가 파라미터 증가 → MVP 제외, 검증 후 추가. 우리 변형: F를 "고점 대비 트레일링 플로어"로 두어 누적 수익 잠금 |

---

## 합성 데이터 방법론 (③ Cheng-Madhavan + 실무 소스)

SOXL 상장 2010-03 → **2008 금융위기·2000 닷컴 미포함**. 하락 대비 전략은 대공황급 구간 검증 필수.

**재구성 절차** (`data_pipeline.py` 구현):
1. 기초 지수: SOXX(상장 2001-07) 또는 SOX(^SOX) 일일 수익률 `R_t`
2. 합성 일일 수익률: `R_SOXL_t = 3·R_t − (보수 + 금융비)/252`
   - 보수 0.89%/yr, 금융비 ≈ 2×(연방기금금리 또는 90d T-bill + 스프레드)/252 (3x → 차입 2배)
   - 변동성 드래그는 일일 복리로 **자동 발생**(별도 −½L(L−1)σ² 항을 빼면 이중 계산이므로 일일 3x 복리만 적용)
3. 일일 복리로 가격 경로 생성 → 실제 SOXL 상장일에서 레벨 splice
4. 검증: 겹치는 구간(2010~)에서 합성 vs 실제 SOXL 일일 수익률 상관 ≥ 0.99 확인 (실무 보고 99% 수준)

⚠️ 역연장 구간은 실제 SOXL이 아님 → **참고용, 과신 금지**.

---

## Phase 0 결론 — MVP 모듈 확정

1차 구현(MVP) = **레짐 필터(⑤ Faber 200MA + ③ TSM 부호) × 변동성 타겟팅(① Cooper + ④ Harvey 실증)** 2개 모듈만.
헤지 오버레이(SOXS/현금)·수익 플로어(⑦ CPPI)는 MVP 검증 통과 후 오버레이로 추가. (PBO 상승 방지 — 최소 파라미터 원칙)

상세 후보 비교 → `module_candidates.md`.

---

## 출처

- Cooper, T. (2010) *Alpha Generation and Risk Smoothing Using Managed Volatility*. SSRN — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1664823
- Cheng, M. & Madhavan, A. (2009) *The Dynamics of Leveraged and Inverse Exchange-Traded Funds*. J. Investment Management — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1393995
- Moskowitz, T., Ooi, Y.H. & Pedersen, L.H. (2012) *Time Series Momentum*. JFE 104:228–250 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2089463
- Harvey, C. et al. (2018) *The Impact of Volatility Targeting*. JPM 45:1 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3175538
- Faber, M. (2007) *A Quantitative Approach to Tactical Asset Allocation*. SSRN — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461
- Antonacci, G. *Dual Momentum Investing* — https://www.optimalmomentum.com/
- CPPI (Black & Jones 1987) 개요 — https://quantpedia.com/introduction-to-cppi-constant-proportion-portfolio-insurance/
- 합성 LETF 방법론 참고 — https://github.com/nateGeorge/simulate_leveraged_ETFs , https://seekingalpha.com/article/4119259-simulating-historical-returns-leveraged-etfs
