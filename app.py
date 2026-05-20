"""
YB MDD OR — Streamlit 대시보드
==================================
백테스트 결과 + 신뢰구간 + 페이퍼 트레이딩 운영 패널 통합.

실행: streamlit run yb_mdd_or_dashboard.py

탭 구성:
1. 📊 Overview — 8년 종합 + 최종 spec
2. 📈 Stress Tests — 5+2 폭락 사이클
3. 🎲 Bootstrap — 5,000 paths 신뢰구간
4. 📅 Year-by-Year — 연도별 + 16년 long-horizon
5. 🔄 Walk-Forward + OOS — 동적 vs 정적
6. 📜 Paper Trading — 실시간 journal 모니터링
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
st.set_page_config(page_title="YB MDD OR Dashboard", layout="wide", page_icon="🚽")

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


def fmt(x, places=2):
    if x is None or pd.isna(x): return "—"
    return f"{x:.{places}f}"


# ───────────────────────────────────────────────────────────
# Header
# ───────────────────────────────────────────────────────────
st.markdown("""
<div style="background:linear-gradient(135deg,#1a2540,#2c3e50);padding:24px 32px;border-radius:12px;color:white;margin-bottom:16px">
  <h1 style="margin:0;font-size:1.8em">🚽 YB MDD 60/40/20 OR</h1>
  <div style="opacity:0.85;margin-top:6px">양변기 v5 + Consensus 2-of-3 + Hybrid fast BEAR override</div>
</div>
""", unsafe_allow_html=True)

# Quick stats row
col1, col2, col3, col4 = st.columns(4)
col1.metric("Bootstrap CAGR median", "+53.7%", "[+32, +78] 95% CI")
col2.metric("MDD median", "-22.7%", "[-35, -16] 95% CI")
col3.metric("Calmar median", "2.34", "[1.10, 4.37] 95% CI")
col4.metric("P(MDD<-40%)", "0.5%", "5,000 paths 중")

st.markdown("---")

tabs = st.tabs(["📊 Overview", "📋 거래 내역", "📈 Stress Tests", "🎲 Bootstrap",
                "📅 Year-by-Year", "🔄 Walk-Forward / OOS", "💰 Alpaca Live"])

# ───────────────────────────────────────────────────────────
# TAB 1: Overview
# ───────────────────────────────────────────────────────────
with tabs[0]:
    st.subheader("최종 매매법 Spec")
    col_a, col_b = st.columns([1, 1])
    with col_a:
        st.code("""
# 자산
universe = ["SOXL", "SOXS"]          # 페어 거래

# 진입 (매일 시초가 기준)
long_threshold = 0.015               # SOXL 시가 + 1.5% stop-buy
short_threshold = 0.060              # SOXS 시가 + 6.0% stop-buy
short_alloc = 0.40                   # 숏 자본 비중 (고정)

# Regime: Consensus + 빠른 BEAR override
# 1단계: QQQ/SPY/SMH SMA200 ±2% 중 ≥2개 합의
# 2단계: VIX9D/VIX > 1.05 OR SOXL 5d mom < -10%
#        둘 중 하나라도 트리거 시 즉시 BEAR
min_dwell = 5                        # BEAR streak 최소 5일

# Long alloc (regime별)
BULL    → long_alloc = 0.60
NEUTRAL → long_alloc = 0.40
BEAR    → long_alloc = 0.20

# 청산
loc_partial = 0.50                   # 종가 수익 시 50% LOC
                                     # 나머지 50% 익일 시가 MOO
