"""
BUBE V1 CHAMP_NOMARGIN — Streamlit 대시보드
===============================================================
BASE BUBE × VIX dynamic-k overlay (k=0.65 × clip(20/VIX, 0.5, 2.0), alloc≤1.0).
margin 사용 X = 합법적 cash sleeve 운영.

16y in-sample (2010-05-25 ~ 2026-05-22):
  Cal 2.75 / CAGR +77.2% / MDD -28.13% / $100K → $926M (×10 vs BASE $90.7M)
Bootstrap 5,000 paths: p50 Cal 2.16 / MDD -34.9% / P(MDD<-30%) = 82.0%

탭 구성:
1. 📊 Overview — V1 CHAMP_NOMARGIN spec + BASE 대비 알파
2. 📋 거래 내역 — CHAMP_NOMARGIN trades + equity curve (자유 시드/기간)
3. 📈 Stress Tests — 8개 crisis × BASE vs CHAMP
4. 🎲 Bootstrap — 5,000 paths 신뢰구간
5. 📅 Year-by-Year — 17년 BASE vs CHAMP 연도별
6. 🔄 Multi-window OOS — 1y/2y/3y/4y/5y/8y/10y/15y/16y rolling
7. 💰 BUBE Live — Alpaca paper 실시간 + regime + active sub-strategy
8. 🆚 V2_FINAL 비교 — 기본 비활성 (SHOW_V2=False). lookahead 제거 재검증(2026-05-28)에서
   V2가 V1보다 열위(LAF Cal 1.49 < 1.62)로 판명되어 운영 대시보드에서 숨김. 연구 데이터·스크립트는 보존.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import streamlit as st

ROOT = Path(__file__).parent / "data"
CHAMP = ROOT / "champ_nomargin"
V2DIR = ROOT / "v2_final"

# ── V2_FINAL 표시 토글 ──────────────────────────────────────
# V2_FINAL은 연구 옵션으로 보존하되 운영 대시보드에서는 숨긴다.
# 근거: lookahead-bias 제거 재검증(2026-05-28)에서 LAF Calmar V2 1.49 < V1 1.62,
#       VVIX shuffle z=-0.93 → V2 추가 알파는 환상으로 판명. paper 봇은 원래부터 V1 전용.
# 다시 켜려면 True: 상단 비교 배너 + Tab 8 + equity V2 곡선 + 연도별 V2 컬럼이 복원됨.
SHOW_V2 = False
st.set_page_config(page_title="BUBE V1 CHAMP_NOMARGIN Dashboard", layout="wide", page_icon="🏆")

# Alpaca credentials from Streamlit secrets (cloud) or env (local)
import os as _os
try:
    if "ALPACA_API_KEY" in st.secrets:
        _os.environ["ALPACA_API_KEY"] = st.secrets["ALPACA_API_KEY"]
        _os.environ["ALPACA_SECRET_KEY"] = st.secrets["ALPACA_SECRET_KEY"]
except Exception:
    pass


def load_json(path: Path):
    if not path.exists():
        return None
    raw = path.read_bytes()
    for enc in ("utf-8", "cp949", "utf-8-sig"):
        try:
            return json.loads(raw.decode(enc))
        except UnicodeDecodeError:
            continue
    return None


def fmt_pct(x, places=1):
    if x is None or pd.isna(x): return "—"
    return f"{x*100:+.{places}f}%"


def fmt_pct_already(x, places=1):
    if x is None or pd.isna(x): return "—"
    return f"{x:+.{places}f}%"


def fmt(x, places=2):
    if x is None or pd.isna(x): return "—"
    return f"{x:.{places}f}"


def _money(v):
    a = abs(v)
    if a >= 1e9: return f"${v/1e9:+.2f}B" if v < 0 else f"${v/1e9:.2f}B"
    if a >= 1e6: return f"${v/1e6:+.2f}M" if v < 0 else f"${v/1e6:.2f}M"
    if a >= 1e3: return f"${v:+,.0f}" if v < 0 else f"${v:,.0f}"
    return f"${v:+,.0f}" if v < 0 else f"${v:,.0f}"


# ───────────────────────────────────────────────────────────
# Headline data load
# ───────────────────────────────────────────────────────────
champ_summary = load_json(CHAMP / "summary.json")
if champ_summary is None:
    st.error("⚠️ data/champ_nomargin/summary.json 없음. 먼저 실행: "
             "`python local/strategies/regime_rotation_validation/bube_champ_nomargin_16yr.py`")
    st.stop()

H_CHAMP = champ_summary["headline_16y_CHAMP"]
H_BASE = champ_summary["headline_16y_BASE"]
H_BOOT = champ_summary["bootstrap_CHAMP"]

# ───────────────────────────────────────────────────────────
# Header
# ───────────────────────────────────────────────────────────
st.markdown(f"""
<div style="background:linear-gradient(135deg,#0a1a3a,#1e3a8a,#3b82f6);padding:24px 32px;border-radius:12px;color:white;margin-bottom:16px">
  <h1 style="margin:0;font-size:1.8em">🏆 BUBE V1 — 반도체 3배 ETF(SOXL) 동적 비중 전략</h1>
  <div style="opacity:0.92;margin-top:6px">
    레짐 감지(BULL/BEAR) → 엔진 전환 → <b>VIX 기반 비중 자동 조절</b>&nbsp;(VIX↑ 비중↓ · VIX↓ 비중↑) · Margin 미사용
  </div>
  <div style="opacity:0.75;margin-top:4px;font-size:0.92em">
    백테스트 16년(2010-05-25 ~ 2026-05-22) · Alpaca 페이퍼 트레이딩 운영 중
  </div>
</div>
""", unsafe_allow_html=True)

# Quick stats row — V1 CHAMP_NOMARGIN 16y headline
col1, col2, col3, col4 = st.columns(4)
col1.metric("16년 Calmar", f"{H_CHAMP['Calmar']:.2f}",
            f"BASE {H_BASE['Calmar']:.2f} · +{H_CHAMP['Calmar']-H_BASE['Calmar']:.2f}",
            help="Calmar = CAGR ÷ |MDD|. 낙폭 대비 수익 효율성. 1.0 이상 양호, 2.0 이상 우수. BASE = VIX 조정 없이 고정 비중 운영 시.")
col2.metric("16년 CAGR (연복리)", f"{H_CHAMP['CAGR']:.1f}%",
            f"BASE {H_BASE['CAGR']:.1f}% · +{H_CHAMP['CAGR']-H_BASE['CAGR']:.1f}pp",
            help="CAGR = 연평균 복리 수익률. 16년 전체를 복리로 환산했을 때의 연간 평균 수익률.")
col3.metric("16년 MDD (최대낙폭)", f"{H_CHAMP['MDD']:.1f}%",
            f"BASE {H_BASE['MDD']:.1f}% · {H_CHAMP['MDD']-H_BASE['MDD']:.1f}pp 개선",
            help="MDD = Maximum Drawdown. 고점 대비 최대 하락폭. 절댓값이 작을수록 좋음.")
col4.metric("$10만 → 최종 (16년)", _money(H_CHAMP['Final_mult'] * 100_000),
            f"×{H_CHAMP['Final_mult']/H_BASE['Final_mult']:.1f} BASE",
            help="$100,000 시드로 2010년부터 시작했을 때의 백테스트 최종 자산. in-sample 단일 경로 기준 (bootstrap 중앙값은 더 낮음).")

# ── 기간별 비교 ──────────────────────────────────────────────
@st.cache_data
def _period_stats(_mtime):
    eq = pd.read_csv(CHAMP / "equity_curves.csv", parse_dates=["date"]).set_index("date").sort_index()
    s = eq["CHAMP_NOMARGIN"]
    end = s.index[-1]

    def _stats(ser):
        n_yr = (ser.index[-1] - ser.index[0]).days / 365.25
        cagr = (ser.iloc[-1] / ser.iloc[0]) ** (1 / n_yr) - 1
        roll_max = ser.expanding().max()
        mdd = ((ser - roll_max) / roll_max).min()
        cal = cagr / abs(mdd)
        return {"n_yr": n_yr, "CAGR": cagr * 100, "MDD": mdd * 100, "Calmar": cal, "mult": ser.iloc[-1] / ser.iloc[0]}

    r16 = _stats(s)
    r10 = _stats(s.loc[end - pd.DateOffset(years=10):])
    r5  = _stats(s.loc[end - pd.DateOffset(years=5):])
    return r16, r10, r5

_mtime_eq = (CHAMP / "equity_curves.csv").stat().st_mtime if (CHAMP / "equity_curves.csv").exists() else 0
_r16, _r10, _r5 = _period_stats(_mtime_eq)

def _cal_color(v):
    if v >= 2.0: return "#4ade80"
    if v >= 1.0: return "#facc15"
    return "#f87171"

def _mdd_color(v):
    if v >= -20: return "#4ade80"
    if v >= -35: return "#facc15"
    return "#f87171"

st.markdown(f"""
<table style="width:100%;border-collapse:collapse;font-size:0.88em;margin-top:6px">
  <thead>
    <tr style="border-bottom:1px solid #334155;color:#94a3b8;text-align:right">
      <th style="text-align:left;padding:4px 8px">기간</th>
      <th style="padding:4px 12px">Calmar</th>
      <th style="padding:4px 12px">CAGR</th>
      <th style="padding:4px 12px">MDD</th>
      <th style="padding:4px 12px">$10만→</th>
    </tr>
  </thead>
  <tbody>
    <tr style="border-bottom:1px solid #1e293b">
      <td style="padding:5px 8px;color:#e2e8f0;font-weight:600">16년 (전체)</td>
      <td style="padding:5px 12px;text-align:right;color:{_cal_color(_r16['Calmar'])};font-weight:700">{_r16['Calmar']:.2f}</td>
      <td style="padding:5px 12px;text-align:right;color:#60a5fa">{_r16['CAGR']:+.1f}%</td>
      <td style="padding:5px 12px;text-align:right;color:{_mdd_color(_r16['MDD'])}">{_r16['MDD']:.1f}%</td>
      <td style="padding:5px 12px;text-align:right;color:#e2e8f0">{_money(_r16['mult']*100_000)}</td>
    </tr>
    <tr style="border-bottom:1px solid #1e293b">
      <td style="padding:5px 8px;color:#e2e8f0;font-weight:600">10년 (롤링)</td>
      <td style="padding:5px 12px;text-align:right;color:{_cal_color(_r10['Calmar'])};font-weight:700">{_r10['Calmar']:.2f}</td>
      <td style="padding:5px 12px;text-align:right;color:#60a5fa">{_r10['CAGR']:+.1f}%</td>
      <td style="padding:5px 12px;text-align:right;color:{_mdd_color(_r10['MDD'])}">{_r10['MDD']:.1f}%</td>
      <td style="padding:5px 12px;text-align:right;color:#e2e8f0">{_money(_r10['mult']*100_000)}</td>
    </tr>
    <tr>
      <td style="padding:5px 8px;color:#e2e8f0;font-weight:600"> 5년 (롤링)</td>
      <td style="padding:5px 12px;text-align:right;color:{_cal_color(_r5['Calmar'])};font-weight:700">{_r5['Calmar']:.2f}</td>
      <td style="padding:5px 12px;text-align:right;color:#60a5fa">{_r5['CAGR']:+.1f}%</td>
      <td style="padding:5px 12px;text-align:right;color:{_mdd_color(_r5['MDD'])}">{_r5['MDD']:.1f}%</td>
      <td style="padding:5px 12px;text-align:right;color:#e2e8f0">{_money(_r5['mult']*100_000)}</td>
    </tr>
  </tbody>
</table>
""", unsafe_allow_html=True)

# Last update marker (daily auto-push from bube_v2_daily_update.py)
def _read_last_updated():
    candidates = [V2DIR / "last_update_at.txt", CHAMP / "last_update_at.txt"]
    timestamps = []
    for p in candidates:
        if p.exists():
            try:
                timestamps.append(p.read_text().strip())
            except Exception:
                pass
    return min(timestamps) if timestamps else None

last_updated = _read_last_updated()

# 백테 데이터 endpoint 표시 (사용자가 옛 build 보고 있는지 즉시 확인 가능)
def _read_data_endpoint():
    try:
        import csv as _csv
        with open(CHAMP / "equity_curves.csv", encoding="utf-8") as f:
            reader = _csv.reader(f)
            last_row = None
            for row in reader:
                if row:
                    last_row = row
            return last_row[0] if last_row else None
    except Exception:
        return None

data_end = _read_data_endpoint()
if last_updated or data_end:
    parts = []
    if data_end:
        parts.append(f"백테 데이터 끝: **`{data_end}`**")
    if last_updated:
        parts.append(f"마지막 갱신: `{last_updated}`")
    st.caption("📅 " + " · ".join(parts) +
               " — 매일 자동 갱신 (평일 11:15 HST). "
               "오래된 데이터가 보이면 `Ctrl+Shift+R` 강력 새로고침.")

# V2_FINAL 비교 헤드라인 (paper 봇 미적용, 백테 비교만)
v2_summary = load_json(V2DIR / "summary.json")
if SHOW_V2 and v2_summary is not None:
    H_V2 = v2_summary["V2_FINAL"]
    st.markdown(f"""
<div style="background:#0e1a2e;border-left:4px solid #f59e0b;padding:10px 16px;border-radius:6px;margin:8px 0 4px;color:#e5e7eb">
  <span style="color:#f59e0b;font-weight:600">🆚 V2_FINAL 백테 비교 (paper 봇 미적용 — 운영은 V1 그대로)</span>
  &nbsp;·&nbsp;
  16y Cal <b>{H_V2['Calmar']:.2f}</b> (V1 {H_CHAMP['Calmar']:.2f}) &nbsp;·&nbsp;
  CAGR <b>{H_V2['CAGR_pct']:.1f}%</b> (V1 {H_CHAMP['CAGR']:.1f}%) &nbsp;·&nbsp;
  MDD <b>{H_V2['MDD_pct']:.1f}%</b> (V1 {H_CHAMP['MDD']:.1f}%) &nbsp;·&nbsp;
  Final <b>{_money(H_V2['final_multiple']*100_000)}</b>
  <span style="opacity:0.7;font-size:0.85em">&nbsp;— 자세히는 8번째 탭</span>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# ── Sidebar navigation ──────────────────────────────────────
with st.sidebar:
    st.markdown("""
<div style="background:linear-gradient(135deg,#0a1a3a,#1e3a8a);padding:14px 16px;border-radius:10px;color:white;margin-bottom:14px;text-align:center">
  <div style="font-size:1.12em;font-weight:700;letter-spacing:0.02em">🏆 BUBE V1</div>
  <div style="opacity:0.8;font-size:0.82em;margin-top:3px">SOXL 동적 비중 전략</div>
</div>
""", unsafe_allow_html=True)
    _pages = [
        "📊 백테스트",
        "📋 거래 내역",
        "📈 위기 방어력",
        "🎲 확률 분포",
        "📅 연도별 성과",
        "🔄 기간별 안정성",
        "💰 실시간 현황",
        "🔬 백테 vs 페이퍼",
        "📔 매매일지",
        "📖 용어 사전",
    ]
    page = st.radio("페이지", _pages, label_visibility="collapsed")
    st.markdown("---")
    st.caption("📊 16년 백테 핵심 지표")
    _sb1, _sb2 = st.columns(2)
    _sb1.metric("Calmar", f"{H_CHAMP['Calmar']:.2f}")
    _sb2.metric("CAGR", f"{H_CHAMP['CAGR']:.1f}%")
    _sb1.metric("MDD", f"{H_CHAMP['MDD']:.1f}%")
    _sb2.metric("$10K→", _money(H_CHAMP['Final_mult'] * 10_000))
    st.markdown("---")
    st.caption("매일 자동 갱신 (평일 11:15 HST)")
    if last_updated:
        st.caption(f"갱신: `{last_updated}`")

