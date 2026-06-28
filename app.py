"""
BUBE V1 CHAMP_NOMARGIN — Streamlit 대시보드  (redeploy nudge: 2026-06-27)
===============================================================
엔진 로테이션 × VIX dynamic-k overlay (k=0.60 × clip(20/VIX, 0.5, 2.0), alloc≤1.0).
margin 사용 X = 합법적 cash sleeve 운영.

16y in-sample (2010-05-25 ~ 2026-06-17, k 기준 0.60 since 2026-06-07):
  Cal 2.75 / CAGR +77.2% / MDD -28.13% / $100K → $926M
Bootstrap 5,000 paths: p50 Cal 2.16 / MDD -34.9% / P(MDD<-30%) = 82.0%

탭 구성:
1. 📊 Overview — V1 CHAMP_NOMARGIN spec
   (구 '📋 거래 내역' 탭은 2026-06-21 '📔 매매일지'로 통합 — 시드 환산·필터·CSV 거래 로그 포함)
3. 📈 Stress Tests — 8개 crisis V1 방어력
4. 🎲 Bootstrap — 5,000 paths 신뢰구간
5. 📅 Year-by-Year — 17년 V1 연도별
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
ASSETS = Path(__file__).parent / "assets"


def load_svg(name: str) -> str:
    """assets/<name> SVG를 읽어 컨테이너 폭에 맞게 반응형으로 렌더링할 수 있는 문자열로 반환."""
    p = ASSETS / name
    if not p.exists():
        return ""
    svg = p.read_text(encoding="utf-8")
    # 루트 <svg>에 반응형 스타일 주입 (viewBox 비율 유지하며 폭 100%)
    if "<svg" in svg and "style=" not in svg.split(">", 1)[0]:
        svg = svg.replace("<svg", '<svg style="width:100%;height:auto;display:block"', 1)
    return svg

# ── V2_FINAL 표시 토글 ──────────────────────────────────────
# V2_FINAL은 연구 옵션으로 보존하되 운영 대시보드에서는 숨긴다.
# 근거: lookahead-bias 제거 재검증(2026-05-28)에서 LAF Calmar V2 1.49 < V1 1.62,
#       VVIX shuffle z=-0.93 → V2 추가 알파는 환상으로 판명. paper 봇은 원래부터 V1 전용.
# 다시 켜려면 True: 상단 비교 배너 + Tab 8 + equity V2 곡선 + 연도별 V2 컬럼이 복원됨.
SHOW_V2 = False
st.set_page_config(page_title="BUBE V1 CHAMP_NOMARGIN Dashboard", layout="wide", page_icon="🏆",
                   initial_sidebar_state="expanded")

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
H_BOOT = champ_summary["bootstrap_CHAMP"]

# ───────────────────────────────────────────────────────────
# Header
# ───────────────────────────────────────────────────────────
st.markdown(f"""
<div style="background:linear-gradient(135deg,#2E3440 0%,#3B4252 55%,#434C5E 100%);border-left:5px solid #34A5C5;padding:24px 32px;border-radius:12px;color:#ECEFF4;margin-bottom:16px">
  <h1 style="margin:0;font-size:1.8em;color:#ECEFF4">🏆 BUBE V1 — 반도체 3배 ETF(SOXL) 동적 비중 전략</h1>
  <div style="opacity:0.92;margin-top:6px;color:#E5E9F0">
    레짐 감지(BULL/BEAR) → 엔진 전환 → <b style="color:#8FBCBB">VIX 기반 비중 자동 조절</b>&nbsp;(VIX↑ 비중↓ · VIX↓ 비중↑) · Margin 미사용
  </div>
  <div style="opacity:0.72;margin-top:4px;font-size:0.92em;color:#D8DEE9">
    백테스트 16년({champ_summary['spec']['period']}) · Alpaca 페이퍼 트레이딩 운영 중
  </div>
</div>
""", unsafe_allow_html=True)

# Quick stats row — V1 CHAMP_NOMARGIN 16y headline
col1, col2, col3, col4 = st.columns(4)
col1.metric("16년 Calmar", f"{H_CHAMP['Calmar']:.2f}",
            help="Calmar = CAGR ÷ |MDD|. 낙폭 대비 수익 효율성. 1.0 이상 양호, 2.0 이상 우수.")
col2.metric("16년 CAGR (연복리)", f"{H_CHAMP['CAGR']:.2f}%",
            help="CAGR = 연평균 복리 수익률. 16년 전체를 복리로 환산했을 때의 연간 평균 수익률.")
col3.metric("16년 MDD (최대낙폭)", f"{H_CHAMP['MDD']:.2f}%",
            help="MDD = Maximum Drawdown. 고점 대비 최대 하락폭. 절댓값이 작을수록 좋음.")
col4.metric("$10만 → 최종 (16년)", _money(H_CHAMP['Final_mult'] * 100_000),
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
    if v >= 2.0: return "#A3BE8C"
    if v >= 1.0: return "#EBCB8B"
    return "#BF616A"

def _mdd_color(v):
    if v >= -20: return "#A3BE8C"
    if v >= -35: return "#EBCB8B"
    return "#BF616A"

st.markdown(f"""
<table style="width:100%;border-collapse:collapse;font-size:0.88em;margin-top:6px">
  <thead>
    <tr style="border-bottom:1px solid #434C5E;color:#9AA5B8;text-align:right">
      <th style="text-align:left;padding:4px 8px">기간</th>
      <th style="padding:4px 12px">Calmar</th>
      <th style="padding:4px 12px">CAGR</th>
      <th style="padding:4px 12px">MDD</th>
      <th style="padding:4px 12px">$10만→</th>
    </tr>
  </thead>
  <tbody>
    <tr style="border-bottom:1px solid #434C5E">
      <td style="padding:5px 8px;color:#D8DEE9;font-weight:600">16년 (전체)</td>
      <td style="padding:5px 12px;text-align:right;color:{_cal_color(_r16['Calmar'])};font-weight:700">{_r16['Calmar']:.2f}</td>
      <td style="padding:5px 12px;text-align:right;color:#88C0D0">{_r16['CAGR']:+.2f}%</td>
      <td style="padding:5px 12px;text-align:right;color:{_mdd_color(_r16['MDD'])}">{_r16['MDD']:.2f}%</td>
      <td style="padding:5px 12px;text-align:right;color:#D8DEE9">{_money(_r16['mult']*100_000)}</td>
    </tr>
    <tr style="border-bottom:1px solid #434C5E">
      <td style="padding:5px 8px;color:#D8DEE9;font-weight:600">10년 (롤링)</td>
      <td style="padding:5px 12px;text-align:right;color:{_cal_color(_r10['Calmar'])};font-weight:700">{_r10['Calmar']:.2f}</td>
      <td style="padding:5px 12px;text-align:right;color:#88C0D0">{_r10['CAGR']:+.2f}%</td>
      <td style="padding:5px 12px;text-align:right;color:{_mdd_color(_r10['MDD'])}">{_r10['MDD']:.2f}%</td>
      <td style="padding:5px 12px;text-align:right;color:#D8DEE9">{_money(_r10['mult']*100_000)}</td>
    </tr>
    <tr>
      <td style="padding:5px 8px;color:#D8DEE9;font-weight:600"> 5년 (롤링)</td>
      <td style="padding:5px 12px;text-align:right;color:{_cal_color(_r5['Calmar'])};font-weight:700">{_r5['Calmar']:.2f}</td>
      <td style="padding:5px 12px;text-align:right;color:#88C0D0">{_r5['CAGR']:+.2f}%</td>
      <td style="padding:5px 12px;text-align:right;color:{_mdd_color(_r5['MDD'])}">{_r5['MDD']:.2f}%</td>
      <td style="padding:5px 12px;text-align:right;color:#D8DEE9">{_money(_r5['mult']*100_000)}</td>
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
<div style="background:#2E3440;border-left:4px solid #D08770;padding:10px 16px;border-radius:6px;margin:8px 0 4px;color:#E5E9F0">
  <span style="color:#D08770;font-weight:600">🆚 V2_FINAL 백테 비교 (paper 봇 미적용 — 운영은 V1 그대로)</span>
  &nbsp;·&nbsp;
  16y Cal <b>{H_V2['Calmar']:.2f}</b> (V1 {H_CHAMP['Calmar']:.2f}) &nbsp;·&nbsp;
  CAGR <b>{H_V2['CAGR_pct']:.2f}%</b> (V1 {H_CHAMP['CAGR']:.2f}%) &nbsp;·&nbsp;
  MDD <b>{H_V2['MDD_pct']:.2f}%</b> (V1 {H_CHAMP['MDD']:.2f}%) &nbsp;·&nbsp;
  Final <b>{_money(H_V2['final_multiple']*100_000)}</b>
  <span style="opacity:0.7;font-size:0.85em">&nbsp;— 자세히는 8번째 탭</span>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# ── Sidebar navigation ──────────────────────────────────────
with st.sidebar:
    st.markdown("""
<div style="background:linear-gradient(135deg,#3B4252,#434C5E);border-left:4px solid #34A5C5;padding:14px 16px;border-radius:10px;color:#ECEFF4;margin-bottom:14px;text-align:center">
  <div style="font-size:1.12em;font-weight:700;letter-spacing:0.02em">🏆 BUBE V1</div>
  <div style="opacity:0.8;font-size:0.82em;margin-top:3px">SOXL 동적 비중 전략</div>
</div>
""", unsafe_allow_html=True)
    _pages = [
        "📊 백테스트",
        "📔 매매일지",
        "📈 위기 방어력",
        "🎲 확률 분포",
        "📅 연도별 성과",
        "🔄 기간별 안정성",
        "💰 실시간 현황",
        "🔬 백테 vs 페이퍼",
        "🔍 데이터 정확성",
        "📖 용어 사전",
    ]
    # ── DS 스타일 버튼 네비게이션 (활성 페이지 = primary) ──
    if "nav_page" not in st.session_state:
        st.session_state.nav_page = _pages[0]
    if st.session_state.nav_page not in _pages:
        st.session_state.nav_page = _pages[0]
    for _p in _pages:
        if st.button(_p, key=f"nav_{_p}", use_container_width=True,
                     type="primary" if st.session_state.nav_page == _p else "secondary"):
            st.session_state.nav_page = _p
            st.rerun()
    page = st.session_state.nav_page
    st.markdown("---")
    st.caption("📊 16년 백테 핵심 지표")
    _sb1, _sb2 = st.columns(2)
    _sb1.metric("Calmar", f"{_r16['Calmar']:.2f}")
    _sb2.metric("CAGR", f"{_r16['CAGR']:+.2f}%")
    _sb1.metric("MDD", f"{_r16['MDD']:.2f}%")
    _sb2.metric("$10K→", _money(_r16['mult'] * 10_000))
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
<div style="background:#3B4252;border-left:4px solid #34A5C5;padding:14px 20px;border-radius:8px;margin-bottom:16px;color:#D8DEE9;line-height:1.9">
<b>전략 핵심 3단계</b><br>
<b>1️⃣ 레짐 감지</b> — QQQ·SPY·SMH 200일선 + VIX9D/SOXL 모멘텀으로 매일 시장 상태 판정 (BULL / NEUTRAL / BEAR)<br>
<b>2️⃣ 엔진 전환</b> — BULL·NEUTRAL → <b>롱변기</b>(SOXL 단방향 매수) · BEAR → <b>양변기</b>(SOXL롱+SOXS숏) · BEAR 90일+ → <b>황금변기</b>(변동성 돌파)<br>
<b>3️⃣ VIX 비중 조절</b> — VIX 높으면(공포) 비중 줄이고, VIX 낮으면(안정) 비중 늘림. Margin 미사용(최대 100%)
</div>
""", unsafe_allow_html=True)

    # ── 매매법 상세 흐름도 (그림) ───────────────────────────────
    _method_svg = load_svg("v1_method.svg")
    if _method_svg:
        with st.expander("🗺️ 매매법 상세 흐름도 — 레짐 판정부터 청산까지 한눈에 (그림)", expanded=True):
            st.markdown(
                f'<div style="background:#0d1117;border-radius:12px;padding:8px;overflow-x:auto">{_method_svg}</div>',
                unsafe_allow_html=True,
            )
            st.caption("매일 한 거래 사이클: ① 레짐 판정(전일 데이터) → ② 엔진 선택 → ③ 09:35 돌파 진입 "
                       "→ ④ 비대칭 갭필터 → ⑤ VIX 동적 비중 → ⑥ 엔진별 청산. 3엔진 모두 stop-buy 변동성 돌파 진입.")

    col_a, col_b = st.columns([1, 1])
    with col_a:
        with st.expander("📐 기술 스펙 보기 (코드)", expanded=True):
         st.code(f"""
# Strategy: V1 CHAMP_NOMARGIN (no-margin variant)
# = 엔진 로테이션 × VIX dynamic-k overlay × alloc cap 1.0

# Overlay 수식
k_today    = k0 × scale_today
k0         = 0.60                                    # 기준 비중 (2026-06-07 디리스킹 0.65→0.60)
scale      = clip(20.0 / VIX_today, 0.5, 2.0)        # VIX 역수 스케일
alloc_today = min(k_today × strategy_alloc, 1.0)     # margin 금지 (cap 1.0)

# 동작 직관
VIX 10  → scale 2.0 → k=1.20 → alloc cap 1.0  (저변동성 풀로딩)
VIX 20  → scale 1.0 → k=0.60 → alloc 0.60×strat  (중립)
VIX 40  → scale 0.5 → k=0.30 → alloc 0.30×strat (고변동성 디리스킹)
VIX 80  → scale 0.5 → 동일 (lo clip)