""", language="python")
    with col_b:
        st.markdown("### 6/6 검증 통과")
        check_data = [
            ("Robustness ±20%", "임계값 변경 시 결과 안정", "✅"),
            ("OOS Train/Test", "Δ Calmar +0.17 (과적합 가장 약함)", "✅"),
            ("Walk-Forward 8년", "정적 Cal 2.67 > 동적 1.84", "✅"),
            ("Bootstrap 5,000", "P(MDD<-40%)=0.5%", "✅"),
            ("Cross-Asset", "SOXL/SOXS 전용으로 확정", "✅"),
            ("16년 Long-Horizon", "7 폭락 중 6 양수", "✅"),
        ]
        for name, desc, mark in check_data:
            st.markdown(f"**{mark} {name}** — {desc}")

        st.markdown("---")
        st.markdown("### ⚠️ 한계")
        st.markdown("""
        - SOXL/SOXS 페어 전용 (자산 다각화 X)
        - 닷컴/2008 검증 부재 (SOXL 2010-03 출시)
        - 임계값 사후 선택 (sensitivity 통과했지만 재튜닝 권장)
        - 실거래 슬리피지로 CAGR 5-10%p 추가 깎임 예상
        """)

# ───────────────────────────────────────────────────────────
# TAB 2: 기간별 거래 내역 (NEW)
# ───────────────────────────────────────────────────────────
with tabs[1]:
    st.subheader("📋 기간별 상세 거래 내역 (YB MDD OR 8년 분봉 풀 백테)")

    FULL = ROOT / "yb_mdd_or_full"
    if not (FULL / "trades.csv").exists():
        st.warning("⚠️ 풀백테 캐시 없음. 먼저 실행: `python yb_mdd_or_full_backtest.py`")
        st.stop()

    # Last update timestamp + refresh button
    last_update_file = FULL / "last_update_at.txt"
    if last_update_file.exists():
        last_update = last_update_file.read_text().strip()
    else:
        last_update = "캐시 생성 후 미갱신 (Task Scheduler 미실행)"
    refresh_col1, refresh_col2 = st.columns([3, 1])
    refresh_col1.caption(f"📅 마지막 갱신: {last_update}")
    refresh_col2.caption("ℹ️ 매일 11:00 HST 자동 갱신 (GitHub push 후 cloud auto-reload)")

    @st.cache_data
    def _load_full():
        trades = pd.read_csv(FULL / "trades.csv")
        trades["date"] = pd.to_datetime(trades["date"])
        equity = pd.read_csv(FULL / "equity.csv", index_col=0, parse_dates=True)
        alloc = pd.read_csv(FULL / "alloc.csv", index_col=0, parse_dates=True)
        bench = pd.read_csv(FULL / "bench.csv", index_col=0, parse_dates=True)
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

    # ── Period metrics ──
    st.markdown("### 📊 기간 성과 요약")
    eq_norm = eq_sl["equity"] / eq_sl["equity"].iloc[0]
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
    win_rate = float((trades_sl["pnl"] > 0).mean())
    gross_win = float(trades_sl.loc[trades_sl["pnl"] > 0, "pnl"].sum())
    gross_loss = float(-trades_sl.loc[trades_sl["pnl"] < 0, "pnl"].sum())
    pf = gross_win / gross_loss if gross_loss > 0 else float("inf")
    realized_pnl = float(trades_sl["pnl"].sum())

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Return", fmt_pct(period_ret))
    c2.metric("CAGR (annualized)", fmt_pct(cagr))
    c3.metric("MDD", fmt_pct(mdd))
    c4.metric("Sharpe", fmt(sharpe))
    c5.metric("SOXL B&H", fmt_pct(bench_ret), f"Δ {fmt_pct(period_ret - bench_ret)}")
    c6.metric("거래수", f"{len(trades_sl):,}")

    c7, c8, c9, c10 = st.columns(4)
    c7.metric("Win Rate", f"{win_rate*100:.1f}%")
    c8.metric("Profit Factor", fmt(pf) if pf != float("inf") else "∞")
    c9.metric("Realized PnL", f"${realized_pnl:,.0f}")
    c10.metric("Avg PnL/trade", f"${realized_pnl/len(trades_sl):,.0f}" if len(trades_sl)>0 else "—")

    # ── Equity curve ──
    st.markdown("### 📈 Equity Curve (선택 기간)")
    chart_df = pd.DataFrame({
        "YB MDD OR": (eq_sl["equity"] / eq_sl["equity"].iloc[0] * 100).values,
        "SOXL B&H": (bench_sl["close"] / bench_sl["close"].iloc[0] * 100).reindex(eq_sl.index).ffill().values,
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

    # 3) Equity at trade date (post-EOD) for capital context
    eq_lookup = equity_all["equity"]
    trades_sl["equity_eod"] = trades_sl["date"].map(eq_lookup)
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

    # ── Trade log ──
    st.markdown(f"### 📒 거래 내역 ({len(trades_sl):,} rows) — 사유·진행 포함")

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
    display_cols += ["qty", "notional", "pnl", "pnl_pct", "pnl_vs_equity",
                     "bench_day_ret", "equity_eod", "진입사유", "청산사유"]
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
    if "qty" in show_disp.columns:
        show_disp["qty"] = show_disp["qty"].apply(lambda x: f"{x:,.2f}")
    if "notional" in show_disp.columns:
        show_disp["notional"] = show_disp["notional"].apply(lambda x: f"${x:,.0f}")
    if "equity_eod" in show_disp.columns:
        show_disp["equity_eod"] = show_disp["equity_eod"].apply(lambda x: f"${x:,.0f}" if pd.notna(x) else "—")
    show_disp["date"] = show_disp["date"].dt.strftime("%Y-%m-%d")
    show_disp = show_disp.rename(columns={
        "date": "날짜", "regime": "Regime", "leg": "방향",
        "entry_px": "진입가", "exit_px": "청산가", "exit_type": "청산타입",
        "qty": "수량", "notional": "Notional", "pnl": "PnL",
        "pnl_pct": "PnL%", "pnl_vs_equity": "Equity영향%",
        "bench_day_ret": "SOXL 당일%", "equity_eod": "EOD Equity",
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
    st.subheader("폭락 사이클 검증 — 7개 사이클 (16년 일봉)")
    crash_rows = [
        ("2011 Euro crisis", -53.2, -6.4, -19.5, -0.44),
        ("2015-16 China", -33.1, +6.8, -10.1, 1.04),
        ("2018 Q4", -47.4, +1.7, -7.4, 0.64),
        ("2020 Covid", -47.2, +15.8, -15.7, 2.79),
        ("2022 full year", -86.6, +25.8, -13.1, 1.99),
        ("2024-08 Aug shock", -47.9, +8.0, -5.1, 11.52),
        ("2025 Tariff", -9.9, +5.0, -8.6, 3.23),
    ]
    df_crash = pd.DataFrame(crash_rows, columns=["Period", "B&H Ret %", "YB Ret %", "YB MDD %", "YB Calmar"])
    df_crash["Outcome"] = df_crash["YB Ret %"].apply(lambda x: "✅ 양수" if x > 0 else "⚠️ 손실")
    st.dataframe(df_crash, use_container_width=True, hide_index=True)

    st.markdown("**핵심**: 7개 중 6개에서 양수. 2011 Euro만 -6%이지만 B&H -53% 대비 1/8 수준.")
    st.markdown("---")

    st.subheader("8년 분봉 stress (IBKR)")
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
    st.subheader("Bootstrap 5,000 paths — 통계적 신뢰구간")
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
    st.subheader("16년 일봉 연도별 (YB MDD OR vs SOXL B&H)")
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

    st.markdown("---")
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
    st.subheader("Walk-Forward 분봉 8년 — 동적 vs 정적")
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

    st.markdown("---")
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
# TAB 7: Alpaca Live (real paper account)
# ───────────────────────────────────────────────────────────
with tabs[6]:
    st.subheader("💰 Alpaca Paper Account — 실시간")
    st.caption("GitHub Actions가 자동 운영하는 진짜 Alpaca paper 계좌 상태. 우리 자체 시뮬과 별개.")

    # Credentials are set globally at top via secrets / env

    @st.cache_data(ttl=60)  # cache 60s to avoid hammering API
    def _fetch_alpaca():
        try:
            from alpaca.trading.client import TradingClient
            from alpaca.trading.requests import GetOrdersRequest
            from alpaca.trading.enums import QueryOrderStatus
            import datetime as _dt
            tc = TradingClient(
                api_key=_os.environ["ALPACA_API_KEY"],
                secret_key=_os.environ["ALPACA_SECRET_KEY"],
                paper=True,
            )
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
    else:
        acc = data["account"]
        seed = 100_000.0
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
            st.info("보유 포지션 없음")

        st.markdown("### 오늘 주문")
        if data["orders_today"]:
            ord_df = pd.DataFrame(data["orders_today"])
            st.dataframe(ord_df, use_container_width=True, hide_index=True)
        else:
            st.info("오늘 주문 없음")

    st.markdown("---")
    st.markdown("**🔗 Alpaca 페이퍼 대시보드 직접**: https://app.alpaca.markets/paper/dashboard/overview")
    st.markdown("**🔗 GitHub Actions 로그**: https://github.com/sunghakg/yb-mdd-or-trader/actions")
    st.caption("실시간 알림은 텔레그램 봇 참고. Alpaca API 직접 호출은 60초 캐시.")
