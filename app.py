"""
BUBE Trader — Streamlit 대시보드 (Tier 2 GOLD_ESCAPE bm=90)
===============================================================
백테스트 결과 + 신뢰구간 + Alpaca paper 통합 봇 실시간 모니터링.

2026-05-24 통합: 기존 YB MDD OR + Rotation P5.5 두 봇 → bube_trader.py 하나.

탭 구성:
1. 📊 Overview — 매매법 spec
2. 📋 거래 내역 — 8년 분봉 백테 거래 로그
3. 📈 Stress Tests — 5+2 폭락 사이클
4. 🎲 Bootstrap — 5,000 paths 신뢰구간
5. 📅 Year-by-Year — 16년 long-horizon
6. 🔄 Walk-Forward / OOS — 동적 vs 정적
7. 💰 BUBE Live — Alpaca paper 실시간 + regime + active sub-strategy
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import streamlit as st

# Cloud-friendly path: relative ROOT, data lives under ./data/
ROOT = Path(__file__).parent / "data"
st.set_page_config(page_title="BUBE Trader Dashboard", layout="wide", page_icon="🚽")

# Alpaca credentials from Streamlit secrets (cloud) or env (local)
# BUBE trader: ALPACA_API_KEY / ALPACA_SECRET_KEY (2026-05-24 통합 후 새 paper 계정)
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


def fmt(x, places=2):
    if x is None or pd.isna(x): return "—"
    return f"{x:.{places}f}"


# ───────────────────────────────────────────────────────────
# Header
# ───────────────────────────────────────────────────────────
st.markdown("""
<div style="background:linear-gradient(135deg,#1a2540,#2c3e50);padding:24px 32px;border-radius:12px;color:white;margin-bottom:16px">
  <h1 style="margin:0;font-size:1.8em">🚽 BUBE Trader — T2 GOLD_ESCAPE bm=90</h1>
  <div style="opacity:0.85;margin-top:6px">롱변기 (BULL/NEUTRAL) + 양변기 v5 F1_A6 (BEAR) + 황금변기 (BEAR streak &gt; 90d escape)</div>
</div>
""", unsafe_allow_html=True)

# Quick stats row — V_bear_cap_comprehensive V1-V9 (2026-05-23) 검증 결과
col1, col2, col3, col4 = st.columns(4)
col1.metric("8년 Calmar", "6.52", "vs baseline 6.46")
col2.metric("닷컴 31m OOS", "+66.9%", "vs baseline +57.1%")
col3.metric("Longest UW", "156d", "−90d (246→156)")
col4.metric("V7 random p", "0.0000", "300 trials 한 번도 안 짐")

st.markdown("---")

tabs = st.tabs(["📊 Overview", "📋 거래 내역", "📈 Stress Tests", "🎲 Bootstrap",
                "📅 Year-by-Year", "🔄 Walk-Forward / OOS",
                "🔀 Slot Rotation", "💰 BUBE Live"])

# ───────────────────────────────────────────────────────────
# TAB 1: Overview
# ───────────────────────────────────────────────────────────
with tabs[0]:
    st.subheader("BUBE Trader — Tier 2 GOLD_ESCAPE bm=90 Spec")
    col_a, col_b = st.columns([1, 1])
    with col_a:
        st.code("""
# Regime → Sub-strategy mapping (Tier 2 GOLD_ESCAPE)
BULL / NEUTRAL          → 롱변기      (SOXL only)
BEAR                    → 양변기 v5  (SOXL+SOXS pair, F1_A6 LOC)
BEAR streak > 90일      → 황금변기   (SOXL K-vol breakout, GOLD_ESCAPE)

# Regime detector (look-ahead safe: .shift(1))
consensus  = QQQ/SPY/SMH SMA200 ±2% 중 ≥2 합의
fast_bear  = VIX9D/VIX > 1.05  OR  SOXL 5d mom < -10%
dwell      = 5일 (regime 전환 최소 유지)
max_bear   = 90일 (Tier 2 GOLD_ESCAPE 트리거)

# 롱변기 (BULL/NEUTRAL)
soxl_stop_buy = +1.5%  alloc=100%  stop=-8% close-based  gap_filter=±5%

# 양변기 v5 F1_A6 (BEAR)
soxl_stop_buy  = +1.5%   long_alloc = 50/60/70 (QQQ RSI <50/50-60/≥60)
soxs_stop_buy  = +6.0%   short_alloc = 40%   gap_filter = ±5%
loc_on_win     = 0%      (수익 100% T+1 carry)
loc_on_loss    = 25%     (손실 25% LOC + 75% T+1 MOO)

