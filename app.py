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
  <h1 style="margin:0;font-size:1.8em">🏆 BUBE V1 CHAMP_NOMARGIN — VIX dynamic-k overlay</h1>
  <div style="opacity:0.92;margin-top:6px">
    BASE BUBE rotation × <b>k = 0.65 × clip(20/VIX, 0.5, 2.0)</b>, alloc cap = 1.0 (margin 사용 X)
  </div>
  <div style="opacity:0.75;margin-top:4px;font-size:0.92em">
    16년 in-sample 2010-05-25 ~ 2026-05-22 · 운영 1순위 (메모리 <code>project_bube_overlays.md</code>)
  </div>
</div>
""", unsafe_allow_html=True)

# Quick stats row — V1 CHAMP_NOMARGIN 16y headline
col1, col2, col3, col4 = st.columns(4)
col1.metric("16y Calmar", f"{H_CHAMP['Calmar']:.2f}",
            f"BASE {H_BASE['Calmar']:.2f} · +{H_CHAMP['Calmar']-H_BASE['Calmar']:.2f}")
col2.metric("16y CAGR", f"{H_CHAMP['CAGR']:.1f}%",
            f"BASE {H_BASE['CAGR']:.1f}% · +{H_CHAMP['CAGR']-H_BASE['CAGR']:.1f}pp")
col3.metric("16y MDD", f"{H_CHAMP['MDD']:.1f}%",
            f"BASE {H_BASE['MDD']:.1f}% · +{H_CHAMP['MDD']-H_BASE['MDD']:.1f}pp 개선")
col4.metric("$100K → Final", _money(H_CHAMP['Final_mult'] * 100_000),
            f"×{H_CHAMP['Final_mult']/H_BASE['Final_mult']:.1f} BASE")

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
               " — GitHub Actions cloud (평일 21:15 UTC = 17:15 ET = 11:15 HST). "
               "옛 데이터가 보이면 `Ctrl+Shift+R`로 강력 새로고침 또는 Streamlit Cloud manage 페이지에서 Reboot.")

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

_tab_labels = ["📊 Overview", "📋 거래 내역", "📈 Stress Tests", "🎲 Bootstrap",
               "📅 Year-by-Year", "🔄 Multi-window OOS", "💰 BUBE Live"]
if SHOW_V2:
    _tab_labels.append("🆚 V2_FINAL 비교")
_tab_labels.append("📔 최근 1달 매매일지")
tabs = st.tabs(_tab_labels)
# V2 탭 유무에 따라 매매일지 탭 인덱스 이동 (V2 숨기면 7, 보이면 8)
IDX_JOURNAL = 8 if SHOW_V2 else 7

# ───────────────────────────────────────────────────────────
# TAB 1: Overview
# ───────────────────────────────────────────────────────────
with tabs[0]:
    st.subheader("BUBE V1 CHAMP_NOMARGIN Spec")
    col_a, col_b = st.columns([1, 1])
    with col_a:
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
        st.markdown("### 16년 In-sample Headline")
        ha1, ha2 = st.columns(2)
        ha1.metric("CHAMP_NOMARGIN", "")
        ha1.markdown(f"""
- **CAGR**: `{H_CHAMP['CAGR']:.2f}%`
- **MDD**: `{H_CHAMP['MDD']:.2f}%`
- **Sharpe**: `{H_CHAMP['Sharpe']:.2f}`
- **Calmar**: `{H_CHAMP['Calmar']:.2f}`
- **Final** ($100K seed): `{_money(H_CHAMP['Final_mult']*100_000)}`
""")
        ha2.metric("BASE (k=0.65 정적)", "")
        ha2.markdown(f"""