# 엔진 로테이션 (sub-strategy mapping)
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
        st.markdown("### 16년 백테스트 결과 (V1 CHAMP_NOMARGIN)")
        st.markdown(f"""
- **CAGR** (연복리): `{H_CHAMP['CAGR']:.2f}%`
- **MDD** (최대낙폭): `{H_CHAMP['MDD']:.2f}%`
- **Sharpe** (위험조정 수익): `{H_CHAMP['Sharpe']:.2f}`
- **Calmar** (수익÷낙폭): `{H_CHAMP['Calmar']:.2f}`
- **최종 자산** ($10만 시드): `{_money(H_CHAMP['Final_mult']*100_000)}`
""")

        st.markdown("### 전략 검증 결과")
        check_data = [
            ("16y 단일 path", f"Calmar {H_CHAMP['Calmar']:.2f}", "✅"),
            ("Bootstrap 5,000",
             f"p50 Cal {H_BOOT['cal_p50']:.2f}, p05 {H_BOOT['cal_p05']:.2f} 이상",
             "✅"),
            ("VIX shuffle test", "alpha 소실 → VIX-conditioning이 진짜 시그널 (random X)", "✅"),
            ("MDD 분포", f"p50 {H_BOOT['mdd_p50']:.2f}%, P(MDD<-30%)={H_BOOT['p_mdd_worse_than_30']:.2f}%", "⚠️"),
            ("CAGR 양수 확률", f"P(CAGR>0)={H_BOOT['p_cagr_positive']:.2f}%, P(CAGR>30%)={H_BOOT['p_cagr_above_30']:.2f}%", "✅"),
            ("margin 사용", "alloc_cap 1.0 → 합법 cash sleeve, leverage 0%", "✅"),
            ("Final $", f"$100K → {_money(H_CHAMP['Final_mult']*100_000)}", "✅"),
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

    # ── 자산 성장 곡선 ──────────────────────────────────────────
    st.markdown("---")

    def _mtime_bt(p):
        try: return p.stat().st_mtime
        except Exception: return 0

    @st.cache_data
    def _load_eq_bt(k):
        return pd.read_csv(CHAMP / "equity_curves.csv", parse_dates=["date"], index_col="date")

    _eq_bt = _load_eq_bt(_mtime_bt(CHAMP / "equity_curves.csv"))
    _eq_end = _eq_bt.index[-1]

    # 기간 선택 버튼
    _periods = {"3M": 3, "6M": 6, "1Y": 12, "3Y": 36, "5Y": 60, "10Y": 120, "전체": None}
    _period_cols = st.columns(len(_periods))
    _sel_period = st.session_state.get("eq_period", "전체")
    for _i, (_lbl, _mo) in enumerate(_periods.items()):
        if _period_cols[_i].button(_lbl, type="primary" if _lbl == _sel_period else "secondary",
                                   use_container_width=True, key=f"eqp_{_lbl}"):
            _sel_period = _lbl
            st.session_state["eq_period"] = _lbl

    # 선택 기간 슬라이스
    _sel_mo = _periods[_sel_period]
    if _sel_mo is not None:
        _eq_slice = _eq_bt.loc[_eq_end - pd.DateOffset(months=_sel_mo):]
    else:
        _eq_slice = _eq_bt

    _seed_bt = 100_000.0
    _s = float(_eq_slice["CHAMP_NOMARGIN"].iloc[0])

    # 기간 내 통계
    _n_yr = (_eq_slice.index[-1] - _eq_slice.index[0]).days / 365.25
    _cagr = ((_eq_slice["CHAMP_NOMARGIN"].iloc[-1] / _eq_slice["CHAMP_NOMARGIN"].iloc[0]) ** (1 / _n_yr) - 1) * 100
    _roll = _eq_slice["CHAMP_NOMARGIN"].expanding().max()
    _mdd  = ((_eq_slice["CHAMP_NOMARGIN"] - _roll) / _roll).min() * 100
    _cal  = _cagr / abs(_mdd)
    _ret  = (_eq_slice["CHAMP_NOMARGIN"].iloc[-1] / _eq_slice["CHAMP_NOMARGIN"].iloc[0] - 1) * 100

    _sc1, _sc2, _sc3, _sc4 = st.columns(4)
    _sc1.metric("구간 수익", f"{_ret:+.2f}%")
    _sc2.metric("CAGR", f"{_cagr:+.2f}%")
    _sc3.metric("MDD", f"{_mdd:.2f}%")
    _sc4.metric("Calmar", f"{_cal:.2f}")

    st.markdown(f"### 📈 자산 성장 곡선 — $10만 시드 ({_sel_period})")

    # Altair 차트 — 툴팁 달러 포맷
    import altair as alt
    _v1_vals = (_eq_slice["CHAMP_NOMARGIN"] / _s * _seed_bt).values
    _chart_df = pd.DataFrame({
        "날짜": list(_eq_slice.index),
        "자산": list(_v1_vals),
    })
    _eq_altair = (
        alt.Chart(_chart_df)
        .mark_line(strokeWidth=2, color="#34A5C5")
        .encode(
            x=alt.X("날짜:T", title="날짜"),
            y=alt.Y("자산:Q", title="자산 ($)", axis=alt.Axis(format="$,.0f")),
            tooltip=[
                alt.Tooltip("날짜:T", title="날짜", format="%Y-%m-%d"),
                alt.Tooltip("자산:Q", title="자산", format="$,.0f"),
            ],
        )
        .properties(height=400)
    )
    st.altair_chart(_eq_altair, use_container_width=True)
    st.caption("V1 CHAMP_NOMARGIN 자산 곡선. 구간 시작 기준 $10만으로 재조정.")


# ───────────────────────────────────────────────────────────
# TAB 3: Stress Tests
# ───────────────────────────────────────────────────────────
elif page == "📈 위기 방어력":
    st.subheader("📈 위기 구간 방어력 — 8개 위기에서 V1 성과")
    st.caption("코로나·금리쇼크 등 실제 위기 구간에서 V1(VIX 동적 비중)의 수익률과 낙폭(MDD).")

    crisis_path = CHAMP / "crisis.csv"
    if crisis_path.exists():
        cr = pd.read_csv(crisis_path)
        # Display columns — V1(CHAMP)만 표시
        disp = cr[["crisis", "from", "to", "CHAMP_ret_%", "CHAMP_mdd_%"]].copy()
        disp["CHAMP_ret_%"] = disp["CHAMP_ret_%"].apply(lambda x: f"{x:+.2f}%")
        disp["CHAMP_mdd_%"] = disp["CHAMP_mdd_%"].apply(lambda x: f"{x:+.2f}%")
        disp.columns = ["Crisis", "From", "To", "V1 Ret", "V1 MDD"]
        st.dataframe(disp, use_container_width=True, hide_index=True)

        # Summary stats — V1 절대 기준
        n_total = len(cr)
        avg_mdd = cr["CHAMP_mdd_%"].mean()
        worst_mdd = cr["CHAMP_mdd_%"].min()
        worst_row = cr.loc[cr["CHAMP_mdd_%"].idxmin()]
        n_pos = int((cr["CHAMP_ret_%"] > 0).sum())

        sc1, sc2, sc3, sc4 = st.columns(4)
        sc1.metric("위기 수", f"{n_total}")
        sc2.metric("평균 위기 MDD", f"{avg_mdd:+.2f}%", "위기 구간 평균 낙폭")
        sc3.metric("최악 위기 MDD", f"{worst_mdd:+.2f}%", str(worst_row["crisis"]))
        sc4.metric("플러스 수익 위기", f"{n_pos}/{n_total}",
                   "위기 중에도 수익난 횟수")

        st.info(
            "💡 VIX가 폭등하는 위기 시작 구간에 scale가 0.5로 clip되어 alloc이 자동 축소 → 손실 제한. "
            "V-recovery 구간에서는 VIX 하락 → scale 1.5~2.0으로 풀로딩 회복. "
            "이 자동 디리스킹이 V1의 위기 방어 메커니즘."
        )

        # 2020 Covid recovery 케이스 — 방어의 trade-off
        cov_rec = cr[cr["crisis"] == "2020 Covid recovery"]
        if len(cov_rec) > 0:
            r = cov_rec.iloc[0]
            st.warning(
                f"⚠️ **2020 Covid recovery**: V1 {r['CHAMP_ret_%']:+.2f}% — VIX가 30~40 구간에 머무를 때 "
                f"scale<1로 풀로딩 못함 → V-recovery upside 일부 놓침. "
                f"**trade-off**: 위기 시작 MDD 보호의 대가."
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
    bc1.metric("하위 5% (최악 케이스)", f"{b['cagr_p05']:.2f}%")
    bc1.metric("중앙값 (기대 기준)", f"{b['cagr_p50']:.2f}%")
    bc1.metric("상위 5% (최선 케이스)", f"{b['cagr_p95']:.2f}%")
    bc1.caption(f"P(CAGR > 0) = **{b['p_cagr_positive']:.2f}%** · P(CAGR > 30%) = **{b['p_cagr_above_30']:.2f}%**")

    bc2.markdown("### MDD (최대낙폭) 분포")
    bc2.metric("하위 5% (낙폭 최대)", f"{b['mdd_p05']:.2f}%")
    bc2.metric("중앙값 (기대 기준)", f"{b['mdd_p50']:.2f}%")
    bc2.metric("상위 5% (낙폭 최소)", f"{b['mdd_p95']:.2f}%")
    bc2.caption(f"P(MDD < -30%) = **{b['p_mdd_worse_than_30']:.2f}%** · P(MDD < -40%) = **{b['p_mdd_worse_than_40']:.2f}%**")

    bc3.markdown("### Calmar (수익÷낙폭) 분포")
    bc3.metric("하위 5%", f"{b['cal_p05']:.2f}")
    bc3.metric("중앙값 (운영 기대치)", f"{b['cal_p50']:.2f}")
    bc3.metric("상위 5%", f"{b['cal_p95']:.2f}")
    bc3.caption("16년 단일 경로 Calmar은 약간 운 좋은 실현 — 운영 기대치는 중앙값 기준으로 봐야 함.")

    st.markdown("---")
    st.markdown("### 핵심 해석 (운영 기대 범위)")
    st.info(
        f"**진짜 운영 기대치**: bootstrap p50 = CAGR **{b['cagr_p50']:.2f}%** / MDD **{b['mdd_p50']:.2f}%** / Calmar **{b['cal_p50']:.2f}**. "
        f"단일 16년 path의 Cal 2.75는 약간 운 좋은 실현이며, 실제로는 **2.0 ~ 2.3 박스**가 기본 시나리오.\n\n"
        f"**MDD 꼬리 위험**: P(MDD<-30%) = {b['p_mdd_worse_than_30']:.2f}%, P(MDD<-40%) = {b['p_mdd_worse_than_40']:.2f}% — "
        f"미래 path가 -30% 넘어갈 확률 {b['p_mdd_worse_than_30']:.0f}%, -40% 확률 {b['p_mdd_worse_than_40']:.0f}% 정도. **mentally prepare**."
    )


    # ── Bootstrap 분포 시각화 ──────────────────────────────────
    st.markdown("---")
    st.markdown("### 📊 Bootstrap 분포 시각화 (5,000 paths)")
    import altair as _alt
    _bv_rows = []
    for _metric, _p05, _p50, _p95, _unit in [
        ("CAGR", b["cagr_p05"], b["cagr_p50"], b["cagr_p95"], "%"),
        ("MDD",  b["mdd_p05"],  b["mdd_p50"],  b["mdd_p95"],  "%"),
        ("Calmar", b["cal_p05"], b["cal_p50"], b["cal_p95"], ""),
    ]:
        _bv_rows.append({"지표": _metric, "구간": "P5~P95", "low": _p05, "high": _p95, "p50": _p50, "unit": _unit})
    _bv_df = pd.DataFrame(_bv_rows)
    _boot_charts = []
    for _, _row in _bv_df.iterrows():
        _fmt = ".2f" if _row["unit"] == "" else "+.2f"
        _band = _alt.Chart(pd.DataFrame({"x": [_row["p50"]], "low": [_row["low"]], "high": [_row["high"]]})).mark_rule(
            color="#4C566A", strokeWidth=12, opacity=0.3
        ).encode(x=_alt.X("low:Q"), x2="high:Q", y=_alt.value(0))
        _med  = _alt.Chart(pd.DataFrame({"x": [_row["p50"]]})).mark_rule(
            color="#34A5C5", strokeWidth=3
        ).encode(x=_alt.X("x:Q", title=f"{_row['지표']} ({_row['unit']})" if _row['unit'] else _row['지표']))
        _p05l = _alt.Chart(pd.DataFrame({"x": [_row["low"]]})).mark_rule(
            color="#BF616A", strokeWidth=1.5, strokeDash=[4, 2]
        ).encode(x="x:Q")
        _p95l = _alt.Chart(pd.DataFrame({"x": [_row["high"]]})).mark_rule(
            color="#A3BE8C", strokeWidth=1.5, strokeDash=[4, 2]
        ).encode(x="x:Q")
        _boot_charts.append((_alt.layer(_band, _med, _p05l, _p95l)
            .properties(title=f"{_row['지표']}: P5={_row['low']:.2f} | P50={_row['p50']:.2f} | P95={_row['high']:.2f}", height=80, width=200)
        ))
    st.altair_chart(_alt.hconcat(*_boot_charts), use_container_width=True)
    st.caption("파란 실선=중앙값(P50) · 회색 막대=P5~P95 구간 · 빨간점선=P5(최악) · 초록점선=P95(최선)")

    st.markdown("---")
    st.markdown("### ✅ VIX shuffle test (검증)")
    st.markdown("""
**테스트**: VIX 시리즈를 무작위 셔플 → scale = clip(20/shuffled_VIX, 0.5, 2.0) 적용 → alpha 0으로 수렴.
**결과**: VIX-conditioning이 진짜 시그널 ✓ (random k variation으로는 alpha 나오지 않음).

이건 단순히 "k=0.60에서 가끔 위아래로 움직인다"가 아니라, **VIX 신호가 시점 정보를 담고 있어서** alpha 발생한다는 것을 입증.
""")


# ───────────────────────────────────────────────────────────
# TAB 5: Year-by-Year
# ───────────────────────────────────────────────────────────
elif page == "📅 연도별 성과":
    st.subheader("📅 연도별 성과 — 17년 V1 CHAMP(우리 매매법)")
    st.markdown(
        "<div style='background:#3B4252;border-left:4px solid #34A5C5;padding:10px 16px;border-radius:8px;"
        "margin-bottom:12px;color:#E5E9F0;line-height:1.6'>"
        "<b style='color:#88C0D0'>🏆 CHAMP_NOMARGIN = 우리가 실제로 운영하는 V1 매매법</b> "
        "(VIX 동적 비중). 연도별 수익률·MDD·Sharpe·연말자본을 보여줍니다. "
        "아래 막대를 클릭하면 그 해 월별 성과가 표시됩니다.</div>",
        unsafe_allow_html=True,
    )

    yp = CHAMP / "yearly.csv"
    if yp.exists():
        y = pd.read_csv(yp)

        # Load V2 yearly for column overlay (daily-updated source)
        v2_yearly = None
        v2_yp = V2DIR / "yearly_breakdown.csv"
        if SHOW_V2 and v2_yp.exists():
            v2_yearly = pd.read_csv(v2_yp).set_index("year")

        # Build display — V1 CHAMP만 표시
        rows = []
        for _, r in y.iterrows():
            yr_int = int(r["year"])
            row = {
                "연도": yr_int,
                "수익률": f"{r['CHAMP_ret_%']:+.2f}%",
                "MDD": f"{r['CHAMP_mdd_%']:+.2f}%",
                "Sharpe": f"{r['CHAMP_sharpe']:.2f}",
                "연말자본": _money(r["CHAMP_end_$"]),
            }
            rows.append(row)
        df_year = pd.DataFrame(rows)

        def _ret_clr(v):
            if isinstance(v, str) and v.startswith("+"): return "color:#A3BE8C;font-weight:600"
            if isinstance(v, str) and v.startswith("-"): return "color:#BF616A"
            return ""

        _sty = (
            df_year.style
            .set_properties(subset=["수익률", "MDD", "Sharpe", "연말자본"],
                            **{"background-color": "#3B4252", "color": "#88C0D0", "font-weight": "700"})
            .map(_ret_clr, subset=["수익률"])
        )
        st.dataframe(_sty, use_container_width=True, hide_index=True, height=(len(df_year) + 1) * 35 + 3)
        st.caption("V1 CHAMP_NOMARGIN 연도별 성과 (VIX 동적 비중).")

        # Summary — V1 절대 기준
        total = len(y)
        pos_years = int((y["CHAMP_ret_%"] > 0).sum())
        best_row = y.loc[y["CHAMP_ret_%"].idxmax()]
        worst_row = y.loc[y["CHAMP_ret_%"].idxmin()]
        avg_yr_ret = y["CHAMP_ret_%"].mean()

        st.markdown("---")
        yc1, yc2, yc3, yc4 = st.columns(4)
        yc1.metric("총 연도", f"{total}")
        yc2.metric("플러스 수익 연도", f"{pos_years}/{total}",
                   f"{pos_years/total*100:.0f}%")
        yc3.metric("평균 연 수익률", f"{avg_yr_ret:+.1f}%")
        yc4.metric("최고 / 최저 연",
                   f"{int(best_row['year'])} / {int(worst_row['year'])}",
                   f"{best_row['CHAMP_ret_%']:+.0f}% / {worst_row['CHAMP_ret_%']:+.0f}%")

        # ── 연도별 CHAMP 수익률 (막대 클릭 → 그 해 월별 막대차트) ──────────
        st.markdown("---")
        st.markdown("### 📊 연도별 CHAMP 수익률 — 막대를 클릭하면 그 해 월별 성과가 아래에 표시됩니다")
        import altair as _alt5
        _y5_df = pd.DataFrame({
            "yr":  y["year"].astype(int).values,
            "ret": y["CHAMP_ret_%"].values,
            "mdd": y["CHAMP_mdd_%"].values,
        })
        _y5sel = _alt5.selection_point(fields=["yr"], name="y5sel")
        _y5_chart = (
            _alt5.Chart(_y5_df).mark_bar().encode(
                x=_alt5.X("yr:O", title="연도"),
                y=_alt5.Y("ret:Q", title="CHAMP 연 수익률 (%)"),
                color=_alt5.condition("datum.ret >= 0",
                                      _alt5.value("#A3BE8C"), _alt5.value("#BF616A")),
                opacity=_alt5.condition(_y5sel, _alt5.value(1.0), _alt5.value(0.55)),
                tooltip=[_alt5.Tooltip("yr:O", title="연도"),
                         _alt5.Tooltip("ret:Q", title="수익률(%)", format="+.2f"),
                         _alt5.Tooltip("mdd:Q", title="연중 MDD(%)", format=".2f")],
            ).add_params(_y5sel).properties(height=300)
        )
        _y5_event = st.altair_chart(_y5_chart, use_container_width=True,
                                    on_select="rerun", key="j5_year_sel")

        # 선택 연도 추출 (클릭 없으면 최근 연도 기본 표시)
        _y5_years = [int(v) for v in _y5_df["yr"].values]
        _y5_sel_year = _y5_years[-1] if _y5_years else None
        try:
            _y5_pick = _y5_event["selection"]["y5sel"]
            if _y5_pick:
                _y5_sel_year = int(_y5_pick[0]["yr"])
        except Exception:
            pass

        # 월별 수익률 (월말 종가 기준, 1월은 전년 말 대비)
        _eq5 = pd.read_csv(CHAMP / "equity_curves.csv", parse_dates=["date"], index_col="date")
        _eq5s = (_eq5["CHAMP_NOMARGIN"].dropna()
                 if "CHAMP_NOMARGIN" in _eq5.columns else pd.Series(dtype=float))
        _m5 = _eq5s.resample("ME").last().pct_change() * 100
        _m5y = _m5[_m5.index.year == _y5_sel_year].dropna()
        _m5_df = pd.DataFrame({"m": [int(d.month) for d in _m5y.index], "ret": _m5y.values})
        _m5_df["mlabel"] = _m5_df["m"].map(lambda x: f"{x}월")
        _m5_order = [f"{m}월" for m in range(1, 13)]

        st.markdown(f"#### 📊 {_y5_sel_year}년 월별 성과")
        if len(_m5_df):
            st.altair_chart(
                _alt5.Chart(_m5_df).mark_bar().encode(
                    x=_alt5.X("mlabel:N", sort=_m5_order, title="월"),
                    y=_alt5.Y("ret:Q", title="월 수익률 (%)"),
                    color=_alt5.condition("datum.ret >= 0",
                                          _alt5.value("#A3BE8C"), _alt5.value("#BF616A")),
                    tooltip=[_alt5.Tooltip("mlabel:N", title="월"),
                             _alt5.Tooltip("ret:Q", title="수익률(%)", format="+.2f")],
                ).properties(height=280),
                use_container_width=True,
            )
            _r5 = _y5_df[_y5_df["yr"] == _y5_sel_year]
            if len(_r5):
                _b5 = _m5_df.loc[_m5_df["ret"].idxmax()]
                _w5 = _m5_df.loc[_m5_df["ret"].idxmin()]
                st.caption(
                    f"{_y5_sel_year}년 — 연수익률 **{_r5['ret'].iloc[0]:+.2f}%** · "
                    f"연중 MDD {_r5['mdd'].iloc[0]:.2f}% · "
                    f"최고 {_b5['mlabel']} {_b5['ret']:+.1f}% · "
                    f"최저 {_w5['mlabel']} {_w5['ret']:+.1f}% · "
                    f"플러스 {int((_m5_df['ret'] > 0).sum())}/{len(_m5_df)}개월")
        else:
            st.info(f"{_y5_sel_year}년 월별 데이터가 없습니다.")
        st.markdown("---")

        # Yearly equity chart — V1만
        st.markdown("### 📈 연말 자본 ($100K 시드 기준)")
        import altair as _alt
        _cy_df = pd.DataFrame({
            "연도": y["year"].astype(int).values,
            "자산": y["CHAMP_end_$"].values,
        })
        st.altair_chart(
            _alt.Chart(_cy_df).mark_line(point=True, strokeWidth=3, color="#34A5C5").encode(
                x=_alt.X("연도:O", title="연도"),
                y=_alt.Y("자산:Q", title="자산 ($)", axis=_alt.Axis(format="$,.0f")),
                tooltip=[_alt.Tooltip("연도:O", title="연도"),
                         _alt.Tooltip("자산:Q", title="자산", format="$,.0f")],
            ).properties(height=320),
            use_container_width=True,
        )

        st.success(
            f"💡 **17년 중 {pos_years}년**에서 플러스 수익 (평균 연 {avg_yr_ret:+.1f}%). "
            f"최고 {int(best_row['year'])}년 {best_row['CHAMP_ret_%']:+.0f}% · "
            f"최저 {int(worst_row['year'])}년 {worst_row['CHAMP_ret_%']:+.0f}% — "
            f"VIX dynamic-k overlay로 낙폭을 통제하며 복리 성장."
        )
    else:
        st.warning("champ_nomargin/yearly.csv 없음.")


# ───────────────────────────────────────────────────────────
# TAB 6: Multi-window OOS
# ───────────────────────────────────────────────────────────
elif page == "🔄 기간별 안정성":
    st.subheader("🔄 기간별 안정성 — 1년~16년 윈도우 검증")
    st.caption("최근 1년, 2년, 5년, 16년 등 다양한 기간에서 V1의 Calmar·CAGR이 일관되게 견조한지 확인. 특정 기간 cherry-pick이 아님을 검증.")

    swp = CHAMP / "summary_wide.csv"
    if swp.exists():
        sw = pd.read_csv(swp)
        # 표시 — V1(CHAMP)만
        disp = sw[["window", "years", "CHAMP_CAGR_%", "CHAMP_MDD_%",
                   "CHAMP_Sharpe", "CHAMP_Calmar", "CHAMP_Final_$"]].copy()
        disp["years"] = disp["years"].round(2)
        disp["CHAMP_CAGR_%"] = disp["CHAMP_CAGR_%"].apply(lambda x: f"{x:+.2f}%")
        disp["CHAMP_MDD_%"] = disp["CHAMP_MDD_%"].apply(lambda x: f"{x:+.2f}%")
        disp["CHAMP_Sharpe"] = disp["CHAMP_Sharpe"].apply(lambda x: f"{x:.2f}")
        disp["CHAMP_Calmar"] = disp["CHAMP_Calmar"].apply(lambda x: f"{x:.2f}")
        disp["CHAMP_Final_$"] = disp["CHAMP_Final_$"].apply(_money)
        disp.columns = ["윈도우", "연수", "CAGR", "MDD", "Sharpe", "Calmar", "최종자본"]
        st.dataframe(disp, use_container_width=True, hide_index=True)

        st.markdown("---")
        # Calmar trajectory across windows — V1만
        st.markdown("### 📈 Window별 Calmar 추이")
        import altair as _alt
        _cal_df = pd.DataFrame({
            "window": sw["window"].values,
            "Calmar": sw["CHAMP_Calmar"].values,
        })
        st.altair_chart(
            _alt.Chart(_cal_df).mark_bar(color="#34A5C5").encode(
                x=_alt.X("window:N", title="윈도우", sort=None),
                y=_alt.Y("Calmar:Q", title="Calmar"),
                tooltip=[_alt.Tooltip("window:N", title="윈도우"),
                         _alt.Tooltip("Calmar:Q", title="Calmar", format=".2f")],
            ).properties(height=300),
            use_container_width=True,
        )

        st.markdown("### 📈 Window별 CAGR")
        import altair as _alt
        _cg_df = pd.DataFrame({
            "window": sw["window"].values,
            "CAGR (%)": sw["CHAMP_CAGR_%"].values,
        })
        st.altair_chart(
            _alt.Chart(_cg_df).mark_bar(color="#34A5C5").encode(
                x=_alt.X("window:N", title="윈도우", sort=None),
                y=_alt.Y("CAGR (%):Q", title="CAGR (%)"),
                tooltip=[_alt.Tooltip("window:N", title="윈도우"),
                         _alt.Tooltip("CAGR (%):Q", title="CAGR", format="+.2f")],
            ).properties(height=300),
            use_container_width=True,
        )

        # V1 일관성 — 모든 window 양호?
        min_cal = float(sw["CHAMP_Calmar"].min())
        min_cagr = float(sw["CHAMP_CAGR_%"].min())
        all_pos = bool((sw["CHAMP_CAGR_%"] > 0).all())
        st.success(
            f"✅ **모든 window에서 CAGR 양수**: {all_pos} · "
            f"최저 Calmar {min_cal:.2f} · 최저 CAGR {min_cagr:+.1f}%. "
            f"단일 window cherry-pick이 아닌 1y~16y 전체에서 일관 견조 → over-fit 가능성 낮음."
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
<div style="background:linear-gradient(135deg,#2E3440,#4C566A);padding:18px 24px;border-radius:10px;color:white;margin:8px 0 16px">
  <div style="font-size:1.1em;font-weight:600;margin-bottom:8px">🏆 V1 CHAMP_NOMARGIN Overlay (운영 중)</div>
  <div style="opacity:0.92;line-height:1.7">
    <b>k_today</b> = 0.60 × clip(20.0 / VIX_today, 0.5, 2.0), <b>alloc_today</b> = min(k × strat_alloc, 1.0) &nbsp;<span style="opacity:0.7">(기준 0.60 — 2026-06-07 디리스킹)</span><br>
    엔진 로테이션: <b>BULL/NEUTRAL</b> 롱변기 · <b>BEAR</b> 양변기 v5 · <b>BEAR streak &gt; 90d</b> 황금변기<br>
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
                k_today = 0.60 * scale   # k0=0.60 (2026-06-07 디리스킹, 봇과 동기)
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
                      f"기준 0.60 대비 {rstate['k_today']/0.60:.1f}×",
                      help="0.60 × 스케일 (기준 0.60, 2026-06-07 디리스킹). 이 값이 전략 원래 비중에 곱해짐.")
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
            # 최근 60일 주문 — 평단(평균단가) 회계용으로 넉넉히, 표시는 30일만
            _month_ago = today_utc - _dt.timedelta(days=60)
            orders_30d = tc.get_orders(filter=GetOrdersRequest(
                status=QueryOrderStatus.CLOSED, after=_month_ago, limit=500
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
                "orders_30d": [{
                    "filled_at": str(o.filled_at) if o.filled_at else (str(o.submitted_at) if o.submitted_at else None),
                    "symbol": o.symbol, "side": o.side.value, "qty": float(o.qty),
                    "status": o.status.value,
                    "fill_avg": float(o.filled_avg_price) if o.filled_avg_price else None,
                } for o in orders_30d],
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

        # ── 최근 30일 매매·수정 타임라인 ──────────────────────────
        st.markdown("---")
        st.markdown("### 📋 최근 30일 매매 · 운영 수정 타임라인")
        st.caption("최근 30일 체결을 시간순으로 — 🟢매수 / 🔴매도(평단 대비 실현 수익률%·손익$) · 날짜별 **누적 실현손익** · "
                   "우리가 적용한 운영 수정(🔧)도 끼워 표시. 평단은 60일 주문 이력으로 평균단가 회계.")

        import datetime as _dtt
        # 운영 수정 이력 (라이브 봇/백테에 실제 적용한 변경)
        _fix_events = [
            ("2026-05-26", "🚀 V1 CHAMP_NOMARGIN 전환", "T2 GOLD_ESCAPE(bm=90) → V1 CHAMP (엔진 로테이션 × VIX 동적-k, cap 1.0)"),
            ("2026-06-03", "🔧 비대칭 갭필터 (A안)", "롱변기·양변기롱 SOXL 매수는 갭다운(−5%↓)만 차단·갭업 허용, 양변기숏 대칭 유지"),
            ("2026-06-07", "📉 k 디리스킹 0.65→0.60", "기준 k(k0) 0.65→0.60 (봇·백테 동기). 저VIX 노출 0.90→0.83, 16y MDD 개선, Calmar 정점 유지"),
            ("2026-06-11", "🔧 롱변기 stop-buy 거부 수리", "강갭업 시 buy-stop이 현재가 아래로 떨어져 Alpaca 거부 → marketable-limit 추격 (PR#12)"),
            ("2026-06-19", "🌡 VIX9D fast-BEAR + 매일 갱신", "regime에 VIX9D/VIX>1.05 즉시 BEAR. V1 CHAMP 백테 평일 매일 자동 갱신 (PR#13)"),
        ]
        _cutoff = (_dtt.date.today() - _dtt.timedelta(days=31)).isoformat()

        # 1) 체결 주문 시간순 → 평균단가 회계 (봇은 SOXL·SOXS 모두 롱: buy=개시, sell=청산)
        _fills = [o for o in data.get("orders_30d", [])
                  if o.get("status") == "filled" and o.get("fill_avg") and o.get("filled_at")]
        _fills.sort(key=lambda o: o["filled_at"])
        _book, _trades = {}, []
        for _o in _fills:
            _sym = _o["symbol"]; _q = float(_o["qty"]); _px = float(_o["fill_avg"]); _side = _o["side"]
            _p = _book.setdefault(_sym, {"q": 0.0, "cost": 0.0})
            _avg = _realized = _ret = None
            if _side == "buy":
                _p["q"] += _q; _p["cost"] += _q * _px
            elif _p["q"] > 1e-9:                       # 청산 (보유분 한도 내)
                _avg = _p["cost"] / _p["q"]
                _sq = min(_q, _p["q"])
                _realized = _sq * (_px - _avg)
                _ret = (_px / _avg - 1) * 100
                _p["cost"] -= _avg * _sq; _p["q"] -= _sq
            _trades.append({"date": _o["filled_at"][:10], "side": _side, "sym": _sym,
                            "qty": _q, "px": _px, "avg": _avg, "realized": _realized, "ret": _ret})

        # 2) 30일 표시분에 누적 실현손익(시간순)
        _disp_trades = [t for t in _trades if t["date"] >= _cutoff]
        _cum = 0.0
        for _t in _disp_trades:
            if _t["realized"] is not None:
                _cum += _t["realized"]
            _t["cum"] = _cum

        # 3) 타임라인 행 — 5컬럼(날짜·유형·내용·손익·누적), 내용에 합쳐 가독성↑
        _tl_rows = []
        for _fd, _ft, _fdesc in _fix_events:
            if _fd < _cutoff:
                continue
            _tl_rows.append({"_d": _fd, "날짜": _fd, "유형": "🔧 수정",
                             "내용": f"{_ft} — {_fdesc}", "손익": "—", "누적": "—"})
        for _t in _disp_trades:
            if _t["side"] == "buy":
                _typ, _pnl = "🟢 매수", "진입"
                _cont = f"{_t['sym']} {_t['qty']:,.0f}주 @ ${_t['px']:,.2f}"
            elif _t["avg"] is not None:
                _typ = "🔴 매도"
                _cont = f"{_t['sym']} {_t['qty']:,.0f}주 · 평단 ${_t['avg']:,.2f} → 체결 ${_t['px']:,.2f}"
                _pnl = f"${_t['realized']:+,.0f} ({_t['ret']:+.2f}%)"
            else:
                _typ, _pnl = "🔴 매도", "—"
                _cont = f"{_t['sym']} {_t['qty']:,.0f}주 @ ${_t['px']:,.2f}"
            _tl_rows.append({"_d": _t["date"], "날짜": _t["date"], "유형": _typ, "내용": _cont,
                             "손익": _pnl, "누적": f"${_t['cum']:+,.0f} ({_t['cum'] / seed * 100:+.2f}%)"})

        if _tl_rows:
            _tl_df = (pd.DataFrame(_tl_rows).sort_values("_d", ascending=False)
                      .drop(columns="_d").reset_index(drop=True))

            def _hl_row(_row):
                if _row["유형"] == "🔧 수정":
                    return ["background-color:#4C566A;color:#EBCB8B;font-weight:600"] * len(_row)
                return [""] * len(_row)

            def _clr_pnl(v):
                if isinstance(v, str) and v not in ("—", "진입"):
                    if "+" in v:
                        return "color:#A3BE8C"
                    if "-" in v or "−" in v:
                        return "color:#BF616A"
                return ""

            _tl_sty = (_tl_df.style.apply(_hl_row, axis=1)
                       .map(_clr_pnl, subset=["손익", "누적"]))
            st.dataframe(
                _tl_sty, use_container_width=True, hide_index=True,
                height=min((len(_tl_df) + 1) * 35 + 3, 680),
                column_config={
                    "날짜": st.column_config.TextColumn(width="small"),
                    "유형": st.column_config.TextColumn(width="small"),
                    "내용": st.column_config.TextColumn(width="large"),
                },
            )
            _n_fix = sum(1 for _r in _tl_rows if _r["유형"] == "🔧 수정")
            _tot_real = sum(t["realized"] for t in _disp_trades if t["realized"] is not None)
            st.caption(f"최근 30일: 체결 **{len(_disp_trades)}건** · 매도 누적 실현손익 **${_tot_real:+,.0f} ({_tot_real / seed * 100:+.2f}%)** (시드 $100K 대비) · 운영 수정 **{_n_fix}건**(🔧 황색). 매도행 = 평단 대비 수익률%.")
        else:
            st.info("최근 30일 체결 내역 없음 — 레짐이 현금 유지 중이었거나 진입 조건 미충족.")

        # 전체 수정 이력 (30일 밖 포함)
        with st.expander("🛠 운영 수정 이력 전체 (시간순)"):
            for _fd, _ft, _fdesc in _fix_events:
                st.markdown(f"- **`{_fd}`** {_ft} — {_fdesc}")

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
<div style="background:linear-gradient(135deg,#3B4252,#434C5E);padding:18px 22px;border-radius:10px;color:#ECEFF4;margin:8px 0 16px">
  <div style="font-size:1.05em;font-weight:700;margin-bottom:6px">🆚 V2_FINAL Spec (D6b conditional VVIX + T4c NDX/SPY RS sizing)</div>
  <div style="font-family:monospace;font-size:0.9em;opacity:0.92;line-height:1.6">
    k = 0.65 × clip(20/VIX, 0.5, 2.0)<br>
    &nbsp;&nbsp;&nbsp;&nbsp;× (clip(90/VVIX, 0.5, 1.0) <b>if SOXL_5d_ret &lt; 0 else 1.0</b>) &nbsp;← D6b: conditional VVIX<br>
    &nbsp;&nbsp;&nbsp;&nbsp;× (<b>0.8 if NDX/SPY_20d_RS &lt; 0 else 1.0</b>) &nbsp;← T4c: tech leadership sizing<br>
    alloc_today = min(k × strat_alloc, 1.0) &nbsp;← margin 사용 X (V1과 동일)
  </div>
  <div style="opacity:0.75;margin-top:8px;font-size:0.85em">
    V1 대비 차이: ① SOXL 약세일 때만 VVIX vol-of-vol clip 추가, ② NDX(=QQQ)/SPY 20일 RS 음수일 때 alloc 20% throttle.
    엔진 로테이션·regime detector는 V1과 완전 동일.
  </div>
</div>
""", unsafe_allow_html=True)

        # ── B. Headline metric grid ──
        st.markdown(f"### 📊 In-sample 비교 ({H_V2.get('start','?')} ~ {H_V2.get('end','?')}, {H_V2.get('years','?')}년)")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Calmar", f"{H_V2['Calmar']:.2f}",
                  f"V1 {H_V1['Calmar']:.2f} · +{H_V2['Calmar']-H_V1['Calmar']:.2f}")
        m2.metric("CAGR", f"{H_V2['CAGR_pct']:.2f}%",
                  f"V1 {H_V1['CAGR_pct']:.2f}% · {H_V2['CAGR_pct']-H_V1['CAGR_pct']:+.2f}pp")
        m3.metric("MDD", f"{H_V2['MDD_pct']:.2f}%",
                  f"V1 {H_V1['MDD_pct']:.2f}% · {H_V2['MDD_pct']-H_V1['MDD_pct']:+.2f}pp")
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
                  f"MDD {H_SOXL_BH['MDD_pct']:.2f}%")

        st.markdown(
            f"💡 V2_FINAL의 핵심 효과: **CAGR은 V1과 사실상 동일** "
            f"({H_V2['CAGR_pct']-H_V1['CAGR_pct']:+.2f}pp), **MDD를 {H_V1['MDD_pct']-H_V2['MDD_pct']:.2f}pp 개선** "
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
        def _load_v2_equity(mtime_key):
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
        _cv2_long = chart_v2.reset_index().melt(id_vars="date", var_name="전략", value_name="자산")
        st.altair_chart(
            alt.Chart(_cv2_long).mark_line(strokeWidth=1.5).encode(
                x=alt.X("date:T", title="날짜"),
                y=alt.Y("자산:Q", title="자산 ($)", axis=alt.Axis(format="$,.0f")),
                color=alt.Color("전략:N"),
                tooltip=[alt.Tooltip("date:T", title="날짜", format="%Y-%m-%d"),
                         alt.Tooltip("전략:N"), alt.Tooltip("자산:Q", title="자산", format="$,.0f")],
            ).properties(height=380),
            use_container_width=True,
        )

        # log scale option
        with st.expander("📐 Log-scale 보기"):
            log_chart = chart_v2.apply(lambda c: np.log10(c))
            log_chart.columns = ["log10 " + c for c in chart_v2.columns]
            _lc_long = log_chart.reset_index().melt(id_vars="date", var_name="전략", value_name="log10값")
            st.altair_chart(
                alt.Chart(_lc_long).mark_line(strokeWidth=1.5).encode(
                    x=alt.X("date:T", title="날짜"),
                    y=alt.Y("log10값:Q", title="log10(자산)"),
                    color=alt.Color("전략:N"),
                    tooltip=[alt.Tooltip("date:T", title="날짜", format="%Y-%m-%d"),
                             alt.Tooltip("전략:N"), alt.Tooltip("log10값:Q", format=".3f")],
                ).properties(height=320),
                use_container_width=True,
            )

        st.markdown("---")

        # ── D. Yearly breakdown V1 vs V2 ──
        st.markdown("### 📅 Year-by-Year — V1 vs V2_FINAL")
        @st.cache_data
        def _load_v2_yearly(mtime_key):
            return pd.read_csv(V2DIR / "yearly_breakdown.csv")
        yb = _load_v2_yearly(_mtime_t8(V2DIR / "yearly_breakdown.csv"))

        rows = []
        for _, r in yb.iterrows():
            rows.append({
                "Year": int(r["year"]),
                "V1 Ret": f"{r['V1_ret']:+.2f}%",
                "V2 Ret": f"{r['V2_FINAL_ret']:+.2f}%",
                "Δ Ret": f"{r['V2_FINAL_ret']-r['V1_ret']:+.2f}pp",
                "V1 MDD": f"{r['V1_mdd']:+.2f}%",
                "V2 MDD": f"{r['V2_FINAL_mdd']:+.2f}%",
                "Δ MDD": f"{r['V2_FINAL_mdd']-r['V1_mdd']:+.2f}pp",
                "SOXL Ret": f"{r['SOXL_ret']:+.2f}%",
                "SOXL MDD": f"{r['SOXL_mdd']:+.2f}%",
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
        yc4.metric("평균 ΔRet / ΔMDD", f"{avg_dret:+.2f}pp / {avg_dmdd:+.2f}pp",
                   "MDD는 양수=V2가 덜 떨어짐")

        st.markdown("### 📊 연도별 Δ MDD (V2 − V1, pp) — 양수 = V2가 덜 떨어짐")
        _ydiff_df = pd.DataFrame({
            "연도": yb["year"].astype(int).values,
            "Δ MDD pp": (yb["V2_FINAL_mdd"] - yb["V1_mdd"]).values,
        })
        st.altair_chart(
            alt.Chart(_ydiff_df).mark_bar().encode(
                x=alt.X("연도:O", title="연도"),
                y=alt.Y("Δ MDD pp:Q", title="Δ MDD (pp)"),
                color=alt.condition(
                    alt.datum["Δ MDD pp"] >= 0,
                    alt.value("#A3BE8C"), alt.value("#BF616A"),
                ),
                tooltip=[alt.Tooltip("연도:O"), alt.Tooltip("Δ MDD pp:Q", format="+.2f")],
            ).properties(height=240),
            use_container_width=True,
        )

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
                st.metric("V2_FINAL", f"{v2b['CAGR_p50']:.2f}%",
                          f"V1 {v1b['CAGR_p50']:.2f}%")
            with bbc2:
                st.markdown("**MDD p50**")
                st.metric("V2_FINAL", f"{v2b['MDD_p50']:.2f}%",
                          f"V1 {v1b['MDD_p50']:.2f}% · "
                          f"{v2b['MDD_p50']-v1b['MDD_p50']:+.2f}pp")
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
                    f"{v1b['P_MDD_lt_25']*100:.2f}%",
                    f"{v1b['P_MDD_lt_30']*100:.2f}%",
                    f"{v1b['P_MDD_lt_40']*100:.2f}%",
                    f"{v1b['P_Cal_gt_2_5']*100:.2f}%",
                    f"{v1b['P_Cal_gt_3']*100:.2f}%",
                    f"{v1b['Cal_p5']:.2f}",
                    f"{v1b['Cal_p95']:.2f}",
                    f"{v1b['MDD_p5']:.2f}%",
                ],
                "V2_FINAL": [
                    f"{v2b['P_MDD_lt_25']*100:.2f}%",
                    f"{v2b['P_MDD_lt_30']*100:.2f}%",
                    f"{v2b['P_MDD_lt_40']*100:.2f}%",
                    f"{v2b['P_Cal_gt_2_5']*100:.2f}%",
                    f"{v2b['P_Cal_gt_3']*100:.2f}%",
                    f"{v2b['Cal_p5']:.2f}",
                    f"{v2b['Cal_p95']:.2f}",
                    f"{v2b['MDD_p5']:.2f}%",
                ],
            })
            st.dataframe(tail_rows, use_container_width=True, hide_index=True)

            st.info(
                f"**진짜 운영 추정치 (bootstrap p50)**: "
                f"V2_FINAL Cal **{v2b['Cal_p50']:.2f}** / MDD **{v2b['MDD_p50']:.2f}%** "
                f"vs V1 Cal {v1b['Cal_p50']:.2f} / MDD {v1b['MDD_p50']:.2f}%. "
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
            disp["v1_ret"] = disp["v1_ret"].apply(lambda x: f"{x:+.2f}%")
            disp["v2_ret"] = disp["v2_ret"].apply(lambda x: f"{x:+.2f}%")
            disp["v1_mdd"] = disp["v1_mdd"].apply(lambda x: f"{x:+.2f}%")
            disp["v2_mdd"] = disp["v2_mdd"].apply(lambda x: f"{x:+.2f}%")
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
- **A4 VVIX 기준선 드리프트** — VVIX Q1→Q3 평균 88→108로 13년간 상승. 임계값 90이 시간에 따라 다른 의미. 향후 롤링 기준선 검토 필요.
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
<div style="background:#3B4252;border-left:4px solid #D08770;padding:12px 18px;border-radius:8px;margin-bottom:12px;color:#D8DEE9;line-height:1.8">
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
            def _load_eq_cmp(k):
                return pd.read_csv(CHAMP / "equity_curves.csv", parse_dates=["date"], index_col="date")

            @st.cache_data
            def _load_daily_cmp(k):
                return pd.read_csv(CHAMP / "daily.csv", parse_dates=["date"], index_col="date")

            @st.cache_data
            def _load_trades_cmp(k):
                t = pd.read_csv(CHAMP / "trades_champ.csv")
                t["date"] = pd.to_datetime(t["date"])
                return t

            _eq_bt_all = _load_eq_cmp(_mtime_cmp(CHAMP / "equity_curves.csv"))
            _daily_bt_all = _load_daily_cmp(_mtime_cmp(CHAMP / "daily.csv"))

            # ── Period overlap (겹치는 구간만 비교 — '가능한 날부터') ──
            _p_start = _paper_df.index[0]
            _p_end = _paper_df.index[-1]
            _bt_start = _eq_bt_all.index.min()
            _bt_end = _eq_bt_all.index.max()

            # 두 데이터셋의 교집합 구간
            _ov_start = max(_p_start, _bt_start)
            _ov_end = min(_p_end, _bt_end)

            _bt_eq = _eq_bt_all.loc[_ov_start:_ov_end, "CHAMP_NOMARGIN"].dropna() if _ov_start <= _ov_end else pd.Series(dtype=float)
            if len(_bt_eq) < 2:
                st.warning(
                    f"⚠️ **비교 가능한 겹침 구간이 없습니다.**\n\n"
                    f"- 백테 데이터: `{_bt_start.date()}` ~ **`{_bt_end.date()}`**\n"
                    f"- 페이퍼 데이터: `{_p_start.date()}` ~ `{_p_end.date()}`\n\n"
                    f"백테 자산곡선이 페이퍼 시작일(`{_p_start.date()}`)보다 이르게 끝났습니다. "
                    f"백테 자동 갱신이 밀린 것으로 보입니다 — `run_daily.py --include-v1`로 최신화하면 복구됩니다."
                )
                st.stop()

            # 겹침이 페이퍼 전체를 못 덮으면 안내 (가능한 구간만 비교 중)
            if _ov_start > _p_start or _ov_end < _p_end:
                st.info(
                    f"ℹ️ **겹치는 구간만 비교합니다:** `{_bt_eq.index[0].date()}` ~ `{_bt_eq.index[-1].date()}` "
                    f"(백테는 `{_bt_end.date()}`까지, 페이퍼는 `{_p_start.date()}`~`{_p_end.date()}`). "
                    f"백테가 최신화되면 자동으로 페이퍼 끝까지 비교됩니다."
                )

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
                f"비교 구간: {_bt_eq.index[0].strftime('%Y-%m-%d')} → {_bt_eq.index[-1].strftime('%Y-%m-%d')} "
                f"({_days}거래일 ≈ {_mo}개월) · 시작 자산: ${_pa_seed:,.0f}"
            )

            import altair as _alt
            _cmp_melt = pd.DataFrame({
                "날짜": list(_bt_eq.index) * 2,
                "자산": list(_bt_norm.values) + list(_pa_norm.values),
                "구분": ["📊 백테스트 (이론)"] * len(_bt_eq) + ["🤖 페이퍼 (실제)"] * len(_bt_eq),
            })
            st.altair_chart(
                _alt.Chart(_cmp_melt).mark_line(strokeWidth=2).encode(
                    x=_alt.X("날짜:T", title="날짜"),
                    y=_alt.Y("자산:Q", title="자산 ($)", axis=_alt.Axis(format="$,.0f")),
                    color=_alt.Color("구분:N", scale=_alt.Scale(
                        domain=["📊 백테스트 (이론)", "🤖 페이퍼 (실제)"],
                        range=["#4C566A", "#34A5C5"])),
                    tooltip=[_alt.Tooltip("날짜:T", title="날짜", format="%Y-%m-%d"),
                             _alt.Tooltip("구분:N", title="구분"),
                             _alt.Tooltip("자산:Q", title="자산", format="$,.0f")],
                ).properties(height=330),
                use_container_width=True,
            )
            if _p_start <= pd.Timestamp("2026-06-07"):
                st.warning(
                    "⚠️ **누락 구간**: 페이퍼 봇 시작일(2026-05-26) ~ EOD 레저 시작일(2026-06-08) "
                    "구간의 페이퍼 자산이 ledger에 없음. 위 차트는 6/8부터만 비교 가능. "
                    "이 기간 BT +21.6% vs 페이퍼 +5.2% 괴리는 stop-buy 거부(PR#12 이전) 추정."
                )

            # Gap chart
            _gap = _pa_norm - _bt_norm
            _gap_df = pd.DataFrame({"페이퍼 − 백테스트 ($)": _gap.values}, index=_bt_eq.index)
            _latest_gap = float(_gap.iloc[-1])
            st.caption(
                f"아래: 페이퍼 − 백테스트 괴리. 양수(+) = 실제가 앞섬, 음수(-) = 이론이 앞섬. "
                f"최근: **${_latest_gap:+,.0f}**"
            )
            import altair as _alt
            _gp_df = pd.DataFrame({"날짜": _bt_eq.index, "괴리": _gap.values})
            st.altair_chart(
                _alt.Chart(_gp_df).mark_bar().encode(
                    x=_alt.X("날짜:T", title="날짜"),
                    y=_alt.Y("괴리:Q", title="페이퍼 − 백테 ($)"),
                    color=_alt.condition(_alt.datum["괴리"] >= 0, _alt.value("#A3BE8C"), _alt.value("#BF616A")),
                    tooltip=[_alt.Tooltip("날짜:T", title="날짜", format="%Y-%m-%d"),
                             _alt.Tooltip("괴리:Q", title="페이퍼−백테", format="$+,.0f")],
                ).properties(height=160),
                use_container_width=True,
            )
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
                        _color = "#A3BE8C" if _d >= 0 and _k != "MDD (최대낙폭)" else "#BF616A"
                        if _k == "MDD (최대낙폭)": _color = "#A3BE8C" if _d >= 0 else "#BF616A"
                        st.markdown(f"`{_v:+.2f}%` <span style='color:{_color};font-size:0.85em'>{_d:+.2f}pp</span>",
                                    unsafe_allow_html=True)
                    elif isinstance(_vb, float) and not isinstance(_v, str):
                        _d = _v - _vb
                        _color = "#A3BE8C" if _d >= 0 else "#BF616A"
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
    st.subheader("📔 V1 매매일지 — 일별 레짐·비중 + 전체 거래 로그")
    st.caption("V1 백테스트의 일별 레짐 판정·VIX 기반 비중(k_today)·활성 엔진·거래를 보여주고, 맨 아래 '전체 거래 로그'에서 시드 환산·필터·CSV 다운로드까지 한 곳에서 처리합니다. 데이터는 백테스트 기준.")

    def _mtime_j2(p):
        try: return p.stat().st_mtime
        except Exception: return 0

    @st.cache_data
    def _load_daily_j2(k):
        return pd.read_csv(CHAMP / "daily.csv", parse_dates=["date"], index_col="date")

    @st.cache_data
    def _load_eq_j2(k):
        return pd.read_csv(CHAMP / "equity_curves.csv", parse_dates=["date"], index_col="date")

    @st.cache_data
    def _load_trades_j2(k):
        t = pd.read_csv(CHAMP / "trades_champ.csv")
        t["date"] = pd.to_datetime(t["date"])
        return t

    _daily_j = _load_daily_j2(_mtime_j2(CHAMP / "daily.csv"))
    _eq_j = _load_eq_j2(_mtime_j2(CHAMP / "equity_curves.csv"))
    _trades_j = _load_trades_j2(_mtime_j2(CHAMP / "trades_champ.csv"))

    # ── 기간 선택 ──
    _d_min = _daily_j.index[0].date()
    _d_max = _daily_j.index[-1].date()

    # 퀵 프리셋 버튼 — date_input 위젯 state도 같이 업데이트해야 반영됨
    _qc = st.columns(6)
    for _qi, (_ql, _qd) in enumerate([("20일", 20), ("1달", 30), ("2달", 60), ("3달", 90), ("6달", 180), ("전체", None)]):
        if _qc[_qi].button(_ql, use_container_width=True, key=f"j2q_{_ql}"):
            _qs = _d_max - pd.Timedelta(days=_qd) if _qd else _d_min
            st.session_state["j2_dpick_s"] = _qs
            st.session_state["j2_dpick_e"] = _d_max

    # 위기/이벤트 프리셋 (절대 구간 — 특정 사건으로 바로 점프)
    _qc2 = st.columns(5)
    _j2_crisis = [
        ("2020 코로나", "2020-01-02", "2020-06-30"),
        ("2022 폭락", "2022-01-01", "2022-12-31"),
        ("2024-08 쇼크", "2024-07-15", "2024-09-15"),
        ("2025 관세", "2025-03-01", "2025-05-15"),
        ("16년 전체", None, None),
    ]
    for _ci, (_cl, _cs, _ce) in enumerate(_j2_crisis):
        if _qc2[_ci].button(_cl, use_container_width=True, key=f"j2c_{_cl}"):
            st.session_state["j2_dpick_s"] = _d_min if _cs is None else max(_d_min, pd.Timestamp(_cs).date())
            st.session_state["j2_dpick_e"] = _d_max if _ce is None else min(_d_max, pd.Timestamp(_ce).date())

    _def_s = st.session_state.get("j2_dpick_s", _d_max - pd.Timedelta(days=30))
    _def_e = st.session_state.get("j2_dpick_e", _d_max)
    _dc1, _dc2 = st.columns(2)
    _j2_s = _dc1.date_input("시작일", value=_def_s, min_value=_d_min, max_value=_d_max, key="j2_dpick_s")
    _j2_e = _dc2.date_input("종료일", value=_def_e, min_value=_d_min, max_value=_d_max, key="j2_dpick_e")

    _daily_rec = _daily_j.loc[str(_j2_s):str(_j2_e)]
    if _daily_rec.empty:
        _daily_rec = _daily_j.tail(30)
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

    _period_label = f"{_j2_s.strftime('%Y-%m-%d')} ~ {_j2_e.strftime('%Y-%m-%d')} ({len(_daily_rec)}일)"
    st.markdown(f"### 📊 {_period_label} 요약")
    _h1, _h2, _h3, _h4 = st.columns(4)
    _h1.metric("레짐 — BULL 일수", f"{_n_bull}일", f"BEAR {_n_bear}일 / NEUTRAL {_n_neut}일")
    _h2.metric("평균 VIX", f"{_avg_vix:.1f}" if not pd.isna(_avg_vix) else "—",
               "20 = 중립 기준")
    _h3.metric("평균 k_today (비중)", f"{_avg_k:.3f}" if not pd.isna(_avg_k) else "—",
               "1.0 = 풀로딩 / 0.33 = 33%")
    _h4.metric("거래 발생일", f"{_trade_days}일",
               f"전체 {len(_daily_rec)}일 중")

    # ── 기간 성과 지표 ──
    _eq_p = _eq_rec.dropna()
    if len(_eq_p) >= 2:
        _tot_ret = _eq_p.iloc[-1] / _eq_p.iloc[0] - 1
        _n_yr = (_eq_p.index[-1] - _eq_p.index[0]).days / 365.25
        _cagr = ((_eq_p.iloc[-1] / _eq_p.iloc[0]) ** (1 / _n_yr) - 1) if _n_yr > 0.01 else _tot_ret
        _roll_max = _eq_p.expanding().max()
        _mdd = ((_eq_p - _roll_max) / _roll_max).min()
        _calmar = _cagr / abs(_mdd) if abs(_mdd) > 1e-9 else float("nan")
        _win_days = int((_eq_daily_ret.dropna() > 0).sum())
        _total_days_r = int(_eq_daily_ret.dropna().count())
        _win_rate = _win_days / _total_days_r if _total_days_r > 0 else float("nan")

        st.markdown("##### 📐 기간 성과")
        _p1, _p2, _p3, _p4, _p5 = st.columns(5)
        _p1.metric("총 수익률", f"{_tot_ret:+.2%}", f"{_n_yr:.1f}년 기간")
        _p2.metric("CAGR (연환산)", f"{_cagr:+.2%}", "연율화 수익률")
        _p3.metric("MDD", f"{_mdd:.2%}", "기간 내 최대 낙폭")
        _p4.metric("Calmar", f"{_calmar:.2f}" if not pd.isna(_calmar) else "—",
                   "CAGR ÷ |MDD|")
        _p5.metric("일간 승률", f"{_win_rate:.1%}" if not pd.isna(_win_rate) else "—",
                   f"{_win_days}/{_total_days_r}일")

    st.markdown("---")

    # ── 미니 자산 차트 ──
    if len(_eq_rec) >= 2:
        st.markdown("### 📈 기간 자산 추이")
        import altair as _alt
        _eq_j_df = pd.DataFrame({"날짜": _eq_rec.index, "자산": _eq_rec.values}).dropna()
        st.altair_chart(
            _alt.Chart(_eq_j_df).mark_line(color="#34A5C5", strokeWidth=2).encode(
                x=_alt.X("날짜:T", title="날짜"),
                y=_alt.Y("자산:Q", title="V1 자산 ($)", axis=_alt.Axis(format="$,.0f"),
                         scale=_alt.Scale(zero=False)),
                tooltip=[_alt.Tooltip("날짜:T", title="날짜", format="%Y-%m-%d"),
                         _alt.Tooltip("자산:Q", title="자산", format="$,.0f")],
            ).properties(height=200),
            use_container_width=True,
        )
        st.markdown("---")

    # ── 연도별 성과 (DS식: 막대 클릭 → 그 해 월별 막대차트) ──────────
    import altair as _alty
    _eq_full = (_eq_j["CHAMP_NOMARGIN"].dropna()
                if "CHAMP_NOMARGIN" in _eq_j.columns else pd.Series(dtype=float))
    if len(_eq_full) >= 30:
        st.markdown("### 📅 연도별 성과 — 막대를 클릭하면 그 해 월별 성과가 아래에 표시됩니다")

        # 연도별 수익률(연말 종가 기준, 첫 해는 데이터 시작값 대비) + 연중 MDD
        _yr_last = _eq_full.resample("YE").last()
        _yr_base = pd.concat([pd.Series([_eq_full.iloc[0]], index=[_eq_full.index[0]]), _yr_last])
        _yr_ret = _yr_base.pct_change().dropna() * 100

        def _year_mdd(s):
            return float((s / s.cummax() - 1).min() * 100)
        _yr_mdd = _eq_full.groupby(_eq_full.index.year).apply(_year_mdd)

        _yr_df = pd.DataFrame({
            "yr":  [int(d.year) for d in _yr_ret.index],
            "ret": _yr_ret.values,
        })
        _yr_df["mdd"] = [float(_yr_mdd.get(y, float("nan"))) for y in _yr_df["yr"]]

        _ysel = _alty.selection_point(fields=["yr"], name="ysel")
        _yr_chart = (
            _alty.Chart(_yr_df).mark_bar().encode(
                x=_alty.X("yr:O", title="연도"),
                y=_alty.Y("ret:Q", title="연 수익률 (%)"),
                color=_alty.condition("datum.ret >= 0",
                                      _alty.value("#A3BE8C"), _alty.value("#BF616A")),
                opacity=_alty.condition(_ysel, _alty.value(1.0), _alty.value(0.55)),
                tooltip=[_alty.Tooltip("yr:O", title="연도"),
                         _alty.Tooltip("ret:Q", title="수익률(%)", format="+.1f"),
                         _alty.Tooltip("mdd:Q", title="연중 MDD(%)", format=".1f")],
            ).add_params(_ysel).properties(height=300)
        )
        _yr_event = st.altair_chart(_yr_chart, use_container_width=True,
                                    on_select="rerun", key="j2_year_sel")

        # 선택 연도 추출 (클릭 없으면 최근 연도 기본 표시)
        _years_all = [int(v) for v in _yr_df["yr"].values]
        _sel_year = _years_all[-1] if _years_all else None
        try:
            _picked = _yr_event["selection"]["ysel"]
            if _picked:
                _sel_year = int(_picked[0]["yr"])
        except Exception:
            pass

        # 월별 수익률(월말 종가 기준, 1월은 전년 말 대비)
        _m_ret = _eq_full.resample("ME").last().pct_change() * 100
        _m_y = _m_ret[_m_ret.index.year == _sel_year].dropna()
        _mon_df = pd.DataFrame({
            "m":   [int(d.month) for d in _m_y.index],
            "ret": _m_y.values,
        })
        _mon_df["mlabel"] = _mon_df["m"].map(lambda x: f"{x}월")
        _mon_order = [f"{m}월" for m in range(1, 13)]

        st.markdown(f"#### 📊 {_sel_year}년 월별 성과")
        if len(_mon_df):
            _mon_chart = (
                _alty.Chart(_mon_df).mark_bar().encode(
                    x=_alty.X("mlabel:N", sort=_mon_order, title="월"),
                    y=_alty.Y("ret:Q", title="월 수익률 (%)"),
                    color=_alty.condition("datum.ret >= 0",
                                          _alty.value("#A3BE8C"), _alty.value("#BF616A")),
                    tooltip=[_alty.Tooltip("mlabel:N", title="월"),
                             _alty.Tooltip("ret:Q", title="수익률(%)", format="+.2f")],
                ).properties(height=280)
            )
            st.altair_chart(_mon_chart, use_container_width=True)
            _yr_row = _yr_df[_yr_df["yr"] == _sel_year]
            if len(_yr_row):
                _best = _mon_df.loc[_mon_df["ret"].idxmax()]
                _worst = _mon_df.loc[_mon_df["ret"].idxmin()]
                st.caption(
                    f"{_sel_year}년 — 연수익률 **{_yr_row['ret'].iloc[0]:+.1f}%** · "
                    f"연중 MDD {_yr_row['mdd'].iloc[0]:.1f}% · "
                    f"최고 {_best['mlabel']} {_best['ret']:+.1f}% · "
                    f"최저 {_worst['mlabel']} {_worst['ret']:+.1f}% · "
                    f"플러스 {(int((_mon_df['ret'] > 0).sum()))}/{len(_mon_df)}개월")
        else:
            st.info(f"{_sel_year}년 월별 데이터가 없습니다.")
        st.markdown("---")

    # ── 일별 현황 테이블 ──
    st.markdown("### 📋 일별 현황 (최신 날짜부터)")

    def _why_no_trade(drow, brief=True):
        """무거래 사유 추론 — 포지션 상태(현금비율)로 proximate reason 표기."""
        try:
            _eq = float(drow.get("CHAMP_equity", float("nan")))
            _csh = float(drow.get("CHAMP_cash", float("nan")))
        except Exception:
            _eq = _csh = float("nan")
        if pd.notna(_eq) and pd.notna(_csh) and _eq > 0:
            _inv = (_eq - _csh) / _eq
            if _inv < 0.02:
                return "현금 대기" if brief else "현금 100% 대기 — 당일 진입(변동성 돌파) 신호 미발생"
            elif _inv > 0.95:
                return "풀보유 유지" if brief else "포지션 풀보유 — 청산 신호(LOC/MOO) 미도달"
            else:
                return (f"{_inv*100:.0f}% 보유" if brief
                        else f"포지션 {_inv*100:.0f}% 보유 — 신규 진입/청산 신호 없음")
        return "신호 없음" if brief else "당일 진입/청산 신호 없음"

    # 기간 시작 대비 누적 수익률 (선택 기간 첫날=0%)
    _eq_nonan = _eq_rec.dropna()
    _eq_first = float(_eq_nonan.iloc[0]) if len(_eq_nonan) else None

    _rows = []
    for _date, _drow in _daily_rec.iloc[::-1].iterrows():
        _rg = _drow["regime"] if _has_rg else "—"
        _act = _drow["active_CHAMP"] if _has_act else "—"
        _vix = float(_drow["VIX"]) if _has_vix else float("nan")
        _k = float(_drow["k_today"]) if _has_k else float("nan")
        _date_norm = _date.normalize() if hasattr(_date, "normalize") else _date
        _dr = float(_eq_daily_ret.get(_date, float("nan")))
        _eqv = _eq_rec.get(_date, float("nan"))
        _cumret = (float(_eqv) / _eq_first - 1) * 100 if (_eq_first and pd.notna(_eqv)) else float("nan")

        if _date_norm in _by_date.index:
            _tr = _by_date.loc[_date_norm]
            _trade_str = f"✅ {int(_tr['건수'])}건 ({_tr['엔진']})"
            _pnl_str = f"${float(_tr['pnl']):+,.0f}"
        else:
            _trade_str = f"🚫 거래 없음 · {_why_no_trade(_drow)}"
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
            "누적 수익률": f"{_cumret:+.2f}%" if not pd.isna(_cumret) else "—",
            "거래": _trade_str,
            "거래 P&L": _pnl_str,
        })

    _view_df = pd.DataFrame(_rows)
    _date_order = list(_daily_rec.iloc[::-1].index)  # 테이블 행 순서와 동일 (최신→구)

    st.caption("💡 표에서 행을 클릭하거나, 아래 **드릴다운 날짜**에서 직접 골라 그 날짜 전후 캔들을 봅니다.")
    _sel_event = st.dataframe(
        _view_df, use_container_width=True, hide_index=True, height=520,
        on_select="rerun", selection_mode="single-row", key="j2_journal_table"
    )

    # ── 드릴다운 ──────────────────────────────────────────────
    # 날짜 선택은 selectbox(표준 위젯=신뢰성)를 주 수단으로. 표 행 클릭은 selectbox 값에
    # 동기화만 함(표 selection은 rerun에 불안정해서 단독으로 쓰지 않음).
    _date_opts = [d.strftime("%Y-%m-%d") for d in _date_order]   # 최신→구
    # 행 클릭은 '새 클릭'일 때만 selectbox에 반영. (key 있는 표는 _sel_rows가 매 rerun
    # 유지돼, 무조건 덮으면 selectbox로 날짜 바꿔도 행 날짜로 스냅백됨 → 안 바뀌는 버그)
    _sel_rows = _sel_event.selection.rows
    _cur_row = _sel_rows[0] if _sel_rows else None
    if (_cur_row is not None and _cur_row < len(_date_opts)
            and _cur_row != st.session_state.get("j2_last_row")):
        st.session_state["j2_sel_date_pick"] = _date_opts[_cur_row]
    st.session_state["j2_last_row"] = _cur_row
    if _date_opts and st.session_state.get("j2_sel_date_pick") not in _date_opts:
        st.session_state["j2_sel_date_pick"] = _date_opts[0]              # 기간 변경 시 첫(최신)일로

    _sel_date_str = None
    if _date_opts:
        _sel_date_str = st.selectbox("🔍 드릴다운 날짜 (드롭다운에서 직접 선택 · 표 행 클릭으로도 선택됨)",
                                     options=_date_opts, key="j2_sel_date_pick")

    if _sel_date_str and pd.Timestamp(_sel_date_str) in _daily_j.index:
        _sel_ts = pd.Timestamp(_sel_date_str)
        _sel_date = _sel_ts

        st.markdown("---")
        st.markdown(f"### 🔍 {_sel_date_str} 드릴다운 (±15 거래일)")

        # ±15 거래일 윈도우
        _all_j_dates = _daily_j.index
        _j_pos = _all_j_dates.searchsorted(_sel_ts)
        _W = 15
        _win = _daily_j.iloc[max(0, _j_pos - _W): min(len(_all_j_dates), _j_pos + _W + 1)].copy()

        # 선택 날짜 메타
        _sin = _sel_ts in _win.index
        _sel_ret  = float(_win.at[_sel_ts, "CHAMP_ret_%"])  if _sin and "CHAMP_ret_%"   in _win.columns else float("nan")
        _rg_sel   = _win.at[_sel_ts, "regime"]              if _sin and "regime"         in _win.columns else "—"
        _vix_sel  = float(_win.at[_sel_ts, "VIX"])          if _sin and "VIX"            in _win.columns else float("nan")
        _k_sel    = float(_win.at[_sel_ts, "k_today"])      if _sin and "k_today"        in _win.columns else float("nan")
        _act_sel  = _win.at[_sel_ts, "active_CHAMP"]        if _sin and "active_CHAMP"   in _win.columns else "—"

        _rg_emoji = {"BULL": "🟢", "NEUTRAL": "🟡", "BEAR": "🔴"}.get(_rg_sel, "")
        _ret_color = "#BF616A" if not pd.isna(_sel_ret) and _sel_ret < 0 else "#A3BE8C"

        st.markdown(f"""
<div style="background:#434C5E;border-left:4px solid {_ret_color};padding:12px 16px;border-radius:8px;margin-bottom:16px">
  <span style="color:#9AA5B8;font-size:0.85em">선택 날짜</span><br>
  <span style="color:#ECEFF4;font-size:1.25em;font-weight:700">{_sel_date_str}</span>
  &nbsp;&nbsp;<span style="color:{_ret_color};font-size:1.5em;font-weight:700">{f"{_sel_ret:+.2f}%" if not pd.isna(_sel_ret) else "—"}</span><br>
  <span style="color:#9AA5B8;font-size:0.88em">레짐: {_rg_emoji} {_rg_sel} &nbsp;·&nbsp; VIX: {f"{_vix_sel:.1f}" if not pd.isna(_vix_sel) else "—"} &nbsp;·&nbsp; k_today: {f"{_k_sel:.3f}" if not pd.isna(_k_sel) else "—"} &nbsp;·&nbsp; 엔진: {_act_sel}</span>
</div>
""", unsafe_allow_html=True)

        # 선택일 거래 유무 + 사유
        _sel_norm = _sel_ts.normalize()
        if _sel_norm in _by_date.index:
            _selt = _by_date.loc[_sel_norm]
            st.success(f"✅ **{_sel_date_str} — 거래 {int(_selt['건수'])}건** · {_selt['엔진']} · 당일 P&L ${float(_selt['pnl']):+,.0f}")
        else:
            _sel_drow_j = _daily_j.loc[_sel_ts] if _sel_ts in _daily_j.index else None
            _no_reason = _why_no_trade(_sel_drow_j, brief=False) if _sel_drow_j is not None else "데이터 없음"
            st.warning(f"🚫 **{_sel_date_str} — 거래 없음** · 사유: {_no_reason}")

        import altair as _alt_dd

        # ── 자산 패널 ──
        _eq_win = _eq_j.reindex(_win.index)["CHAMP_NOMARGIN"].dropna()
        _ret_win = _win.reindex(_eq_win.index)["CHAMP_ret_%"] if "CHAMP_ret_%" in _win.columns else pd.Series(dtype=float)
        _eq_df = pd.DataFrame({
            "날짜": _eq_win.index,
            "자산": _eq_win.values,
            "수익률": _ret_win.reindex(_eq_win.index).values,
        })
        _vline_src = pd.DataFrame({"날짜": [_sel_ts]})
        _vline = _alt_dd.Chart(_vline_src).mark_rule(color="#EBCB8B", strokeWidth=2, strokeDash=[6, 3]).encode(x="날짜:T")

        _eq_line = _alt_dd.Chart(_eq_df).mark_line(color="#34A5C5", strokeWidth=2).encode(
            x=_alt_dd.X("날짜:T", title=None, axis=_alt_dd.Axis(labels=False)),
            y=_alt_dd.Y("자산:Q", title="V1 자산 ($)", scale=_alt_dd.Scale(zero=False),
                        axis=_alt_dd.Axis(format="$,.0f")),
            tooltip=[_alt_dd.Tooltip("날짜:T", format="%Y-%m-%d"),
                     _alt_dd.Tooltip("자산:Q", title="자산", format="$,.0f"),
                     _alt_dd.Tooltip("수익률:Q", title="수익률", format="+.2f")],
        )
        _sel_eq_val = float(_eq_j.at[_sel_ts, "CHAMP_NOMARGIN"]) if _sel_ts in _eq_j.index else None
        if _sel_eq_val:
            _sel_dot = _alt_dd.Chart(pd.DataFrame({"날짜": [_sel_ts], "자산": [_sel_eq_val]})).mark_point(
                size=160, filled=True, color=_ret_color
            ).encode(x="날짜:T", y="자산:Q")
            _eq_line = _eq_line + _sel_dot
        _eq_panel = (_eq_line + _vline).properties(height=160, title="V1 자산 추이")

        # ── VIX 패널 ──
        _vix_src = _win.reset_index()[["date", "VIX"]].rename(columns={"date": "날짜"}).dropna(subset=["VIX"])
        _vix_panel = (_alt_dd.Chart(_vix_src).mark_line(color="#D08770", strokeWidth=1.5).encode(
            x=_alt_dd.X("날짜:T", title=None, axis=_alt_dd.Axis(labels=False)),
            y=_alt_dd.Y("VIX:Q", title="VIX", scale=_alt_dd.Scale(zero=False)),
            tooltip=[_alt_dd.Tooltip("날짜:T", format="%Y-%m-%d"), _alt_dd.Tooltip("VIX:Q", format=".1f")],
        ) + _vline).properties(height=100, title="VIX (공포지수)")

        # ── k_today 패널 ──
        _k_src = _win.reset_index()[["date", "k_today"]].rename(columns={"date": "날짜"}).dropna(subset=["k_today"])
        _k_panel = (_alt_dd.Chart(_k_src).mark_line(color="#B48EAD", strokeWidth=1.5).encode(
            x=_alt_dd.X("날짜:T", title="날짜"),
            y=_alt_dd.Y("k_today:Q", title="k_today", scale=_alt_dd.Scale(zero=False)),
            tooltip=[_alt_dd.Tooltip("날짜:T", format="%Y-%m-%d"), _alt_dd.Tooltip("k_today:Q", format=".3f")],
        ) + _vline).properties(height=100, title="k_today (배분 비중)")

        st.altair_chart(
            _alt_dd.vconcat(_eq_panel, _vix_panel, _k_panel).resolve_scale(x="shared"),
            use_container_width=True,
        )

        # ── SOXL 캔들 + 매매 시점 마커 (전후 거래일 선택 가능) ──
        # radio(클릭형)로 — 슬라이더보다 조작 확실, 한 번 클릭으로 창 변경
        st.session_state.setdefault("j2_soxl_win", 5)
        st.radio("🕯 SOXL 캔들 전후 거래일", options=[3, 5, 7, 10, 15],
                 horizontal=True, key="j2_soxl_win",
                 format_func=lambda x: f"±{x}일",
                 help="선택일 기준 앞뒤로 보여줄 거래일 수 (넓힐수록 추세 맥락↑)")
        _soxl_win = st.session_state["j2_soxl_win"]
        try:
            import yfinance as _yf
            @st.cache_data(ttl=3600)
            def _fetch_soxl_ohlc(ds, w):   # ★인자명 밑줄 금지: st.cache_data가 _접두 인자를 해시 제외 → 날짜·창 미구분 캐시버그
                _d = pd.Timestamp(ds)
                _s = (_d - pd.offsets.BDay(w + 1)).strftime("%Y-%m-%d")
                _e = (_d + pd.offsets.BDay(w + 1)).strftime("%Y-%m-%d")
                _df = _yf.download("SOXL", start=_s, end=_e, auto_adjust=True,
                                   progress=False, multi_level_index=False)
                if isinstance(_df.columns, pd.MultiIndex):
                    _df.columns = _df.columns.droplevel(1)
                return _df.reset_index()[["Date", "Open", "High", "Low", "Close"]]

            _soxl_raw = _fetch_soxl_ohlc(_sel_date_str, _soxl_win)
            if not _soxl_raw.empty:
                _soxl_df = _soxl_raw.copy()
                _soxl_df.columns = ["날짜", "시가", "고가", "저가", "종가"]
                for _pc in ["시가", "고가", "저가", "종가"]:   # 가격 소수 2자리로
                    _soxl_df[_pc] = _soxl_df[_pc].astype(float).round(2)
                _soxl_df["날짜_str"] = pd.to_datetime(_soxl_df["날짜"]).dt.strftime("%Y-%m-%d")
                _soxl_df["날짜_표시"] = pd.to_datetime(_soxl_df["날짜"]).dt.strftime("%m/%d")
                _close_map = dict(zip(_soxl_df["날짜_str"], _soxl_df["종가"].astype(float)))
                _open_map = dict(zip(_soxl_df["날짜_str"], _soxl_df["시가"].astype(float)))
                _x_domain = list(_soxl_df["날짜_표시"])

                # daily 컨텍스트
                def _dval(col, d_str):
                    _ts = pd.Timestamp(d_str)
                    return _win.at[_ts, col] if _ts in _win.index and col in _win.columns else None

                _soxl_df["V1수익률"] = _soxl_df["날짜_str"].apply(lambda d: _dval("CHAMP_ret_%", d))
                _soxl_df["레짐"]     = _soxl_df["날짜_str"].apply(lambda d: _dval("regime", d) or "—")
                _soxl_df["VIX"]      = _soxl_df["날짜_str"].apply(lambda d: _dval("VIX", d))
                _soxl_df["k값"]      = _soxl_df["날짜_str"].apply(lambda d: _dval("k_today", d))

                # SOXL 종가 라인 + 선택일 강조
                _x_enc = _alt_dd.X("날짜_표시:O", sort=_x_domain, title=None,
                                    axis=_alt_dd.Axis(labels=False, ticks=False))
                _x_enc_lbl = _alt_dd.X("날짜_표시:O", sort=_x_domain, title="날짜",
                                        axis=_alt_dd.Axis(labelAngle=0))
                _soxl_df["일중%"] = ((_soxl_df["종가"] / _soxl_df["시가"] - 1) * 100).round(2)
                _soxl_df["일중$"] = (_soxl_df["종가"] - _soxl_df["시가"]).round(2)
                _soxl_df["일중변동"] = _soxl_df.apply(
                    lambda _r: f"{'+' if _r['일중$'] >= 0 else '−'}${abs(_r['일중$']):,.2f} ({_r['일중%']:+.2f}%)",
                    axis=1)
                _y_scale = _alt_dd.Scale(zero=False, nice=True, padding=12)
                _y_enc = _alt_dd.Y("종가:Q", title="SOXL ($)", scale=_y_scale,
                                    axis=_alt_dd.Axis(format="$,.2f"))

                _soxl_tip = [
                    _alt_dd.Tooltip("날짜_str:N",  title="날짜"),
                    _alt_dd.Tooltip("시가:Q",       title="시가",        format="$,.2f"),
                    _alt_dd.Tooltip("고가:Q",       title="고가",        format="$,.2f"),
                    _alt_dd.Tooltip("저가:Q",       title="저가",        format="$,.2f"),
                    _alt_dd.Tooltip("종가:Q",       title="종가",        format="$,.2f"),
                    _alt_dd.Tooltip("일중변동:N",   title="일중 변동(시가→종가)"),
                    _alt_dd.Tooltip("V1수익률:Q",   title="V1 수익률(%)", format="+.2f"),
                    _alt_dd.Tooltip("레짐:N",       title="레짐"),
                    _alt_dd.Tooltip("VIX:Q",        title="VIX",         format=".1f"),
                    _alt_dd.Tooltip("k값:Q",        title="k_today",     format=".3f"),
                ]
                # 캔들스틱: 위크(저가-고가) + 바디(시가-종가), 양봉=초록·음봉=빨강
                _oc_color = _alt_dd.condition(
                    "datum.종가 >= datum.시가", _alt_dd.value("#A3BE8C"), _alt_dd.value("#BF616A"))
                # 거래일 수에 맞춰 캔들·hover 폭 적응 (적을수록 굵게)
                _n_cdl = max(len(_soxl_df), 1)
                _body_px = max(7, min(30, int(660 / _n_cdl * 0.42)))
                _hover_px = max(22, int(660 / _n_cdl * 0.96))
                _soxl_wick = _alt_dd.Chart(_soxl_df).mark_rule(strokeWidth=1.4).encode(
                    x=_x_enc,
                    y=_alt_dd.Y("저가:Q", title="SOXL ($)", scale=_y_scale, axis=_alt_dd.Axis(format="$,.2f")),
                    y2="고가:Q", color=_oc_color, tooltip=_soxl_tip)
                _soxl_body = _alt_dd.Chart(_soxl_df).mark_bar(size=_body_px).encode(
                    x=_x_enc, y=_alt_dd.Y("시가:Q", scale=_y_scale), y2="종가:Q",
                    color=_oc_color, tooltip=_soxl_tip)
                # 투명 hover 밴드: 거래일 컬럼 전체 높이를 덮어 '근처만 가도' OHLC 툴팁 표시
                _soxl_hover = _alt_dd.Chart(_soxl_df).mark_rule(
                    opacity=0, strokeWidth=_hover_px
                ).encode(x=_x_enc, tooltip=_soxl_tip)
                _soxl_line = _soxl_wick + _soxl_body   # (이름 유지) 캔들 = 위크+바디

                # 선택일 강조: 수직선 + 링 마커 + 종가 라벨
                _sel_soxl_row = _soxl_df[_soxl_df["날짜_str"] == _sel_date_str].copy()
                if not _sel_soxl_row.empty:
                    _sel_close = float(_sel_soxl_row["종가"].iloc[0])
                    _sel_soxl_row["종가라벨"] = _sel_soxl_row["종가"].apply(lambda v: f"${v:,.2f}")
                    _soxl_vrule = _alt_dd.Chart(_sel_soxl_row).mark_rule(
                        color="#EBCB8B", strokeWidth=1.5, strokeDash=[5, 3], opacity=0.7
                    ).encode(x=_x_enc)
                    _soxl_sel_dot = _alt_dd.Chart(_sel_soxl_row).mark_point(
                        size=240, color="#EBCB8B", filled=False, strokeWidth=3
                    ).encode(x=_x_enc, y=_y_enc, tooltip=_soxl_tip)
                    _soxl_sel_lbl = _alt_dd.Chart(_sel_soxl_row).mark_text(
                        dy=-16, color="#EBCB8B", fontWeight="bold", fontSize=12
                    ).encode(x=_x_enc, y=_y_enc, text="종가라벨:N")
                else:
                    _sel_close = None
                    _empty_dd = _alt_dd.Chart(pd.DataFrame()).mark_point()
                    _soxl_vrule = _soxl_sel_dot = _soxl_sel_lbl = _empty_dd

                # 매매 시점 마커 빌드
                _tw_soxl = _trades_j[
                    (_trades_j["date"].dt.normalize() >= pd.Timestamp(_soxl_df["날짜_str"].iloc[0])) &
                    (_trades_j["date"].dt.normalize() <= pd.Timestamp(_soxl_df["날짜_str"].iloc[-1]))
                ].copy()

                _buy_rows, _sell_rows = [], []
                for _, _tr in _tw_soxl.iterrows():
                    _td_str  = _tr["date"].strftime("%Y-%m-%d")
                    _td_disp = _tr["date"].strftime("%m/%d")
                    _cpx = _close_map.get(_td_str)
                    if _cpx is None:
                        continue
                    _is_buy  = _tr["action"] == "STOP_BUY"
                    _pnl_v   = float(_tr["pnl"]) if pd.notna(_tr["pnl"]) else 0.0
                    _px      = float(_tr["price"]) if pd.notna(_tr["price"]) else None
                    _qty     = float(_tr["qty"]) if pd.notna(_tr["qty"]) else None
                    _strat   = str(_tr["strategy"])
                    _leg     = str(_tr["leg"])
                    _tkr     = str(_tr["ticker"])
                    _act     = str(_tr["action"])
                    _strat_kor = {
                        "longbyungi":   "롱변기",
                        "yangbyungi":   "양변기-" + ("롱" if _leg == "LONG" else "숏"),
                        "goldenbyungi": "황금변기",
                    }.get(_strat, _strat)
                    _act_kor = {
                        "STOP_BUY": "▲ 진입",
                        "LOC_SELL": "▼ LOC 청산",
                        "MOO_SELL": "▼ MOO 청산",
                        "STOP":     "↩ 스탑 취소",
                    }.get(_act, _act)
                    if _is_buy:
                        # 진입: 시가 대비 돌파%(=얼마 올라서 진입했나). SOXL 레그만(시가 데이터 보유)
                        _open_px = _open_map.get(_td_str)
                        _brk = ((_px / _open_px - 1) * 100) if (_px and _open_px and _tkr == "SOXL") else None
                        _detail = f"{_strat_kor} 진입 {_tkr} ${_px:,.2f}" if _px else f"{_strat_kor} 진입 {_tkr}"
                        if _brk is not None:
                            _detail += f" — 시가 ${_open_px:,.2f}에서 +{_brk:.2f}% 돌파 진입"
                        _lblval = f"+{_brk:.1f}%" if _brk is not None else "진입"
                    else:
                        # 청산: 평단(보유 평균단가, pnl/qty로 leg-aware 역산) → 청산가, 실현 수익률, 손익$
                        _ret = None; _avg = None
                        if _px and _qty:
                            _pps = _pnl_v / _qty   # 주당 실현손익
                            _avg = (_px + _pps) if _leg == "SHORT" else (_px - _pps)   # 평단
                            if _avg:
                                _ret = (_pps / _avg) * 100
                        if _px and _avg is not None:
                            _detail = (f"{_strat_kor} {_act_kor} {_tkr} · 평단 ${_avg:,.2f} → 청산 ${_px:,.2f}"
                                       f" · 손익 ${_pnl_v:+,.0f}")
                        elif _px:
                            _detail = f"{_strat_kor} {_act_kor} {_tkr} 청산 ${_px:,.2f} · 손익 ${_pnl_v:+,.0f}"
                        else:
                            _detail = f"{_strat_kor} {_act_kor} {_tkr} · 손익 ${_pnl_v:+,.0f}"
                        if _ret is not None:
                            _detail += f" (수익률 {_ret:+.2f}%)"
                        _lblval = f"{_ret:+.1f}%" if _ret is not None else f"${_pnl_v:+,.0f}"
                    _row = {
                        "날짜_표시": _td_disp, "날짜_str": _td_str, "종가": _cpx,
                        "엔진": _strat_kor, "종목": _tkr, "액션": _act_kor,
                        "상세": _detail, "라벨값": _lblval, "손익v": _pnl_v,
                    }
                    (_buy_rows if _is_buy else _sell_rows).append(_row)

                # 가격 패널 (캔들 + 선택일 강조 + 투명 hover 밴드 최상단으로 근처 호버 캐치)
                _price_panel = _alt_dd.layer(
                    _soxl_vrule, _soxl_line, _soxl_sel_dot, _soxl_sel_lbl, _soxl_hover
                ).properties(height=220)

                # 매매 마커: (날짜, 진입/청산)별 집계 → 2-레인 스트립 (같은 날 진입·청산이 겹치지 않음)
                _LANES = ["▲ 진입", "▼ 청산"]
                _strip_rows = []
                for _grp, _lane in [(_buy_rows, "▲ 진입"), (_sell_rows, "▼ 청산")]:
                    _bd = {}
                    for _r in _grp:
                        _bd.setdefault(_r["날짜_표시"], []).append(_r)
                    for _disp, _lst in _bd.items():
                        _det = "  /  ".join(x["상세"] for x in _lst)
                        if len(_lst) == 1:
                            _lbl = _lst[0]["라벨값"]
                        elif _lane == "▼ 청산":
                            _lbl = f"{len(_lst)}건 ${sum(x['손익v'] for x in _lst):+,.0f}"
                        else:
                            _lbl = f"{len(_lst)}건"
                        _strip_rows.append({
                            "날짜_표시": _disp, "날짜_str": _lst[0]["날짜_str"], "구분": _lane,
                            "건수": len(_lst), "라벨": _lbl, "내역": _det,
                        })

                _sel_close_txt = f" · 선택일 종가 **${_sel_close:,.2f}**" if _sel_close is not None else ""
                _yr_rng = f"{_soxl_df['날짜_str'].iloc[0]} ~ {_soxl_df['날짜_str'].iloc[-1]}"
                st.markdown(f"**🕯 SOXL 캔들 · {_yr_rng}** (전후 {_soxl_win}거래일){_sel_close_txt}")
                st.caption("x축은 월/일 표기, 정확한 연·월·일은 위 범위·호버 툴팁에서 확인 · 양봉🟢/음봉🔴 — 컬럼 근처만 가도 OHLC·일중변동 툴팁 · 아래 스트립 = 🟢▲ 진입(시가 대비 +돌파%) · 🔴▼ 청산(실현 수익률). 전후 일수는 위 슬라이더로 조절")

                if _strip_rows:
                    _strip_df = pd.DataFrame(_strip_rows)
                    _strip_y = _alt_dd.Y("구분:N", sort=_LANES, title=None,
                                          scale=_alt_dd.Scale(domain=_LANES),
                                          axis=_alt_dd.Axis(labelFontSize=12, labelLimit=80))
                    _strip_layers = []
                    if not _sel_soxl_row.empty:
                        _strip_layers.append(_alt_dd.Chart(_sel_soxl_row).mark_rule(
                            color="#EBCB8B", strokeWidth=1.5, strokeDash=[5, 3], opacity=0.7
                        ).encode(x=_x_enc_lbl))
                    _strip_layers.append(_alt_dd.Chart(_strip_df).mark_point(
                        size=220, filled=True, stroke="white", strokeWidth=0.8
                    ).encode(
                        x=_x_enc_lbl, y=_strip_y,
                        shape=_alt_dd.Shape("구분:N", scale=_alt_dd.Scale(
                            domain=_LANES, range=["triangle-up", "triangle-down"]), legend=None),
                        color=_alt_dd.Color("구분:N", scale=_alt_dd.Scale(
                            domain=_LANES, range=["#A3BE8C", "#BF616A"]), legend=None),
                        tooltip=[
                            _alt_dd.Tooltip("날짜_str:N", title="날짜"),
                            _alt_dd.Tooltip("구분:N", title="구분"),
                            _alt_dd.Tooltip("건수:Q", title="건수"),
                            _alt_dd.Tooltip("내역:N", title="상세"),
                        ],
                    ))
                    _strip_layers.append(_alt_dd.Chart(_strip_df).mark_text(
                        dy=-13, color="#E5E9F0", fontSize=10, fontWeight="bold"
                    ).encode(x=_x_enc_lbl, y=_strip_y, text="라벨:N"))
                    _strip_panel = _alt_dd.layer(*_strip_layers).properties(height=88)
                    _final_chart = _alt_dd.vconcat(_price_panel, _strip_panel).resolve_scale(x="shared")
                else:
                    _final_chart = _price_panel.properties(height=230)

                st.altair_chart(_final_chart, use_container_width=True)
        except Exception as _e_soxl:
            st.caption(f"SOXL 차트 로딩 실패: {_e_soxl}")

        # ── 거래 내역 ──
        _trades_win = _trades_j[
            (_trades_j["date"].dt.normalize() >= _win.index[0]) &
            (_trades_j["date"].dt.normalize() <= _win.index[-1])
        ].copy()
        if not _trades_win.empty:
            st.markdown("**📋 해당 기간 거래 내역**")
            _tw = _trades_win[["date", "strategy", "leg", "ticker", "action", "qty", "price", "pnl"]].copy()
            _tw["date"] = _tw["date"].dt.strftime("%Y-%m-%d")
            _tw["엔진"] = _tw.apply(lambda r: {
                "longbyungi": "롱변기", "goldenbyungi": "황금변기",
                "yangbyungi": "양변기-" + ("롱" if r["leg"] == "LONG" else "숏"),
            }.get(r["strategy"], r["strategy"]), axis=1)
            _tw["액션"] = _tw["action"].map({
                "STOP_BUY": "▲ 진입", "LOC_SELL": "▼ LOC 청산",
                "MOO_SELL": "▼ MOO 청산", "STOP": "↩ 취소",
            }).fillna(_tw["action"])
            _tw["price"] = _tw["price"].apply(lambda x: f"${float(x):,.2f}" if pd.notna(x) else "—")
            _tw["pnl"]   = _tw["pnl"].apply(lambda x: f"${float(x):+,.0f}" if pd.notna(x) else "—")
            _tw["qty"]   = _tw["qty"].apply(lambda x: f"{float(x):,.2f}" if pd.notna(x) else "—")
            _tw = _tw[["date", "엔진", "ticker", "액션", "qty", "price", "pnl"]]
            _tw.columns  = ["날짜", "엔진", "종목", "액션", "수량", "가격", "손익"]
            st.dataframe(_tw, use_container_width=True, hide_index=True)
        else:
            st.info("해당 기간 내 거래 없음.")

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
- **k_today** — 오늘 투자 비중. `0.60 × clip(20/VIX, 0.5, 2.0)`. VIX 20→0.60, VIX 10→1.0(풀로딩), VIX 40→0.30(축소)
- **일간 변동** — V1 포트폴리오 당일 수익률 (백테스트 기준)
- **거래** — 당일 매매 이벤트 수 및 사용한 엔진
- **거래 P&L** — 당일 실현·미실현 손익 합계 (백테스트 기준)
""")

    # ═══════════════════════════════════════════════════════════
    # 📒 전체 거래 로그 (구 '거래 내역' 탭 흡수) — 시드 환산·필터·CSV
    # ═══════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("### 📒 전체 거래 로그 (선택 기간)")
    st.caption("위에서 고른 기간의 모든 개별 거래를 한 줄씩. 시작 자본을 넣으면 모든 $ 값이 비례 환산됩니다 (% 수익률은 불변).")

    # ── 시작 자본 ──
    _sc1, _sc2 = st.columns([1, 3])
    _user_seed_j = _sc1.number_input(
        "시작 자본 ($)", min_value=100, max_value=10_000_000,
        value=10_000, step=1_000, key="j2_user_seed",
        help="백테는 $100K 시드로 실행. 이 값으로 모든 $ 결과를 비례 스케일링합니다. % 수익률은 변하지 않음."
    )
    _sc2.markdown(
        f"<div style='padding-top:1.7em;color:#888'>💡 모든 $ 값이 <b>${_user_seed_j:,.0f}</b> 시드 기준으로 환산됩니다. % 수익률은 동일.</div>",
        unsafe_allow_html=True,
    )

    # ── 기간 자산 → 시드 환산 (period-rebase) ──
    _eqp = _eq_j.loc[str(_j2_s):str(_j2_e)]
    if len(_eqp) >= 2 and "CHAMP_NOMARGIN" in _eqp.columns:
        _champ0 = float(_eqp["CHAMP_NOMARGIN"].iloc[0]); _champ1 = float(_eqp["CHAMP_NOMARGIN"].iloc[-1])
        _scale_champ = _user_seed_j / _champ0 if _champ0 else _user_seed_j / 100_000.0
        _champ_final = _champ1 * _scale_champ
        _sm1, _sm2 = st.columns(2)
        _sm1.metric("V1 최종 자산", f"${_champ_final:,.0f}", f"{(_champ1/_champ0 - 1)*100:+,.2f}%")
        _sm2.metric("기간 수익률", f"{(_champ1/_champ0 - 1)*100:+,.2f}%",
                    f"{_j2_s} ~ {_j2_e}")
    else:
        _scale_champ = _user_seed_j / 100_000.0

    # ── 거래 로그 필터 ──
    _strat_map = {"longbyungi": "롱변기", "yangbyungi": "양변기", "goldenbyungi": "황금변기"}
    _act_map = {"STOP_BUY": "▲ 진입", "LOC_SELL": "▼ LOC청산", "MOO_SELL": "▼ MOO청산", "STOP": "↩ 취소"}

    _tl = _trades_j[(_trades_j["date"] >= pd.Timestamp(_j2_s)) & (_trades_j["date"] <= pd.Timestamp(_j2_e))].copy()
    _f1, _f2, _f3 = st.columns([2, 1, 1])
    _strat_opts = sorted(_tl["strategy"].unique())
    _strat_pick = _f1.multiselect("엔진", options=_strat_opts, default=_strat_opts,
                                  format_func=lambda s: _strat_map.get(s, s), key="j2_log_strat")
    _act_opts = sorted(_tl["action"].unique())
    _act_pick = _f2.multiselect("액션", options=_act_opts, default=_act_opts,
                                format_func=lambda a: _act_map.get(a, a), key="j2_log_act")
    _pnl_pick = _f3.radio("손익", options=["전체", "수익만", "손실만"], horizontal=True, key="j2_log_pnl")

    _tl = _tl[_tl["strategy"].isin(_strat_pick) & _tl["action"].isin(_act_pick)]
    if _pnl_pick == "수익만":
        _tl = _tl[_tl["pnl"] > 0]
    elif _pnl_pick == "손실만":
        _tl = _tl[_tl["pnl"] < 0]

    _tl = _tl.copy()
    _tl["pnl_s"] = _tl["pnl"] * _scale_champ
    _tl["qty_s"] = (_tl["qty"] * _scale_champ).round().astype("int64")

    # ── 로그 헤드라인 ──
    _lm1, _lm2, _lm3, _lm4 = st.columns(4)
    _lm1.metric("거래 이벤트", f"{len(_tl):,}건")
    _realized = float(_tl["pnl_s"].sum())
    _lm2.metric("실현 손익 (시드 환산)", f"${_realized:+,.0f}")
    _nz = _tl[_tl["pnl_s"] != 0]
    _wr = (_nz["pnl_s"] > 0).mean() * 100 if len(_nz) else float("nan")
    _lm3.metric("승률 (손익≠0)", f"{_wr:.1f}%" if not pd.isna(_wr) else "—")
    _lm4.metric("기간", f"{_tl['date'].min().date()} → {_tl['date'].max().date()}" if len(_tl) else "—")

    # ── 페이지네이션 + 표시 ──
    _rpp = 100
    _ntot = len(_tl)
    _npg = max(1, (_ntot + _rpp - 1) // _rpp)
    _pg = st.number_input(f"페이지 (총 {_ntot:,}건, {_npg}p)", min_value=1, max_value=_npg,
                          value=1, key="j2_log_page") if _npg > 1 else 1
    _s0 = (_pg - 1) * _rpp
    _disp = _tl.iloc[_s0:_s0 + _rpp].copy()
    if len(_disp):
        _disp["날짜"] = _disp["date"].dt.strftime("%Y-%m-%d")
        _disp["엔진"] = _disp["strategy"].map(lambda s: _strat_map.get(s, s))
        _disp["액션"] = _disp["action"].map(lambda a: _act_map.get(a, a))
        _disp["체결가"] = _disp["price"].apply(lambda x: f"${x:.4f}")
        _disp["수량(환산)"] = _disp["qty_s"].apply(lambda x: f"{x:,}")
        _disp["손익(환산)"] = _disp["pnl_s"].apply(lambda x: f"${x:+,.2f}")
        _cols = ["날짜", "엔진", "leg", "ticker", "액션", "수량(환산)", "체결가", "손익(환산)", "side"]
        _disp = _disp[_cols].rename(columns={"leg": "방향", "ticker": "종목", "side": "Side"})
        st.dataframe(_disp, use_container_width=True, hide_index=True, height=420)
    else:
        st.info("선택한 필터/기간에 해당하는 거래가 없습니다.")

    # ── CSV ──
    if st.button(f"💾 CSV 준비 ({_ntot:,}건)", key="j2_log_dl_prep"):
        st.session_state["j2_log_csv"] = _tl.drop(columns=["pnl_s", "qty_s"]).to_csv(index=False).encode("utf-8-sig")
    if "j2_log_csv" in st.session_state:
        st.download_button("⬇️ 거래 로그 CSV", data=st.session_state["j2_log_csv"],
            file_name=f"v1_trades_{_j2_s}_{_j2_e}.csv", mime="text/csv", key="j2_log_dl")


# ───────────────────────────────────────────────────────────
# 데이터 정확성 탭
# ───────────────────────────────────────────────────────────
elif page == "🔍 데이터 정확성":
    import altair as _altd
    st.subheader("🔍 데이터 정확성 — 백테가 쓰는 가격 데이터를 독립 3소스로 교차검증")
    st.caption("검증일: 2026-06-21 (HST) · 대상: V1 '떨사오팔' 백테가 사용하는 SOXL·VIX 가격 데이터")

    # ── 한 줄 결론 배너 ──
    st.markdown("""
<div style="background:#3B4252;border-left:4px solid #A3BE8C;padding:16px 22px;border-radius:8px;margin-bottom:18px;color:#D8DEE9;line-height:1.85">
<b style="color:#A3BE8C">✅ 한 줄 결론</b><br>
V1 백테가 쓰는 가격 데이터는 <b>완전히 독립된 3개 소스</b> — yfinance(캐논)·Stooq(독립 벤더)·<b>IBKR(실제 브로커)</b> —
에서 <b>16년치 일일 수익률 쌍별 상관 ≥ 0.9977</b>, 사건일 변동률은 <b>3bp 이내</b>로 일치합니다.
VIX 핵심 값은 공개기록(역대최고 82.69)과 <b>정확히 0.00 차이</b>.
</div>
""", unsafe_allow_html=True)

    st.info("📌 **스코프**: 이 탭은 **입력(가격) 데이터의 정확성**만 검증합니다. 전략 *결과/수익률*의 타당성은 별도(15-섹션 기관급 검증·12-모듈 종합검증)에서 다룹니다.", icon="ℹ️")

    # ── 핵심 지표 4카드 ──
    _da1, _da2, _da3, _da4 = st.columns(4)
    _da1.metric("일일수익률 최저 상관", "0.9977", "3소스 쌍별 (16년)")
    _da2.metric("사건일 최대 편차", "≤ 3 bp", "코로나·관세충격 포함")
    _da3.metric("VIX 공개기록 차이", "0.00", "역대최고 82.69 등")
    _da4.metric("무결성 결함", "0건", "5개 티커 전수 스캔")

    st.markdown("---")

    # ── 1. 독립 소스 3종 ──
    st.markdown("### 1️⃣ 독립 소스 3종 인벤토리")
    st.caption("성격이 다른 3개 소스 — 데이터 벤더 2종(yfinance·Stooq) + 실제 브로커 체결 피드(IBKR). 모두 과거 시세 읽기 전용.")
    _src_df = pd.DataFrame([
        {"소스": "yfinance", "성격": "우리 캐논 백테 소스 (라이브 재다운로드)", "거래일": "4,094", "기간": "2010-03 ~ 2026-06", "조정": "분할만 (배당 미반영)"},
        {"소스": "Stooq", "성격": "완전 독립 데이터 벤더 (저장본)", "거래일": "4,035", "기간": "2010-03 ~ 2026-03", "조정": "분할+배당"},
        {"소스": "IBKR", "성격": "실제 브로커 체결 피드 (TWS API, TRADES, RTH)", "거래일": "4,094", "기간": "2010-03 ~ 2026-06", "조정": "분할만"},
    ])
    st.dataframe(_src_df, use_container_width=True, hide_index=True)
    st.caption("Alpaca도 시도했으나 데이터 API 자격증명 401로 제외. IBKR(실거래 브로커)가 들어와 목적 달성.")

    st.markdown("---")

    # ── 2. 상관 행렬 + 수익률 비교 이유 ──
    st.markdown("### 2️⃣ 일일수익률 상관 행렬 (3종 교차)")
    st.markdown("""
<div style="background:#434C5E;padding:12px 16px;border-radius:8px;margin-bottom:12px;color:#E5E9F0;font-size:0.92em;line-height:1.7">
💡 <b>왜 절대가가 아닌 '수익률'로 비교하나?</b><br>
yfinance Close는 분할만 조정(배당 미반영), Stooq는 분할+배당 조정 → <b>절대 가격은 누적배당만큼 배수 차이</b>가 납니다.
하지만 <b>일일 수익률</b>은 조정 기준과 무관하게 불변이라, 두 소스가 같은 원본인지 가리는 가장 공정한 잣대입니다. (1bp = 0.01%)
</div>
""", unsafe_allow_html=True)

    _corr_df = pd.DataFrame({
        "": ["yfinance", "Stooq", "IBKR"],
        "yfinance": [1.000000, 0.999830, 0.997912],
        "Stooq": [0.999830, 1.000000, 0.997658],
        "IBKR": [0.997912, 0.997658, 1.000000],
    })
    st.dataframe(
        _corr_df.style.format({"yfinance": "{:.6f}", "Stooq": "{:.6f}", "IBKR": "{:.6f}"})
        .background_gradient(cmap="Greens", vmin=0.997, vmax=1.0, subset=["yfinance", "Stooq", "IBKR"]),
        use_container_width=True, hide_index=True,
    )

    st.markdown("**yfinance(우리 소스) 대비 상세**")
    _vs_df = pd.DataFrame([
        {"소스": "Stooq", "공통 거래일": "4,034", "상관": "0.999830", "평균 절대차": "0.85 bp", "최대 절대차": "468 bp ¹"},
        {"소스": "IBKR", "공통 거래일": "4,093", "상관": "0.997912", "평균 절대차": "17.7 bp ²", "최대 절대차": "246 bp"},
    ])
    st.dataframe(_vs_df, use_container_width=True, hide_index=True)
    st.caption("¹ Stooq 최대차 1건(2016-12-20)은 연말 분배금(배당) 조정일 — 데이터 오류 아님.  ²  IBKR 평균차 원인은 아래 3️⃣에서 정직하게 해명.")

    st.markdown("---")

    # ── 3. IBKR 연도별 수렴 (핵심 정직 포인트) ──
    st.markdown("### 3️⃣ IBKR 평균차 17.7bp의 정직한 해명 — 연도별 수렴")
    st.markdown("""
<div style="background:#3B4252;border-left:4px solid #D08770;padding:14px 20px;border-radius:8px;margin-bottom:14px;color:#D8DEE9;line-height:1.8">
<b style="color:#EBCB8B">★ 핵심</b> — IBKR(브로커)의 평균차가 Stooq(0.85bp)보다 큰데, 연도별로 쪼개면
<b>SOXL 초기 저유동성 시절에만 몰려 있고 실거래 시대에는 0으로 수렴</b>합니다.
원인은 브로커 <b>RTH 마지막 체결가</b> vs yfinance <b>공식 통합 종가</b>의 정의 차이 — 오류가 아니라 종가 정의의 미세 노이즈입니다.
</div>
""", unsafe_allow_html=True)

    _yearly = [
        {"year": 2010, "mean_bp": 60.5}, {"year": 2011, "mean_bp": 51.5}, {"year": 2012, "mean_bp": 69.5},
        {"year": 2013, "mean_bp": 46.9}, {"year": 2014, "mean_bp": 20.4}, {"year": 2015, "mean_bp": 17.5},
        {"year": 2016, "mean_bp": 16.8}, {"year": 2017, "mean_bp": 5.7}, {"year": 2018, "mean_bp": 3.4},
        {"year": 2019, "mean_bp": 3.4}, {"year": 2020, "mean_bp": 2.8}, {"year": 2021, "mean_bp": 0.1},
        {"year": 2022, "mean_bp": 0.0}, {"year": 2023, "mean_bp": 0.0}, {"year": 2024, "mean_bp": 0.0},
        {"year": 2025, "mean_bp": 0.0}, {"year": 2026, "mean_bp": 0.0},
    ]
    _yr_df = pd.DataFrame(_yearly)
    _yr_df["구간"] = _yr_df["year"].apply(lambda y: "2021+ 실거래 시대" if y >= 2021 else ("2014~2020 성숙기" if y >= 2014 else "2010~2013 저유동성"))
    _bars = _altd.Chart(_yr_df).mark_bar().encode(
        x=_altd.X("year:O", title="연도", axis=_altd.Axis(labelAngle=0)),
        y=_altd.Y("mean_bp:Q", title="IBKR vs yfinance 평균 수익률차 (bp)"),
        color=_altd.Color("구간:N", scale=_altd.Scale(
            domain=["2010~2013 저유동성", "2014~2020 성숙기", "2021+ 실거래 시대"],
            range=["#BF616A", "#D08770", "#A3BE8C"]), legend=_altd.Legend(title="시기", orient="top")),
        tooltip=[_altd.Tooltip("year:O", title="연도"), _altd.Tooltip("mean_bp:Q", title="평균차(bp)", format=".1f"),
                 _altd.Tooltip("구간:N", title="구간")],
    ).properties(height=300)
    st.altair_chart(_bars, use_container_width=True)

    _decay_df = pd.DataFrame([
        {"구간": "2010~2013 (주가 $0.4~0.6, 거래량 희박)", "평균 절대차": "47~70 bp", "최대차": "246 bp", "상관": "—", "성격": "페니 틱 노이즈"},
        {"구간": "2014~2020 (성숙기)", "평균 절대차": "3~20 bp", "최대차": "76 bp", "상관": "0.99993", "성격": "미세 노이즈"},
        {"구간": "2021~2026 (실거래 시대)", "평균 절대차": "0.0 bp", "최대차": "17 bp", "상관": "0.999998", "성격": "완전 일치"},
    ])
    st.dataframe(_decay_df, use_container_width=True, hide_index=True)
    st.success("⭐ 최대 괴리 상위 5일이 전부 2011~2012년(주가 $0.38~0.47)이고 방향이 양쪽으로 갈립니다(+17.10 vs +14.63, −2.25 vs +0.00). **편향이 아니라 노이즈**라는 증거이고, 분할 오정렬이면 50%+ 거대 점프가 떠야 하지만 최대 246bp뿐입니다. **실제 봇이 거래하는 2021년 이후 구간은 세 소스가 픽셀 단위로 동일.**")

    st.markdown("---")

    # ── 4. 사건일 정합성 ──
    st.markdown("### 4️⃣ 사건일 정합성 — 가장 흔들린 날에 3소스가 일치")
    _evt_df = pd.DataFrame([
        {"날짜": "2020-03-16", "사건": "코로나 패닉 (VIX 82.69)", "yfinance": "−38.59%", "Stooq": "−38.60%", "IBKR": "−38.57%"},
        {"날짜": "2022-11-10", "사건": "CPI 서프라이즈 랠리", "yfinance": "+30.74%", "Stooq": "+30.74%", "IBKR": "+30.74%"},
        {"날짜": "2024-08-05", "사건": "엔캐리 청산 급락", "yfinance": "−4.94%", "Stooq": "−4.94%", "IBKR": "−4.94%"},
        {"날짜": "2025-04-09", "사건": "관세 충격 반등", "yfinance": "+54.79%", "Stooq": "+54.79%", "IBKR": "+54.79%"},
    ])
    st.dataframe(_evt_df, use_container_width=True, hide_index=True)
    st.caption("→ 가장 변동성 큰 날에 세 독립 소스가 3bp 이내로 일치. 같은 원본임을 가장 강하게 보여주는 표.")

    st.markdown("---")

    # ── 5. VIX 공개기록 앵커 ──
    st.markdown("### 5️⃣ VIX — 공개기록 앵커 (인덱스라 분할/배당 조정 없음 → 절대값 직접 비교)")
    _vix_df = pd.DataFrame([
        {"날짜": "2020-03-16", "우리 데이터": "82.69", "공개기록": "82.69 (역대 최고 종가)", "차이": "0.00"},
        {"날짜": "2024-08-05", "우리 데이터": "38.57", "공개기록": "38.57", "차이": "0.00"},
        {"날짜": "2018-02-05", "우리 데이터": "37.32", "공개기록": "37.32 (Volmageddon)", "차이": "0.00"},
    ])
    st.dataframe(_vix_df, use_container_width=True, hide_index=True)
    st.caption("재현성: 캐시 vs 신선 yfinance VIX 종가 max 상대차 0.0000% (4,320일).")

    st.markdown("---")

    # ── 6. 재현성 & 무결성 ──
    st.markdown("### 6️⃣ 재현성 & 무결성")
    _rc1, _rc2 = st.columns(2)
    with _rc1:
        st.markdown("**재현성** — 백테 캐시 vs 오늘 신선 yfinance")
        st.dataframe(pd.DataFrame([
            {"검사": "SOXL OHLC 최대 상대차", "결과": "0.0000%"},
            {"검사": ">0.1% 차이 난 날", "결과": "0일 / 4,076일"},
            {"검사": "VIX 종가 최대 상대차", "결과": "0.0000%"},
        ]), use_container_width=True, hide_index=True)
    with _rc2:
        st.markdown("**무결성** — D1 전수 스캔 (5개 티커)")
        st.dataframe(pd.DataFrame([
            {"검사": "NaN / ≤0 가격 / High<Low / Close∉[L,H]", "결과": "0 / 0 / 0 / 0"},
            {"검사": "중복·역순 날짜 / 미조정 분할 점프", "결과": "0 / 0"},
            {"검사": "총 이슈", "결과": "0건"},
        ]), use_container_width=True, hide_index=True)
    st.caption("티커: SOXL·SOXS·QQQ·VIX·VIX9D (2026-06-20 D1 모듈)")

    st.markdown("---")

    # ── 7. 한계 & 정직한 단서 ──
    st.markdown("### 7️⃣ 한계 & 정직한 단서")
    st.markdown("""
<div style="background:#434C5E;padding:14px 18px;border-radius:8px;color:#E5E9F0;line-height:1.85">
• <b>스코프</b>: 입력 가격 데이터 정확성만 검증. 전략 수익률 주장은 별도 검증 문서 참조.<br>
• <b>3종 모두 독립</b>: yfinance·Stooq(데이터 벤더) + IBKR(브로커 피드). Bloomberg급 틱 감사는 아니나
  성격이 다른 독립 소스 3종 + 공개기록 삼각검증 → 리테일 백테 신뢰성 기준 충족.<br>
• <b style="color:#A3BE8C">보수성</b>: 백테는 분할조정 Close 사용(배당 미반영) → 16년 누적 총수익 대비 약 <b>7~8% 과소</b>평가.
  데이터 선택이 결과를 부풀리는 게 아니라 <b>깎는</b> 방향.
</div>
""", unsafe_allow_html=True)
    st.caption("재현 스크립트: data_accuracy_2026_06_21/compare3.py (3종) · compare.py (2종 상세) · 무결성: v1_full_reverify_2026_06_20/d1_data_integrity.py")


# ───────────────────────────────────────────────────────────
# 용어 사전 탭
# ───────────────────────────────────────────────────────────
elif page == "📖 용어 사전":
    st.subheader("📖 용어 사전 — 처음 보는 분을 위한 용어 정리")
    st.caption("이 대시보드에 등장하는 용어들을 카테고리별로 정리했습니다.")

    def _glossary_card(term, definition, example=None):
        ex_html = f"<div style='color:#9AA5B8;font-size:0.88em;margin-top:4px'>예시: {example}</div>" if example else ""
        st.markdown(f"""
<div style="background:#3B4252;border-left:3px solid #34A5C5;padding:10px 14px;border-radius:6px;margin-bottom:8px;color:#D8DEE9">
  <span style="color:#88C0D0;font-weight:700">{term}</span><br>
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
        "공식: 0.60 × clip(20/VIX, 0.5, 2.0). VIX 20일 때 0.60(중립), VIX 10이면 1.0(풀), VIX 40이면 0.30(축소).",
        "VIX=15 → k=0.80 → 전략 비중의 80%만 투자"
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