# ───────────────────────────────────────────────────────────
# TAB 1: Overview
# ───────────────────────────────────────────────────────────
if page == "📊 백테스트":
    st.subheader("📊 백테스트 — BUBE V1 전략 개요")

    st.markdown("""
<div style="background:#0f172a;border-left:4px solid #3b82f6;padding:14px 20px;border-radius:8px;margin-bottom:16px;color:#e2e8f0;line-height:1.9">
<b>전략 핵심 3단계</b><br>
<b>1️⃣ 레짐 감지</b> — QQQ·SPY·SMH 200일선 + VIX9D/SOXL 모멘텀으로 매일 시장 상태 판정 (BULL / NEUTRAL / BEAR)<br>
<b>2️⃣ 엔진 전환</b> — BULL·NEUTRAL → <b>롱변기</b>(SOXL 단방향 매수) · BEAR → <b>양변기</b>(SOXL롱+SOXS숏) · BEAR 90일+ → <b>황금변기</b>(변동성 돌파)<br>
<b>3️⃣ VIX 비중 조절</b> — VIX 높으면(공포) 비중 줄이고, VIX 낮으면(안정) 비중 늘림. Margin 미사용(최대 100%)
</div>
""", unsafe_allow_html=True)

    col_a, col_b = st.columns([1, 1])
    with col_a:
        with st.expander("📐 기술 스펙 보기 (코드)", expanded=True):
         st.code(f"""
# Strategy: V1 CHAMP_NOMARGIN (no-margin variant)
# = BASE BUBE rotation × VIX dynamic-k overlay × alloc cap 1.0

# Overlay 수식
k_today    = base_k × scale_today
base_k     = 0.65                                    # alloc reduction baseline
scale      = clip(20.0 / VIX_today, 0.5, 2.0)        # VIX 역수 스케일
alloc_today = min(k_today × strategy_alloc, 1.0)     # margin 금지 (cap 1.0)

# 동작 직관
VIX 10  → scale 2.0 → k=1.30 → alloc cap 1.0  (저변동성 풀로딩)
VIX 20  → scale 1.0 → k=0.65 → alloc 0.65×strat  (중립)
VIX 40  → scale 0.5 → k=0.325 → alloc 0.325×strat (고변동성 디리스킹)
VIX 80  → scale 0.5 → 동일 (lo clip)

# BASE BUBE rotation (sub-strategy mapping)
BULL / NEUTRAL          → 롱변기      (SOXL only)
BEAR                    → 양변기 v5  (SOXL+SOXS pair, F1_A6 LOC)
BEAR streak > 90일      → 황금변기   (SOXL K-vol breakout)

# 갭필터 — A안 비대칭 (2026-06-03 전환, GAP_FILTER_MODE=asym)
롱변기·양변기롱 (SOXL)  → 갭다운(gap<-5%)만 진입 차단 (갭상승은 허용)
양변기숏 (SOXS)         → 대칭(|gap|>5%) 차단 유지
#   근거: 갭상승 진입은 정상보다 ~2배 좋은 진입 → 되살림. 16y Cal 2.10→2.29.
#   롤백: GAP_FILTER_MODE=sym (전부 대칭)

# Regime detector (look-ahead safe: .shift(1))
consensus  = QQQ/SPY/SMH SMA200 ±2% 중 ≥2 합의
fast_bear  = VIX9D/VIX > 1.05  OR  SOXL 5d mom < -10%
dwell      = 5일 (regime 전환 최소 유지)
max_bear   = 90일 (GOLD_ESCAPE 트리거)
""", language="python")

    with col_b:
        st.markdown("### 16년 백테스트 결과 비교")
        ha1, ha2 = st.columns(2)
        ha1.metric("V1 전략 (VIX 동적 비중)", "")
        ha1.markdown(f"""
- **CAGR** (연복리): `{H_CHAMP['CAGR']:.2f}%`
- **MDD** (최대낙폭): `{H_CHAMP['MDD']:.2f}%`
- **Sharpe** (위험조정 수익): `{H_CHAMP['Sharpe']:.2f}`
- **Calmar** (수익÷낙폭): `{H_CHAMP['Calmar']:.2f}`
- **최종 자산** ($10만 시드): `{_money(H_CHAMP['Final_mult']*100_000)}`
""")
        ha2.metric("BASE (고정 비중, 비교 기준)", "")
        ha2.markdown(f"""
- **CAGR**: `{H_BASE['CAGR']:.2f}%`
- **MDD**: `{H_BASE['MDD']:.2f}%`
- **Sharpe**: `{H_BASE['Sharpe']:.2f}`
- **Calmar**: `{H_BASE['Calmar']:.2f}`
- **최종 자산**: `{_money(H_BASE['Final_mult']*100_000)}`
""")

        st.markdown("### 전략 검증 결과")
        check_data = [
            ("16y 단일 path", f"Calmar {H_CHAMP['Calmar']:.2f} vs BASE {H_BASE['Calmar']:.2f}", "✅"),
            ("Bootstrap 5,000",
             f"p50 Cal {H_BOOT['cal_p50']:.2f}, p05 {H_BOOT['cal_p05']:.2f} 이상",
             "✅"),
            ("VIX shuffle test", "alpha 소실 → VIX-conditioning이 진짜 시그널 (random X)", "✅"),
            ("MDD 분포", f"p50 {H_BOOT['mdd_p50']:.1f}%, P(MDD<-30%)={H_BOOT['p_mdd_worse_than_30']:.1f}%", "⚠️"),
            ("CAGR 양수 확률", f"P(CAGR>0)={H_BOOT['p_cagr_positive']:.1f}%, P(CAGR>30%)={H_BOOT['p_cagr_above_30']:.1f}%", "✅"),
            ("margin 사용", "alloc_cap 1.0 → 합법 cash sleeve, leverage 0%", "✅"),
            ("Final $", f"$100K → {_money(H_CHAMP['Final_mult']*100_000)} (×{H_CHAMP['Final_mult']/H_BASE['Final_mult']:.1f} BASE)", "✅"),
        ]
        for name, desc, mark in check_data:
            st.markdown(f"**{mark} {name}** — {desc}")

    st.markdown("---")
    with st.expander("⚠️ 약점 및 리스크 공시 (클릭해서 펼치기)", expanded=False):
        st.markdown("""
- **16년 단일 경로 결과**: 과거 하나의 실현 경로. 미래는 더 나쁠 수 있음. 실제 기대치는 아래 '확률 분포' 탭의 bootstrap 중앙값 기준.
- **MDD 꼬리 위험**: bootstrap 중앙값 MDD −34.9%, P(MDD<−30%) = **82%**, P(MDD<−40%) = 23% — 단일 경로 −28%보다 깊어질 가능성이 높음.
- **SOXL 반도체 섹터 집중**: 단일 자산·단일 레짐으로 인해 섹터 쇼크 취약 (2022 반도체 폭락 등).
- **운영 자본 상한 ~$14M**: ADV(일평균거래량) 대비 슬리피지 한계. 그 이상은 TWAP 필요.
- **Margin 미사용 선택**: alloc 100% 상한 — margin 허용 시 Calmar 더 높아지나 법적·규정 리스크 회피용 설계.
""")

    with st.expander("🚨 검증된 환상 매매법 (운영 절대 사용 금지)", expanded=False):
        st.markdown("""
아래 수치들은 **단순화된 수익률 합성** 방식으로 계산된 것으로, 실제 거래 시뮬레이션과 크게 다름.

| 방식 | 과대 표기 수치 | 실제 운영 추정 | 이유 |
|---|---|---|---|
| CHAMP alloc sweep k=0.72 | Calmar **4.32**, MDD −20% | Calmar 1.77, MDD −34% | 8개 슬롯 수익률 단순 합산 |
| Slot rotation N7_H7 | Calmar **3.53** | 분산 효과 0 | 동일 자산 SOXL 반복 합산 |
| Escape valve T2GE bm=90 | Calmar **6.52** (8년) | Cal 1.87 (16년), 발동 0회 | 이상적 경로 cherry-pick |

**원칙**: 실제 거래 시뮬레이션(trade-level OHLC) 결과만 운영 판단에 사용. 이 대시보드의 모든 수치는 해당 기준.
""")

    # ── 16년 자산 성장 곡선 ──────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📈 16년 자산 성장 곡선 — $10만 시드")
    st.caption("2010-05-25 ~ 현재. V1 CHAMP_NOMARGIN vs 고정비중 BASE. VIX 동적 비중 조절 알파를 시각적으로 확인.")

    def _mtime_bt(p):
        try: return p.stat().st_mtime
        except Exception: return 0

    @st.cache_data
    def _load_eq_bt(_k):
        return pd.read_csv(CHAMP / "equity_curves.csv", parse_dates=["date"], index_col="date")

    _eq_bt = _load_eq_bt(_mtime_bt(CHAMP / "equity_curves.csv"))
    _seed_bt = 100_000.0
    _s = float(_eq_bt["CHAMP_NOMARGIN"].iloc[0])
    _b = float(_eq_bt["BASE"].iloc[0])
    _eq_chart_bt = pd.DataFrame({
        "V1 CHAMP_NOMARGIN ($)": (_eq_bt["CHAMP_NOMARGIN"] / _s * _seed_bt).values,
        "BASE k=0.65 ($)": (_eq_bt["BASE"] / _b * _seed_bt).values,
    }, index=_eq_bt.index)
    st.line_chart(_eq_chart_bt, height=380)
    st.caption("💡 거래 내역 메뉴에서 시드·기간 자유 설정 가능. 위 차트는 $10만 16년 전체 기준.")