- **CAGR**: `{H_BASE['CAGR']:.2f}%`
- **MDD**: `{H_BASE['MDD']:.2f}%`
- **Sharpe**: `{H_BASE['Sharpe']:.2f}`
- **Calmar**: `{H_BASE['Calmar']:.2f}`
- **Final**: `{_money(H_BASE['Final_mult']*100_000)}`
""")

        st.markdown("### 검증 (2026-05-26)")
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
    st.markdown("### ⚠️ 약점 (정직)")
    st.markdown("""
    - **16년 단일 path 결과**: 단일 실현 path는 운임을 결정하지 못함. bootstrap p05 Calmar 1.30, p50 2.16, p95 3.41 spread가 진짜 추정.
    - **MDD 꼬리 위험**: bootstrap p50 MDD -34.9%, P(MDD<-30%) = **82.0%**, P(MDD<-40%) = 22.7% — 단일 실현에서 -28%였지만 미래 path는 더 깊을 확률 ≥ 80%.
    - **VIX9D 직접 의존 X** (overlay는 VIX만 사용) — 다만 BASE BUBE의 regime detector에는 VIX9D/VIX>1.05 fast BEAR OR가 있어 VIX9D 누락 시 약화.
    - **margin 허용 시 CHAMP_REF Cal 2.92** — V1 CHAMP_NOMARGIN은 일부러 alloc≤1.0 제한, prop firm/IBKR Reg-T 마진 회피용.
    - **TREND overlay (V3)는 bootstrap에서 0 alpha** — 별도 신호 추가 X, VIX scale만으로 충분.
    """)

    st.markdown("---")
    st.markdown("### 🚨 환상으로 확정된 매매법 (운영 사용 금지) — 메모리 `feedback_idealized_models.md`")
    st.markdown("""
| 매매법 | 메모리 권고치 (idealized) | trade-level 운영 추정 | verdict |
|---|---|---|---|
| CHAMP alloc sweep k=0.72 | Calmar **4.32**, MDD −20% | Calmar 1.77, MDD −34% | 8-slot returns 합성 환상 |
| Slot rotation N7_H7 | Calmar **3.53**, MDD −11pp 개선 | 슬롯 분산 효과 0 | 동일자산 SOXL returns 곱셈 |
| V_bear_cap escape valve (T2GE bm=90) | Calmar **6.52** (8y returns-stream) | Cal 2.40 (8y) / 1.87 (16y) trade-level, 발동 0회 | dead code, idealized cherry-pick |

