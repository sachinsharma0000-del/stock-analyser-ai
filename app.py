"""
stock-analyser-ai
Main Streamlit app — NSE fundamental screener + AI analysis dashboard.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from modules.data_fetcher import (
    get_stock_info, get_price_history, get_financials,
    format_market_cap, pct, compute_cagr, NIFTY500_SYMBOLS,
)
from modules.screener import (
    run_screener, format_screener_df, DEFAULT_FILTERS,
)
from modules.ai_analysis import (
    analyse_stock, rec_colour, val_colour,
)


# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Stock Analyser AI",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── Sidebar nav ───────────────────────────────────────────────────────────────

st.sidebar.title("📈 Stock Analyser AI")
st.sidebar.caption("NSE Fundamentals + AI Analysis")
st.sidebar.divider()

page = st.sidebar.radio(
    "Navigate",
    ["🔍 Screener", "🔬 Stock Deep Dive", "📋 Watchlist"],
    label_visibility="collapsed",
)

st.sidebar.divider()
st.sidebar.caption("Data via yfinance · Analysis via Claude")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — SCREENER
# ══════════════════════════════════════════════════════════════════════════════

if page == "🔍 Screener":
    st.title("🔍 NSE Stock Screener")
    st.caption("Filter Nifty 500 stocks by fundamental criteria. Results ranked by quality score.")

    # ── Filter panel ──────────────────────────────────────────────────────────
    with st.expander("⚙️ Filters", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            min_roe      = st.slider("Min ROE (%)",            0, 50,  int(DEFAULT_FILTERS["min_roe"]))
            max_pe       = st.slider("Max PE Ratio",           0, 100, int(DEFAULT_FILTERS["max_pe"]))
            max_de       = st.slider("Max Debt/Equity",        0, 5,   int(DEFAULT_FILTERS["max_debt_to_equity"]), step=1)
        with col2:
            min_rev_g    = st.slider("Min Revenue Growth (%)", 0, 50,  int(DEFAULT_FILTERS["min_revenue_growth"]))
            min_margin   = st.slider("Min Net Margin (%)",     0, 30,  int(DEFAULT_FILTERS["min_profit_margins"]))
            min_op_mg    = st.slider("Min Op. Margin (%)",     0, 30,  int(DEFAULT_FILTERS["min_operating_margins"]))
        with col3:
            min_cr       = st.slider("Min Current Ratio",      0, 5,   int(DEFAULT_FILTERS["min_current_ratio"]), step=1)
            max_pb       = st.slider("Max PB Ratio",           0, 20,  int(DEFAULT_FILTERS["max_pb_ratio"]))
            min_mcap     = st.slider("Min Market Cap (₹Cr)",   0, 5000, int(DEFAULT_FILTERS["min_market_cap_cr"]), step=100)

    filters = {
        "min_roe":               min_roe,
        "max_pe":                max_pe,
        "max_debt_to_equity":    max_de,
        "min_revenue_growth":    min_rev_g,
        "min_profit_margins":    min_margin,
        "min_operating_margins": min_op_mg,
        "min_current_ratio":     min_cr,
        "max_pb_ratio":          max_pb,
        "min_market_cap_cr":     min_mcap,
    }

    if st.button("▶ Run Screener", type="primary", use_container_width=True):
        with st.spinner("Fetching data for all stocks… (first run takes ~60s, then cached)"):
            results = run_screener(NIFTY500_SYMBOLS, filters)

        st.session_state["screener_results"] = results
        st.success(f"✅ {len(results)} stocks passed your filters out of {len(NIFTY500_SYMBOLS)} screened.")

    # ── Results ───────────────────────────────────────────────────────────────
    if "screener_results" in st.session_state:
        results = st.session_state["screener_results"]

        if results.empty:
            st.warning("No stocks matched your filters. Try relaxing the criteria.")
        else:
            display = format_screener_df(results)
            st.dataframe(display, use_container_width=True, height=500)

            # Quality score bar chart
            fig = px.bar(
                results.head(20),
                x="symbol", y="quality_score",
                color="quality_score",
                color_continuous_scale="Greens",
                title="Top 20 by Quality Score",
                labels={"quality_score": "Score", "symbol": "Stock"},
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#FAFAFA",
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)

            # Quick link to deep dive
            selected = st.selectbox(
                "Analyse a stock in depth →",
                [""] + list(results["symbol"]),
            )
            if selected:
                st.session_state["deep_dive_symbol"] = selected
                st.info(f"Go to **Stock Deep Dive** in the sidebar to see full analysis for {selected}")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — STOCK DEEP DIVE
# ══════════════════════════════════════════════════════════════════════════════

elif page == "🔬 Stock Deep Dive":
    st.title("🔬 Stock Deep Dive")

    default_sym = st.session_state.get("deep_dive_symbol", "RELIANCE")
    symbol = st.text_input(
        "Enter NSE symbol",
        value=default_sym,
        placeholder="e.g. RELIANCE, INFY, HDFCBANK",
    ).strip().upper()

    if symbol:
        st.session_state["deep_dive_symbol"] = symbol

        with st.spinner(f"Loading data for {symbol}…"):
            info    = get_stock_info(symbol)
            history = get_price_history(symbol, "5y")

        if not info.get("name"):
            st.error(f"Could not find data for '{symbol}'. Check the NSE symbol and try again.")
            st.stop()

        # ── Header ────────────────────────────────────────────────────────────
        st.subheader(f"{info['name']} ({symbol}.NS)")
        st.caption(f"{info.get('sector', '')} · {info.get('industry', '')}")

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Price",        f"₹{info.get('current_price', 'N/A'):,}" if info.get('current_price') else "N/A")
        m2.metric("Market Cap",   format_market_cap(info.get("market_cap")))
        m3.metric("PE (TTM)",     f"{info.get('pe_ratio', 'N/A'):.1f}" if info.get('pe_ratio') else "N/A")
        m4.metric("ROE",          pct(info.get("roe")))
        m5.metric("Net Margin",   pct(info.get("profit_margins")))

        st.divider()

        # ── Price chart ───────────────────────────────────────────────────────
        tab1, tab2, tab3 = st.tabs(["📈 Price Chart", "📊 Fundamentals", "🤖 AI Analysis"])

        with tab1:
            cagr = compute_cagr(history, 5)
            if cagr:
                st.caption(f"5Y Price CAGR: **{cagr*100:.1f}%**")

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=history.index, y=history["Close"],
                mode="lines", name="Close Price",
                line=dict(color="#00C853", width=2),
                fill="tozeroy",
                fillcolor="rgba(0,200,83,0.08)",
            ))
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#FAFAFA",
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
                margin=dict(l=0, r=0, t=10, b=0),
                height=380,
            )
            st.plotly_chart(fig, use_container_width=True)

        with tab2:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Valuation**")
                _vals = {
                    "PE (TTM)":     info.get("pe_ratio"),
                    "Forward PE":   info.get("forward_pe"),
                    "PB Ratio":     info.get("pb_ratio"),
                    "PS Ratio":     info.get("ps_ratio"),
                    "Dividend Yield": f"{pct(info.get('dividend_yield'))}",
                }
                for k, v in _vals.items():
                    st.markdown(f"- **{k}:** {v if v is not None else 'N/A'}")

                st.markdown("**Profitability**")
                _prof = {
                    "Gross Margin":     pct(info.get("gross_margins")),
                    "Operating Margin": pct(info.get("operating_margins")),
                    "Net Margin":       pct(info.get("profit_margins")),
                    "ROE":              pct(info.get("roe")),
                    "ROA":              pct(info.get("roa")),
                }
                for k, v in _prof.items():
                    st.markdown(f"- **{k}:** {v}")

            with c2:
                st.markdown("**Growth**")
                _growth = {
                    "Revenue Growth (YoY)":  pct(info.get("revenue_growth")),
                    "Earnings Growth (YoY)": pct(info.get("earnings_growth")),
                }
                for k, v in _growth.items():
                    st.markdown(f"- **{k}:** {v}")

                st.markdown("**Financial Health**")
                _health = {
                    "Debt/Equity":   info.get("debt_to_equity", "N/A"),
                    "Current Ratio": info.get("current_ratio", "N/A"),
                    "Free Cash Flow": format_market_cap(info.get("free_cashflow")),
                    "Total Debt":    format_market_cap(info.get("total_debt")),
                    "Total Cash":    format_market_cap(info.get("total_cash")),
                    "Beta":          info.get("beta", "N/A"),
                }
                for k, v in _health.items():
                    st.markdown(f"- **{k}:** {v}")

        with tab3:
            if st.button("🤖 Run AI Analysis", type="primary"):
                with st.spinner("Asking Claude to analyse this stock… (takes ~10s)"):
                    analysis = analyse_stock(symbol)
                st.session_state[f"analysis_{symbol}"] = analysis

            if f"analysis_{symbol}" in st.session_state:
                a = st.session_state[f"analysis_{symbol}"]

                if "error" in a:
                    st.error(f"Analysis failed: {a['error']}")
                else:
                    # Recommendation badge
                    rec   = a.get("recommendation", "N/A")
                    conv  = a.get("conviction", "")
                    val   = a.get("valuation", "N/A")
                    col_r = rec_colour(rec)
                    col_v = val_colour(val)

                    r1, r2, r3 = st.columns(3)
                    r1.markdown(
                        f"<div style='background:{col_r};padding:12px;border-radius:8px;text-align:center'>"
                        f"<b style='color:#000;font-size:22px'>{rec}</b><br>"
                        f"<small style='color:#000'>Conviction: {conv}</small></div>",
                        unsafe_allow_html=True,
                    )
                    r2.markdown(
                        f"<div style='background:{col_v};padding:12px;border-radius:8px;text-align:center'>"
                        f"<b style='color:#000;font-size:18px'>{val}</b><br>"
                        f"<small style='color:#000'>{a.get('valuation_note','')}</small></div>",
                        unsafe_allow_html=True,
                    )
                    r3.markdown(
                        f"<div style='background:#1A1F2E;padding:12px;border-radius:8px;text-align:center'>"
                        f"<b style='color:#FAFAFA;font-size:14px'>Horizon</b><br>"
                        f"<span style='color:#FAFAFA'>{a.get('target_horizon','N/A')}</span></div>",
                        unsafe_allow_html=True,
                    )

                    st.markdown(f"\n> {a.get('summary', '')}")

                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("**✅ Strengths**")
                        for s in a.get("strengths", []):
                            st.markdown(f"- {s}")
                        st.markdown("**🏭 Sector Context**")
                        st.markdown(a.get("sector_context", ""))

                    with c2:
                        st.markdown("**🚩 Red Flags**")
                        for f in a.get("red_flags", []):
                            st.markdown(f"- {f}")
                        st.markdown("**⚠️ Key Risks**")
                        for r in a.get("key_risks", []):
                            st.markdown(f"- {r}")

                    st.info(f"**👁 Watch:** {a.get('what_to_watch', '')}")

                    # Add to watchlist
                    if st.button("⭐ Add to Watchlist"):
                        wl = st.session_state.get("watchlist", [])
                        if symbol not in wl:
                            wl.append(symbol)
                            st.session_state["watchlist"] = wl
                            st.success(f"{symbol} added to watchlist!")
                        else:
                            st.info(f"{symbol} is already in your watchlist.")
            else:
                st.caption("Click **Run AI Analysis** to get Claude's take on this stock.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — WATCHLIST
# ══════════════════════════════════════════════════════════════════════════════

elif page == "📋 Watchlist":
    st.title("📋 Watchlist")

    wl = st.session_state.get("watchlist", [])

    if not wl:
        st.info("Your watchlist is empty. Add stocks from the **Stock Deep Dive** page.")
        st.stop()

    st.caption(f"{len(wl)} stocks tracked")

    for sym in wl:
        with st.expander(f"📌 {sym}", expanded=False):
            info = get_stock_info(sym)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Price",      f"₹{info.get('current_price', 'N/A')}")
            c2.metric("PE",         f"{info.get('pe_ratio', 'N/A'):.1f}" if info.get('pe_ratio') else "N/A")
            c3.metric("ROE",        pct(info.get("roe")))
            c4.metric("Net Margin", pct(info.get("profit_margins")))

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button(f"🔬 Deep Dive", key=f"dd_{sym}"):
                    st.session_state["deep_dive_symbol"] = sym
                    st.info("Go to **Stock Deep Dive** in sidebar →")
            with col_b:
                if st.button(f"🗑 Remove", key=f"rm_{sym}"):
                    wl.remove(sym)
                    st.session_state["watchlist"] = wl
                    st.rerun()