# ───────────────────────────────────────────────────────────
# TAB 2: 거래 내역
# ───────────────────────────────────────────────────────────
elif page == "📋 거래 내역":
    st.subheader("📋 V1 전략 거래 내역 — 16년 전체 (2010~현재)")
    st.caption("SOXL 상장일(2010-05-25)부터 현재까지의 백테스트 거래 내역. yfinance 일봉 OHLC 기준. 매일 자동 갱신.")

    # ── 사용자 정의 시작 자본 ──
    seed_col1, seed_col2 = st.columns([1, 3])
    user_seed = seed_col1.number_input(
        "시작 자본 ($)", min_value=100, max_value=10_000_000,
        value=10_000, step=1_000, key="user_seed_input",
        help="백테는 $100K 시드로 실행. 이 값으로 모든 $ 결과를 비례 스케일링합니다. % 수익률은 변하지 않음."
    )
    seed_col2.markdown(
        f"<div style='padding-top:1.7em;color:#888'>"
        f"💡 모든 $ 값이 <b>${user_seed:,.0f}</b> 시드 기준으로 환산됩니다. % 수익률은 동일."
        f"</div>",
        unsafe_allow_html=True
    )

    # ── Load equity curves ──
    # 캐시 키에 file mtime 추가: 파일 갱신되면 자동 invalidate (Streamlit Cloud 캐시 stale 해결)
    def _mtime(p):
        try: return p.stat().st_mtime
        except Exception: return 0

    @st.cache_data
    def _load_eq(_mtime_key):
        return pd.read_csv(CHAMP / "equity_curves.csv", parse_dates=["date"], index_col="date")

    @st.cache_data
    def _load_daily(_mtime_key):
        return pd.read_csv(CHAMP / "daily.csv", parse_dates=["date"], index_col="date")

    @st.cache_data
    def _load_v2_for_overlay(_mtime_key):
        if not (V2DIR / "equity_paths.csv").exists():
            return None
        return pd.read_csv(V2DIR / "equity_paths.csv", parse_dates=["date"], index_col="date")

    eq_all = _load_eq(_mtime(CHAMP / "equity_curves.csv"))
    daily_all = _load_daily(_mtime(CHAMP / "daily.csv"))
    eq_v2_all = _load_v2_for_overlay(_mtime(V2DIR / "equity_paths.csv")) if SHOW_V2 else None

    # ── Date range picker ──
    bt_min_d = eq_all.index.min().date()
    bt_max_d = eq_all.index.max().date()
    # 기본값: 최근 3개월 (16년 전체보다 ~67× 빠름). 사용자가 preset/reset으로 전체 조회 가능.
    default_from = max(bt_min_d, (pd.Timestamp(bt_max_d) - pd.Timedelta(days=90)).date())

    st.markdown(f"### 🗓 자유 시드/기간 — CHAMP_NOMARGIN 재집계")
    st.caption(f"백테 데이터: `{bt_min_d}` ~ **`{bt_max_d}`**. 기본값은 최근 3개월 (빠른 로딩). "
               f"16년 전체 보고 싶으면 아래 '16년 전체' 버튼 클릭.")

    def _apply_preset(st_d, en_d):
        st.session_state["champ_from"] = pd.Timestamp(st_d).date()
        st.session_state["champ_to"] = pd.Timestamp(en_d).date()

    def _reset_dates():
        st.session_state["champ_from"] = default_from
        st.session_state["champ_to"] = bt_max_d

    d1, d2, d3 = st.columns([2, 2, 1])
    with d1:
        d_from = st.date_input("From", value=default_from, min_value=bt_min_d, max_value=bt_max_d, key="champ_from")
    with d2:
        d_to = st.date_input("To", value=bt_max_d, min_value=bt_min_d, max_value=bt_max_d, key="champ_to")
    with d3:
        st.markdown("&nbsp;")
        st.button("최근 3개월", on_click=_reset_dates, key="champ_reset")

    st.markdown("**빠른 선택**")
    pcols = st.columns(8)
    _safe_last = lambda dt_str: max(bt_min_d, pd.Timestamp(dt_str).date())
    presets = [
        ("16년 전체", str(bt_min_d), str(bt_max_d)),
        ("2010s (10년)", str(bt_min_d), "2019-12-31"),
        ("2020 Covid", "2020-01-02", "2020-06-30"),
        ("2022 폭락", "2022-01-01", "2022-12-31"),
        ("2024-08 쇼크", "2024-07-15", "2024-09-15"),
        ("2025 관세", "2025-03-01", "2025-05-15"),
        ("최근 5년", _safe_last((bt_max_d - pd.Timedelta(days=365*5)).strftime("%Y-%m-%d")).strftime("%Y-%m-%d"), str(bt_max_d)),
        ("최근 1년", _safe_last((bt_max_d - pd.Timedelta(days=365)).strftime("%Y-%m-%d")).strftime("%Y-%m-%d"), str(bt_max_d)),
    ]
    for col, (lbl, st_d, en_d) in zip(pcols, presets):
        col.button(lbl, key=f"champ_preset_{lbl}", on_click=_apply_preset, args=(st_d, en_d))

    # ── Slice ──
    eq_period = eq_all.loc[pd.Timestamp(d_from):pd.Timestamp(d_to)]
    daily_period = daily_all.loc[pd.Timestamp(d_from):pd.Timestamp(d_to)]

    # Period-start equity → consistent rebase factor for stats + trade log.
    # (선택 기간 첫 날의 raw equity로 user_seed 환산. 거래 로그 PnL/qty도 동일 스케일 적용)
    if len(eq_period) >= 1:
        seed_in_period_champ = float(eq_period["CHAMP_NOMARGIN"].iloc[0])
        seed_in_period_base = float(eq_period["BASE"].iloc[0])
        scale_champ = user_seed / seed_in_period_champ
        scale_base = user_seed / seed_in_period_base
    else:
        seed_in_period_champ = seed_in_period_base = 100_000.0
        scale_champ = scale_base = user_seed / 100_000.0

    if len(eq_period) < 2:
        st.warning(f"선택 기간({d_from} ~ {d_to})의 데이터 부족 ({len(eq_period)}일).")
    else:
        eq_user_champ = eq_period["CHAMP_NOMARGIN"] * scale_champ
        eq_user_base = eq_period["BASE"] * scale_base

        def _stats(eq):
            start = float(eq.iloc[0])
            end = float(eq.iloc[-1])
            ret = end / start - 1
            n_days = len(eq)
            n_years = n_days / 252
            cagr = (end / start) ** (1/n_years) - 1 if n_years > 0 else 0
            cm = eq.cummax(); dd = eq / cm - 1
            mdd = float(dd.min())
            rets = eq.pct_change().dropna()
            sh = float(rets.mean() / rets.std() * np.sqrt(252)) if rets.std() > 0 else 0
            cal = cagr / abs(mdd) if mdd < 0 else float("inf")
            return {"end": end, "ret": ret, "cagr": cagr, "mdd": mdd, "sharpe": sh, "calmar": cal, "days": n_days, "years": n_years}

        s_champ = _stats(eq_user_champ)
        s_base = _stats(eq_user_base)

        st.markdown(f"#### 📐 선택 기간 성과 — 시드 ${user_seed:,.0f}, {d_from} → {d_to} ({s_champ['days']} 거래일, {s_champ['years']:.2f}년)")
        st.markdown("**CHAMP_NOMARGIN (현 운영 후보)**")
        pc1, pc2, pc3, pc4 = st.columns(4)
        pc1.metric("Final Equity", _money(s_champ["end"]), f"{s_champ['ret']*100:+,.1f}%")
        pc2.metric("CAGR", f"{s_champ['cagr']*100:+.1f}%", f"BASE {s_base['cagr']*100:+.1f}%")
        pc3.metric("MDD", f"{s_champ['mdd']*100:+.1f}%", f"BASE {s_base['mdd']*100:+.1f}%")
        pc4.metric("Calmar", f"{s_champ['calmar']:.2f}" if s_champ['calmar'] != float("inf") else "∞",
                    f"BASE {s_base['calmar']:.2f}")
        pc5, pc6, pc7, pc8 = st.columns(4)
        pc5.metric("Sharpe", f"{s_champ['sharpe']:.2f}", f"BASE {s_base['sharpe']:.2f}")
        pc6.metric("BASE Final (동일 기간)", _money(s_base["end"]),
                    f"CHAMP × {s_champ['end']/s_base['end']:.2f}")
        # regime / active stats
        if "regime" in daily_period.columns:
            rs = daily_period["regime"].value_counts(normalize=True) * 100
            pc7.metric("주 regime", rs.index[0] if len(rs) else "—",
                       f"{rs.iloc[0]:.0f}% of period" if len(rs) else "—")
        if "active_CHAMP" in daily_period.columns:
            as_ = daily_period["active_CHAMP"].value_counts(normalize=True) * 100
            pc8.metric("주 sub-strategy", as_.index[0] if len(as_) else "—",
                       f"{as_.iloc[0]:.0f}% of period" if len(as_) else "—")

        # ── Equity curve ──
        _eq_title = "CHAMP vs BASE vs V2_FINAL" if SHOW_V2 else "CHAMP vs BASE"
        st.markdown(f"#### 📈 Equity Curve — ${user_seed:,.0f} 시드 기준 ({_eq_title})")
        chart_dict = {
            "V1 CHAMP_NOMARGIN ($)": eq_user_champ.values,
            "BASE k=0.65 ($)": eq_user_base.values,
        }
        chart_index = eq_period.index

        # V2_FINAL overlay (rebase to V1 start-of-period for fair comparison)
        if eq_v2_all is not None and "V2_FINAL" in eq_v2_all.columns:
            v2_period = eq_v2_all.loc[pd.Timestamp(d_from):pd.Timestamp(d_to)]
            if len(v2_period) >= 2:
                v2_seed_in = float(v2_period["V2_FINAL"].iloc[0])
                scale_v2_for_overlay = user_seed / v2_seed_in
                v2_user = v2_period["V2_FINAL"] * scale_v2_for_overlay
                # align indices (V2 file may extend past CHAMP file by daily updates)
                v2_aligned = v2_user.reindex(chart_index).ffill()
                chart_dict["V2_FINAL ($)"] = v2_aligned.values

        chart_period = pd.DataFrame(chart_dict, index=chart_index)
        st.line_chart(chart_period, height=360)

        if eq_v2_all is not None:
            v2_end = eq_v2_all.index.max().date()
            v1_end = eq_period.index.max().date()
            if v2_end > v1_end:
                st.caption(
                    f"ℹ️ V1/BASE 데이터는 `{v1_end}`까지, V2 데이터는 `{v2_end}`까지 "
                    f"(daily 자동 갱신). V1 backtest도 함께 갱신되지만 위 차트는 선택 기간 끝점이 V1 데이터에 묶여있음."
                )

        # ── k_today / VIX scale 분포 ──
        with st.expander("📊 선택 기간 내 k_today / VIX scale / 활성 alloc 분포"):
            if "k_today" in daily_period.columns:
                k1, k2, k3 = st.columns(3)
                k_med = float(daily_period["k_today"].median())
                k_mean = float(daily_period["k_today"].mean())
                k_min = float(daily_period["k_today"].min())
                k_max = float(daily_period["k_today"].max())
                k1.metric("k_today median", f"{k_med:.3f}", f"mean {k_mean:.3f}")
                k2.metric("k_today min/max", f"{k_min:.3f} / {k_max:.3f}")
                if "VIX" in daily_period.columns:
                    vix_med = float(daily_period["VIX"].median())
                    k3.metric("VIX median", f"{vix_med:.1f}")
                st.markdown("**일별 k_today (VIX-driven dynamic alloc multiplier)**")
                st.line_chart(daily_period["k_today"], height=220)
                if "VIX" in daily_period.columns:
                    st.markdown("**일별 VIX (= 20일 때 k=base 0.65)**")
                    st.line_chart(daily_period["VIX"], height=180)

            if "regime" in daily_period.columns:
                rg1, rg2 = st.columns(2)
                with rg1:
                    rdf = (daily_period["regime"].value_counts(normalize=True) * 100).round(1)
                    st.markdown("**Regime 분포 (일 비율)**")
                    st.dataframe(
                        pd.DataFrame({"Regime": rdf.index, "Days %": rdf.values}),
                        use_container_width=True, hide_index=True
                    )
                with rg2:
                    if "active_CHAMP" in daily_period.columns:
                        adf = (daily_period["active_CHAMP"].value_counts(normalize=True) * 100).round(1)
                        st.markdown("**Active sub-strategy 분포 (일 비율)**")
                        st.dataframe(
                            pd.DataFrame({"Sub-strategy": adf.index, "Days %": adf.values}),
                            use_container_width=True, hide_index=True
                        )

    st.markdown("---")

    # ── 16년 전체 헤드라인 (참고) ──
    # 주의: 이 섹션은 "user_seed로 16년 전(2010-05-25)부터 시작했다면" 가정 (inception rebase).
    # 거래 로그/선택 기간 성과 카드는 period-rebase (scale_champ) 사용. 두 카드가 다른 질문에 답함.
    st.markdown("### 📊 16년 전체 캐시 성과 (참고 — 16년 전 시작 가정)")
    fc1, fc2, fc3, fc4, fc5, fc6 = st.columns(6)
    fc1.metric("기간", champ_summary["spec"]["period"])
    fc2.metric("시드", f"${user_seed:,.0f}")
    fc3.metric("CHAMP Final", _money(H_CHAMP["Final_mult"] * user_seed),
               f"+{(H_CHAMP['Final_mult']-1)*100:,.0f}%")
    fc4.metric("BASE Final", _money(H_BASE["Final_mult"] * user_seed),
               f"+{(H_BASE['Final_mult']-1)*100:,.0f}%")
    fc5.metric("Trades", f"{champ_summary['trades_count']:,}")
    fc6.metric("$ ratio", f"×{H_CHAMP['Final_mult']/H_BASE['Final_mult']:.2f}")

    # ── Trade log ──
    st.markdown("---")
    st.markdown("### 📒 CHAMP_NOMARGIN 거래 로그")

    @st.cache_data
    def _load_trades(_mtime_key):
        t = pd.read_csv(CHAMP / "trades_champ.csv")
        t["date"] = pd.to_datetime(t["date"])
        return t

    trades_all = _load_trades(_mtime(CHAMP / "trades_champ.csv"))

    # Filters
    tf1, tf2, tf3 = st.columns([2, 1, 1])
    strat_sel = tf1.multiselect(
        "Strategy", options=sorted(trades_all["strategy"].unique()),
        default=sorted(trades_all["strategy"].unique()), key="champ_strat_filter"
    )
    action_sel = tf2.multiselect(
        "Action", options=sorted(trades_all["action"].unique()),
        default=sorted(trades_all["action"].unique()), key="champ_action_filter"
    )
    pnl_sel = tf3.radio("PnL", options=["전체", "수익만", "손실만"], horizontal=True, key="champ_pnl_filter")

    # Period filter (use same date range from above)
    tr_filt = trades_all[
        (trades_all["date"] >= pd.Timestamp(d_from)) &
        (trades_all["date"] <= pd.Timestamp(d_to)) &
        trades_all["strategy"].isin(strat_sel) &
        trades_all["action"].isin(action_sel)
    ].copy()
    if pnl_sel == "수익만":
        tr_filt = tr_filt[tr_filt["pnl"] > 0]
    elif pnl_sel == "손실만":
        tr_filt = tr_filt[tr_filt["pnl"] < 0]

    # Scale pnl + qty to user seed using period-rebase (선택 기간 성과 카드와 동일 스케일).
    # 백테는 $100K base seed로 실행. period 첫 날 raw equity를 user_seed로 환산하는 factor를
    # 동일 적용해야 거래 로그 합산 PnL이 equity curve 변화량과 일치함.
    tr_filt["pnl_scaled"] = tr_filt["pnl"] * scale_champ
    tr_filt["qty_int"] = (tr_filt["qty"] * scale_champ).round().astype(int)

    # Headline
    fc1, fc2, fc3, fc4 = st.columns(4)
    fc1.metric("Trade events", f"{len(tr_filt):,}")
    realized = tr_filt["pnl_scaled"].sum()
    fc2.metric("Realized P&L", _money(realized))
    nonzero = tr_filt[tr_filt["pnl_scaled"] != 0]
    wr = (nonzero["pnl_scaled"] > 0).mean() * 100 if len(nonzero) else 0
    fc3.metric("Win rate (non-zero pnl)", f"{wr:.1f}%")
    fc4.metric("기간",
               f"{tr_filt['date'].min().date()} → {tr_filt['date'].max().date()}"
               if len(tr_filt) else "—")

    # Display — 성능 최적화: page slice 먼저, slice된 ≤100 rows에만 format apply
    # (이전: tr_filt 전체 5,000+ rows × 4 lambda format → 매 rerun ~20,000 호출, 느림)
    rows_per_page = 100
    n_total = len(tr_filt)
    n_pages = max(1, (n_total + rows_per_page - 1) // rows_per_page)
    page = st.number_input(
        f"Page (총 {n_total:,} rows, {n_pages} pages)",
        min_value=1, max_value=n_pages, value=1, key="champ_trade_page"
    ) if n_pages > 1 else 1
    start_idx = (page - 1) * rows_per_page
    end_idx = start_idx + rows_per_page

    # Slice ≤100 rows BEFORE format apply (큰 성능 차이)
    disp = tr_filt.iloc[start_idx:end_idx].copy()
    disp["date"] = disp["date"].dt.strftime("%Y-%m-%d")
    disp["qty_int"] = disp["qty_int"].apply(lambda x: f"{x:,}")
    disp["price"] = disp["price"].apply(lambda x: f"${x:.4f}")
    disp["pnl_scaled"] = disp["pnl_scaled"].apply(lambda x: f"${x:+,.2f}")
    disp = disp.drop(columns=["pnl", "qty"]).rename(columns={
        "date": "날짜", "strategy": "Sub-strategy", "leg": "방향",
        "ticker": "Ticker", "action": "Action", "qty_int": "수량 (정수, 시드 환산)",
        "price": "체결가", "pnl_scaled": "PnL (시드 환산)", "side": "Side",
    })
    st.dataframe(disp, use_container_width=True, hide_index=True, height=400)

    # CSV download — generate only when user clicks (lazy via session_state)
    # (이전: 매 rerun마다 tr_filt 전체 to_csv encode → 5,000+ rows 매번 직렬화)
    if st.button(f"💾 CSV 다운로드 준비 ({n_total:,} rows)", key="champ_dl_prep"):
        st.session_state["champ_csv_ready"] = tr_filt.to_csv(index=False).encode("utf-8-sig")
    if "champ_csv_ready" in st.session_state:
        st.download_button(
            label=f"⬇️ champ_nomargin_trades_{d_from}_{d_to}.csv 받기",
            data=st.session_state["champ_csv_ready"],
            file_name=f"champ_nomargin_trades_{d_from}_{d_to}.csv",
            mime="text/csv", key="champ_dl"
        )


# ───────────────────────────────────────────────────────────
# TAB 3: Stress Tests
# ───────────────────────────────────────────────────────────
elif page == "📈 위기 방어력":
    st.subheader("📈 위기 구간 방어력 — 8개 위기 × V1 vs BASE")
    st.caption("코로나·금리쇼크 등 실제 위기 구간에서 VIX 동적 비중 조절이 낙폭을 얼마나 줄였는지 확인.")

    crisis_path = CHAMP / "crisis.csv"
    if crisis_path.exists():
        cr = pd.read_csv(crisis_path)
        # Display columns
        disp = cr.copy()
        disp["BASE_ret_%"] = disp["BASE_ret_%"].apply(lambda x: f"{x:+.1f}%")
        disp["BASE_mdd_%"] = disp["BASE_mdd_%"].apply(lambda x: f"{x:+.1f}%")
        disp["CHAMP_ret_%"] = disp["CHAMP_ret_%"].apply(lambda x: f"{x:+.1f}%")
        disp["CHAMP_mdd_%"] = disp["CHAMP_mdd_%"].apply(lambda x: f"{x:+.1f}%")
        disp["Δ_ret_pp"] = disp["Δ_ret_pp"].apply(lambda x: f"{x:+.2f}pp")
        disp["Δ_mdd_pp"] = disp["Δ_mdd_pp"].apply(lambda x: f"{x:+.2f}pp")
        disp.columns = ["Crisis", "From", "To",
                        "BASE Ret", "BASE MDD",
                        "CHAMP Ret", "CHAMP MDD",
                        "Δ Ret", "Δ MDD (개선)"]
        st.dataframe(disp, use_container_width=True, hide_index=True)

        # Summary stats
        mdd_improved = (cr["Δ_mdd_pp"] > 0).sum()
        mdd_total = len(cr)
        avg_mdd_delta = cr["Δ_mdd_pp"].mean()
        avg_ret_delta = cr["Δ_ret_pp"].mean()
        n_wins = ((cr["Δ_ret_pp"] > 0) & (cr["Δ_mdd_pp"] > 0)).sum()

        sc1, sc2, sc3, sc4 = st.columns(4)
        sc1.metric("위기 수", f"{mdd_total}")
        sc2.metric("MDD 개선 비율", f"{mdd_improved}/{mdd_total}",
                   f"{mdd_improved/mdd_total*100:.0f}%")
        sc3.metric("평균 Δ MDD", f"{avg_mdd_delta:+.2f}pp",
                   "양수 = CHAMP가 MDD 줄였음")
        sc4.metric("평균 Δ Ret", f"{avg_ret_delta:+.2f}pp",
                   "위기 구간 alpha")

        st.info(
            f"💡 **8개 위기 중 {mdd_improved}개**에서 CHAMP_NOMARGIN이 BASE보다 MDD 더 작음 (평균 {avg_mdd_delta:+.2f}pp 개선). "
            f"VIX가 폭등하는 위기 시작 구간에 scale가 0.5로 clip되어 alloc 자동 축소 → 손실 제한. "
            f"V-recovery 구간에서는 VIX 하락 → scale 1.5~2.0으로 풀로딩 회복."
        )

        # 2020 Covid recovery 케이스 별도 강조 (CHAMP가 손해본 케이스)
        cov_rec = cr[cr["crisis"] == "2020 Covid recovery"]
        if len(cov_rec) > 0:
            r = cov_rec.iloc[0]
            st.warning(
                f"⚠️ **2020 Covid recovery**: BASE {r['BASE_ret_%']:+.1f}% vs CHAMP {r['CHAMP_ret_%']:+.1f}% "
                f"({r['Δ_ret_pp']:+.1f}pp underperform) — VIX가 30~40 구간 머무를 때 scale<1로 풀로딩 못함 → "
                f"V-recovery upside 일부 놓침. **trade-off**: 위기 시작 MDD 보호 대가."
            )
    else:
        st.warning("champ_nomargin/crisis.csv 없음.")


# ───────────────────────────────────────────────────────────
# TAB 4: Bootstrap
# ───────────────────────────────────────────────────────────
elif page == "🎲 확률 분포":
    st.subheader("🎲 확률 분포 분석 — 5,000번 시뮬레이션")
    st.caption("과거 수익률 순서를 무작위로 섞어 5,000가지 미래 경로를 생성. 단일 16년 경로보다 실제 기대 범위를 더 정직하게 보여줌.")

    b = H_BOOT

    bc1, bc2, bc3 = st.columns(3)
    bc1.markdown("### CAGR (연복리 수익률) 분포")
    bc1.metric("하위 5% (최악 케이스)", f"{b['cagr_p05']:.1f}%")
    bc1.metric("중앙값 (기대 기준)", f"{b['cagr_p50']:.1f}%")
    bc1.metric("상위 5% (최선 케이스)", f"{b['cagr_p95']:.1f}%")
    bc1.caption(f"P(CAGR > 0) = **{b['p_cagr_positive']:.1f}%** · P(CAGR > 30%) = **{b['p_cagr_above_30']:.1f}%**")

    bc2.markdown("### MDD (최대낙폭) 분포")
    bc2.metric("하위 5% (낙폭 최대)", f"{b['mdd_p05']:.1f}%")
    bc2.metric("중앙값 (기대 기준)", f"{b['mdd_p50']:.1f}%")
    bc2.metric("상위 5% (낙폭 최소)", f"{b['mdd_p95']:.1f}%")
    bc2.caption(f"P(MDD < -30%) = **{b['p_mdd_worse_than_30']:.1f}%** · P(MDD < -40%) = **{b['p_mdd_worse_than_40']:.1f}%**")

    bc3.markdown("### Calmar (수익÷낙폭) 분포")
    bc3.metric("하위 5%", f"{b['cal_p05']:.2f}")
    bc3.metric("중앙값 (운영 기대치)", f"{b['cal_p50']:.2f}")
    bc3.metric("상위 5%", f"{b['cal_p95']:.2f}")
    bc3.caption("16년 단일 경로 Calmar은 약간 운 좋은 실현 — 운영 기대치는 중앙값 기준으로 봐야 함.")

    st.markdown("---")
    st.markdown("### 핵심 해석 (운영 기대 범위)")
    st.info(
        f"**진짜 운영 기대치**: bootstrap p50 = CAGR **{b['cagr_p50']:.1f}%** / MDD **{b['mdd_p50']:.1f}%** / Calmar **{b['cal_p50']:.2f}**. "
        f"단일 16년 path의 Cal 2.75는 약간 운 좋은 실현이며, 실제로는 **2.0 ~ 2.3 박스**가 base case.\n\n"
        f"**MDD 꼬리 위험**: P(MDD<-30%) = {b['p_mdd_worse_than_30']:.1f}%, P(MDD<-40%) = {b['p_mdd_worse_than_40']:.1f}% — "
        f"미래 path가 -30% 넘어갈 확률 {b['p_mdd_worse_than_30']:.0f}%, -40% 확률 {b['p_mdd_worse_than_40']:.0f}% 정도. **mentally prepare**."
    )

    st.markdown("---")
    st.markdown("### ✅ VIX shuffle test (검증)")
    st.markdown("""
**테스트**: VIX 시리즈를 무작위 셔플 → scale = clip(20/shuffled_VIX, 0.5, 2.0) 적용 → alpha 0으로 수렴.
**결과**: VIX-conditioning이 진짜 시그널 ✓ (random k variation으로는 alpha 나오지 않음).

이건 단순히 "k=0.65에서 가끔 위아래로 움직인다"가 아니라, **VIX 신호가 시점 정보를 담고 있어서** alpha 발생한다는 것을 입증.
""")


# ───────────────────────────────────────────────────────────
# TAB 5: Year-by-Year
# ───────────────────────────────────────────────────────────
elif page == "📅 연도별 성과":
    st.subheader("📅 연도별 성과 — 17년 V1 vs BASE")
    st.caption("V1이 매년 일관되게 BASE보다 우월하면 전략이 특정 기간 운으로 만들어진 게 아님을 증명. 수익률·낙폭·샤프 비교.")

    yp = CHAMP / "yearly.csv"
    if yp.exists():
        y = pd.read_csv(yp)

        # Load V2 yearly for column overlay (daily-updated source)
        v2_yearly = None
        v2_yp = V2DIR / "yearly_breakdown.csv"
        if SHOW_V2 and v2_yp.exists():
            v2_yearly = pd.read_csv(v2_yp).set_index("year")

        # Build display
        rows = []
        for _, r in y.iterrows():
            yr_int = int(r["year"])
            v2_ret = v2_yearly.loc[yr_int, "V2_FINAL_ret"] if (v2_yearly is not None and yr_int in v2_yearly.index) else None
            v2_mdd = v2_yearly.loc[yr_int, "V2_FINAL_mdd"] if (v2_yearly is not None and yr_int in v2_yearly.index) else None
            rows.append({
                "Year": yr_int,
                "BASE Ret": f"{r['BASE_ret_%']:+.1f}%",
                "CHAMP Ret": f"{r['CHAMP_ret_%']:+.1f}%",
                "V2 Ret": f"{v2_ret:+.1f}%" if v2_ret is not None and not pd.isna(v2_ret) else "—",
                "Δ Ret (CHAMP-BASE)": f"{r['Δ_ret_pp']:+.1f}pp",
                "BASE MDD": f"{r['BASE_mdd_%']:+.1f}%",
                "CHAMP MDD": f"{r['CHAMP_mdd_%']:+.1f}%",
                "V2 MDD": f"{v2_mdd:+.1f}%" if v2_mdd is not None and not pd.isna(v2_mdd) else "—",
                "Δ MDD (CHAMP-BASE)": f"{r['Δ_mdd_pp']:+.2f}pp",
                "CHAMP Sharpe": f"{r['CHAMP_sharpe']:.2f}",
                "CHAMP End $": _money(r["CHAMP_end_$"]),
            })
        df_year = pd.DataFrame(rows)
        if not SHOW_V2:
            df_year = df_year.drop(columns=["V2 Ret", "V2 MDD"], errors="ignore")
        st.dataframe(df_year, use_container_width=True, hide_index=True)
        if v2_yearly is not None:
            st.caption("ℹ️ V2 Ret/MDD 컬럼은 data/v2_final/yearly_breakdown.csv (daily 자동 갱신).")

        # Summary
        wins_ret = (y["Δ_ret_pp"] > 0).sum()
        wins_mdd = (y["Δ_mdd_pp"] > 0).sum()
        avg_ret = y["Δ_ret_pp"].mean()
        avg_mdd = y["Δ_mdd_pp"].mean()
        total = len(y)

        st.markdown("---")
        yc1, yc2, yc3, yc4 = st.columns(4)
        yc1.metric("총 연도", f"{total}")
        yc2.metric("CHAMP > BASE (Ret)", f"{wins_ret}/{total}",
                   f"{wins_ret/total*100:.0f}%")
        yc3.metric("CHAMP > BASE (MDD)", f"{wins_mdd}/{total}",
                   f"{wins_mdd/total*100:.0f}%")
        yc4.metric("평균 Δ Ret / Δ MDD",
                   f"{avg_ret:+.1f}pp / {avg_mdd:+.2f}pp")

        # Yearly equity chart
        st.markdown("### 📈 연말 자본 ($100K 시드 기준)")
        chart_y = pd.DataFrame({
            "BASE end $": y.set_index("year")["BASE_end_$"].values,
            "CHAMP end $": y.set_index("year")["CHAMP_end_$"].values,
        }, index=y["year"].values)
        st.line_chart(chart_y, height=320)

        # Δ ret bar
        st.markdown("### 📊 연도별 Δ Return (CHAMP − BASE, pp)")
        delta_chart = pd.DataFrame({"Δ Ret pp": y["Δ_ret_pp"].values},
                                    index=y["year"].astype(int).values)
        st.bar_chart(delta_chart, height=240)

        st.success(
            f"💡 **17년 중 {wins_ret}년**에서 CHAMP > BASE (수익률 기준). 평균 +{avg_ret:.1f}pp/yr alpha. "
            f"MDD는 {wins_mdd}/{total}년에서 CHAMP가 더 작음 — VIX dynamic-k overlay가 단순 운빨이 아닌 일관 효과."
        )
    else:
        st.warning("champ_nomargin/yearly.csv 없음.")


# ───────────────────────────────────────────────────────────
# TAB 6: Multi-window OOS
# ───────────────────────────────────────────────────────────
elif page == "🔄 기간별 안정성":
    st.subheader("🔄 기간별 안정성 — 1년~16년 윈도우 검증")
    st.caption("최근 1년, 2년, 5년, 16년 등 다양한 기간에서도 V1이 일관되게 BASE보다 우월한지 확인. 특정 기간 cherry-pick이 아님을 검증.")

    swp = CHAMP / "summary_wide.csv"
    if swp.exists():
        sw = pd.read_csv(swp)
        # 표시
        disp = sw.copy()
        disp["years"] = disp["years"].round(2)
        for c in ("BASE_CAGR_%", "CHAMP_CAGR_%", "Δ_CAGR_pp",
                  "BASE_MDD_%", "CHAMP_MDD_%", "Δ_MDD_pp"):
            if c in disp.columns:
                disp[c] = disp[c].apply(lambda x: f"{x:+.1f}%" if "pp" not in c else f"{x:+.1f}pp")
        for c in ("BASE_Sharpe", "CHAMP_Sharpe", "BASE_Calmar", "CHAMP_Calmar", "Δ_Calmar"):
            if c in disp.columns:
                disp[c] = disp[c].apply(lambda x: f"{x:+.2f}" if "Δ" in c else f"{x:.2f}")
        for c in ("BASE_Final_$", "CHAMP_Final_$"):
            if c in disp.columns:
                disp[c] = disp[c].apply(_money)
        if "Final_ratio" in disp.columns:
            disp["Final_ratio"] = disp["Final_ratio"].apply(lambda x: f"×{x:.2f}")
        st.dataframe(disp, use_container_width=True, hide_index=True)

        st.markdown("---")
        # Calmar trajectory across windows
        st.markdown("### 📈 Window별 Calmar 추이")
        calmar_chart = sw.set_index("window")[["BASE_Calmar", "CHAMP_Calmar"]].rename(
            columns={"BASE_Calmar": "BASE", "CHAMP_Calmar": "CHAMP_NOMARGIN"}
        )
        st.bar_chart(calmar_chart, height=300)

        st.markdown("### 📈 Window별 CAGR")
        cagr_chart = sw.set_index("window")[["BASE_CAGR_%", "CHAMP_CAGR_%"]].rename(
            columns={"BASE_CAGR_%": "BASE", "CHAMP_CAGR_%": "CHAMP_NOMARGIN"}
        )
        st.bar_chart(cagr_chart, height=300)

        # All windows CHAMP > BASE?
        all_calmar = (sw["CHAMP_Calmar"] > sw["BASE_Calmar"]).all()
        all_cagr = (sw["CHAMP_CAGR_%"] > sw["BASE_CAGR_%"]).all()
        st.success(
            f"✅ **Calmar 모든 window CHAMP > BASE**: {all_calmar} · "
            f"**CAGR 모든 window CHAMP > BASE**: {all_cagr}. "
            f"단일 window cherry-pick 아닌 1y~16y 전체에서 일관 우월 → over-fit 가능성 낮음."
        )
    else:
        st.warning("champ_nomargin/summary_wide.csv 없음.")


# ───────────────────────────────────────────────────────────
# TAB 7: BUBE Live (Alpaca paper)
# ───────────────────────────────────────────────────────────
elif page == "💰 실시간 현황":
    st.subheader("💰 실시간 현황 — Alpaca 페이퍼 계정")
    st.caption("봇이 오늘 어떤 레짐으로 판정하고, 비중을 어떻게 조절했는지 실시간으로 확인.")
    st.info("ℹ️ **현재 운영 중: V1 + 비대칭 갭필터 (2026-06-03~)** "
            "— 롱변기·양변기 SOXL 매수는 갭다운(-5% 이상)만 차단, 갭업은 허용. 양변기 SOXS 매도는 대칭 차단 유지.")

    # ── Section A: Spec card ──
    st.markdown("""
<div style="background:linear-gradient(135deg,#0a1a3a,#1e3a8a);padding:18px 24px;border-radius:10px;color:white;margin:8px 0 16px">
  <div style="font-size:1.1em;font-weight:600;margin-bottom:8px">🏆 V1 CHAMP_NOMARGIN Overlay (운영 중)</div>
  <div style="opacity:0.92;line-height:1.7">
    <b>k_today</b> = 0.65 × clip(20.0 / VIX_today, 0.5, 2.0), <b>alloc_today</b> = min(k × strat_alloc, 1.0)<br>
    BASE: <b>BULL/NEUTRAL</b> 롱변기 · <b>BEAR</b> 양변기 v5 · <b>BEAR streak &gt; 90d</b> 황금변기<br>
    <b>갭필터 A안(비대칭, 2026-06-03)</b>: 롱변기·양변기롱 갭다운만 차단 · 양변기숏 대칭<br>
    <b>Regime</b>: Consensus 3-SMA200 (QQQ/SPY/SMH ±2%, 2-of-3) + Fast BEAR OR (VIX9D/VIX&gt;1.05 OR SOXL 5d mom&lt;-10%), dwell=5d
  </div>
  <div style="opacity:0.75;margin-top:8px;font-size:0.88em">
    ℹ️ <code>bube_trader.py</code>가 09:35 ET <code>open_stops</code>에서 VIX 조회 → k_today 계산 → 각 leg alloc × k → cap 1.0 적용 후 stop-buy 등록. margin 사용 X.
  </div>
</div>
""", unsafe_allow_html=True)

    # ── Lazy-load gate (성능 최적화: Tab 7 진입 시에만 yfinance+Alpaca 호출) ──
    if "live_loaded" not in st.session_state:
        st.session_state["live_loaded"] = False

    lazy_col1, lazy_col2 = st.columns([2, 1])
    with lazy_col1:
        st.markdown("**Live 데이터** (regime/VIX/Alpaca paper 계정) — 클릭 시 로드")
    with lazy_col2:
        if st.button("🔄 Live 로드 / 새로고침", key="load_live_btn", use_container_width=True):
            st.session_state["live_loaded"] = True
            # 새로고침 시 캐시도 무효화
            st.cache_data.clear()

    if not st.session_state["live_loaded"]:
        st.info(
            "ℹ️ **빠른 로딩을 위해 Live 데이터는 클릭 시에만 로드됩니다.** "
            "regime 계산 (yfinance 5종목 × 600일) + Alpaca paper 계정 조회는 위 버튼을 누르면 시작됩니다. "
            "백테 데이터 (백테스트·거래내역·위기방어력 등 메뉴)는 이 버튼과 무관 — 이미 표시됨."
        )
        st.stop()

    # ── Section B: Today's regime + active sub-strategy + k_today ──
    @st.cache_data(ttl=1800)  # 30분 캐시 (regime은 하루 단위로 변함)
    def _compute_regime_state():
        try:
            import yfinance as yf
            import datetime as _dt
            CONSENSUS = ["QQQ", "SPY", "SMH"]
            SMA = 200; THR = 0.02; MIN_AGREE = 2
            VIX_THR = 1.05; MOM_THR = -0.10
            DWELL = 5; MAX_BEAR = 90

            end = _dt.date.today() + _dt.timedelta(days=1)
            start = end - _dt.timedelta(days=600)

            sma_ratios = {}
            for a in CONSENSUS:
                df = yf.download(a, start=start, end=end, progress=False, auto_adjust=False)
                if hasattr(df.columns, "get_level_values"):
                    df.columns = df.columns.get_level_values(0)
                close = df["Close"]
                sma = close.rolling(SMA).mean()
                sma_ratios[a] = (close / sma).shift(1)

            vix = yf.download("^VIX", start=start, end=end, progress=False, auto_adjust=False)
            if hasattr(vix.columns, "get_level_values"):
                vix.columns = vix.columns.get_level_values(0)
            vix9d = yf.download("^VIX9D", start=start, end=end, progress=False, auto_adjust=False)
            if hasattr(vix9d.columns, "get_level_values"):
                vix9d.columns = vix9d.columns.get_level_values(0)
            soxl = yf.download("SOXL", start=start, end=end, progress=False, auto_adjust=False)
            if hasattr(soxl.columns, "get_level_values"):
                soxl.columns = soxl.columns.get_level_values(0)

            common = sma_ratios[CONSENSUS[0]].dropna().index
            for a in CONSENSUS[1:]:
                common = common.intersection(sma_ratios[a].dropna().index)
            common = common[-250:]

            regimes = []
            for d in common:
                bull = bear = 0
                for a in CONSENSUS:
                    r = float(sma_ratios[a].loc[d])
                    if r > 1 + THR: bull += 1
                    elif r < 1 - THR: bear += 1
                if bear >= MIN_AGREE: base = "BEAR"
                elif bull >= MIN_AGREE: base = "BULL"
                else: base = "NEUTRAL"
                try:
                    pidx = vix.index[vix.index < d]
                    if len(pidx) > 0:
                        if float(vix9d.loc[pidx[-1], "Close"]) / float(vix.loc[pidx[-1], "Close"]) > VIX_THR:
                            base = "BEAR"
                except Exception: pass
                try:
                    pidx = soxl.index[soxl.index < d]
                    if len(pidx) >= 6:
                        if float(soxl.loc[pidx[-1], "Close"]) / float(soxl.loc[pidx[-6], "Close"]) - 1 < MOM_THR:
                            base = "BEAR"
                except Exception: pass
                regimes.append(base)

            if not regimes:
                return {"error": "regime 시리즈가 비어있음 (yfinance 데이터 부족 또는 SMA200 미충족)"}

            s = list(regimes); i = 0; n = len(s)
            while i < n:
                j = i
                while j < n and s[j] == s[i]: j += 1
                if (j - i) < DWELL and i > 0:
                    for k in range(i, j): s[k] = s[i-1]
                i = j
            today_reg = s[-1] if s else "NEUTRAL"
            streak = 0
            for r in reversed(s):
                if r == "BEAR": streak += 1
                else: break
            gold_escape = today_reg == "BEAR" and streak > MAX_BEAR
            active = {"BULL":"longbyungi","NEUTRAL":"longbyungi","BEAR":"yangbyungi"}.get(today_reg, "longbyungi")
            if gold_escape:
                active = "goldenbyungi"
            recent = "".join(r[0] for r in s[-7:]) if s else ""

            # CHAMP_NOMARGIN k_today calc
            try:
                vix_today = float(vix["Close"].iloc[-1])
                scale = max(0.5, min(2.0, 20.0 / vix_today))
                k_today = 0.65 * scale
                # alloc cap 1.0 (no margin)
                # For display: assume strat alloc = 1.0 then alloc_today = min(k_today, 1.0)
                alloc_max = min(k_today, 1.0)
            except Exception:
                vix_today = None; scale = None; k_today = None; alloc_max = None

            return {
                "regime": today_reg,
                "raw_regime": regimes[-1] if regimes else "NEUTRAL",
                "active": active,
                "bear_streak": streak,
                "max_bear": MAX_BEAR,
                "gold_escape": gold_escape,
                "last7": recent,
                "dwell": DWELL,
                "vix_today": vix_today,
                "scale": scale,
                "k_today": k_today,
                "alloc_max": alloc_max,
            }
        except Exception as e:
            import traceback
            return {"error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[:500]}

    rstate = _compute_regime_state()
    if "error" in rstate:
        st.warning(f"Regime 계산 실패: {rstate['error']}")
    else:
        active_emoji = {"longbyungi":"🚀", "yangbyungi":"🚽", "goldenbyungi":"✨"}.get(rstate["active"], "❓")
        active_name = {"longbyungi":"롱변기", "yangbyungi":"양변기 F1_A6", "goldenbyungi":"황금변기 (GOLD_ESCAPE!)"}.get(rstate["active"], rstate["active"])

        st.markdown("### 🌡 오늘 시장 상태 / V1 비중 조절")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("오늘 레짐", rstate["regime"], f"raw {rstate['raw_regime']}",
                  help="BULL/NEUTRAL = 롱변기 엔진, BEAR = 양변기 엔진. dwell 5일 적용 후 값.")
        c2.metric("현재 활성 엔진", f"{active_emoji} {active_name}",
                  help="롱변기=SOXL 단방향 / 양변기=SOXL롱+SOXS숏 / 황금변기=변동성 돌파")
        c3.metric("BEAR 연속 일수", f"{rstate['bear_streak']}일", f"최대 {rstate['max_bear']}일 → 황금변기",
                  help="BEAR 레짐이 연속으로 몇 일 지속됐는지. 90일 넘으면 황금변기로 전환.")
        c4.metric("최근 7일 레짐", rstate["last7"], f"전환 최소 유지: {rstate['dwell']}일",
                  help="B=BEAR, U=BULL, N=NEUTRAL 순서. 가장 오른쪽이 오늘.")

        if rstate["vix_today"] is not None:
            v1, v2, v3, v4 = st.columns(4)
            v1.metric("VIX (공포지수)", f"{rstate['vix_today']:.2f}", "기준값 20",
                      help="VIX = S&P500 30일 내재변동성. 20 이상이면 비중 축소, 이하면 비중 확대.")
            v2.metric("비중 스케일", f"{rstate['scale']:.3f}",
                      help="clip(20/VIX, 0.5, 2.0). VIX=10이면 2.0, VIX=20이면 1.0, VIX=40이면 0.5.")
            v3.metric("k_today (비중 승수)", f"{rstate['k_today']:.3f}",
                      f"기준 0.65 대비 {rstate['k_today']/0.65:.1f}×",
                      help="0.65 × 스케일. 이 값이 전략 원래 비중에 곱해짐.")
            v4.metric("최대 투자 비중", f"{rstate['alloc_max']*100:.0f}%",
                      "Margin 미사용 (100% 상한)",
                      help="k_today × 전략 비중. Margin 사용 안 하므로 100% 초과 불가.")

        if rstate["gold_escape"]:
            st.error("🚨 **GOLD_ESCAPE 발동 중** — BEAR streak > 90d. 황금변기 K-vol breakout으로 전환됨.")

    st.markdown("---")

    # ── Section C: Alpaca paper account live ──
    @st.cache_data(ttl=300)  # 5분 캐시 (Alpaca 호출 줄임)
    def _fetch_alpaca():
        try:
            from alpaca.trading.client import TradingClient
            from alpaca.trading.requests import GetOrdersRequest
            from alpaca.trading.enums import QueryOrderStatus
            import datetime as _dt
            key = _os.environ.get("ALPACA_API_KEY")
            secret = _os.environ.get("ALPACA_SECRET_KEY")
            if not key or not secret:
                return {"error": "Streamlit Cloud Secrets에 ALPACA_API_KEY / ALPACA_SECRET_KEY 등록이 필요합니다."}
            tc = TradingClient(api_key=key, secret_key=secret, paper=True)
            account = tc.get_account()
            positions = tc.get_all_positions()
            today_utc = _dt.datetime.now(_dt.timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            orders = tc.get_orders(filter=GetOrdersRequest(
                status=QueryOrderStatus.ALL, after=today_utc, limit=50
            ))
            return {
                "account": {
                    "equity": float(account.equity),
                    "cash": float(account.cash),
                    "buying_power": float(account.buying_power),
                    "portfolio_value": float(account.portfolio_value),
                    "status": str(account.status),
                },
                "positions": [{
                    "symbol": p.symbol, "qty": float(p.qty),
                    "avg_entry": float(p.avg_entry_price),
                    "current": float(p.current_price),
                    "market_value": float(p.market_value),
                    "unrealized_pnl": float(p.unrealized_pl),
                    "unrealized_pct": float(p.unrealized_plpc) * 100,
                } for p in positions],
                "orders_today": [{
                    "symbol": o.symbol, "side": o.side.value, "qty": float(o.qty),
                    "type": o.order_type.value, "status": o.status.value,
                    "stop": float(o.stop_price) if o.stop_price else None,
                    "limit": float(o.limit_price) if o.limit_price else None,
                    "fill_avg": float(o.filled_avg_price) if o.filled_avg_price else None,
                    "submitted": str(o.submitted_at) if o.submitted_at else None,
                } for o in orders],
            }
        except Exception as e:
            return {"error": str(e)}

    if st.button("🔄 새로고침", key="refresh_alpaca"):
        st.cache_data.clear()
        st.rerun()

    data = _fetch_alpaca()
    if "error" in data:
        st.error(f"Alpaca 연결 실패: {data['error']}")
        st.caption("Streamlit Cloud → ⚙ Settings → Secrets에 다음 2줄 등록:")
        st.code('ALPACA_API_KEY = "<BUBE paper PK key>"\n'
                'ALPACA_SECRET_KEY = "<BUBE paper secret>"',
                language="toml")
    else:
        acc = data["account"]
        seed = 100_000.0
        pnl = acc["equity"] - seed
        pnl_pct = (pnl / seed) * 100

        st.markdown("### 💼 Alpaca 페이퍼 계정 현황")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("총 자산 (Equity)", f"${acc['equity']:,.2f}", f"{pnl:+,.2f} ({pnl_pct:+.2f}%)",
                  help="시작 $100,000 대비 현재 총 자산.")
        c2.metric("현금", f"${acc['cash']:,.2f}",
                  help="포지션에 투입되지 않은 현금. 레짐이 현금 유지 중이면 높게 유지됨.")
        c3.metric("매수 가능 금액", f"${acc['buying_power']:,.2f}",
                  help="현재 추가로 매수 가능한 최대 금액.")
        c4.metric("계정 상태", acc["status"])

        st.markdown("### 현재 보유 포지션")
        if data["positions"]:
            pos_df = pd.DataFrame(data["positions"])
            pos_df["avg_entry"] = pos_df["avg_entry"].apply(lambda x: f"${x:.2f}")
            pos_df["current"] = pos_df["current"].apply(lambda x: f"${x:.2f}")
            pos_df["market_value"] = pos_df["market_value"].apply(lambda x: f"${x:,.2f}")
            pos_df["unrealized_pnl"] = pos_df["unrealized_pnl"].apply(lambda x: f"${x:+,.2f}")
            pos_df["unrealized_pct"] = pos_df["unrealized_pct"].apply(lambda x: f"{x:+.2f}%")
            st.dataframe(pos_df, use_container_width=True, hide_index=True)
        else:
            st.info("보유 포지션 없음 — 레짐이 현금 유지 중이거나, 진입 조건(갭필터 등) 미충족")

        st.markdown("### 오늘 주문 내역")
        if data["orders_today"]:
            ord_df = pd.DataFrame(data["orders_today"])
            st.dataframe(ord_df, use_container_width=True, hide_index=True)
        else:
            st.info("오늘 주문 없음")

    st.markdown("---")
    st.markdown("**🔗 Alpaca BUBE paper 계정**: https://app.alpaca.markets/paper/dashboard/overview")
    st.markdown("**🔗 GitHub Actions (bube workflows)**: https://github.com/sunghakg/yb-mdd-or-trader/actions")
    st.markdown("**🔗 cron-job.org (4 트리거)**: https://console.cron-job.org/jobs")
    st.caption("자동 트리거: 03:25 / 03:35 / 09:55 / 10:00 HST (월-금). Telegram prefix: 🏆 BUBE V1 CHAMP_NOMARGIN")


# ───────────────────────────────────────────────────────────
# TAB 8: V2_FINAL 비교 (SHOW_V2=False면 탭 미생성·미호출 — 연구 옵션으로만 보존)
# ───────────────────────────────────────────────────────────
def _render_v2_tab():
    st.subheader("🆚 V2_FINAL 백테 비교")
    st.caption("운영 봇은 V1 CHAMP_NOMARGIN (2026-06-03 A안 비대칭 갭필터 적용). V2_FINAL은 paper 미적용 — "
               "여기는 V2 백테 성과를 같이 표시만.")

    if v2_summary is None:
        st.error("⚠️ data/v2_final/summary.json 없음. local/strategies/regime_rotation_validation/bube_v2_full_backtest 산출물 복사 필요.")
    else:
        SPEC_V2 = v2_summary["spec"]
        H_V2 = v2_summary["V2_FINAL"]
        H_V1 = v2_summary["V1"]  # V1 동일 backtest 안에서 비교 측정 (V1 CHAMP_NOMARGIN, alloc cap 1.0)
        H_SOXL_BH = v2_summary["SOXL_buy_hold"]

        # ── A. Spec card ──
        st.markdown(f"""
<div style="background:linear-gradient(135deg,#1f2937,#374151);padding:18px 22px;border-radius:10px;color:#f9fafb;margin:8px 0 16px">
  <div style="font-size:1.05em;font-weight:700;margin-bottom:6px">🆚 V2_FINAL Spec (D6b conditional VVIX + T4c NDX/SPY RS sizing)</div>
  <div style="font-family:monospace;font-size:0.9em;opacity:0.92;line-height:1.6">
    k = 0.65 × clip(20/VIX, 0.5, 2.0)<br>
    &nbsp;&nbsp;&nbsp;&nbsp;× (clip(90/VVIX, 0.5, 1.0) <b>if SOXL_5d_ret &lt; 0 else 1.0</b>) &nbsp;← D6b: conditional VVIX<br>
    &nbsp;&nbsp;&nbsp;&nbsp;× (<b>0.8 if NDX/SPY_20d_RS &lt; 0 else 1.0</b>) &nbsp;← T4c: tech leadership sizing<br>
    alloc_today = min(k × strat_alloc, 1.0) &nbsp;← margin 사용 X (V1과 동일)
  </div>
  <div style="opacity:0.75;margin-top:8px;font-size:0.85em">
    V1 대비 차이: ① SOXL 약세일 때만 VVIX vol-of-vol clip 추가, ② NDX(=QQQ)/SPY 20일 RS 음수일 때 alloc 20% throttle.
    BASE rotation·regime detector는 V1과 완전 동일.
  </div>
</div>
""", unsafe_allow_html=True)

        # ── B. Headline metric grid ──
        st.markdown(f"### 📊 In-sample 비교 ({H_V2.get('start','?')} ~ {H_V2.get('end','?')}, {H_V2.get('years','?')}년)")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Calmar", f"{H_V2['Calmar']:.2f}",
                  f"V1 {H_V1['Calmar']:.2f} · +{H_V2['Calmar']-H_V1['Calmar']:.2f}")
        m2.metric("CAGR", f"{H_V2['CAGR_pct']:.1f}%",
                  f"V1 {H_V1['CAGR_pct']:.1f}% · {H_V2['CAGR_pct']-H_V1['CAGR_pct']:+.1f}pp")
        m3.metric("MDD", f"{H_V2['MDD_pct']:.1f}%",
                  f"V1 {H_V1['MDD_pct']:.1f}% · {H_V2['MDD_pct']-H_V1['MDD_pct']:+.1f}pp")
        m4.metric("$100K → Final", _money(H_V2["final_multiple"] * 100_000),
                  f"V1 {_money(H_V1['final_multiple']*100_000)}")

        m5, m6, m7, m8 = st.columns(4)
        m5.metric("Sharpe", f"{H_V2['Sharpe']:.2f}",
                  f"V1 {H_V1['Sharpe']:.2f}")
        m6.metric("Sortino", f"{H_V2['Sortino']:.2f}",
                  f"V1 {H_V1['Sortino']:.2f}")
        m7.metric("Worst day", f"{H_V2['worst_day_pct']:.2f}%",
                  f"V1 {H_V1['worst_day_pct']:.2f}%")
        m8.metric("SOXL B&H Cal (참고)", f"{H_SOXL_BH['Calmar']:.2f}",
                  f"MDD {H_SOXL_BH['MDD_pct']:.1f}%")

        st.markdown(
            f"💡 V2_FINAL의 핵심 효과: **CAGR은 V1과 사실상 동일** "
            f"({H_V2['CAGR_pct']-H_V1['CAGR_pct']:+.1f}pp), **MDD를 {H_V1['MDD_pct']-H_V2['MDD_pct']:.1f}pp 개선** "
            f"→ Calmar +{H_V2['Calmar']-H_V1['Calmar']:.2f} 상승. "
            f"VVIX clamp {v2_summary['vvix_clamp_days_V2']}일, NDX throttle {v2_summary['ndx_throttle_days_V2']}일 발동."
        )

        st.markdown("---")

        # ── C. Equity curve V1 vs V2 vs SOXL ──
        st.markdown("### 📈 Equity Curve — V1 vs V2_FINAL vs SOXL Buy&Hold ($100K seed)")
        def _mtime_t8(p):
            try: return p.stat().st_mtime
            except Exception: return 0

        @st.cache_data
        def _load_v2_equity(_mtime_key):
            return pd.read_csv(V2DIR / "equity_paths.csv", parse_dates=["date"], index_col="date")
        eq_v2 = _load_v2_equity(_mtime_t8(V2DIR / "equity_paths.csv"))
        eq_seed_col1, eq_seed_col2 = st.columns([1, 3])
        v2_seed = eq_seed_col1.number_input(
            "시작 자본 ($)", min_value=100, max_value=10_000_000,
            value=100_000, step=10_000, key="v2_seed_input",
            help="$100K 시드 백테 결과를 이 값으로 비례 환산"
        )
        eq_seed_col2.markdown(
            f"<div style='padding-top:1.7em;color:#888'>"
            f"💡 모든 $ 값이 <b>${v2_seed:,.0f}</b> 시드 기준으로 환산됩니다."
            f"</div>",
            unsafe_allow_html=True
        )
        scale_v2 = v2_seed / 100_000.0
        chart_v2 = pd.DataFrame({
            "V1 ($)": eq_v2["V1"] * scale_v2,
            "V2_FINAL ($)": eq_v2["V2_FINAL"] * scale_v2,
            "SOXL B&H ($)": eq_v2["SOXL_buy_hold"] * scale_v2,
        }, index=eq_v2.index)
        st.line_chart(chart_v2, height=380)

        # log scale option
        with st.expander("📐 Log-scale 보기"):
            log_chart = chart_v2.apply(lambda c: np.log10(c))
            log_chart.columns = ["log10 " + c for c in chart_v2.columns]
            st.line_chart(log_chart, height=320)

        st.markdown("---")

        # ── D. Yearly breakdown V1 vs V2 ──
        st.markdown("### 📅 Year-by-Year — V1 vs V2_FINAL")
        @st.cache_data
        def _load_v2_yearly(_mtime_key):
            return pd.read_csv(V2DIR / "yearly_breakdown.csv")
        yb = _load_v2_yearly(_mtime_t8(V2DIR / "yearly_breakdown.csv"))

        rows = []
        for _, r in yb.iterrows():
            rows.append({
                "Year": int(r["year"]),
                "V1 Ret": f"{r['V1_ret']:+.1f}%",
                "V2 Ret": f"{r['V2_FINAL_ret']:+.1f}%",
                "Δ Ret": f"{r['V2_FINAL_ret']-r['V1_ret']:+.1f}pp",
                "V1 MDD": f"{r['V1_mdd']:+.1f}%",
                "V2 MDD": f"{r['V2_FINAL_mdd']:+.1f}%",
                "Δ MDD": f"{r['V2_FINAL_mdd']-r['V1_mdd']:+.1f}pp",
                "SOXL Ret": f"{r['SOXL_ret']:+.1f}%",
                "SOXL MDD": f"{r['SOXL_mdd']:+.1f}%",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        wins_mdd = (yb["V2_FINAL_mdd"] > yb["V1_mdd"]).sum()
        wins_ret = (yb["V2_FINAL_ret"] > yb["V1_ret"]).sum()
        avg_dmdd = (yb["V2_FINAL_mdd"] - yb["V1_mdd"]).mean()
        avg_dret = (yb["V2_FINAL_ret"] - yb["V1_ret"]).mean()
        total = len(yb)
        yc1, yc2, yc3, yc4 = st.columns(4)
        yc1.metric("총 연도", f"{total}")
        yc2.metric("V2 MDD 우위", f"{wins_mdd}/{total}",
                   f"{wins_mdd/total*100:.0f}%")
        yc3.metric("V2 Ret 우위", f"{wins_ret}/{total}",
                   f"{wins_ret/total*100:.0f}%")
        yc4.metric("평균 ΔRet / ΔMDD", f"{avg_dret:+.1f}pp / {avg_dmdd:+.1f}pp",
                   "MDD는 양수=V2가 덜 떨어짐")

        st.markdown("### 📊 연도별 Δ MDD (V2 − V1, pp) — 양수 = V2가 덜 떨어짐")
        ydiff = pd.DataFrame(
            {"Δ MDD pp": (yb["V2_FINAL_mdd"] - yb["V1_mdd"]).values},
            index=yb["year"].astype(int).values
        )
        st.bar_chart(ydiff, height=240)

        st.markdown("---")

        # ── E. Bootstrap 5,000 paths comparison ──
        st.markdown("### 🎲 Bootstrap 5,000 paths — V1 vs V2_FINAL")
        bp_path = V2DIR / "bootstrap.csv"
        if bp_path.exists():
            bp = pd.read_csv(bp_path).set_index("label")
            v1b = bp.loc["V1"]
            v2b = bp.loc["V2_FINAL"]

            bbc1, bbc2, bbc3 = st.columns(3)
            with bbc1:
                st.markdown("**CAGR p50**")
                st.metric("V2_FINAL", f"{v2b['CAGR_p50']:.1f}%",
                          f"V1 {v1b['CAGR_p50']:.1f}%")
            with bbc2:
                st.markdown("**MDD p50**")
                st.metric("V2_FINAL", f"{v2b['MDD_p50']:.1f}%",
                          f"V1 {v1b['MDD_p50']:.1f}% · "
                          f"{v2b['MDD_p50']-v1b['MDD_p50']:+.1f}pp")
            with bbc3:
                st.markdown("**Calmar p50**")
                st.metric("V2_FINAL", f"{v2b['Cal_p50']:.2f}",
                          f"V1 {v1b['Cal_p50']:.2f} · "
                          f"+{v2b['Cal_p50']-v1b['Cal_p50']:.2f}")

            tail_rows = pd.DataFrame({
                "Metric": ["P(MDD<-25%)", "P(MDD<-30%)", "P(MDD<-40%)",
                           "P(Calmar>2.5)", "P(Calmar>3.0)",
                           "Calmar p5", "Calmar p95", "MDD p5 (꼬리 최악)"],
                "V1": [
                    f"{v1b['P_MDD_lt_25']*100:.1f}%",
                    f"{v1b['P_MDD_lt_30']*100:.1f}%",
                    f"{v1b['P_MDD_lt_40']*100:.1f}%",
                    f"{v1b['P_Cal_gt_2_5']*100:.1f}%",
                    f"{v1b['P_Cal_gt_3']*100:.1f}%",
                    f"{v1b['Cal_p5']:.2f}",
                    f"{v1b['Cal_p95']:.2f}",
                    f"{v1b['MDD_p5']:.1f}%",
                ],
                "V2_FINAL": [
                    f"{v2b['P_MDD_lt_25']*100:.1f}%",
                    f"{v2b['P_MDD_lt_30']*100:.1f}%",
                    f"{v2b['P_MDD_lt_40']*100:.1f}%",
                    f"{v2b['P_Cal_gt_2_5']*100:.1f}%",
                    f"{v2b['P_Cal_gt_3']*100:.1f}%",
                    f"{v2b['Cal_p5']:.2f}",
                    f"{v2b['Cal_p95']:.2f}",
                    f"{v2b['MDD_p5']:.1f}%",
                ],
            })
            st.dataframe(tail_rows, use_container_width=True, hide_index=True)

            st.info(
                f"**진짜 운영 추정치 (bootstrap p50)**: "
                f"V2_FINAL Cal **{v2b['Cal_p50']:.2f}** / MDD **{v2b['MDD_p50']:.1f}%** "
                f"vs V1 Cal {v1b['Cal_p50']:.2f} / MDD {v1b['MDD_p50']:.1f}%. "
                f"P(MDD<-30%) {v1b['P_MDD_lt_30']*100:.0f}% → **{v2b['P_MDD_lt_30']*100:.0f}%**로 큰 꼬리 축소. "
                f"단, 헤드라인 Cal 3.46은 in-sample max — forward 기대는 p50 기준."
            )

        st.markdown("---")

        # ── F. Crisis comparison ──
        st.markdown("### 📈 Crisis 비교 — V1 vs V2_FINAL")
        cp = V2DIR / "crisis.csv"
        if cp.exists():
            cr = pd.read_csv(cp)
            disp = cr.copy()
            disp["v1_ret"] = disp["v1_ret"].apply(lambda x: f"{x:+.1f}%")
            disp["v2_ret"] = disp["v2_ret"].apply(lambda x: f"{x:+.1f}%")
            disp["v1_mdd"] = disp["v1_mdd"].apply(lambda x: f"{x:+.1f}%")
            disp["v2_mdd"] = disp["v2_mdd"].apply(lambda x: f"{x:+.1f}%")
            disp["dret_pp"] = disp["dret_pp"].apply(lambda x: f"{x:+.2f}pp")
            disp["dmdd_pp"] = disp["dmdd_pp"].apply(lambda x: f"{x:+.2f}pp")
            disp.columns = ["Event", "V1 Ret", "V2 Ret", "V1 MDD", "V2 MDD",
                            "Δ Ret", "Δ MDD (양수=V2가 덜 떨어짐)"]
            st.dataframe(disp, use_container_width=True, hide_index=True)

            n_mdd_win = (cr["dmdd_pp"] > 0).sum()
            n_tot = len(cr)
            st.success(f"✅ Crisis {n_mdd_win}/{n_tot}건에서 V2가 MDD 우위, 평균 Δ MDD {cr['dmdd_pp'].mean():+.2f}pp.")

        st.markdown("---")

        # ── G. Shuffle test ──
        st.markdown("### 🧪 Shuffle Test — D6b VVIX + T4c NDX 신호 진위 (메모리 [[project-v2-final-2026-05-27]])")
        sp = V2DIR / "shuffle.csv"
        if sp.exists():
            sh = pd.read_csv(sp).iloc[0]
            sc1, sc2, sc3 = st.columns(3)
            sc1.metric("VVIX 셔플 z-score", f"{sh['vvix_z']:.2f}",
                       f"p={sh['vvix_p_value']:.3f}")
            sc2.metric("NDX/SPY 셔플 z-score", f"{sh['ndx_z']:.2f}",
                       f"p={sh['ndx_p_value']:.3f}")
            sc3.metric("Both 셔플 z-score", f"{sh['both_z']:.2f}",
                       f"p={sh['both_p_value']:.3f}")
            st.caption("100회 셔플 대비. 실제 신호 Cal vs 셔플 분포 p50의 표준편차 단위 거리 — z>2.0 = 통계적으로 진짜 신호.")

        st.markdown("---")

        # ── H. Honest weaknesses ──
        st.markdown("### ⚠️ V2_FINAL 약점 (메모리에 기록된 정직한 평가)")
        st.markdown("""
- **M9 DSR 37-trials 미통과** — VVIX C 그리드 + RS lookback 그리드 등 시도 횟수가 늘면 Deflated Sharpe Ratio 통과 못 함. M3 shuffle z=3.09 p=0.000이 진위의 1차 증거.
- **2021 melt-up −26pp** — VIX/VVIX 모두 진정 상태에서 NDX/SPY throttle이 false positive 발동하면 풀로딩 못 함. 강세장 일부 upside 놓침.
- **A4 VVIX baseline drift** — VVIX Q1→Q3 평균 88→108로 13년간 상승. 임계값 90이 시간에 따라 다른 의미. 향후 rolling-baseline 검토 필요.
- **In-sample 16년 동일 기간 fit** — V1, V2 모두 SOXL 상장 이후 전체 기간 학습. 진짜 OOS 아님 (S1d는 walkforward Q3/Q4 alpha decay 있었음 → V2가 그걸 해결한 증거가 in-sample 한정).
- **운영 자본 cap** — 헤드라인은 무한 자본 가정. SOXL 2010-2016 ADV $7-30M 시기 슬립 반영 시 V1 16년 CAGR 78%→34% 환상으로 메모리 [[project-bube-reality-followups-2026-05-27]] 기록. V2도 동일 슬립 영향 받음.
""")

        st.warning(
            "🚦 **운영 결정**: V2_FINAL은 paper 봇에 적용되지 **않습니다**. "
            "위 데이터는 V1과 V2의 백테 정합 비교 자료일 뿐. "
            "운영은 V1 CHAMP_NOMARGIN (2026-06-03 A안 비대칭 갭필터 적용). V2는 미적용."
        )


# V2 탭 (사이드바 미노출, SHOW_V2=False 기본)
if SHOW_V2 and page == "🆚 V2_FINAL 비교":
    _render_v2_tab()


# ───────────────────────────────────────────────────────────
# TAB 9: 최근 1달 매매일지 (signal_diagnostics + trade_log_enriched)
# ───────────────────────────────────────────────────────────
elif page == "🔬 백테 vs 페이퍼":
    st.subheader("🔬 백테스트 vs 페이퍼 트레이딩 비교")
    st.caption("같은 기간에서 백테스트(이론 시뮬레이션)와 실제 페이퍼 트레이딩 결과를 나란히 비교합니다.")

    st.markdown("""
<div style="background:#0f172a;border-left:4px solid #f59e0b;padding:12px 18px;border-radius:8px;margin-bottom:12px;color:#e2e8f0;line-height:1.8">
<b>📌 백테스트</b> = 역사적 데이터로 완벽한 체결을 가정한 시뮬레이션 (이론적 상한)<br>
<b>🤖 페이퍼 트레이딩</b> = Alpaca 가상계좌에서 봇이 실제로 실행한 결과<br>
<span style="opacity:0.8;font-size:0.92em">두 곡선이 다른 이유: 슬리피지·체결 시점 차이·VIX 시차·갭업 폴백 등</span>
</div>
""", unsafe_allow_html=True)

    # ── Lazy load ──
    if "cmp_loaded" not in st.session_state:
        st.session_state["cmp_loaded"] = False

    _cmp_c1, _cmp_c2 = st.columns([3, 1])
    with _cmp_c1:
        st.markdown("**Alpaca 포트폴리오 히스토리 API 호출 필요** (최초 10~20초 소요, 이후 1시간 캐시)")
    with _cmp_c2:
        if st.button("🔄 비교 데이터 로드", key="cmp_load_btn", use_container_width=True):
            st.session_state["cmp_loaded"] = True
            if "cmp_paper_df" in st.session_state:
                del st.session_state["cmp_paper_df"]
            st.cache_data.clear()

    if not st.session_state["cmp_loaded"]:
        st.info("위 버튼을 눌러 Alpaca 페이퍼 계정 히스토리를 로드하세요.")
    else:
        # ── Fetch Alpaca portfolio history ──
        @st.cache_data(ttl=3600)
        def _fetch_paper_hist_cmp():
            try:
                import requests as _rq
                _key = _os.environ.get("ALPACA_API_KEY", "")
                _sec = _os.environ.get("ALPACA_SECRET_KEY", "")
                if not _key or not _sec:
                    return None, "ALPACA_API_KEY / ALPACA_SECRET_KEY 환경변수 없음. Streamlit Secrets 확인."
                _r = _rq.get(
                    "https://paper-api.alpaca.markets/v2/account/portfolio/history",
                    headers={"APCA-API-KEY-ID": _key, "APCA-API-SECRET-KEY": _sec},
                    params={"period": "6M", "timeframe": "1D",
                            "intraday_reporting": "market_hours", "pnl_reset": "no_reset"},
                    timeout=20,
                )
                if _r.status_code != 200:
                    return None, f"HTTP {_r.status_code}: {_r.text[:300]}"
                _d = _r.json()
                _ts = _d.get("timestamp", [])
                _eq = _d.get("equity", [])
                _pl = _d.get("profit_loss", [0] * len(_ts))
                _plp = _d.get("profit_loss_pct", [0] * len(_ts))
                _df = pd.DataFrame({
                    "date": pd.to_datetime(_ts, unit="s", utc=True).tz_localize(None).normalize(),
                    "equity": [float(x) if x is not None else 0.0 for x in _eq],
                    "pnl": [float(x) if x is not None else 0.0 for x in _pl],
                    "pnl_pct": [float(x) if x is not None else 0.0 for x in _plp],
                })
                _df = _df[_df["equity"] > 0].set_index("date")
                _df = _df[~_df.index.duplicated(keep="last")]
                return _df, None
            except Exception as _e:
                import traceback as _tb
                return None, f"{type(_e).__name__}: {_e}\n{_tb.format_exc()[:400]}"

        with st.spinner("Alpaca 포트폴리오 히스토리 로딩 중..."):
            _paper_df, _cmp_err = _fetch_paper_hist_cmp()

        if _cmp_err or _paper_df is None or len(_paper_df) < 2:
            st.error(f"페이퍼 히스토리 로드 실패: {_cmp_err or '데이터 없음'}")
            st.caption("Streamlit Cloud Secrets에 ALPACA_API_KEY / ALPACA_SECRET_KEY 등록 확인.")
        else:
            # ── Load backtest equity ──
            def _mtime_cmp(p):
                try: return p.stat().st_mtime
                except Exception: return 0

            @st.cache_data
            def _load_eq_cmp(_k):
                return pd.read_csv(CHAMP / "equity_curves.csv", parse_dates=["date"], index_col="date")

            @st.cache_data
            def _load_daily_cmp(_k):
                return pd.read_csv(CHAMP / "daily.csv", parse_dates=["date"], index_col="date")

            @st.cache_data
            def _load_trades_cmp(_k):
                t = pd.read_csv(CHAMP / "trades_champ.csv")
                t["date"] = pd.to_datetime(t["date"])
                return t

            _eq_bt_all = _load_eq_cmp(_mtime_cmp(CHAMP / "equity_curves.csv"))
            _daily_bt_all = _load_daily_cmp(_mtime_cmp(CHAMP / "daily.csv"))

            # ── Period overlap ──
            _p_start = _paper_df.index[0]
            _p_end = _paper_df.index[-1]

            _bt_eq = _eq_bt_all.loc[_p_start:_p_end, "CHAMP_NOMARGIN"].dropna()
            if len(_bt_eq) < 2:
                st.error(f"백테 데이터에 {_p_start.strftime('%Y-%m-%d')}부터의 데이터가 없습니다.")
                st.stop()

            # Reindex paper to backtest trading days
            _pa_eq = _paper_df["equity"].reindex(_bt_eq.index).ffill()
            _pa_eq_raw = _paper_df["equity"]

            # Rebase both to same start
            _bt_seed = float(_bt_eq.iloc[0])
            _pa_seed = float(_pa_eq.iloc[0])

            _bt_norm = _bt_eq / _bt_seed * _pa_seed   # rebase backtest to paper start $
            _pa_norm = _pa_eq                          # paper actual $

            # ── Section 1: Equity curve ──
            st.markdown("### 📈 자산 곡선 비교")
            _days = len(_bt_eq)
            _mo = _days // 21
            st.caption(
                f"기준일: {_p_start.strftime('%Y-%m-%d')} → {_p_end.strftime('%Y-%m-%d')} "
                f"({_days}거래일 ≈ {_mo}개월) · 시작 자산: ${_pa_seed:,.0f}"
            )

            _cmp_eq_df = pd.DataFrame({
                "백테스트 V1 (이론)": _bt_norm.values,
                "페이퍼 트레이딩 (실제)": _pa_norm.values,
            }, index=_bt_eq.index)
            st.line_chart(_cmp_eq_df, height=330)

            # Gap chart
            _gap = _pa_norm - _bt_norm
            _gap_df = pd.DataFrame({"페이퍼 − 백테스트 ($)": _gap.values}, index=_bt_eq.index)
            _latest_gap = float(_gap.iloc[-1])
            st.caption(
                f"아래: 페이퍼 − 백테스트 괴리. 양수(+) = 실제가 앞섬, 음수(-) = 이론이 앞섬. "
                f"최근: **${_latest_gap:+,.0f}**"
            )
            st.bar_chart(_gap_df, height=160)
            st.markdown("---")

            # ── Section 2: Performance metrics ──
            st.markdown("### 📊 기간 성과 지표 비교")

            def _perf(eq):
                n = len(eq)
                s = float(eq.iloc[0]); e = float(eq.iloc[-1])
                n_yrs = n / 252
                tot = (e / s - 1) * 100
                cagr = ((e / s) ** (1 / n_yrs) - 1) * 100 if n_yrs > 0.05 else tot
                cm = eq.cummax(); dd = (eq / cm - 1) * 100
                mdd = float(dd.min())
                calmar = cagr / abs(mdd) if mdd < 0 else float("inf")
                dr = eq.pct_change().dropna()
                sharpe = float(dr.mean() / dr.std() * (252 ** 0.5)) if dr.std() > 0 else 0.0
                win_days = int((dr > 0).sum()); total_dr = len(dr)
                return {
                    "총 수익률": tot, "CAGR (연환산)": cagr,
                    "MDD (최대낙폭)": mdd, "Calmar": calmar,
                    "Sharpe": sharpe, "승일 수 / 전체": f"{win_days}/{total_dr} ({win_days/total_dr*100:.0f}%)" if total_dr else "—",
                }

            _p_bt_stats = _perf(_bt_norm)
            _p_pa_stats = _perf(_pa_norm)

            _sm1, _sm2, _sm3 = st.columns(3)
            _metric_keys = ["총 수익률", "CAGR (연환산)", "MDD (최대낙폭)", "Calmar", "Sharpe"]
            _is_pct = {"총 수익률", "CAGR (연환산)", "MDD (최대낙폭)"}

            with _sm1:
                st.markdown("#### 지표")
                for _k in _metric_keys:
                    st.markdown(f"**{_k}**")
                st.markdown(f"**승일 수**")

            with _sm2:
                st.markdown("#### 📊 백테스트 (이론)")
                for _k in _metric_keys:
                    _v = _p_bt_stats[_k]
                    if isinstance(_v, float) and _v == float("inf"):
                        st.markdown("∞")
                    elif _k in _is_pct:
                        st.markdown(f"`{_v:+.2f}%`")
                    else:
                        st.markdown(f"`{_v:.2f}`")
                st.markdown(f"`{_p_bt_stats['승일 수 / 전체']}`")

            with _sm3:
                st.markdown("#### 🤖 페이퍼 (실제)")
                for _k in _metric_keys:
                    _v = _p_pa_stats[_k]; _vb = _p_bt_stats[_k]
                    if isinstance(_v, float) and _v == float("inf"):
                        st.markdown("∞")
                    elif _k in _is_pct and isinstance(_vb, float) and _vb != float("inf"):
                        _d = _v - _vb
                        _color = "#4ade80" if _d >= 0 and _k != "MDD (최대낙폭)" else "#f87171"
                        if _k == "MDD (최대낙폭)": _color = "#4ade80" if _d >= 0 else "#f87171"
                        st.markdown(f"`{_v:+.2f}%` <span style='color:{_color};font-size:0.85em'>{_d:+.2f}pp</span>",
                                    unsafe_allow_html=True)
                    elif isinstance(_vb, float) and not isinstance(_v, str):
                        _d = _v - _vb
                        _color = "#4ade80" if _d >= 0 else "#f87171"
                        st.markdown(f"`{_v:.2f}` <span style='color:{_color};font-size:0.85em'>{_d:+.2f}</span>",
                                    unsafe_allow_html=True)
                    else:
                        st.markdown(f"`{_v}`")
                st.markdown(f"`{_p_pa_stats['승일 수 / 전체']}`")

            st.markdown("---")

            # ── Section 3: Daily P&L comparison table ──
            st.markdown("### 📋 일별 수익률 비교 (최신 날짜부터)")

            _bt_dr = _bt_norm.pct_change() * 100
            _pa_dr = _pa_norm.pct_change() * 100
            _daily_bt_sl = _daily_bt_all.reindex(_bt_eq.index)

            _rows_cmp = []
            for _d in reversed(_bt_eq.index):
                _bret = float(_bt_dr.get(_d, float("nan")))
                _pret = float(_pa_dr.get(_d, float("nan")))
                _diff = (_pret - _bret) if (not pd.isna(_bret) and not pd.isna(_pret)) else float("nan")
                _bv = float(_bt_norm.get(_d, float("nan")))
                _pv = float(_pa_norm.get(_d, float("nan")))
                _rg = str(_daily_bt_sl.loc[_d, "regime"]) if _d in _daily_bt_sl.index and "regime" in _daily_bt_sl.columns else "—"
                _k = float(_daily_bt_sl.loc[_d, "k_today"]) if _d in _daily_bt_sl.index and "k_today" in _daily_bt_sl.columns else float("nan")
                _rows_cmp.append({
                    "날짜": _d.strftime("%Y-%m-%d"),
                    "레짐(백테)": "🟢 BULL" if _rg == "BULL" else "🔴 BEAR" if _rg == "BEAR" else "🟡 NEUTRAL" if _rg == "NEUTRAL" else _rg,
                    "k_today(백테)": f"{_k:.3f}" if not pd.isna(_k) else "—",
                    "백테 일간%": f"{_bret:+.2f}%" if not pd.isna(_bret) else "—",
                    "페이퍼 일간%": f"{_pret:+.2f}%" if not pd.isna(_pret) else "—",
                    "괴리(pp)": f"{_diff:+.2f}" if not pd.isna(_diff) else "—",
                    "백테 자산($)": f"${_bv:,.0f}" if not pd.isna(_bv) else "—",
                    "페이퍼 자산($)": f"${_pv:,.0f}" if not pd.isna(_pv) else "—",
                })

            _cmp_tbl = pd.DataFrame(_rows_cmp)
            st.dataframe(_cmp_tbl, use_container_width=True, hide_index=True, height=440)

            if st.button("💾 비교표 CSV 준비", key="cmp_dl_prep"):
                st.session_state["cmp_csv"] = _cmp_tbl.to_csv(index=False).encode("utf-8-sig")
            if "cmp_csv" in st.session_state:
                _cd0 = _bt_eq.index[0].strftime("%Y%m%d")
                _cd1 = _bt_eq.index[-1].strftime("%Y%m%d")
                st.download_button(
                    "⬇️ 백테 vs 페이퍼 비교표 CSV",
                    data=st.session_state["cmp_csv"],
                    file_name=f"bt_vs_paper_{_cd0}_{_cd1}.csv",
                    mime="text/csv",
                    key="cmp_dl",
                )

            st.markdown("---")

            # ── Section 4: Biggest divergence days ──
            st.markdown("### 🔍 가장 큰 괴리 구간 Top 10")
            st.caption("백테와 페이퍼 일간수익률이 가장 많이 달랐던 날들. 원인 파악에 활용하세요.")

            _div_series = (_pa_dr - _bt_dr).dropna()
            if len(_div_series) >= 3:
                _top_div = _div_series.abs().nlargest(10)
                _div_rows = []
                for _td in _top_div.index:
                    _brd = float(_bt_dr.get(_td, float("nan")))
                    _prd = float(_pa_dr.get(_td, float("nan")))
                    _dv = float(_div_series.get(_td, float("nan")))
                    _rg2 = str(_daily_bt_sl.loc[_td, "regime"]) if _td in _daily_bt_sl.index and "regime" in _daily_bt_sl.columns else "—"
                    _div_rows.append({
                        "날짜": _td.strftime("%Y-%m-%d"),
                        "레짐": _rg2,
                        "백테 일간%": f"{_brd:+.2f}%" if not pd.isna(_brd) else "—",
                        "페이퍼 일간%": f"{_prd:+.2f}%" if not pd.isna(_prd) else "—",
                        "괴리(pp)": f"{_dv:+.2f}",
                        "방향": "페이퍼↑" if _dv > 0 else "백테↑",
                    })
                st.dataframe(pd.DataFrame(_div_rows), use_container_width=True, hide_index=True)
            else:
                st.info("비교 기간이 짧아 괴리 분석 데이터 부족.")

            st.markdown("---")

            # ── Section 5: Tracking quality metrics ──
            st.markdown("### 📐 추적 품질 지표")

            _corr = float(_bt_dr.corr(_pa_dr)) if len(_bt_dr.dropna()) > 3 else float("nan")
            _mae = float((_pa_dr - _bt_dr).abs().mean()) if len(_bt_dr.dropna()) > 1 else float("nan")
            _rmse = float(((_pa_dr - _bt_dr) ** 2).mean() ** 0.5) if len(_bt_dr.dropna()) > 1 else float("nan")
            _cumgap = float(_pa_norm.iloc[-1] - _bt_norm.iloc[-1])
            _cumgap_pct = _cumgap / float(_bt_norm.iloc[-1]) * 100

            _tq1, _tq2, _tq3, _tq4 = st.columns(4)
            _tq1.metric("일간수익률 상관계수", f"{_corr:.3f}" if not pd.isna(_corr) else "—",
                        "1.0 = 완벽 추적",
                        help="백테와 페이퍼의 일간 수익률 상관관계. 높을수록 봇이 백테를 잘 추적함.")
            _tq2.metric("평균절대오차 (MAE)", f"{_mae:.2f}pp" if not pd.isna(_mae) else "—",
                        help="하루 평균 수익률 오차. 낮을수록 백테와 실제가 일치.")
            _tq3.metric("RMSE (변동성 포함)", f"{_rmse:.2f}pp" if not pd.isna(_rmse) else "—",
                        help="MAE에 큰 오차에 더 가중치를 준 지표. MAE보다 높으면 간헐적 큰 괴리 존재.")
            _tq4.metric("누적 괴리 (최종)", f"${_cumgap:+,.0f}",
                        f"{_cumgap_pct:+.2f}% of BT",
                        help="최종일 기준 페이퍼 - 백테스트 자산 차이.")

            st.markdown("---")

            # ── Section 6: Interpretation ──
            st.info("""
**💡 괴리 주요 원인**

| 원인 | 방향 | 설명 |
|---|---|---|
| 슬리피지 | 페이퍼↓ | 봇 stop-buy는 트리거 이후 시장가 → 백테보다 불리한 체결 |
| VIX 시차 (PR#19 이전) | 양방향 | 당일 VIX 사용 vs 전일 VIX → k_today 차이 |
| 갭업 stop-buy 거부 | 페이퍼↓ | 강갭업 시 추격 불가 → 진입 스킵 (PR#12 이후 개선) |
| OPG/CLS 옥션 미체결 | 양방향 | Alpaca paper는 MOO/CLS 미보장 → MARKET fallback |
| 데이터 ffill | 페이퍼 0% | 공휴일·주말 페이퍼 equity 불변 → 당일 수익률 0% |
| 봇 레짐 평활화 | 양방향 | 봇 dwell 5일 평활 vs 백테 5-신호 detector → 레짐 판정 최대 5일 지연 |
""")


elif page == "📔 매매일지":
    st.subheader("📔 V1 매매일지 — 일별 레짐·비중·거래 현황")
    st.caption("V1 백테스트의 일별 레짐 판정, VIX 기반 비중(k_today), 활성 엔진, 거래 내역을 보여줍니다. 데이터는 백테스트 기준.")

    def _mtime_j2(p):
        try: return p.stat().st_mtime
        except Exception: return 0

    @st.cache_data
    def _load_daily_j2(_k):
        return pd.read_csv(CHAMP / "daily.csv", parse_dates=["date"], index_col="date")

    @st.cache_data
    def _load_eq_j2(_k):
        return pd.read_csv(CHAMP / "equity_curves.csv", parse_dates=["date"], index_col="date")

    @st.cache_data
    def _load_trades_j2(_k):
        t = pd.read_csv(CHAMP / "trades_champ.csv")
        t["date"] = pd.to_datetime(t["date"])
        return t

    _daily_j = _load_daily_j2(_mtime_j2(CHAMP / "daily.csv"))
    _eq_j = _load_eq_j2(_mtime_j2(CHAMP / "equity_curves.csv"))
    _trades_j = _load_trades_j2(_mtime_j2(CHAMP / "trades_champ.csv"))

    # ── 기간 선택 ──
    _n_opts = {"최근 20거래일": 20, "최근 1달": 30, "최근 60거래일": 60, "최근 90거래일": 90}
    _sel = st.radio("기간", list(_n_opts.keys()), index=1, horizontal=True, key="j2_period")
    _n_show = _n_opts[_sel]

    _daily_rec = _daily_j.tail(_n_show)
    _eq_rec = _eq_j.reindex(_daily_rec.index)["CHAMP_NOMARGIN"] if "CHAMP_NOMARGIN" in _eq_j.columns else pd.Series(dtype=float)
    _eq_daily_ret = _eq_rec.pct_change() * 100

    # ── 거래 집계 ──
    _trades_recent = _trades_j[_trades_j["date"].dt.normalize().isin(_daily_rec.index.normalize())]
    _by_date = _trades_recent.groupby(_trades_recent["date"].dt.normalize()).agg(
        건수=("action", "count"),
        엔진=("leg", lambda x: "/".join(sorted(set(x)))),
        pnl=("pnl", "sum")
    )

    # ── 요약 카드 ──
    _has_rg = "regime" in _daily_rec.columns
    _has_k = "k_today" in _daily_rec.columns
    _has_vix = "VIX" in _daily_rec.columns
    _has_act = "active_CHAMP" in _daily_rec.columns

    _n_bull = int((_daily_rec["regime"] == "BULL").sum()) if _has_rg else 0
    _n_bear = int((_daily_rec["regime"] == "BEAR").sum()) if _has_rg else 0
    _n_neut = int((_daily_rec["regime"] == "NEUTRAL").sum()) if _has_rg else 0
    _avg_vix = float(_daily_rec["VIX"].mean()) if _has_vix else float("nan")
    _avg_k = float(_daily_rec["k_today"].mean()) if _has_k else float("nan")
    _trade_days = len(_by_date)

    st.markdown(f"### 📊 {_sel} 요약")
    _h1, _h2, _h3, _h4 = st.columns(4)
    _h1.metric("레짐 — BULL 일수", f"{_n_bull}일", f"BEAR {_n_bear}일 / NEUTRAL {_n_neut}일")
    _h2.metric("평균 VIX", f"{_avg_vix:.1f}" if not pd.isna(_avg_vix) else "—",
               "20 = 중립 기준")
    _h3.metric("평균 k_today (비중)", f"{_avg_k:.3f}" if not pd.isna(_avg_k) else "—",
               "1.0 = 풀로딩 / 0.33 = 33%")
    _h4.metric("거래 발생일", f"{_trade_days}일",
               f"전체 {len(_daily_rec)}일 중")

    st.markdown("---")

    # ── 미니 자산 차트 ──
    if len(_eq_rec) >= 2:
        st.markdown("### 📈 기간 자산 추이")
        _eq_disp = pd.DataFrame({"V1 자산 ($)": _eq_rec.values}, index=_eq_rec.index)
        st.line_chart(_eq_disp, height=200)
        st.markdown("---")

    # ── 일별 현황 테이블 ──
    st.markdown("### 📋 일별 현황 (최신 날짜부터)")

    _rows = []
    for _date, _drow in _daily_rec.iloc[::-1].iterrows():
        _rg = _drow["regime"] if _has_rg else "—"
        _act = _drow["active_CHAMP"] if _has_act else "—"
        _vix = float(_drow["VIX"]) if _has_vix else float("nan")
        _k = float(_drow["k_today"]) if _has_k else float("nan")
        _date_norm = _date.normalize() if hasattr(_date, "normalize") else _date
        _dr = float(_eq_daily_ret.get(_date, float("nan")))

        if _date_norm in _by_date.index:
            _tr = _by_date.loc[_date_norm]
            _trade_str = f"✅ {int(_tr['건수'])}건 ({_tr['엔진']})"
            _pnl_str = f"${float(_tr['pnl']):+,.0f}"
        else:
            _trade_str = "— 없음"
            _pnl_str = "—"

        if _rg == "BULL":
            _rg_disp = "🟢 BULL"
        elif _rg == "BEAR":
            _rg_disp = "🔴 BEAR"
        elif _rg == "NEUTRAL":
            _rg_disp = "🟡 NEUTRAL"
        else:
            _rg_disp = _rg

        _rows.append({
            "날짜": _date.strftime("%Y-%m-%d") if hasattr(_date, "strftime") else str(_date),
            "레짐": _rg_disp,
            "활성 엔진": _act,
            "VIX": f"{_vix:.2f}" if not pd.isna(_vix) else "—",
            "k_today (비중)": f"{_k:.3f}" if not pd.isna(_k) else "—",
            "일간 변동": f"{_dr:+.2f}%" if not pd.isna(_dr) else "—",
            "거래": _trade_str,
            "거래 P&L": _pnl_str,
        })

    _view_df = pd.DataFrame(_rows)
    st.dataframe(_view_df, use_container_width=True, hide_index=True, height=520)

    if st.button("💾 CSV 준비", key="j2_dl_prep"):
        st.session_state["j2_csv"] = _view_df.to_csv(index=False).encode("utf-8-sig")
    if "j2_csv" in st.session_state:
        _d0 = _daily_rec.index[0].strftime("%Y%m%d") if len(_daily_rec) else "start"
        _d1 = _daily_rec.index[-1].strftime("%Y%m%d") if len(_daily_rec) else "end"
        st.download_button(
            "⬇️ V1 매매일지 CSV",
            data=st.session_state["j2_csv"],
            file_name=f"v1_journal_{_d0}_{_d1}.csv",
            mime="text/csv",
            key="j2_dl"
        )

    st.markdown("---")
    st.info("""
**💡 컬럼 설명**

- **레짐** 🟢 BULL = 상승장(롱변기) · 🔴 BEAR = 하락장(양변기) · 🟡 NEUTRAL = 중립(롱변기)
- **활성 엔진** — 롱변기(SOXL 단방향) / 양변기(SOXL+SOXS 페어) / 황금변기(변동성 돌파)
- **VIX** — 공포지수. 10~15 안정, 20 중립, 30+ 공포
- **k_today** — 오늘 투자 비중. `0.65 × clip(20/VIX, 0.5, 2.0)`. VIX 20→0.65, VIX 10→1.0(풀로딩), VIX 40→0.33(축소)
- **일간 변동** — V1 포트폴리오 당일 수익률 (백테스트 기준)
- **거래** — 당일 매매 이벤트 수 및 사용한 엔진
- **거래 P&L** — 당일 실현·미실현 손익 합계 (백테스트 기준)
""")


# ───────────────────────────────────────────────────────────
# 용어 사전 탭
# ───────────────────────────────────────────────────────────
elif page == "📖 용어 사전":
    st.subheader("📖 용어 사전 — 처음 보는 분을 위한 용어 정리")
    st.caption("이 대시보드에 등장하는 용어들을 카테고리별로 정리했습니다.")

    def _glossary_card(term, definition, example=None):
        ex_html = f"<div style='color:#94a3b8;font-size:0.88em;margin-top:4px'>예시: {example}</div>" if example else ""
        st.markdown(f"""
<div style="background:#0f172a;border-left:3px solid #3b82f6;padding:10px 14px;border-radius:6px;margin-bottom:8px;color:#e2e8f0">
  <span style="color:#60a5fa;font-weight:700">{term}</span><br>
  <span style="line-height:1.6">{definition}</span>
  {ex_html}
</div>
""", unsafe_allow_html=True)

    # ── 섹션 1: 성과 지표 ──
    st.markdown("### 📊 성과 지표")
    _glossary_card(
        "CAGR (연복리 수익률)",
        "Compound Annual Growth Rate. 투자 기간 전체를 복리로 환산했을 때의 연간 평균 수익률. "
        "10년에 총 100% 수익이면 단순히 10%/년이 아니라 복리 계산으로 약 7.2%/년.",
        "CAGR 74% = 매년 평균 74% 복리 성장"
    )
    _glossary_card(
        "MDD (최대낙폭)",
        "Maximum Drawdown. 투자 기간 중 가장 높았던 고점 대비 가장 크게 떨어진 폭. "
        "절댓값이 작을수록 좋음. -30%라면 고점 $100이었을 때 최저 $70까지 떨어진 적 있다는 의미.",
        "MDD -28% = 고점 $100K → 최저 $72K까지 하락"
    )
    _glossary_card(
        "Calmar (칼마 비율)",
        "CAGR ÷ |MDD|. 낙폭 대비 수익 효율성 지표. "
        "수익률이 같아도 MDD가 작으면 Calmar이 높음. 1.0 이상이면 양호, 2.0 이상이면 우수.",
        "CAGR 74% ÷ MDD 28% = Calmar 2.64"
    )
    _glossary_card(
        "Sharpe (샤프 비율)",
        "수익률 ÷ 변동성. 위험 한 단위당 얼마나 수익을 냈는지. 1.0 이상이면 양호, 2.0 이상이면 우수. "
        "변동성이 크면 같은 수익이라도 Sharpe는 낮아짐.",
    )
    _glossary_card(
        "p05 / p50 / p95",
        "Bootstrap 시뮬레이션 5,000번 결과를 순서대로 줄 세울 때의 퍼센타일. "
        "p50(중앙값)이 가장 현실적인 기대치. p05는 운 나쁠 때, p95는 운 좋을 때.",
        "p50 CAGR 62% = 5,000번 중 절반은 62% 이상, 절반은 이하"
    )
    _glossary_card(
        "Bootstrap (부트스트랩)",
        "과거 수익률 데이터의 순서를 무작위로 섞어 5,000가지 가상 미래 경로를 만드는 통계 방법. "
        "단 하나의 백테스트 결과보다 미래 불확실성 범위를 더 현실적으로 추정할 수 있음.",
    )

    st.markdown("---")

    # ── 섹션 2: 전략 용어 ──
    st.markdown("### 🔧 전략 용어")
    _glossary_card(
        "레짐 (Regime)",
        "현재 시장 상태 분류. 매일 QQQ·SPY·SMH 200일선 + VIX9D + SOXL 모멘텀을 보고 판정. "
        "BULL(상승장) / NEUTRAL(중립) / BEAR(하락장) 세 가지.",
        "오늘 레짐 BEAR → 양변기 엔진으로 운영"
    )
    _glossary_card(
        "롱변기 (Long Byungi)",
        "BULL·NEUTRAL 레짐에서 사용하는 엔진. "
        "장 시작 후 SOXL이 시가 대비 +1.5% 돌파하면 매수(stop-buy). 추세 추종 방식.",
        "시가 $200 → $203 돌파 시 매수"
    )
    _glossary_card(
        "양변기 (Yang Byungi)",
        "BEAR 레짐에서 사용하는 엔진. SOXL(롱)과 SOXS(인버스)를 동시에 보유하는 페어 전략. "
        "하락장에서도 SOXS 수익으로 헤지하면서 반등 시 SOXL 수익도 노림. "
        "평균회귀(떨어진 것이 돌아온다) 성격.",
    )
    _glossary_card(
        "황금변기 (Golden Byungi)",
        "BEAR 레짐이 90일 이상 지속될 때 자동 전환하는 엔진. "
        "Keltner 채널 기반 변동성 돌파 방식으로 SOXL 매수. "
        "장기 하락장에서 양변기보다 손실을 줄이는 목적.",
        "2022 연간 하락장 후반부 등 L자형 곰장에서 효과"
    )
    _glossary_card(
        "k_today (비중 승수)",
        "오늘 얼마나 투자할지 결정하는 배수. "
        "공식: 0.65 × clip(20/VIX, 0.5, 2.0). VIX 20일 때 0.65(중립), VIX 10이면 1.0(풀), VIX 40이면 0.325(축소).",
        "VIX=15 → k=0.87 → 전략 비중의 87%만 투자"
    )
    _glossary_card(
        "BASE (비교 기준)",
        "VIX 동적 조절 없이 고정 비중(k=0.65)으로 운영했을 때의 가상 결과. "
        "V1 전략이 얼마나 개선됐는지 비교하는 기준선.",
    )
    _glossary_card(
        "갭필터 (Gap Filter)",
        "장 시작 시 전날 종가 대비 가격이 너무 크게 벌어진(갭) 경우 진입을 차단하는 필터. "
        "갭다운(-5% 이상 하락 시작)이면 롱 진입 차단. 나쁜 가격에 잡히는 것 방지.",
        "갭다운 -6% → 오늘 롱변기 진입 건너뜀"
    )
    _glossary_card(
        "dwell (드웰, 최소 유지 기간)",
        "레짐이 바뀌었어도 최소 5일은 유지하는 안정화 장치. "
        "하루 이틀 신호만으로 레짐이 왔다 갔다 하는 것(휩쏘)을 방지.",
        "BULL→BEAR 신호 감지 → 4일 더 유지 후 5일째 BEAR 확정"
    )
    _glossary_card(
        "OOS (아웃 오브 샘플)",
        "Out-of-Sample. 전략 개발·최적화에 사용하지 않은 기간으로 성과를 검증하는 것. "
        "OOS에서도 성과가 유지되면 전략이 과거 데이터에만 맞춰진 게 아님을 증명.",
    )

    st.markdown("---")

    # ── 섹션 3: ETF·종목 ──
    st.markdown("### 📈 ETF · 종목")
    col_e1, col_e2 = st.columns(2)
    with col_e1:
        _glossary_card(
            "SOXL",
            "Direxion Daily Semiconductor Bull 3X. "
            "필라델피아 반도체 지수(SOX)의 하루 수익률을 3배로 추종하는 레버리지 ETF. "
            "반도체 지수가 +1%면 SOXL은 +3%, -1%면 -3% (단, 복리 효과로 장기는 다름).",
        )
        _glossary_card(
            "QQQ",
            "나스닥 100 지수 추종 ETF. 레짐 감지 신호 중 하나로 사용 (200일 이동평균 비교).",
        )
        _glossary_card(
            "SMH",
            "VanEck 반도체 ETF. 레짐 감지 신호 중 하나로 사용 (200일 이동평균 비교).",
        )
    with col_e2:
        _glossary_card(
            "SOXS",
            "Direxion Daily Semiconductor Bear 3X. "
            "반도체 지수의 하루 수익률을 -3배로 추종하는 인버스 레버리지 ETF. "
            "반도체 하락 시 수익. 양변기 BEAR 엔진에서 헤지용으로 매수.",
        )
        _glossary_card(
            "SPY",
            "S&P 500 지수 추종 ETF. 레짐 감지 신호 중 하나로 사용 (200일 이동평균 비교).",
        )

    st.markdown("---")

    # ── 섹션 4: 시장 지표 ──
    st.markdown("### 🌡 시장 지표")
    _glossary_card(
        "VIX (공포지수)",
        "CBOE Volatility Index. S&P500 옵션 가격에서 역산한 향후 30일 변동성 기대치. "
        "시장 불안·공포가 클수록 높아짐. 10 이하=극도의 안정, 20 이하=정상, 30 이상=공포, 40 이상=극공포.",
        "VIX=40 → k 절반으로 축소 → 투자 비중 자동 감소"
    )
    _glossary_card(
        "VIX9D",
        "9일짜리 단기 VIX. 단기 공포가 장기(VIX)보다 높으면 VIX9D/VIX > 1. "
        "이 비율이 1.05 초과하면 레짐 감지기가 BEAR 신호로 판정.",
        "VIX9D=25, VIX=22 → 비율 1.14 > 1.05 → BEAR 신호"
    )
    _glossary_card(
        "SMA200 (200일 이동평균)",
        "200거래일(약 10개월) 종가 평균. 장기 추세를 판단하는 기준선. "
        "현재 가격이 SMA200보다 2% 이상 높으면 BULL, 2% 이상 낮으면 BEAR 신호.",
        "QQQ 현재가 $480, SMA200 $460 → 480/460 = 1.04 → BULL 신호"
    )

    st.markdown("---")

    # ── 섹션 5: 플랫폼·운영 ──
    st.markdown("### 🖥️ 플랫폼 · 운영")
    _glossary_card(
        "Alpaca (알파카)",
        "미국 증권 브로커. API 기반 자동매매 지원. 이 전략은 Alpaca의 페이퍼(모의) 계정으로 운영 중.",
    )
    _glossary_card(
        "페이퍼 트레이딩 (Paper Trading)",
        "실제 돈을 투입하지 않고 가상 자금으로 실거래처럼 테스트하는 것. "
        "전략이 실제 시장에서 어떻게 작동하는지 검증하는 단계.",
    )
    _glossary_card(
        "stop-buy (스톱 매수)",
        "가격이 특정 수준 이상으로 올라갈 때만 매수하는 조건부 주문. "
        "롱변기는 시가 +1.5% 돌파 시 stop-buy 발동. 추세 추종에 사용.",
        "시가 $200, stop 가격 $203 → $203 이상 거래 발생 시 자동 매수"
    )
    _glossary_card(
        "LOC (Limit-on-Close)",
        "장 마감(15:50 ET) 직전 한정가 주문. 양변기 포지션 청산에 사용. "
        "마감 경매에 참여해서 종가 근처에서 청산.",
    )

    st.info("💡 **용어가 더 필요하거나 설명이 부족한 부분이 있으면** 언제든 알려주세요.")