# 황금변기 (GOLD_ESCAPE)
soxl_stop_buy = open + (전일 H-L) × 0.25       # K-vol breakout
whipsaw_filter = 전일 |return| ≤ 5%
alloc by QQQ weekly RSI: ≥60 100% / 45-60 70% / <45 30% watch
""", language="python")
    with col_b:
        st.markdown("### V1-V9 검증 (2026-05-23)")
        st.caption("V_bear_cap_comprehensive — BEAR upper bound escape valve 종합 재검증, 9개 중 7 PASS / 2 조건부 PASS")
        check_data = [
            ("V1 Look-ahead audit", "regime detector 전부 shift(1), escape는 cumulative past만", "✅"),
            ("V2 bear_max grid", "T1 bm60 / T2GE bm75-90 sweet spot", "⚠️"),
            ("V3 Bootstrap 6000", "T1 bm60 p50 Cal 3.43 vs None 3.17 (+0.26)", "✅"),
            ("V4 Cost sweep 0-70bp", "모든 비용 수준에서 우위 유지", "✅"),
            ("V5 IS/OOS 4 splits", "IS 일관 우월(+0.16~+0.53), OOS 동등 — 과적합 X", "✅"),
            ("V6 5개 위기 stress", "2022만 발동 (T1 +3.5%p, T2GE bm90 +5%p)", "⚠️"),
            ("V7 Random escape 300", "p=0.0000 — random 한 번도 못 이김", "✅"),
            ("V8 Yearly breakdown", "발동 해(2020/2022) 모두 양수 +80%p alpha", "✅"),
            ("V9 Drawdown duration", "longest UW 246d → 156d (-90d)", "✅"),
        ]
        for name, desc, mark in check_data:
            st.markdown(f"**{mark} {name}** — {desc}")

        st.markdown("---")
        st.markdown("### ⚠️ 약점 (정직)")
        st.markdown("""
        - 8년 표본에서 bear_cap 발동 단 2회 (2020/2022 각 10일) → grid noise 가능성
        - bm 값 future-proof 아님 (10년 후 bm=45/120이 더 나을 수도)
        - VIX9D 부재 시 vix_shock proxy로 Cal 6.46→5.79 (10% 손해)
        - 백테 탭들(거래 내역/Stress/Bootstrap/Year-by-Year/Walk-Forward)은 **양변기 v5 단독** 결과 — BUBE의 BEAR slot 컴포넌트만 반영. 전체 BUBE rotation 백테는 별도.
        """)

# ───────────────────────────────────────────────────────────
# TAB 2: 기간별 거래 내역 (NEW)
# ───────────────────────────────────────────────────────────
with tabs[1]:
    st.subheader("📋 BUBE 전체 rotation 8년 거래 내역 (롱변기 + 양변기 + 황금변기)")
    st.caption("ℹ️ Tier 2 GOLD_ESCAPE bm=90 mapping. yfinance daily OHLC. multi_strategy_paper.simulate_day 엔진 + BUBE T2 mapping 어댑터.")

    # ── 사용자 정의 시작 자본 — 이 페이지의 모든 $ 값이 이 시드 기준으로 비례 환산됨 ──
    seed_col1, seed_col2 = st.columns([1, 3])
    user_seed = seed_col1.number_input(
        "시작 자본 ($)",
        min_value=100,
        max_value=10_000_000,
        value=10_000,
        step=1_000,
        key="user_seed_input",
        help="백테는 $100K 시드로 실행되었지만, 이 값으로 모든 $ 결과를 비례 스케일링합니다. % 수익률은 변하지 않음."
    )
    seed_col2.markdown(
        f"<div style='padding-top:1.7em;color:#888'>"
        f"💡 모든 $ 값(자본, PnL, notional, 누적 PnL)이 <b>${user_seed:,.0f}</b> 시드 기준으로 환산됩니다. % 수익률은 동일."
        f"</div>",
        unsafe_allow_html=True
    )

    FULL = ROOT / "bube_full"
    if not (FULL / "trades.csv").exists():
        st.warning("⚠️ BUBE 풀백테 캐시 없음. 먼저 실행: `python local/strategies/regime_rotation_validation/bube_full_backtest.py`")
        st.stop()

    # Summary stats from summary.json — user_seed 기준으로 비례 환산
    bube_summary = load_json(FULL / "summary.json")
    if bube_summary:
        bt_seed = float(bube_summary.get("seed", 100_000))
        scale_bube = user_seed / bt_seed
        final_eq_scaled = float(bube_summary["final_equity"]) * scale_bube
        gain_scaled = final_eq_scaled - user_seed

        def _money(v):
            a = abs(v)
            if a >= 1e6: return f"${v/1e6:+.2f}M" if v < 0 else f"${v/1e6:.2f}M"
            if a >= 1e3: return f"${v:+,.0f}" if v < 0 else f"${v:,.0f}"
            return f"${v:+,.0f}" if v < 0 else f"${v:,.0f}"

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("기간", bube_summary.get("period", "—"))
        c2.metric("시작 시드", f"${user_seed:,.0f}")
        c3.metric("Final Equity",
                  _money(final_eq_scaled),
                  f"{bube_summary['total_return_pct']:+,.0f}%")
        c4.metric("기간 $ PnL",
                  f"${gain_scaled/1e6:+.2f}M" if abs(gain_scaled) >= 1e6 else f"${gain_scaled:+,.0f}")
        c5.metric("CAGR", f"{bube_summary['cagr_pct']:+.1f}%")
        c6.metric("MDD", f"{bube_summary['mdd_pct']:+.1f}%")
        st.caption(f"📐 Calmar: {bube_summary.get('calmar', '—')} · 백테 시드 ${bt_seed:,.0f} → 사용자 시드 ${user_seed:,.0f} (×{scale_bube:.4f} 환산)")

        usage = bube_summary.get("strategy_usage", {})
        if usage:
            usage_str = " · ".join(f"{k}: {v}" for k, v in sorted(usage.items(), key=lambda x: -x[1]))
            st.caption(f"🔄 Sub-strategy trade events: {usage_str}")
            if "goldenbyungi" not in usage:
                st.info(
                    "ℹ️ 8년 표본에서 **GOLD_ESCAPE 미발동** (BEAR streak > 90일이 발생 안 함). "
                    "닷컴급 super-bear (31개월 BEAR)에서만 발동되는 escape valve — V_bear_cap dotcom OOS 검증에서 +9.8%p alpha 입증."
                )

    # ── BUBE 풀 trades quick view ──
    @st.cache_data
    def _load_bube_trades():
        t = pd.read_csv(ROOT / "bube_full" / "trades.csv")
        t["date"] = pd.to_datetime(t["date"])
        return t

    bube_trades = _load_bube_trades()
    bf1, bf2, bf3 = st.columns([2, 1, 1])
    strategy_sel = bf1.multiselect(
        "Strategy filter",
        options=sorted(bube_trades["strategy"].unique()),
        default=sorted(bube_trades["strategy"].unique()),
        key="bube_strategy_filter"
    )
    action_sel = bf2.multiselect(
        "Action",
        options=sorted(bube_trades["action"].unique()),
        default=sorted(bube_trades["action"].unique()),
        key="bube_action_filter"
    )
    pnl_sel = bf3.radio("PnL", options=["전체", "수익만", "손실만"],
                         horizontal=True, key="bube_pnl_filter")

    bube_filt = bube_trades[
        bube_trades["strategy"].isin(strategy_sel) &
        bube_trades["action"].isin(action_sel)
    ].copy()
    if pnl_sel == "수익만":
        bube_filt = bube_filt[bube_filt["pnl"] > 0]
    elif pnl_sel == "손실만":
        bube_filt = bube_filt[bube_filt["pnl"] < 0]

    # Headline stats
    fc1, fc2, fc3, fc4 = st.columns(4)
    fc1.metric("Trade events", f"{len(bube_filt):,}")
    realized = bube_filt["pnl"].sum()
    fc2.metric("Realized P&L", f"${realized:+,.0f}")
    nonzero = bube_filt[bube_filt["pnl"] != 0]
    if len(nonzero):
        wr = (nonzero["pnl"] > 0).mean() * 100
        fc3.metric("Win rate (non-zero pnl)", f"{wr:.1f}%")
    else:
        fc3.metric("Win rate", "—")
    fc4.metric("기간",
               f"{bube_filt['date'].min().date()} → {bube_filt['date'].max().date()}"
               if len(bube_filt) else "—")

    # Display table
    disp = bube_filt.copy()
    disp["date"] = disp["date"].dt.strftime("%Y-%m-%d")
    disp["qty"] = disp["qty"].apply(lambda x: f"{x:,.2f}")
    disp["price"] = disp["price"].apply(lambda x: f"${x:.4f}")
    disp["pnl"] = disp["pnl"].apply(lambda x: f"${x:+,.2f}")
    disp = disp.rename(columns={
        "date": "날짜", "strategy": "Sub-strategy", "leg": "방향",
        "ticker": "Ticker", "action": "Action", "qty": "수량",
        "price": "체결가", "pnl": "PnL", "side": "Side",
    })
    rows_per_page = 100
    n_pages = max(1, (len(disp) + rows_per_page - 1) // rows_per_page)
    page = st.number_input(
        f"Page (총 {len(disp):,} rows, {n_pages} pages)",
        min_value=1, max_value=n_pages, value=1, key="bube_trade_page"
    ) if n_pages > 1 else 1
    start_idx = (page - 1) * rows_per_page
    st.dataframe(disp.iloc[start_idx:start_idx + rows_per_page],
                 use_container_width=True, hide_index=True, height=400)

    # CSV download
    st.download_button(
        label=f"💾 BUBE trades CSV 다운로드 ({len(bube_filt):,} rows)",
        data=bube_filt.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"bube_full_trades_{bube_filt['date'].min().date() if len(bube_filt) else 'empty'}_"
                  f"{bube_filt['date'].max().date() if len(bube_filt) else 'empty'}.csv",
        mime="text/csv", key="bube_dl"
    )

    st.markdown("---")
    st.markdown("### 📜 양변기 v5 단독 — BEAR slot 컴포넌트 풀 백테 (참고용)")
    st.caption("ℹ️ BUBE의 BEAR regime에서 active되는 sub-strategy 단독 백테. 8년 분봉 (IBKR) + alloc/bench/regime context 포함 — 거래별 진입사유/청산사유 풀스택 분석은 이쪽이 더 풍부.")

    YB_FULL = ROOT / "yb_mdd_or_full"
    if not (YB_FULL / "trades.csv").exists():
        st.info("양변기 v5 단독 풀백테 없음.")
        st.stop()

    # Last update timestamp
    last_update_file = YB_FULL / "last_update_at.txt"
    if last_update_file.exists():
        last_update = last_update_file.read_text().strip()
    else:
        last_update = "캐시 생성 후 미갱신"
    st.caption(f"📅 마지막 갱신: {last_update}")

    @st.cache_data
    def _load_full():
        trades = pd.read_csv(YB_FULL / "trades.csv")
        trades["date"] = pd.to_datetime(trades["date"])
        equity = pd.read_csv(YB_FULL / "equity.csv", index_col=0, parse_dates=True)
        alloc = pd.read_csv(YB_FULL / "alloc.csv", index_col=0, parse_dates=True)
        bench = pd.read_csv(YB_FULL / "bench.csv", index_col=0, parse_dates=True)
        return trades, equity, alloc, bench

    trades_all, equity_all, alloc_all, bench_all = _load_full()

    # ── Date range picker ──
    min_d = trades_all["date"].min().date()
    max_d = trades_all["date"].max().date()

    def _apply_preset(st_d, en_d):
        st.session_state["trade_from"] = pd.Timestamp(st_d).date()
        st.session_state["trade_to"] = pd.Timestamp(en_d).date()

    def _reset_dates():
        st.session_state["trade_from"] = min_d
        st.session_state["trade_to"] = max_d

    col_a, col_b, col_c = st.columns([2, 2, 1])
    with col_a:
        d_from = st.date_input("From", value=min_d, min_value=min_d, max_value=max_d, key="trade_from")
    with col_b:
        d_to = st.date_input("To", value=max_d, min_value=min_d, max_value=max_d, key="trade_to")
    with col_c:
        st.markdown("&nbsp;")
        st.button("Reset", on_click=_reset_dates)

    # Quick preset buttons
    st.markdown("**빠른 선택**")
    p1, p2, p3, p4, p5, p6, p7, p8 = st.columns(8)
    presets = [
        ("2018 Q4", "2018-09-01", "2019-01-15"),
        ("2020 Covid", "2020-01-02", "2020-05-31"),
        ("2022 폭락", "2022-01-01", "2022-12-31"),
        ("2024-08", "2024-07-15", "2024-09-15"),
        ("2025 관세", "2025-03-01", "2025-05-15"),
        ("최근 1년", (max_d - pd.Timedelta(days=365)).strftime("%Y-%m-%d"), str(max_d)),
        ("최근 3개월", (max_d - pd.Timedelta(days=90)).strftime("%Y-%m-%d"), str(max_d)),
        ("전체", str(min_d), str(max_d)),
    ]
    for col, (lbl, st_d, en_d) in zip([p1, p2, p3, p4, p5, p6, p7, p8], presets):
        col.button(lbl, key=f"preset_{lbl}", on_click=_apply_preset, args=(st_d, en_d))

    # Filter trades
    mask = (trades_all["date"] >= pd.Timestamp(d_from)) & (trades_all["date"] <= pd.Timestamp(d_to))
    trades_sl = trades_all[mask].copy()
    eq_sl = equity_all.loc[pd.Timestamp(d_from):pd.Timestamp(d_to)]
    bench_sl = bench_all.loc[pd.Timestamp(d_from):pd.Timestamp(d_to)]
    alloc_sl = alloc_all.loc[pd.Timestamp(d_from):pd.Timestamp(d_to)]

    if len(trades_sl) == 0 or len(eq_sl) == 0:
        st.info(f"선택 기간({d_from} ~ {d_to})에 거래 없음.")
        st.stop()

    # ── Period metrics — user_seed 기준으로 비례 환산 ──
    st.markdown("### 📊 기간 성과 요약")
    bt_start_eq = float(eq_sl["equity"].iloc[0])      # 백테 원본 시작 자본
    scale_yb = user_seed / bt_start_eq                 # 사용자 시드 / 백테 시작 자본
    start_eq = user_seed                                # 사용자가 지정한 시작 자본
    end_eq = float(eq_sl["equity"].iloc[-1]) * scale_yb
    period_dollar_pnl = end_eq - start_eq
    eq_norm = eq_sl["equity"] / bt_start_eq
    period_ret = float(eq_norm.iloc[-1] - 1)
    n_days = len(eq_sl)
    n_years = n_days / 252
    cagr = float(eq_norm.iloc[-1] ** (1/n_years) - 1) if n_years > 0 else 0
    cummax = eq_sl["equity"].cummax()
    dd = eq_sl["equity"] / cummax - 1
    mdd = float(dd.min())
    rets = eq_sl["equity"].pct_change().dropna()
    sharpe = float(rets.mean() / rets.std() * np.sqrt(252)) if rets.std() > 0 else 0
    bench_ret = float(bench_sl["close"].iloc[-1] / bench_sl["close"].iloc[0] - 1) if len(bench_sl) > 1 else 0

    # 거래 PnL/notional 비례 환산 (% 컬럼은 그대로 유지)
    trades_sl["pnl"] = trades_sl["pnl"] * scale_yb
    if "notional" in trades_sl.columns:
        trades_sl["notional"] = trades_sl["notional"] * scale_yb

    win_rate = float((trades_sl["pnl"] > 0).mean())
    gross_win = float(trades_sl.loc[trades_sl["pnl"] > 0, "pnl"].sum())
    gross_loss = float(-trades_sl.loc[trades_sl["pnl"] < 0, "pnl"].sum())
    pf = gross_win / gross_loss if gross_loss > 0 else float("inf")
    realized_pnl = float(trades_sl["pnl"].sum())

    # Row 1: 자본 흐름 (시작/종료/PnL $) — 사용자가 한눈에 보길 원한 부분
    st.markdown(f"**🪙 자본 흐름** ({d_from} → {d_to}, {n_days} 거래일)")
    cap1, cap2, cap3 = st.columns(3)
    cap1.metric("시작 자본", f"${start_eq:,.0f}")
    cap2.metric("종료 자본", f"${end_eq:,.0f}",
                f"{period_ret*100:+.1f}%")
    cap3.metric("기간 $ PnL",
                f"${period_dollar_pnl:+,.0f}",
                f"Realized: ${realized_pnl:+,.0f}")

    # Row 2: 수익률 metrics
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Return", fmt_pct(period_ret))
    c2.metric("CAGR (annualized)", fmt_pct(cagr))
    c3.metric("MDD", fmt_pct(mdd))
    c4.metric("Sharpe", fmt(sharpe))
    c5.metric("SOXL B&H", fmt_pct(bench_ret), f"Δ {fmt_pct(period_ret - bench_ret)}")
    c6.metric("거래수", f"{len(trades_sl):,}")

    # Row 3: 거래 통계
    c7, c8, c9, c10 = st.columns(4)
    c7.metric("Win Rate", f"{win_rate*100:.1f}%")
    c8.metric("Profit Factor", fmt(pf) if pf != float("inf") else "∞")
    c9.metric("Avg PnL/trade", f"${realized_pnl/len(trades_sl):,.0f}" if len(trades_sl)>0 else "—")
    c10.metric("Gross Win / Loss", f"${gross_win:,.0f} / ${gross_loss:,.0f}")

    # ── Equity curve — user_seed 기준 절대 $ ──
    st.markdown(f"### 📈 Equity Curve (선택 기간, ${user_seed:,.0f} 시드 기준)")
    chart_df = pd.DataFrame({
        "양변기 v5 ($)": (eq_sl["equity"] / bt_start_eq * user_seed).values,
        "SOXL B&H ($)": (bench_sl["close"] / bench_sl["close"].iloc[0] * user_seed).reindex(eq_sl.index).ffill().values,
    }, index=eq_sl.index)
    st.line_chart(chart_df)

    # ── Regime/alloc usage ──
    st.markdown("### 🎯 Active Long Alloc 분포")
    alloc_counts = alloc_sl["alloc"].round(2).value_counts(normalize=True).sort_index(ascending=False)
    alloc_df = pd.DataFrame({
        "Long Alloc": [f"{v*100:.0f}%" for v in alloc_counts.index],
        "Regime": ["BULL" if v >= 0.60 else "NEUTRAL" if v >= 0.40 else "BEAR" for v in alloc_counts.index],
        "Days %": [f"{p*100:.1f}%" for p in alloc_counts.values],
    })
    st.dataframe(alloc_df, use_container_width=True, hide_index=True)

    # ── Enrich trades with regime/alloc context + Korean reason text ──
    # 1) Merge alloc(day-level) into every trade row → regime context for entry day
    alloc_day = alloc_all["alloc"].rename("active_long_alloc")
    trades_sl = trades_sl.merge(
        alloc_day, left_on="date", right_index=True, how="left"
    )
    # 2) Regime label from active long_alloc
    def _regime(a):
        if pd.isna(a): return "—"
        if a >= 0.59: return "BULL"
        if a >= 0.39: return "NEUTRAL"
        return "BEAR"
    trades_sl["regime"] = trades_sl["active_long_alloc"].apply(_regime)

    # 3) Equity at trade date (post-EOD) for capital context — user_seed 기준으로 환산
    eq_lookup = equity_all["equity"]
    trades_sl["equity_eod"] = trades_sl["date"].map(eq_lookup) * scale_yb
    trades_sl["pnl_vs_equity"] = trades_sl["pnl"] / trades_sl["equity_eod"]

    # 4) SOXL B&H daily return on trade date (시장 흐름 컨텍스트)
    bench_ret_d = bench_all["close"].pct_change().rename("bench_day_ret")
    trades_sl = trades_sl.merge(bench_ret_d, left_on="date", right_index=True, how="left")

    # 5) Korean entry/exit reason strings
    LONG_TH = 0.015   # SOXL stop-buy 시가 +1.5%
    SHORT_TH = 0.060  # SOXS stop-buy 시가 +6.0%
    def _entry_reason(r):
        if r["leg"] == "LONG":
            return (f"[{r['regime']}] SOXL 시가+1.5% stop-buy 체결 "
                    f"(롱비중 {r['active_long_alloc']*100:.0f}% × 시드)")
        else:
            return (f"[{r['regime']}] SOXS 시가+6.0% stop-buy 체결 "
                    f"(숏헷지 40% 고정 비중)")
    def _exit_reason(r):
        et = r.get("exit_type", "")
        if et == "LOC":
            return "종가 양수 → 50% LOC 익절 청산"
        if et == "MOO_NEXT":
            return "익일 시가 MOO 청산 (잔여 50% 또는 손실 컷)"
        return str(et) if pd.notna(et) else "—"
    trades_sl["진입사유"] = trades_sl.apply(_entry_reason, axis=1)
    trades_sl["청산사유"] = trades_sl.apply(_exit_reason, axis=1)

    # 6) 기간 누적 PnL — 시작 자본 기준 매 거래 후 누적 이익 ($)
    trades_sl = trades_sl.sort_values("date").reset_index(drop=True)
    trades_sl["cum_period_pnl"] = trades_sl["pnl"].cumsum()
    trades_sl["equity_after_trade"] = start_eq + trades_sl["cum_period_pnl"]

    # ── Trade log ──
    st.markdown(f"### 📒 거래 내역 ({len(trades_sl):,} rows) — 사유·진행 포함")
    st.caption(f"💡 시작 자본 ${start_eq:,.0f} 기준 — '기간 누적 PnL' 컬럼이 매 거래 후 누적 이익을 보여줍니다 (= 거래 후 자본 − 시작 자본).")

    # Filter by leg / exit_type / regime / pnl
    f1, f2, f3, f4 = st.columns(4)
    leg_filter = f1.multiselect("Leg", options=sorted(trades_sl["leg"].unique()),
                                 default=sorted(trades_sl["leg"].unique()))
    if "exit_type" in trades_sl.columns:
        exit_opts = sorted(trades_sl["exit_type"].dropna().unique().tolist())
        exit_filter = f2.multiselect("Exit type", options=exit_opts, default=exit_opts)
    else:
        exit_filter = None
    regime_opts = sorted([r for r in trades_sl["regime"].unique() if r != "—"])
    regime_filter = f3.multiselect("Regime", options=regime_opts, default=regime_opts)
    pnl_filter = f4.radio("PnL", options=["전체", "수익만", "손실만"], horizontal=True)

    show_t = trades_sl[trades_sl["leg"].isin(leg_filter) & trades_sl["regime"].isin(regime_filter)]
    if exit_filter is not None and "exit_type" in show_t.columns:
        show_t = show_t[show_t["exit_type"].isin(exit_filter)]
    if pnl_filter == "수익만":
        show_t = show_t[show_t["pnl"] > 0]
    elif pnl_filter == "손실만":
        show_t = show_t[show_t["pnl"] < 0]

    # Display columns — 사유·진행 컬럼 포함
    display_cols = ["date", "regime", "leg"]
    if "ticker" in show_t.columns: display_cols.append("ticker")
    display_cols += ["entry_px", "exit_px"]
    if "exit_type" in show_t.columns: display_cols.append("exit_type")
    display_cols += ["qty", "notional", "pnl", "cum_period_pnl", "equity_after_trade",
                     "pnl_pct", "pnl_vs_equity",
                     "bench_day_ret", "진입사유", "청산사유"]
    display_cols = [c for c in display_cols if c in show_t.columns]
    show_disp = show_t[display_cols].copy()

    if "pnl_pct" in show_disp.columns:
        show_disp["pnl_pct"] = show_disp["pnl_pct"].apply(lambda x: f"{x*100:+.2f}%" if pd.notna(x) else "")
    if "pnl_vs_equity" in show_disp.columns:
        show_disp["pnl_vs_equity"] = show_disp["pnl_vs_equity"].apply(lambda x: f"{x*100:+.3f}%" if pd.notna(x) else "")
    if "bench_day_ret" in show_disp.columns:
        show_disp["bench_day_ret"] = show_disp["bench_day_ret"].apply(lambda x: f"{x*100:+.2f}%" if pd.notna(x) else "")
    if "entry_px" in show_disp.columns:
        show_disp["entry_px"] = show_disp["entry_px"].apply(lambda x: f"${x:.2f}")
    if "exit_px" in show_disp.columns:
        show_disp["exit_px"] = show_disp["exit_px"].apply(lambda x: f"${x:.2f}")
    if "pnl" in show_disp.columns:
        show_disp["pnl"] = show_disp["pnl"].apply(lambda x: f"${x:+,.2f}")
    if "cum_period_pnl" in show_disp.columns:
        show_disp["cum_period_pnl"] = show_disp["cum_period_pnl"].apply(lambda x: f"${x:+,.0f}")
    if "equity_after_trade" in show_disp.columns:
        show_disp["equity_after_trade"] = show_disp["equity_after_trade"].apply(lambda x: f"${x:,.0f}")
    if "qty" in show_disp.columns:
        show_disp["qty"] = show_disp["qty"].apply(lambda x: f"{x:,.2f}")
    if "notional" in show_disp.columns:
        show_disp["notional"] = show_disp["notional"].apply(lambda x: f"${x:,.0f}")
    show_disp["date"] = show_disp["date"].dt.strftime("%Y-%m-%d")
    show_disp = show_disp.rename(columns={
        "date": "날짜", "regime": "Regime", "leg": "방향",
        "entry_px": "진입가", "exit_px": "청산가", "exit_type": "청산타입",
        "qty": "수량", "notional": "Notional", "pnl": "거래 PnL",
        "cum_period_pnl": "기간 누적 PnL", "equity_after_trade": "거래 후 자본",
        "pnl_pct": "PnL%", "pnl_vs_equity": "Equity영향%",
        "bench_day_ret": "SOXL 당일%",
    })

    # Pagination — large tables can be slow
    rows_per_page = 100
    n_pages = max(1, (len(show_disp) + rows_per_page - 1) // rows_per_page)
    page = st.number_input(f"Page (총 {len(show_disp):,} rows, {n_pages} pages)",
                            min_value=1, max_value=n_pages, value=1) if n_pages > 1 else 1
    start_idx = (page - 1) * rows_per_page
    st.dataframe(show_disp.iloc[start_idx:start_idx + rows_per_page],
                  use_container_width=True, hide_index=True, height=480)

    # CSV download (사유 포함)
    csv_bytes = show_t.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label=f"💾 CSV 다운로드 (사유 포함, {len(show_t):,} rows)",
        data=csv_bytes,
        file_name=f"yb_mdd_or_trades_{d_from}_{d_to}.csv",
        mime="text/csv"
    )

    # ── 단일 거래 상세 패널 ──
    st.markdown("### 🔬 거래 상세 보기 — 사유·진행 풀스택")
    st.caption("위 표에서 보고 싶은 거래의 인덱스(번호)를 입력하면 진입/보유/청산 진행과 자본 흐름을 보여줍니다.")
    if len(show_t) > 0:
        idx_min, idx_max = int(show_t.index.min()), int(show_t.index.max())
        sel_idx = st.number_input(
            f"거래 인덱스 (선택 가능 범위 {idx_min} ~ {idx_max})",
            min_value=idx_min, max_value=idx_max, value=idx_min, step=1, key="trade_detail_idx",
        )
        if sel_idx in show_t.index:
            tr = show_t.loc[sel_idx]
            tr_date = tr["date"]
            # equity context: 5 영업일 전 ~ 5 영업일 후
            eq_around = equity_all.loc[
                tr_date - pd.Timedelta(days=10): tr_date + pd.Timedelta(days=10)
            ]
            bench_around = bench_all.loc[
                tr_date - pd.Timedelta(days=10): tr_date + pd.Timedelta(days=10)
            ]
            alloc_around = alloc_all.loc[
                tr_date - pd.Timedelta(days=10): tr_date + pd.Timedelta(days=10)
            ]

            dcol1, dcol2 = st.columns([1, 1])
            with dcol1:
                st.markdown(f"**🗓 {tr_date.strftime('%Y-%m-%d (%A)')}**")
                st.markdown(f"- **Regime**: `{tr['regime']}` (active long alloc {tr['active_long_alloc']*100:.0f}%)")
                st.markdown(f"- **방향**: `{tr['leg']}`")
                st.markdown(f"- **진입가 → 청산가**: `${tr['entry_px']:.4f}` → `${tr['exit_px']:.4f}` "
                            f"(`{(tr['exit_px']/tr['entry_px']-1)*100:+.2f}%`)")
                st.markdown(f"- **수량**: `{tr['qty']:,.2f}` 주, **Notional**: `${tr['notional']:,.0f}`")
                st.markdown(f"- **청산 타입**: `{tr['exit_type']}`")
                st.markdown(f"- **PnL**: `${tr['pnl']:+,.2f}` (`{tr['pnl_pct']*100:+.2f}%` of notional, "
                            f"`{tr['pnl']/tr['equity_eod']*100:+.3f}%` of equity)")
            with dcol2:
                st.markdown("**📜 사유·진행 풀스택**")
                steps = []
                # 1) 시초가 시점: regime check & threshold
                if tr["leg"] == "LONG":
                    open_est = tr["entry_px"] / (1 + LONG_TH)
                    steps.append(f"**1. 시초가** — SOXL 추정 시가 ≈ `${open_est:.4f}` (entry / 1.015 역산)")
                    steps.append(f"**2. 주문** — 시가 +1.5% stop-buy 등록 → `${tr['entry_px']:.4f}` 이상 시 매수")
                    steps.append(f"**3. Regime 확인** — `{tr['regime']}` → 롱 비중 `{tr['active_long_alloc']*100:.0f}%` 적용 (Consensus 2-of-3 + fast BEAR override)")
                    steps.append(f"**4. 체결** — `${tr['entry_px']:.4f}` × {tr['qty']:,.2f} 주 ≈ ${tr['notional']:,.0f}")
                else:
                    open_est = tr["entry_px"] / (1 + SHORT_TH)
                    steps.append(f"**1. 시초가** — SOXS 추정 시가 ≈ `${open_est:.4f}` (entry / 1.06 역산)")
                    steps.append(f"**2. 주문** — 시가 +6.0% stop-buy 등록 (SOXS 매수 = 인버스 헷지)")
                    steps.append(f"**3. Regime 확인** — `{tr['regime']}` (숏 헷지는 alloc 무관 40% 고정)")
                    steps.append(f"**4. 체결** — `${tr['entry_px']:.4f}` × {tr['qty']:,.2f} 주 ≈ ${tr['notional']:,.0f}")
                # 5) 보유 중
                steps.append(f"**5. 보유** — 당일 SOXL B&H 일간 수익률 `{tr['bench_day_ret']*100:+.2f}%`")
                # 6) 청산
                if tr["exit_type"] == "LOC":
                    steps.append(f"**6. 청산 사유** — 종가가 진입가보다 양수 → 50% LOC 익절. "
                                 f"청산가 `${tr['exit_px']:.4f}` (LOC 종가)")
                elif tr["exit_type"] == "MOO_NEXT":
                    steps.append(f"**6. 청산 사유** — 종가 미달 또는 잔여 50% → 익일 시가 MOO 청산. "
                                 f"청산가 `${tr['exit_px']:.4f}` (다음 영업일 시가)")
                else:
                    steps.append(f"**6. 청산** — 청산가 `${tr['exit_px']:.4f}` ({tr['exit_type']})")
                # 7) 결과
                arrow = "🟢" if tr["pnl"] >= 0 else "🔴"
                steps.append(f"**7. 결과** {arrow} PnL `${tr['pnl']:+,.2f}` "
                             f"(equity `${tr['equity_eod']:,.0f}` 기준 `{tr['pnl']/tr['equity_eod']*100:+.3f}%`)")
                for s in steps:
                    st.markdown(f"- {s}")

            # mini equity chart around trade date with marker
            if len(eq_around) > 1:
                st.markdown("**📈 ±10 영업일 equity / SOXL B&H (trade 시점 ▼)**")
                mini = pd.DataFrame({
                    "Equity (정규화)": (eq_around["equity"] / eq_around["equity"].iloc[0] * 100).values,
                    "SOXL B&H (정규화)": (bench_around["close"] / bench_around["close"].iloc[0] * 100)
                        .reindex(eq_around.index).ffill().values,
                }, index=eq_around.index)
                st.line_chart(mini)
                st.caption(f"진입일 {tr_date.strftime('%Y-%m-%d')} | 기간 평균 long_alloc "
                           f"{alloc_around['alloc'].mean()*100:.0f}%")

    # ── 일자별 chronological progression ──
    st.markdown("### 📆 일자별 진행 타임라인")
    st.caption("선택 기간 내 각 영업일별로 발생한 거래·regime·equity 흐름을 시간 순으로 정리합니다.")
    daily_view_n = st.slider("표시할 최근 영업일 수", min_value=10, max_value=min(250, max(10, len(eq_sl))),
                              value=min(60, len(eq_sl)), step=10, key="daily_view_n")
    eq_recent = eq_sl.tail(daily_view_n)
    daily_rows = []
    for dt, row in eq_recent.iterrows():
        day_trades = show_t[show_t["date"] == dt]
        n_long = (day_trades["leg"] == "LONG").sum()
        n_short = (day_trades["leg"] == "SHORT").sum()
        day_pnl = day_trades["pnl"].sum()
        prev_eq = eq_lookup.shift(1).get(dt)
        day_ret = (row["equity"] / prev_eq - 1) if pd.notna(prev_eq) else None
        a = alloc_all["alloc"].get(dt)
        events = []
        if n_long: events.append(f"LONG×{n_long}")
        if n_short: events.append(f"SHORT×{n_short}")
        if not events: events.append("관망")
        # exit type breakdown
        if len(day_trades):
            et_counts = day_trades["exit_type"].value_counts().to_dict()
            et_str = ", ".join(f"{k}×{v}" for k, v in et_counts.items())
        else:
            et_str = "—"
        daily_rows.append({
            "날짜": dt.strftime("%Y-%m-%d (%a)"),
            "Regime": _regime(a),
            "Long alloc": f"{a*100:.0f}%" if pd.notna(a) else "—",
            "이벤트": " / ".join(events),
            "청산구성": et_str,
            "당일 PnL": f"${day_pnl:+,.2f}",
            "Equity": f"${row['equity']:,.0f}",
            "당일 수익률": f"{day_ret*100:+.2f}%" if day_ret is not None else "—",
        })
    daily_df = pd.DataFrame(daily_rows).iloc[::-1]  # 최신이 위로
    st.dataframe(daily_df, use_container_width=True, hide_index=True, height=420)

    # ── 일자별 PnL 막대그래프 ──
    st.markdown("### 📊 일자별 실현 PnL & 거래 빈도")
    daily_pnl = trades_sl.groupby(trades_sl["date"].dt.date)["pnl"].sum()
    daily_cnt = trades_sl.groupby(trades_sl["date"].dt.date)["pnl"].size()
    bc1, bc2 = st.columns(2)
    with bc1:
        st.markdown("**일별 실현 PnL ($)**")
        st.bar_chart(daily_pnl)
    with bc2:
        st.markdown("**일별 체결 건수**")
        st.bar_chart(daily_cnt)

    # ── PnL distribution ──
    st.markdown("### 📊 거래 PnL 분포")
    cc1, cc2 = st.columns(2)
    with cc1:
        st.markdown("**Leg별 PnL 합계**")
        leg_pnl = trades_sl.groupby("leg").agg(
            count=("pnl", "size"),
            total_pnl=("pnl", "sum"),
            avg_pnl=("pnl", "mean"),
            win_rate=("pnl", lambda x: (x > 0).mean()),
        ).round(2)
        leg_pnl["total_pnl"] = leg_pnl["total_pnl"].apply(lambda x: f"${x:+,.0f}")
        leg_pnl["avg_pnl"] = leg_pnl["avg_pnl"].apply(lambda x: f"${x:+,.0f}")
        leg_pnl["win_rate"] = leg_pnl["win_rate"].apply(lambda x: f"{x*100:.1f}%")
        st.dataframe(leg_pnl, use_container_width=True)
    with cc2:
        st.markdown("**PnL 히스토그램**")
        pnl_series = trades_sl["pnl"].clip(lower=trades_sl["pnl"].quantile(0.01),
                                            upper=trades_sl["pnl"].quantile(0.99))  # clip 1% tails
        hist_df = pd.DataFrame({"pnl": pnl_series})
        st.bar_chart(hist_df["pnl"].value_counts(bins=30).sort_index())


# ───────────────────────────────────────────────────────────
# TAB 3: Stress Tests
# ───────────────────────────────────────────────────────────
with tabs[2]:
    sub = st.tabs(['🛡️ BUBE V6 위기 (PRIMARY)', '📜 양변기 v5 — 16년 일봉', '⏱️ 8년 분봉 stress'])

    # — sub[0] 🛡️ BUBE V6 위기 (PRIMARY) —
    with sub[0]:
        # ── Section 1: BUBE rotation V6 crisis stress (PRIMARY) ──
        st.subheader("🛡️ BUBE V6 Crisis Stress (2026-05-23)")
        st.caption("V_bear_cap_comprehensive — 5개 위기 × T1 (NEUTRAL→황금변기) / T2GE (BUBE GOLD_ESCAPE) × bear_max 변형")

        def _bm_label(x):
            if pd.isna(x) or str(x).lower() in ("none", "nan"):
                return "baseline"
            return f"bm{int(float(x))}"

        v6_path = ROOT / "V_bear_cap" / "V6_crisis_stress.csv"
        if v6_path.exists():
            v6 = pd.read_csv(v6_path)

            # Pivot: rows = crisis, cols = spec (tier+bear_max), values = total_ret
            v6["spec"] = v6["tier"].astype(str) + "_" + v6["bear_max"].apply(_bm_label)
            pivot_ret = v6.pivot_table(index="crisis", columns="spec", values="total_ret", aggfunc="first")
            pivot_mdd = v6.pivot_table(index="crisis", columns="spec", values="mdd", aggfunc="first")

            # Highlighted view: T1 baseline vs T1 bm60 vs T2GE baseline vs T2GE bm90
            key_cols = ["T1_baseline", "T1_bm60", "T2GE_baseline", "T2GE_bm90"]
            avail_cols = [c for c in key_cols if c in pivot_ret.columns]
            if avail_cols:
                display_df = pd.DataFrame(index=pivot_ret.index)
                for col in avail_cols:
                    display_df[f"{col} Ret"] = pivot_ret[col].apply(lambda x: fmt_pct(x) if pd.notna(x) else "—")
                    display_df[f"{col} MDD"] = pivot_mdd[col].apply(lambda x: fmt_pct(x) if pd.notna(x) else "—")
                st.dataframe(display_df, use_container_width=True)

                # Alpha vs baseline
                st.markdown("### Δ Return: bear_cap escape valve 알파")
                alpha_rows = []
                for crisis in pivot_ret.index:
                    row = {"Crisis": crisis}
                    if "T1_baseline" in pivot_ret.columns and "T1_bm60" in pivot_ret.columns:
                        delta = pivot_ret.loc[crisis, "T1_bm60"] - pivot_ret.loc[crisis, "T1_baseline"]
                        row["T1 bm60 Δ"] = f"{delta*100:+.1f}%p" if abs(delta) > 0.001 else "0 (escape 미발동)"
                    if "T2GE_baseline" in pivot_ret.columns and "T2GE_bm90" in pivot_ret.columns:
                        delta = pivot_ret.loc[crisis, "T2GE_bm90"] - pivot_ret.loc[crisis, "T2GE_baseline"]
                        row["T2GE bm90 Δ"] = f"{delta*100:+.1f}%p" if abs(delta) > 0.001 else "0 (escape 미발동)"
                    if "T2GE_baseline" in pivot_ret.columns and "T2GE_bm60" in pivot_ret.columns:
                        delta = pivot_ret.loc[crisis, "T2GE_bm60"] - pivot_ret.loc[crisis, "T2GE_baseline"]
                        row["T2GE bm60 Δ (위험!)"] = f"{delta*100:+.1f}%p" if abs(delta) > 0.001 else "0"
                    alpha_rows.append(row)
                st.dataframe(pd.DataFrame(alpha_rows), use_container_width=True, hide_index=True)

                st.info(
                    "**핵심**: 5 위기 중 **2022_full만 escape 발동**. T1 bm60 +3.5%p, T2GE bm90 +5%p 알파. "
                    "T2GE **bm60는 절대 금지** (2022 -10.9%p 폭망)."
                )

            with st.expander("전체 변형 (T1 bm30/45/60/None, T2GE bm60/90/None)"):
                st.dataframe(v6.round(4), use_container_width=True, hide_index=True)
        else:
            st.warning("V_bear_cap/V6_crisis_stress.csv 없음")

    # — sub[1] 📜 양변기 v5 — 16년 일봉 —
    with sub[1]:
        # ── Section 2: 양변기 v5 단독 16년 일봉 (BEAR slot 컴포넌트) ──
        st.subheader("📜 양변기 v5 단독 — BEAR slot 컴포넌트 (16년 일봉)")
        st.caption("ℹ️ BUBE의 BEAR regime sub-strategy 단독 백테. 참고용.")
        crash_rows = [
            ("2011 Euro crisis", -53.2, -6.4, -19.5, -0.44),
            ("2015-16 China", -33.1, +6.8, -10.1, 1.04),
            ("2018 Q4", -47.4, +1.7, -7.4, 0.64),
            ("2020 Covid", -47.2, +15.8, -15.7, 2.79),
            ("2022 full year", -86.6, +25.8, -13.1, 1.99),
            ("2024-08 Aug shock", -47.9, +8.0, -5.1, 11.52),
            ("2025 Tariff", -9.9, +5.0, -8.6, 3.23),
        ]
        df_crash = pd.DataFrame(crash_rows, columns=["Period", "B&H Ret %", "YB v5 Ret %", "YB v5 MDD %", "YB v5 Calmar"])
        df_crash["Outcome"] = df_crash["YB v5 Ret %"].apply(lambda x: "✅ 양수" if x > 0 else "⚠️ 손실")
        st.dataframe(df_crash, use_container_width=True, hide_index=True)

    # — sub[2] ⏱️ 8년 분봉 stress —
    with sub[2]:
        st.subheader("8년 분봉 stress (양변기 v5 단독, IBKR)")
        extended = load_json(ROOT / "extended_stress_oos" / "summary.json")
        if extended:
            # Show only 2022/Covid/2018 for key crashes (분봉)
            for period_key, period_label in [
                ("2018_Q4", "2018 Q4 (분봉)"),
                ("2020_Covid", "2020 Covid (분봉)"),
                ("2022_full", "2022 (분봉)"),
                ("Full_8yr", "Full 8년 (2018-06 ~ 2026-05)"),
            ]:
                if period_key in extended:
                    rows = []
                    for strat, s in extended[period_key].items():
                        rows.append({
                            "Strategy": strat,
                            "CAGR": fmt_pct(s.get("cagr")),
                            "MDD": fmt_pct(s.get("mdd")),
                            "Sharpe": fmt(s.get("sharpe")),
                            "Calmar": fmt(s.get("calmar")),
                        })
                    with st.expander(f"📊 {period_label}", expanded=(period_key == "Full_8yr")):
                        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("백테 결과 파일 없음. extended_stress_oos.py 먼저 실행 필요.")

# ───────────────────────────────────────────────────────────
# TAB 4: Bootstrap
# ───────────────────────────────────────────────────────────
with tabs[3]:
    sub = st.tabs(['🎲 BUBE V3 (6000 paths, PRIMARY)', '📜 양변기 v5 — 5000 paths (참고용)'])

    # — sub[0] 🎲 BUBE V3 (6000 paths, PRIMARY) —
    with sub[0]:
        # ── Section 1: BUBE rotation V3 bootstrap (PRIMARY) ──
        st.subheader("🎲 BUBE V3 Bootstrap — 6,000 paths (2026-05-23)")
        st.caption("V_bear_cap_comprehensive — 4 spec × 11 metric × 6000 stationary block bootstrap paths")

        v3_path = ROOT / "V_bear_cap" / "V3_bootstrap.csv"
        if v3_path.exists():
            v3 = pd.read_csv(v3_path)

            # Spec ordering: highlight T2GE bm90 + show others
            spec_order = ["T2GE_bm90", "T2GE_None", "T1_bm60", "T1_None", "T2GE_bm60", "T1_bm45", "T1_bm30"]
            v3["spec_rank"] = v3["spec"].map({s: i for i, s in enumerate(spec_order)}).fillna(99)
            v3 = v3.sort_values("spec_rank").drop(columns="spec_rank")

            rows = []
            for _, r in v3.iterrows():
                star = " 🏆" if r["spec"] == "T2GE_bm90" else (" ⚠️" if r["spec"] == "T2GE_bm60" else "")
                rows.append({
                    "Spec": f"{r['spec']}{star}",
                    "Cal p05": fmt(r["cal_p05"]),
                    "Cal p50": fmt(r["cal_p50"]),
                    "Cal p95": fmt(r["cal_p95"]),
                    "CAGR p50": fmt_pct(r["cagr_p50"]),
                    "MDD p50": fmt_pct(r["mdd_p50"]),
                    "P(MDD<-30%)": f"{r['p_mdd_under_30p']*100:.1f}%",
                    "P(MDD<-40%)": f"{r['p_mdd_under_40p']*100:.1f}%",
                    "P(Cal>2)": f"{r['p_cal_over_2']*100:.1f}%",
                    "P(Cal>3)": f"{r['p_cal_over_3']*100:.1f}%",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            # Key comparisons
            col1, col2 = st.columns(2)
            t1_b = v3[v3["spec"] == "T1_None"].iloc[0] if (v3["spec"] == "T1_None").any() else None
            t1_60 = v3[v3["spec"] == "T1_bm60"].iloc[0] if (v3["spec"] == "T1_bm60").any() else None
            t2_b = v3[v3["spec"] == "T2GE_None"].iloc[0] if (v3["spec"] == "T2GE_None").any() else None
            t2_90 = v3[v3["spec"] == "T2GE_bm90"].iloc[0] if (v3["spec"] == "T2GE_bm90").any() else None

            if t1_b is not None and t1_60 is not None:
                col1.markdown("### T1 (NEUTRAL→황금변기)")
                col1.metric("Cal p50 (baseline → bm60)",
                            f"{t1_b['cal_p50']:.2f} → {t1_60['cal_p50']:.2f}",
                            f"+{t1_60['cal_p50']-t1_b['cal_p50']:.2f}")
                col1.metric("P(Cal>3)",
                            f"{t1_b['p_cal_over_3']*100:.1f}% → {t1_60['p_cal_over_3']*100:.1f}%",
                            f"+{(t1_60['p_cal_over_3']-t1_b['p_cal_over_3'])*100:.1f}%p")

            if t2_b is not None and t2_90 is not None:
                col2.markdown("### T2GE (BUBE GOLD_ESCAPE)")
                col2.metric("Cal p50 (baseline → bm90)",
                            f"{t2_b['cal_p50']:.2f} → {t2_90['cal_p50']:.2f}",
                            f"+{t2_90['cal_p50']-t2_b['cal_p50']:.2f}")
                col2.metric("P(Cal>3)",
                            f"{t2_b['p_cal_over_3']*100:.1f}% → {t2_90['p_cal_over_3']*100:.1f}%",
                            f"+{(t2_90['p_cal_over_3']-t2_b['p_cal_over_3'])*100:.1f}%p")

            st.info(
                "**Free lunch 확인**: T2GE bm90이 baseline 대비 Cal 우월 + MDD risk 동등 (P(MDD<-30%) 88.0% vs 87.1%). "
                "🏆 = production 추천, ⚠️ = V6 stress -10.9%p 폭망 위험으로 절대 금지."
            )

            # V9 drawdown duration supplement
            v9_path = ROOT / "V_bear_cap" / "V9_drawdown.csv"
            if v9_path.exists():
                v9 = pd.read_csv(v9_path)
                st.markdown("### V9 Drawdown Duration")
                v9_disp = v9.copy()
                v9_disp["spec"] = v9_disp["tier"].astype(str) + "_" + v9_disp["bear_max"].apply(_bm_label)
                v9_disp = v9_disp[["spec","underwater_pct","longest_underwater_days","mdd","worst_day_pct"]]
                v9_disp["underwater_pct"] = v9_disp["underwater_pct"].apply(lambda x: f"{x*100:.1f}%")
                v9_disp["mdd"] = v9_disp["mdd"].apply(fmt_pct)
                v9_disp["worst_day_pct"] = v9_disp["worst_day_pct"].apply(fmt_pct)
                v9_disp.columns = ["Spec", "Underwater %", "Longest UW (days)", "MDD", "Worst day"]
                st.dataframe(v9_disp, use_container_width=True, hide_index=True)
                st.caption("T1 bm60 longest UW **246d → 156d (-90일, -37%)**. MDD 동일하지만 회복 속도 대폭 상승.")
        else:
            st.warning("V_bear_cap/V3_bootstrap.csv 없음")

    # — sub[1] 📜 양변기 v5 — 5000 paths (참고용) —
    with sub[1]:
        st.subheader("📜 양변기 v5 단독 — BEAR slot 컴포넌트 5,000 paths (참고용)")
        st.caption("ℹ️ BUBE의 BEAR regime sub-strategy 단독 bootstrap. BUBE rotation 전체와는 다름.")
        bs = load_json(ROOT / "bootstrap_results" / "summary.json")
        if bs:
            rows = []
            for strat, s in bs.items():
                rows.append({
                    "Strategy": strat,
                    "CAGR median": fmt_pct(s["cagr"]["median"]),
                    "CAGR 95% lo": fmt_pct(s["cagr"]["ci_2.5"]),
                    "CAGR 95% hi": fmt_pct(s["cagr"]["ci_97.5"]),
                    "MDD median": fmt_pct(s["mdd"]["median"]),
                    "MDD worst (95%)": fmt_pct(s["mdd"]["ci_2.5"]),
                    "Calmar median": fmt(s["calmar"]["median"]),
                    "Calmar 95% lo": fmt(s["calmar"]["ci_2.5"]),
                    "Calmar 95% hi": fmt(s["calmar"]["ci_97.5"]),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            st.markdown("---")
            st.subheader("실패 확률 (5,000 path 중)")
            prob_rows = []
            for strat in bs:
                # Re-read paths CSV for prob calc
                paths_csv = ROOT / "bootstrap_results" / f"paths_{strat}.csv"
                if paths_csv.exists():
                    pd_df = pd.read_csv(paths_csv)
                    prob_rows.append({
                        "Strategy": strat,
                        "P(CAGR<0)": f"{(pd_df['cagr']<0).mean()*100:.1f}%",
                        "P(MDD<-40%)": f"{(pd_df['mdd']<-0.40).mean()*100:.1f}%",
                        "P(Calmar<1)": f"{(pd_df['calmar']<1).mean()*100:.1f}%",
                        "P(Calmar<2)": f"{(pd_df['calmar']<2).mean()*100:.1f}%",
                    })
            st.dataframe(pd.DataFrame(prob_rows), use_container_width=True, hide_index=True)
        else:
            st.info("Bootstrap 결과 없음. bootstrap_validation.py 먼저 실행 필요.")

# ───────────────────────────────────────────────────────────
# TAB 5: Year-by-Year
# ───────────────────────────────────────────────────────────
with tabs[4]:
    sub = st.tabs(['📈 BUBE 8년 Equity Curve', '📅 BUBE V8 Yearly (PRIMARY)', '📜 양변기 v5 — 16년 yearly', '🌐 Cross-Asset 일반화'])

    # — sub[0] 📈 BUBE 8년 Equity Curve —
    with sub[0]:
        # ── Section 0: BUBE rotation 8년 equity curve (line chart) ──
        st.subheader("📈 BUBE Rotation 8년 Equity Curve (2018-06 ~ 2026-05)")
        st.caption("V_bear_cap_comprehensive _cache_eq.pkl 기반 sub-strategy equities × regime series 합성 ($100K seed)")

        eq_path = ROOT / "V_bear_cap" / "bube_equity.csv"
        if eq_path.exists():
            eq_df = pd.read_csv(eq_path, parse_dates=["date"], index_col="date")

            # Final equity summary
            final = eq_df.iloc[-1]
            col_show = ["t2ge_bm90", "t2ge_baseline", "t1_bm60", "t1_baseline", "bench"]
            labels = {
                "t2ge_bm90": "🏆 BUBE T2GE bm90",
                "t2ge_baseline": "T2GE baseline (no escape)",
                "t1_bm60": "T1 bm60",
                "t1_baseline": "T1 baseline",
                "bench": "SOXL B&H",
            }

            # Headline metrics row
            c1, c2, c3, c4, c5 = st.columns(5)
            seed = 100_000.0
            for col, ccol in zip(col_show, [c1, c2, c3, c4, c5]):
                v = final[col]
                pct = (v/seed - 1) * 100
                display_v = f"${v/1e6:.2f}M" if v >= 1e6 else (f"${v/1e3:.1f}K" if v >= 1000 else f"${v:,.0f}")
                ccol.metric(labels[col], display_v, f"{pct:+,.0f}%")

            # Line chart — log scale for compounding visibility
            chart_df = eq_df[col_show].rename(columns=labels)
            st.line_chart(chart_df, height=400)
            st.caption("ℹ️ SOXL B&H 8년 -100% (3x daily leverage drift). BUBE rotation 4 변형 모두 살아남음.")

            # Sub-strategy breakdown
            with st.expander("Sub-strategy 단독 equity (롱/양/황금변기 8년 단독 백테)"):
                sub_df = eq_df[["longbyungi", "yangbyungi", "goldenbyungi", "bench"]].rename(columns={
                    "longbyungi": "롱변기 단독",
                    "yangbyungi": "양변기 v5 단독",
                    "goldenbyungi": "황금변기 단독",
                    "bench": "SOXL B&H",
                })
                st.line_chart(sub_df, height=350)
                st.caption(
                    "각 sub-strategy를 8년 내내 단독 실행한 가상 equity. 실제 BUBE에서는 regime에 따라 매일 switching. "
                    "롱변기 단독이 가장 폭발적이지만 BEAR에서 무방비 — 통합 시 양변기/황금변기가 BEAR 보호."
                )

            st.markdown("---")
            st.warning(
                "⚠️ **정직한 관찰** — 단일 8년 실현 path에서는 T2GE bm90 (BUBE) < T2GE baseline. "
                "Bootstrap 6,000 paths median에서는 bm90이 baseline 대비 Cal +0.05 우위지만 단일 path에서는 escape 발동 시점 "
                "(2020 Covid, 2022 후반) 직후 longbyungi가 더 좋았던 노이즈. **8년 표본 escape 발동 2회는 통계적으로 약한 증거** — "
                "future-proof 확신엔 부족. 메모리 `project_strategies.md` V_bear_cap 약점 섹션 참조."
            )
        else:
            st.warning("V_bear_cap/bube_equity.csv 없음 — compute_bube_equity.py 먼저 실행 필요")

    # — sub[1] 📅 BUBE V8 Yearly (PRIMARY) —
    with sub[1]:
        # ── Section 1: BUBE V8 yearly breakdown ──
        st.subheader("📅 BUBE V8 Yearly (2018-2026, 9년)")
        st.caption("V_bear_cap_comprehensive — T1 / T2GE × bear_max 변형 연도별 수익률 + escape 발동 일수")

        v8_path = ROOT / "V_bear_cap" / "V8_yearly.csv"
        if v8_path.exists():
            v8 = pd.read_csv(v8_path)
            # Normalize bear_max
            v8["bm_label"] = v8["bear_max"].apply(_bm_label)
            v8["spec"] = v8["tier"].astype(str) + "_" + v8["bm_label"]

            # Focus specs: T1_baseline, T1_bm60, T2GE_baseline, T2GE_bm90
            focus = ["T1_baseline", "T1_bm60", "T2GE_baseline", "T2GE_bm90"]
            v8f = v8[v8["spec"].isin(focus)].copy()
            # Pivot ret
            pivot_ret = v8f.pivot_table(index="year", columns="spec", values="ret", aggfunc="first")
            pivot_esc = v8f.pivot_table(index="year", columns="spec", values="escape_days", aggfunc="first")

            # Display
            rows = []
            for yr in pivot_ret.index:
                row = {"Year": int(yr)}
                for spec in focus:
                    if spec in pivot_ret.columns:
                        ret = pivot_ret.loc[yr, spec]
                        esc = pivot_esc.loc[yr, spec] if spec in pivot_esc.columns else 0
                        val = fmt_pct(ret) if pd.notna(ret) else "—"
                        if pd.notna(esc) and esc > 0 and "bm" in spec:
                            val += f" ⚡{int(esc)}d"
                        row[spec] = val
                rows.append(row)
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            st.caption("⚡ = bear_cap escape valve 발동 일수 (해당 연도 BUBE 효과 발생)")

            # Cumulative + alpha
            st.markdown("### 누적 수익 (compound)")
            cum_rows = []
            for spec in focus:
                if spec in pivot_ret.columns:
                    cum = (1 + pivot_ret[spec].fillna(0)).prod() - 1
                    cum_rows.append({"Spec": spec, "9년 누적 ret": fmt_pct(cum)})
            st.dataframe(pd.DataFrame(cum_rows), use_container_width=True, hide_index=True)

            # Highlight escape-active years
            active_years = v8f[(v8f["bm_label"] != "baseline") & (v8f["escape_days"] > 0)]
            if not active_years.empty:
                st.markdown("### Escape valve 발동 연도")
                disp = active_years[["tier","bm_label","year","ret","escape_days"]].copy()
                disp["ret"] = disp["ret"].apply(fmt_pct)
                disp.columns = ["Tier", "bear_max", "Year", "Return", "Escape days"]
                st.dataframe(disp, use_container_width=True, hide_index=True)
                st.info(
                    "**8년 표본에서 escape 발동 단 2회** (2020 Covid V-rebound, 2022 폭락 후반 relief rally). "
                    "V8에서 발동 해 모두 양수 alpha — 미발동 해는 baseline과 동일 (free lunch 구조)."
                )

            with st.expander("전체 변형 (T1 bm30/45/60/None, T2GE bm60/90/None)"):
                v8_disp = v8.copy()
                v8_disp["ret"] = v8_disp["ret"].apply(fmt_pct)
                v8_disp["mdd"] = v8_disp["mdd"].apply(fmt_pct)
                st.dataframe(v8_disp[["tier","bm_label","year","ret","mdd","escape_days"]],
                             use_container_width=True, hide_index=True)
        else:
            st.warning("V_bear_cap/V8_yearly.csv 없음")

    # — sub[2] 📜 양변기 v5 — 16년 yearly —
    with sub[2]:
        # ── Section 2: 양변기 v5 단독 16년 일봉 (참고용) ──
        st.subheader("📜 양변기 v5 단독 — BEAR slot 16년 일봉 (참고용)")
        st.caption("ℹ️ BUBE의 BEAR regime sub-strategy 단독. BUBE rotation 전체와는 다름.")
        extra = load_json(ROOT / "yb_mdd_or_extra" / "summary.json")
        if extra and "daily_16yr" in extra:
            yearly = extra["daily_16yr"]["yearly"]
            rows = []
            for y_str, r in sorted(yearly.items()):
                rows.append({
                    "Year": int(y_str),
                    "YB Return": fmt_pct(r.get("return")),
                    "YB MDD": fmt_pct(r.get("mdd")),
                    "YB Calmar": fmt(r.get("calmar")),
                    "B&H Return": fmt_pct(r.get("bench_return")),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            full = extra["daily_16yr"]["full"]
            st.markdown("### 16년 종합")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("CAGR", fmt_pct(full.get("cagr")))
            c2.metric("MDD", fmt_pct(full.get("mdd")))
            c3.metric("Sharpe", fmt(full.get("sharpe")))
            c4.metric("Total Return", fmt_pct(full.get("total_return")))
        else:
            st.info("yb_mdd_or_extra/summary.json 없음.")

    # — sub[3] 🌐 Cross-Asset 일반화 —
    with sub[3]:
        st.subheader("Cross-Asset 일반화 (분봉 5.8년)")
        if extra and "cross_asset" in extra:
            rows = [{
                "Pair": r["pair"], "Spec": r["note"],
                "CAGR": fmt_pct(r.get("cagr")),
                "MDD": fmt_pct(r.get("mdd")),
                "Sharpe": fmt(r.get("sharpe")),
                "Calmar": fmt(r.get("calmar")),
                "Alpha": fmt_pct(r.get("alpha"))
            } for r in extra["cross_asset"]]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            st.markdown("**결론**: SOXL/SOXS만 Calmar 2.91. TQQQ/TECL은 자산별 튜닝해도 1/3 수준.")

# ───────────────────────────────────────────────────────────
# TAB 6: Walk-Forward + OOS
# ───────────────────────────────────────────────────────────
with tabs[5]:
    sub = st.tabs(['🔬 BUBE V5 IS/OOS (PRIMARY)', '📜 양변기 v5 — Walk-Forward', '🧪 OOS Train/Test split'])

    # — sub[0] 🔬 BUBE V5 IS/OOS (PRIMARY) —
    with sub[0]:
        # ── Section 1: BUBE V5 IS/OOS 4 splits (PRIMARY) ──
        st.subheader("🔬 BUBE V5 IS/OOS 4 splits — 과적합 검증")
        st.caption("V_bear_cap_comprehensive — 4가지 train/test 분할 × 4 specs. OOS Calmar > IS면 과적합 없음.")

        v5_path = ROOT / "V_bear_cap" / "V5_time_split.csv"
        if v5_path.exists():
            v5 = pd.read_csv(v5_path)

            # Display table: per-split
            rows = []
            for _, r in v5.iterrows():
                delta_cal = r["oos_cal"] - r["is_cal"]
                rows.append({
                    "Split": r["split"],
                    "Cut Date": r["cut"],
                    "Spec": r["spec"],
                    "IS CAGR": fmt_pct(r["is_cagr"]),
                    "IS Cal": fmt(r["is_cal"]),
                    "OOS CAGR": fmt_pct(r["oos_cagr"]),
                    "OOS Cal": fmt(r["oos_cal"]),
                    "Δ Cal (OOS-IS)": f"{delta_cal:+.2f}",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            # Alpha check: per-split T2GE bm90 vs baseline
            st.markdown("### bm90 알파 (split별 IS Cal — 검증된 우월성 / OOS Cal)")
            alpha_rows = []
            for split in v5["split"].unique():
                sub = v5[v5["split"] == split]
                try:
                    t2_base = sub[sub["spec"] == "T2GE_None"].iloc[0]
                    t2_90 = sub[sub["spec"] == "T2GE_bm90"].iloc[0]
                    t1_base = sub[sub["spec"] == "T1_None"].iloc[0]
                    t1_60 = sub[sub["spec"] == "T1_bm60"].iloc[0]
                    alpha_rows.append({
                        "Split": split,
                        "T1 bm60 IS Δ Cal": f"{t1_60['is_cal']-t1_base['is_cal']:+.2f}",
                        "T1 bm60 OOS Δ Cal": f"{t1_60['oos_cal']-t1_base['oos_cal']:+.2f}",
                        "T2GE bm90 IS Δ Cal": f"{t2_90['is_cal']-t2_base['is_cal']:+.2f}",
                        "T2GE bm90 OOS Δ Cal": f"{t2_90['oos_cal']-t2_base['oos_cal']:+.2f}",
                    })
                except (IndexError, KeyError):
                    continue
            if alpha_rows:
                st.dataframe(pd.DataFrame(alpha_rows), use_container_width=True, hide_index=True)
                st.success(
                    "**핵심**: 모든 split에서 IS 일관 우월(+0.16~+0.53), OOS 동등. "
                    "= **과적합 없음**, escape valve가 학습 구간에서 본 효과가 미래 구간에서도 유지."
                )
        else:
            st.warning("V_bear_cap/V5_time_split.csv 없음")

    # — sub[1] 📜 양변기 v5 — Walk-Forward —
    with sub[1]:
        # ── Section 2: 양변기 v5 단독 Walk-Forward + OOS (참고용) ──
        st.subheader("📜 양변기 v5 단독 — BEAR slot 컴포넌트 Walk-Forward (참고용)")
        st.caption("ℹ️ BUBE의 BEAR regime sub-strategy 단독. 동적 timing 함정 (Calmar 1.84) 보여줌.")
        wf = load_json(ROOT / "walkforward_8yr" / "summary.json")
        if wf:
            rows = []
            wf_stats = wf.get("walk_forward", {})
            rows.append({
                "Strategy": "Walk-Forward (분기 동적 회전)",
                "CAGR": fmt_pct(wf_stats.get("cagr")),
                "MDD": fmt_pct(wf_stats.get("mdd")),
                "Sharpe": fmt(wf_stats.get("sharpe")),
                "Calmar": fmt(wf_stats.get("calmar")),
            })
            for name, s in wf.get("static", {}).items():
                rows.append({
                    "Strategy": f"Static: {name}",
                    "CAGR": fmt_pct(s.get("cagr")),
                    "MDD": fmt_pct(s.get("mdd")),
                    "Sharpe": fmt(s.get("sharpe")),
                    "Calmar": fmt(s.get("calmar")),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            st.markdown("### Active usage (post-warmup)")
            usage = wf.get("usage", {})
            if usage:
                usage_df = pd.DataFrame([{"Strategy": k, "Usage": f"{v*100:.1f}%"} for k, v in usage.items()])
                st.dataframe(usage_df, use_container_width=True, hide_index=True)

            st.warning("⚠️ Walk-Forward Calmar 1.84 < 모든 정적 변형. 동적 timing은 함정.")
        else:
            st.info("walk-forward 결과 없음.")

    # — sub[2] 🧪 OOS Train/Test split —
    with sub[2]:
        st.subheader("OOS Train(2018-2022) vs Test(2023-2026)")
        if extended:
            train = extended.get("Train_2018-06_2022-12", {})
            test = extended.get("Test_2023-01_2026-05", {})
            rows = []
            for strat in train.keys():
                t = train.get(strat, {})
                te = test.get(strat, {})
                train_cal = t.get("calmar") or 0
                test_cal = te.get("calmar") or 0
                rows.append({
                    "Strategy": strat,
                    "Train CAGR": fmt_pct(t.get("cagr")),
                    "Train Calmar": fmt(train_cal),
                    "Test CAGR": fmt_pct(te.get("cagr")),
                    "Test Calmar": fmt(test_cal),
                    "Δ Calmar": fmt(test_cal - train_cal, places=2),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            st.markdown("**해석**: YB MDD OR의 Δ Calmar가 가장 작아 과적합 가장 약함.")

# ───────────────────────────────────────────────────────────
# TAB 7: Slot Rotation (BUBE × N분할 × H일 hold 그리드)
# ───────────────────────────────────────────────────────────
with tabs[6]:
    st.subheader("🔀 Slot Rotation — BUBE × N분할 × H일 hold 그리드 (2026-05-25)")
    st.caption("BUBE에 자금을 N등분 + 매일 1차수씩 rotation 진입 + H일 후 강제 청산. MDD 분산 시도. position-level 백테 (SOXL OHLC + per-slot stop)")

    sr_summary_path = ROOT / "slot_rotation" / "summary_pos.json"
    if sr_summary_path.exists():
        sr = load_json(sr_summary_path)

        # Baseline + Top picks
        baseline = sr.get("baseline", {})
        best_cal = sr.get("grid_best_calmar", {})
        best_cagr = sr.get("grid_best_cagr", {})

        st.markdown("### 🏁 Headline")
        b1, b2, b3 = st.columns(3)
        b1.markdown("**BASELINE (BUBE 단일)**")
        b1.metric("CAGR", f"{baseline.get('cagr', 0)*100:+.1f}%")
        b1.metric("MDD", f"{baseline.get('mdd', 0)*100:+.1f}%")
        b1.metric("Calmar", f"{baseline.get('calmar', 0):.2f}")

        b2.markdown(f"**🏆 Best Calmar (N={int(best_cal.get('n_slots', 0))}, H={int(best_cal.get('hold_days', 0))}d)**")
        b2.metric("CAGR", f"{best_cal.get('cagr', 0)*100:+.1f}%",
                  f"{(best_cal.get('cagr', 0) - baseline.get('cagr', 0))*100:+.1f}p")
        b2.metric("MDD", f"{best_cal.get('mdd', 0)*100:+.1f}%",
                  f"{(best_cal.get('mdd', 0) - baseline.get('mdd', 0))*100:+.1f}p")
        b2.metric("Calmar", f"{best_cal.get('calmar', 0):.2f}",
                  f"+{best_cal.get('calmar', 0) - baseline.get('calmar', 0):.2f}")

        b3.markdown(f"**🚀 Best CAGR (N={int(best_cagr.get('n_slots', 0))}, H={int(best_cagr.get('hold_days', 0))}d)**")
        b3.metric("CAGR", f"{best_cagr.get('cagr', 0)*100:+.1f}%",
                  f"{(best_cagr.get('cagr', 0) - baseline.get('cagr', 0))*100:+.1f}p")
        b3.metric("MDD", f"{best_cagr.get('mdd', 0)*100:+.1f}%",
                  f"{(best_cagr.get('mdd', 0) - baseline.get('mdd', 0))*100:+.1f}p")
        b3.metric("Calmar", f"{best_cagr.get('calmar', 0):.2f}",
                  f"+{best_cagr.get('calmar', 0) - baseline.get('calmar', 0):.2f}")

        st.info(
            "**핵심**: N=5~7 / H=7~14일이 sweet spot — MDD 11pp 줄이면서 CAGR도 살짝 개선 (Calmar 2.46 → 3.5+). "
            "N>>H면 자금 idle로 CAGR 망함 (N30_H7 = +24%). H=30+이면 regime 늦게 따라가 BULL run 길게 탐."
        )

        # Grid heatmap
        st.markdown("### 📊 N × H 그리드 (Calmar by combo)")
        grid_path = ROOT / "slot_rotation" / "grid_n_h_pos_lb08.csv"
        if grid_path.exists():
            grid = pd.read_csv(grid_path)
            pivot_cal = grid.pivot(index="n_slots", columns="hold_days", values="calmar").round(2)
            pivot_cagr = grid.pivot(index="n_slots", columns="hold_days", values="cagr").round(3)
            pivot_mdd = grid.pivot(index="n_slots", columns="hold_days", values="mdd").round(3)

            col_l, col_r = st.columns(2)
            with col_l:
                st.markdown("**Calmar (heatmap)**")
                st.dataframe(pivot_cal.style.background_gradient(cmap="RdYlGn", axis=None),
                             use_container_width=True)
            with col_r:
                st.markdown("**MDD (heatmap, 빨강일수록 깊음)**")
                st.dataframe(pivot_mdd.style.background_gradient(cmap="RdYlGn_r", axis=None),
                             use_container_width=True)
            with st.expander("CAGR heatmap"):
                st.dataframe(pivot_cagr.style.background_gradient(cmap="RdYlGn", axis=None),
                             use_container_width=True)

            # Top 10 by Calmar
            st.markdown("### 🥇 Top 10 by Calmar")
            top10 = grid.nlargest(10, "calmar")[["n_slots", "hold_days", "cagr", "mdd", "calmar", "sharpe", "final"]].copy()
            top10["cagr"] = top10["cagr"].apply(fmt_pct)
            top10["mdd"] = top10["mdd"].apply(fmt_pct)
            top10["calmar"] = top10["calmar"].round(2)
            top10["sharpe"] = top10["sharpe"].round(2)
            top10["final"] = top10["final"].apply(lambda x: f"${x/1e6:.2f}M")
            top10.columns = ["N slots", "Hold days", "CAGR", "MDD", "Calmar", "Sharpe", "Final ($100K → )"]
            st.dataframe(top10, use_container_width=True, hide_index=True)

        # Per-slot LB stop sweep
        sweep = sr.get("per_slot_stop_sweep", [])
        if sweep:
            st.markdown("### 🛑 LB(롱변기) per-slot stop sweep")
            st.caption("각 슬롯이 자체 -X% 손절을 독립 트리거. -10~-12% 사이가 sweet spot.")
            sw_df = pd.DataFrame(sweep)
            sw_df["cagr"] = sw_df["cagr"].apply(fmt_pct)
            sw_df["mdd"] = sw_df["mdd"].apply(fmt_pct)
            sw_df["calmar"] = sw_df["calmar"].round(2)
            sw_df["sharpe"] = sw_df["sharpe"].round(2)
            sw_df["final"] = sw_df["final"].apply(lambda x: f"${x/1e6:.2f}M")
            sw_df.columns = ["LB stop", "CAGR", "MDD", "Calmar", "Sharpe", "Vol", "Final ($100K → )"]
            st.dataframe(sw_df, use_container_width=True, hide_index=True)
            st.info("⚠️ stop **off 또는 -20%** = CAGR 130%+ but MDD -37% (BUBE보다 깊음). -10~-12% = Calmar 3.7+ sweet spot.")

        # Plot if exists
        plot_path = ROOT / "slot_rotation" / "slot_rotation_plot.png"
        if plot_path.exists():
            with st.expander("📈 slot_rotation_plot.png (초기 returns-stream overlay grid)"):
                st.image(str(plot_path), use_container_width=True)

        st.markdown("---")
        st.warning(
            "⚠️ **Caveat**: 슬롯 rotation은 paper cloud 환경(단일 Alpaca 계정 + 7+ 슬롯 stagger)에서 state 관리 복잡. "
            "IBKR 실거래 환경이 더 적합. 현 산출물은 position-level 백테로 BUBE 단일 대비 sweet spot 영역 확인. "
            "메모리: `project_slot_rotation.md`."
        )
    else:
        st.warning(f"slot_rotation/summary_pos.json 없음 — {sr_summary_path}")


# ───────────────────────────────────────────────────────────
# TAB 8: BUBE Live (Tier 2 GOLD_ESCAPE bm=90)
# ───────────────────────────────────────────────────────────
with tabs[7]:
    st.subheader("💰 BUBE Trader — Alpaca Paper (T2 GOLD_ESCAPE bm=90)")
    st.caption("2026-05-24 통합 봇. GitHub Actions × cron-job.org 자동 운영. 04:00 HST 데이터 60초 캐시.")

    # ── Section A: Spec card ──
    st.markdown("""