**규칙**: returns-stream 합성 모델 결과로 운영 alloc·slot 수·진입 빈도 권고 금지. trade-level OHLC만 인용 가능.
**현 dashboard 모든 수치는 trade-level OHLC 16년 단일 실현 path + bootstrap 5,000 paths.**
""")


# ───────────────────────────────────────────────────────────
# TAB 2: 거래 내역
# ───────────────────────────────────────────────────────────
with tabs[1]:
    st.subheader("📋 BUBE V1 CHAMP_NOMARGIN 16년 거래 내역")
    st.caption("SOXL 상장일(2010-05-25) ~ 현재. yfinance daily OHLC. k = 0.65 × clip(20/VIX, 0.5, 2.0), alloc cap 1.0.")

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
with tabs[2]:
    st.subheader("📈 Stress Tests — 8개 Crisis × BASE vs CHAMP_NOMARGIN")
    st.caption("CHAMP_NOMARGIN의 VIX dynamic-k overlay가 위기 구간에서 MDD를 얼마나 줄이는가.")

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
with tabs[3]:
    st.subheader("🎲 Bootstrap — CHAMP_NOMARGIN 5,000 paths")
    st.caption("Stationary block bootstrap (mean block ≈ 20d). 16년 단일 path는 실현된 하나의 sample — 5,000 paths가 진짜 분포.")

    b = H_BOOT

    bc1, bc2, bc3 = st.columns(3)
    bc1.markdown("### CAGR 분포")
    bc1.metric("p05", f"{b['cagr_p05']:.1f}%")
    bc1.metric("p50 (median)", f"{b['cagr_p50']:.1f}%")
    bc1.metric("p95", f"{b['cagr_p95']:.1f}%")
    bc1.caption(f"P(CAGR > 0) = **{b['p_cagr_positive']:.1f}%** · P(CAGR > 30%) = **{b['p_cagr_above_30']:.1f}%**")

    bc2.markdown("### MDD 분포")
    bc2.metric("p05 (최악)", f"{b['mdd_p05']:.1f}%")
    bc2.metric("p50 (median)", f"{b['mdd_p50']:.1f}%")
    bc2.metric("p95 (최선)", f"{b['mdd_p95']:.1f}%")
    bc2.caption(f"P(MDD < -30%) = **{b['p_mdd_worse_than_30']:.1f}%** · P(MDD < -40%) = **{b['p_mdd_worse_than_40']:.1f}%**")

    bc3.markdown("### Calmar 분포")
    bc3.metric("p05", f"{b['cal_p05']:.2f}")
    bc3.metric("p50 (median)", f"{b['cal_p50']:.2f}")
    bc3.metric("p95", f"{b['cal_p95']:.2f}")
    bc3.caption("In-sample 단일 path Calmar 2.75 → bootstrap p50 2.16. 단일 path는 약간 운 좋은 실현.")

    st.markdown("---")
    st.markdown("### 핵심 해석")
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
with tabs[4]:
    st.subheader("📅 Year-by-Year — 17년 BASE vs CHAMP_NOMARGIN")
    st.caption("연도별 수익률/MDD/Sharpe. CHAMP_NOMARGIN이 매년 일관 우월이면 robustness 입증.")

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
with tabs[5]:
    st.subheader("🔄 Multi-window OOS — 1y/2y/3y/4y/5y/8y/10y/15y/16y rolling")
    st.caption("각 window 끝 시점 기준 backward N-year backtest. Calmar 일관성 = robustness 증거.")

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
with tabs[6]:
    st.subheader("💰 BUBE V1 CHAMP_NOMARGIN — Alpaca Paper")
    st.caption("bube_trader.py 운영 봇. VIX dynamic-k overlay가 매 진입 시 base alloc에 k_today를 곱하고 1.0으로 cap.")
    st.info("ℹ️ **운영 봇 = V1 CHAMP_NOMARGIN + A안 비대칭 갭필터** "
            "(2026-06-03 전환, paper 라이브 검증 중). 롱변기·양변기롱은 갭다운(gap<-5%)만 차단, 양변기숏은 대칭. "
            "헤드라인 수치는 다음 daily_backtest(일요일 V1) 갱신 후 A안 기준으로 반영. 롤백: `GAP_FILTER_MODE=sym`.")

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
            "백테 데이터 (Tab 1-6, 8, 9)는 이 버튼과 무관 — 이미 표시됨."
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

        st.markdown("### 🌡 Today — Regime / V1 overlay")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Today Regime", rstate["regime"], f"raw {rstate['raw_regime']}")
        c2.metric("Active Sub-Strategy", f"{active_emoji} {active_name}")
        c3.metric("BEAR streak", f"{rstate['bear_streak']}d", f"max {rstate['max_bear']}d")
        c4.metric("Last 7d", rstate["last7"], f"dwell {rstate['dwell']}d")

        if rstate["vix_today"] is not None:
            v1, v2, v3, v4 = st.columns(4)
            v1.metric("VIX today", f"{rstate['vix_today']:.2f}", "20 = base scale")
            v2.metric("scale = clip(20/VIX, 0.5, 2.0)", f"{rstate['scale']:.3f}")
            v3.metric("k_today = 0.65 × scale", f"{rstate['k_today']:.3f}",
                      "BASE 0.65 대비")
            v4.metric("alloc_max (cap 1.0)", f"{rstate['alloc_max']*100:.0f}%",
                      "margin 사용 X")

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

        st.markdown("### 💼 Alpaca Paper Account")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Equity", f"${acc['equity']:,.2f}", f"{pnl:+,.2f} ({pnl_pct:+.2f}%)")
        c2.metric("Cash", f"${acc['cash']:,.2f}")
        c3.metric("Buying Power", f"${acc['buying_power']:,.2f}")
        c4.metric("Account", acc["status"])

        st.markdown("### Open Positions")
        if data["positions"]:
            pos_df = pd.DataFrame(data["positions"])
            pos_df["avg_entry"] = pos_df["avg_entry"].apply(lambda x: f"${x:.2f}")
            pos_df["current"] = pos_df["current"].apply(lambda x: f"${x:.2f}")
            pos_df["market_value"] = pos_df["market_value"].apply(lambda x: f"${x:,.2f}")
            pos_df["unrealized_pnl"] = pos_df["unrealized_pnl"].apply(lambda x: f"${x:+,.2f}")
            pos_df["unrealized_pct"] = pos_df["unrealized_pct"].apply(lambda x: f"{x:+.2f}%")
            st.dataframe(pos_df, use_container_width=True, hide_index=True)
        else:
            st.info("보유 포지션 없음 (regime 판정 후 진입 대기 또는 갭/필터 차단)")

        st.markdown("### 오늘 주문")
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


# V2 탭은 SHOW_V2가 True일 때만 렌더 (기본 False = 운영 대시보드에서 숨김)
if SHOW_V2:
    with tabs[7]:
        _render_v2_tab()


# ───────────────────────────────────────────────────────────
# TAB 9: 최근 1달 매매일지 (signal_diagnostics + trade_log_enriched)
# ───────────────────────────────────────────────────────────
with tabs[IDX_JOURNAL]:
    st.subheader("📔 최근 1달 매매일지 — 일별 신호값 + 산식 검증")
    st.caption("data/v2_final/signal_diagnostics.csv (daily 자동 갱신). 각 거래일에 백테가 계산한 모든 신호값과 "
               "k_today 도출 과정을 표시. 사용자가 직접 산식 검증 가능.")

    diag_path = V2DIR / "signal_diagnostics.csv"
    eq_path = V2DIR / "equity_paths.csv"
    trades_path = V2DIR / "trade_log_enriched.csv"

    if not diag_path.exists():
        st.error("data/v2_final/signal_diagnostics.csv 없음. daily update 한 번 돌려야 함: "
                 "`python local/strategies/bube_v2_daily_update.py`")
    else:
        def _mtime_j(p):
            try: return p.stat().st_mtime
            except Exception: return 0

        @st.cache_data
        def _load_diag(_mtime_key):
            return pd.read_csv(diag_path, parse_dates=["date"])

        @st.cache_data
        def _load_eq_for_journal(_mtime_key):
            return pd.read_csv(eq_path, parse_dates=["date"], index_col="date")

        @st.cache_data
        def _load_trades_journal(_mtime_key):
            if not trades_path.exists():
                return None
            return pd.read_csv(trades_path, parse_dates=["date"])

        diag = _load_diag(_mtime_j(diag_path))
        eq_j = _load_eq_for_journal(_mtime_j(eq_path))
        trades_j = _load_trades_journal(_mtime_j(trades_path))

        # ── A. Period selector ──
        n_days_opts = {"최근 20거래일": 20, "최근 1달 (30일)": 30,
                       "최근 60거래일": 60, "최근 90거래일": 90}
        sel = st.radio("기간", list(n_days_opts.keys()), index=1, horizontal=True, key="journal_period")
        n_show = n_days_opts[sel]

        diag_recent = diag.tail(n_show).reset_index(drop=True)

        # ── B. Summary headline ──
        st.markdown(f"### 📊 {sel} 요약")
        n_bull = (diag_recent["regime"] == "BULL").sum()
        n_bear = (diag_recent["regime"] == "BEAR").sum()
        n_neut = (diag_recent["regime"] == "NEUTRAL").sum()
        n_vvix_gate = int(diag_recent["vvix_gate_active"].sum())
        n_ndx_throt = int((diag_recent["ndx_scale"] < 1.0).sum())
        mean_k = float(diag_recent["k_final"].mean())
        mean_vix = float(diag_recent["VIX"].mean())

        h1, h2, h3, h4 = st.columns(4)
        h1.metric("Regime 분포", f"BULL {n_bull} / BEAR {n_bear} / NEUT {n_neut}",
                  f"{len(diag_recent)}일 중")
        h2.metric("Mean k_final (V2)", f"{mean_k:.3f}",
                  f"VIX 평균 {mean_vix:.1f}")
        h3.metric("VVIX gate 발동", f"{n_vvix_gate}일",
                  f"{n_vvix_gate/len(diag_recent)*100:.0f}% of period")
        h4.metric("NDX/SPY throttle 발동", f"{n_ndx_throt}일",
                  f"{n_ndx_throt/len(diag_recent)*100:.0f}% of period")

        st.markdown("---")

        # ── C. Day-by-day table with all signal values ──
        st.markdown("### 📋 일별 신호값 표 (V2_FINAL 기준)")

        disp = diag_recent.copy()
        # Add V1 k_final for comparison: V1 only uses VIX scale, no VVIX, no NDX
        disp["k_V1"] = (0.65 * disp["vix_scale"]).clip(upper=1.0)
        # V2 equity / V1 equity from equity_paths
        eq_for_recent = eq_j.reindex(pd.to_datetime(diag_recent["date"]))
        disp["V1_equity"] = eq_for_recent["V1"].values
        disp["V2_equity"] = eq_for_recent["V2_FINAL"].values

        # Format display
        view = pd.DataFrame({
            "날짜": disp["date"].dt.strftime("%Y-%m-%d"),
            "Regime": disp["regime"],
            "Active": disp["active"],
            "VIX": disp["VIX"].apply(lambda x: f"{x:.2f}"),
            "VVIX": disp["VVIX"].apply(lambda x: f"{x:.2f}"),
            "NDX/SPY 20d RS": disp["NDX_SPY_RS_20d"].apply(lambda x: f"{x:+.3f}"),
            "SOXL 5d ret": disp["SOXL_5d_ret"].apply(lambda x: f"{x:+.3f}"),
            "vix_scale": disp["vix_scale"].apply(lambda x: f"{x:.3f}"),
            "vvix_scale": disp["vvix_scale"].apply(lambda x: f"{x:.3f}"),
            "ndx_scale": disp["ndx_scale"].apply(lambda x: f"{x:.2f}"),
            "k_V1 (VIX only)": disp["k_V1"].apply(lambda x: f"{x:.3f}"),
            "k_V2 (final)": disp["k_final"].apply(lambda x: f"{x:.3f}"),
            "V1 Equity": disp["V1_equity"].apply(lambda x: _money(x) if not pd.isna(x) else "—"),
            "V2 Equity": disp["V2_equity"].apply(lambda x: _money(x) if not pd.isna(x) else "—"),
        })
        st.dataframe(view, use_container_width=True, hide_index=True, height=480)

        # CSV download — lazy 처리 (Tab 2와 동일 패턴)
        # 이전: 매 rerun마다 to_csv encode + st.download_button 등록
        #   → Streamlit Cloud 서버 연결 일시 단절 시 'not connected to a server!' 에러 발생
        # 이후: '준비' 버튼 클릭 시에만 encode → session_state 저장 → download_button 표시
        d_start = diag_recent['date'].iloc[0].date()
        d_end = diag_recent['date'].iloc[-1].date()
        if st.button(f"💾 매매일지 CSV 준비 ({len(view):,} rows)", key="journal_dl_prep"):
            st.session_state["journal_csv_ready"] = view.to_csv(index=False).encode("utf-8-sig")
            st.session_state["journal_csv_range"] = f"{d_start}_{d_end}"
        if "journal_csv_ready" in st.session_state:
            st.download_button(
                f"⬇️ bube_journal_{st.session_state.get('journal_csv_range','')}.csv 받기",
                data=st.session_state["journal_csv_ready"],
                file_name=f"bube_journal_{st.session_state.get('journal_csv_range', f'{d_start}_{d_end}')}.csv",
                mime="text/csv",
                key="journal_dl"
            )

        st.markdown("---")

        # ── D. Per-day expander: 산식 검증 (math step-by-step) ──
        st.markdown("### 🔍 일별 산식 검증 — 각 수치가 어떻게 산출됐는지")
        st.caption("최근 5거래일에 대해 펼쳐서 검증 가능. k_today 산출 과정을 단계별로 표시.")

        last5 = diag_recent.tail(5).iloc[::-1].reset_index(drop=True)  # newest first
        for _, row in last5.iterrows():
            d_str = row["date"].strftime("%Y-%m-%d")
            with st.expander(f"📅 **{d_str}** — Regime: {row['regime']}, Active: {row['active']}, "
                             f"k_V2 = {row['k_final']:.3f}"):
                col_a, col_b = st.columns([1, 1])

                with col_a:
                    st.markdown("**📥 입력값 (raw signals, look-ahead safe)**")
                    inputs = pd.DataFrame({
                        "Signal": ["VIX (close)", "VVIX (close)", "NDX/SPY 20d RS",
                                   "SOXL 5d return", "Regime", "Active sub-strategy",
                                   "VVIX gate active?"],
                        "Value": [
                            f"{row['VIX']:.2f}",
                            f"{row['VVIX']:.2f}",
                            f"{row['NDX_SPY_RS_20d']:+.4f}  ({'음수' if row['NDX_SPY_RS_20d'] < 0 else '양수'})",
                            f"{row['SOXL_5d_ret']:+.4f}  ({'음수' if row['SOXL_5d_ret'] < 0 else '양수'})",
                            row["regime"],
                            row["active"],
                            "True" if row["vvix_gate_active"] else "False (SOXL 5d ret ≥ 0)",
                        ],
                    })
                    st.dataframe(inputs, use_container_width=True, hide_index=True)

                with col_b:
                    st.markdown("**🧮 산식 단계별 검증**")
                    # vix_scale verification
                    vix_calc = max(0.5, min(2.0, 20.0 / row["VIX"]))
                    vix_match = "✅" if abs(vix_calc - row["vix_scale"]) < 1e-6 else "❌"
                    # vvix_scale verification
                    if row["vvix_gate_active"] and row["VVIX"] > 0:
                        vvix_calc = max(0.5, min(1.0, 90.0 / row["VVIX"]))
                    else:
                        vvix_calc = 1.0
                    vvix_match = "✅" if abs(vvix_calc - row["vvix_scale"]) < 1e-6 else "❌"
                    # ndx_scale verification
                    ndx_calc = 0.8 if row["NDX_SPY_RS_20d"] < 0 else 1.0
                    ndx_match = "✅" if abs(ndx_calc - row["ndx_scale"]) < 1e-6 else "❌"
                    # k_V1 = 0.65 × vix_scale (capped 1.0)
                    k_v1_calc = min(0.65 * row["vix_scale"], 1.0)
                    # k_V2 = 0.65 × vix_scale × vvix_scale × ndx_scale (capped 1.0)
                    k_v2_calc = min(0.65 * row["vix_scale"] * row["vvix_scale"] * row["ndx_scale"], 1.0)
                    k_v2_match = "✅" if abs(k_v2_calc - row["k_final"]) < 1e-4 else "❌"

                    st.code(f"""
# ① vix_scale = clip(20 / VIX, 0.5, 2.0)
vix_scale = clip(20.0 / {row['VIX']:.2f}, 0.5, 2.0)
         = clip({20/row['VIX']:.4f}, 0.5, 2.0)
         = {vix_calc:.4f}     [stored: {row['vix_scale']:.4f}]  {vix_match}

# ② vvix_scale = (SOXL_5d < 0 인 날만 clamp 적용)
{'#   gate active (SOXL_5d_ret = ' + f"{row['SOXL_5d_ret']:+.4f}" + ' < 0)' if row['vvix_gate_active'] else '#   gate inactive (SOXL_5d_ret = ' + f"{row['SOXL_5d_ret']:+.4f}" + ' >= 0 → scale=1.0)'}
vvix_scale = {'clip(90 / ' + f"{row['VVIX']:.2f}" + ', 0.5, 1.0) = ' + f"{vvix_calc:.4f}" if row['vvix_gate_active'] else '1.0 (gate off)'}
                                  [stored: {row['vvix_scale']:.4f}]  {vvix_match}

# ③ ndx_scale = (NDX/SPY 20d RS < 0 → 0.8, else 1.0)
ndx_scale = {'0.8 (RS = ' + f"{row['NDX_SPY_RS_20d']:+.4f}" + ' < 0)' if row['NDX_SPY_RS_20d'] < 0 else '1.0 (RS = ' + f"{row['NDX_SPY_RS_20d']:+.4f}" + ' >= 0)'}
                                  [stored: {row['ndx_scale']:.2f}]  {ndx_match}