<div style="background:linear-gradient(135deg,#0d3b2e,#1e6b4f);padding:18px 24px;border-radius:10px;color:white;margin:8px 0 16px">
  <div style="font-size:1.1em;font-weight:600;margin-bottom:8px">📐 Tier 2 GOLD_ESCAPE Mapping</div>
  <div style="opacity:0.92;line-height:1.7">
    <b>BULL / NEUTRAL</b> → 롱변기 (SOXL 100%, +1.5% stop-buy, -8% close-based stop)<br>
    <b>BEAR</b> → 양변기 v5 F1_A6 (SOXL+SOXS pair, win 0% / loss 25% LOC, QQQ RSI per long_alloc)<br>
    <b>GOLD_ESCAPE</b> (BEAR streak &gt; <b>90d</b>) → 황금변기 (SOXL K-vol breakout 0.25, RSI mode 30/70/100%)<br>
    <b>Regime</b>: Consensus 3-SMA200 (QQQ/SPY/SMH ±2%, 2-of-3) + Fast BEAR OR (VIX9D/VIX&gt;1.05 OR SOXL 5d mom&lt;-10%), dwell=5d
  </div>
</div>
""", unsafe_allow_html=True)

    # ── Section B: Today's regime + active sub-strategy ──
    @st.cache_data(ttl=300)  # 5분 캐시 (yfinance 다수 호출)
    def _compute_regime_state():
        """bube_trader.py와 동일 로직: consensus + fast OR + dwell 5 + bear_max 90."""
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
            # Smooth runs < DWELL
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
            return {
                "regime": today_reg,
                "raw_regime": regimes[-1] if regimes else "NEUTRAL",
                "active": active,
                "bear_streak": streak,
                "max_bear": MAX_BEAR,
                "gold_escape": gold_escape,
                "last7": recent,
                "dwell": DWELL,
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
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Today Regime", rstate["regime"], f"raw {rstate['raw_regime']}")
        c2.metric("Active Sub-Strategy", f"{active_emoji} {active_name}")
        c3.metric("BEAR streak", f"{rstate['bear_streak']}d", f"max {rstate['max_bear']}d")
        c4.metric("Last 7d", rstate["last7"], f"dwell {rstate['dwell']}d")
        if rstate["gold_escape"]:
            st.error("🚨 **GOLD_ESCAPE 발동 중** — BEAR streak > 90d. 황금변기 K-vol breakout으로 전환됨.")

    st.markdown("---")

    # ── Section C: Alpaca paper account live ──
    @st.cache_data(ttl=60)
    def _fetch_alpaca():
        try:
            from alpaca.trading.client import TradingClient
            from alpaca.trading.requests import GetOrdersRequest
            from alpaca.trading.enums import QueryOrderStatus
            import datetime as _dt
            key = _os.environ.get("ALPACA_API_KEY")
            secret = _os.environ.get("ALPACA_SECRET_KEY")
            if not key or not secret:
                return {"error": "Streamlit Cloud Secrets에 ALPACA_API_KEY / ALPACA_SECRET_KEY 등록이 필요합니다. (앱 메뉴 → Settings → Secrets)"}
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
        st.caption("Streamlit Cloud → ⚙ Settings → Secrets에 다음 2줄 등록 (2026-05-24 신규 BUBE paper 계정):")
        st.code('ALPACA_API_KEY = "<신규 BUBE paper PK key>"\n'
                'ALPACA_SECRET_KEY = "<신규 BUBE paper secret>"',
                language="toml")
        st.caption("실제 key는 GitHub repo sunghakg/yb-mdd-or-trader → Settings → Secrets에 등록된 값 그대로 사용.")
    else:
        acc = data["account"]
        seed = 100_000.0   # Alpaca paper 기본 시드
        pnl = acc["equity"] - seed
        pnl_pct = (pnl / seed) * 100

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
    st.markdown("**🔗 Alpaca 신규 BUBE paper 계정**: https://app.alpaca.markets/paper/dashboard/overview")
    st.markdown("**🔗 GitHub Actions (bube workflows)**: https://github.com/sunghakg/yb-mdd-or-trader/actions")
    st.markdown("**🔗 cron-job.org (4 트리거)**: https://console.cron-job.org/jobs")
    st.caption("자동 트리거: 03:25 / 03:35 / 09:55 / 10:00 HST (월-금). Telegram prefix: 🚽 BUBE")