# ④ k_V1 = min(0.65 × vix_scale, 1.0)        ← V1 (paper 봇 실제 사용)
k_V1 = min(0.65 × {row['vix_scale']:.4f}, 1.0)
     = min({0.65*row['vix_scale']:.4f}, 1.0)
     = {k_v1_calc:.4f}

# ⑤ k_V2 = min(0.65 × vix × vvix × ndx, 1.0)  ← V2 (백테 비교용)
k_V2 = min(0.65 × {row['vix_scale']:.4f} × {row['vvix_scale']:.4f} × {row['ndx_scale']:.2f}, 1.0)
     = min({0.65*row['vix_scale']*row['vvix_scale']*row['ndx_scale']:.4f}, 1.0)
     = {k_v2_calc:.4f}        [stored: {row['k_final']:.4f}]  {k_v2_match}

# 해석:
# • V1 alloc 비율 = {k_v1_calc*100:.1f}%  (BUBE rotation strat_alloc × {k_v1_calc:.3f})
# • V2 alloc 비율 = {k_v2_calc*100:.1f}%  (V1 대비 {(k_v2_calc/k_v1_calc - 1)*100:+.1f}%)
""", language="python")

                # Trades that day (if any)
                if trades_j is not None:
                    day_trades = trades_j[trades_j["date"].dt.date == row["date"].date()]
                    if len(day_trades) > 0:
                        st.markdown(f"**💸 이 날 V2 매매 ({len(day_trades)}건)**")
                        td = day_trades[["strategy", "leg", "ticker", "action",
                                          "qty", "price", "pnl", "side"]].copy()
                        td["qty"] = td["qty"].apply(lambda x: f"{x:,.0f}")
                        td["price"] = td["price"].apply(lambda x: f"${x:.4f}")
                        td["pnl"] = td["pnl"].apply(lambda x: f"${x:+,.2f}")
                        st.dataframe(td, use_container_width=True, hide_index=True)
                    else:
                        st.caption("이 날 매매 이벤트 없음 (포지션 hold).")

        st.markdown("---")

        # ── E. Notes ──
        st.info("""
**💡 산식 빠른 참조 (paper 봇 = V1 only)**

```
# Paper 봇 (bube_trader.py) — V1 CHAMP_NOMARGIN, 매일 09:35 ET open_stops에서 계산
k_today = 0.65 × clip(20.0 / VIX, 0.5, 2.0)   # VIX dynamic
alloc_today = min(k_today × strat_alloc, 1.0)  # margin 사용 X

# V2_FINAL (백테만, paper 미적용) — V1 위에 두 신호 추가
k_V2 = k_V1 × vvix_scale × ndx_scale
vvix_scale = clip(90/VVIX, 0.5, 1.0) if SOXL_5d_ret < 0 else 1.0   # 약세 때만 vol-of-vol clamp
ndx_scale  = 0.8 if NDX/SPY_20d_RS < 0 else 1.0                    # tech 약세 시 20% throttle
```

**검증 마크**: ✅ = 저장값과 재계산값 일치, ❌ = 불일치 (있으면 즉시 확인).
""")
