import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# --- 1. CONFIGURATION ---
st.set_page_config(layout="wide", page_title="Stock Scenario Analyzer")

# --- 2. SIDEBAR ---
st.sidebar.header("Settings")
ticker = st.sidebar.text_input("Stock Ticker", value="GOOG").upper()
years = st.sidebar.slider("Analysis Horizon (Years)", 3, 10, 5)

# --- 3. MAIN APP LOGIC ---
if ticker:
    try:
        # Fetch Data
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # --- A. METRICS EXTRACTION ---
        # We use .get() with defaults to prevent crashes if data is missing
        price = info.get('currentPrice', 0)
        
        # P/E handling (Some stocks have negative or missing PE)
        pe = info.get('trailingPE')
        if pe is None: pe = 0
            
        margin = info.get('profitMargins', 0) * 100
        
        # FCF Calculation
        mcap = info.get('marketCap', 1)
        rev = info.get('totalRevenue', 1)
        fcf = info.get('freeCashflow')
        
        # Fallback: If FCF is missing, approximate with Operating Cash Flow
        if fcf is None:
            ocf = info.get('operatingCashflow', 0)
            fcf = ocf 
            
        fcf_yield = (fcf / mcap) * 100 if mcap else 0
        fcf_margin = (fcf / rev) * 100 if rev else 0
        
        # --- B. DASHBOARD HEADER ---
        st.title(f"Analysis: {info.get('longName', ticker)}")
        
        # Display Top Metrics (Native Streamlit Columns)
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Price", f"${price:.2f}")
        col2.metric("P/E Ratio", f"{pe:.2f}")
        col3.metric("Profit Margin", f"{margin:.1f}%")
        col4.metric("FCF Yield", f"{fcf_yield:.2f}%")
        col5.metric("FCF Margin", f"{fcf_margin:.1f}%")
        
        st.divider()

        # --- C. SCENARIO ENGINE ---
        st.subheader("Scenario Assumptions")
        
        # Create 3 columns for inputs
        c_bear, c_base, c_bull = st.columns(3)
        
        # Helper function to generate clean input fields
        def make_inputs(col, name, d_growth, d_pm, d_fcfm, d_pe, d_fcfy):
            with col:
                st.markdown(f"### {name} Case")
                # We use unique keys for every input to avoid Streamlit errors
                g = st.number_input(f"Rev Growth %", key=f"g_{name}", value=float(d_growth))
                pm = st.number_input(f"Target Margin %", key=f"pm_{name}", value=float(d_pm))
                fcfm = st.number_input(f"Target FCF Margin %", key=f"fcfm_{name}", value=float(d_fcfm))
                pe = st.number_input(f"Exit P/E", key=f"pe_{name}", value=float(d_pe))
                yld = st.number_input(f"Exit FCF Yield %", key=f"yld_{name}", value=float(d_fcfy))
                return g, pm, fcfm, pe, yld

        # Define Default Values (Bear = Lower, Base = Current, Bull = Higher)
        bear_inputs = make_inputs(c_bear, "Bear", 5.0, margin-5, fcf_margin-5, 15.0, 6.0)
        base_inputs = make_inputs(c_base, "Base", 10.0, margin, fcf_margin, 20.0, 4.0)
        bull_inputs = make_inputs(c_bull, "Bull", 15.0, margin+5, fcf_margin+5, 25.0, 3.0)

        # --- D. CALCULATION ENGINE ---
        if st.button("Run Projection", type="primary"):
            results = []
            scenarios = [("Bear", bear_inputs), ("Base", base_inputs), ("Bull", bull_inputs)]
            
            # Data specifically for the chart
            chart_scenarios = []
            chart_prices = []
            chart_colors = []
            color_map = {"Bear": "#ff4b4b", "Base": "#7d7d7d", "Bull": "#09ab3b"}

            for name, vals in scenarios:
                g, pm, fcfm, t_pe, t_yld = vals
                
                # 1. Project Future Financials
                future_rev = rev * ((1 + g/100)**years)
                future_earnings = future_rev * (pm/100)
                future_fcf = future_rev * (fcfm/100)
                
                # 2. Calculate Exit Valuations (Market Cap)
                target_mcap_eps = future_earnings * t_pe
                # Handle division by zero for yield
                target_mcap_fcf = future_fcf / (t_yld/100) if t_yld > 0 else 0
                
                # 3. Convert to Share Price
                shares = mcap / price
                if shares == 0: shares = 1 # Safety check
                
                price_eps = target_mcap_eps / shares
                price_fcf = target_mcap_fcf / shares
                avg_price = (price_eps + price_fcf) / 2
                
                # 4. Calculate CAGR
                # Formula: (End/Start)^(1/n) - 1
                if price > 0:
                    cagr = ((avg_price / price)**(1/years)) - 1
                else:
                    cagr = 0
                
                # Add to Results Table
                results.append({
                    "Scenario": name,
                    "EPS Target": f"${price_eps:.2f}",
                    "FCF Target": f"${price_fcf:.2f}",
                    "Avg Price Target": f"${avg_price:.2f}",
                    "CAGR": f"{cagr:.2%}"
                })
                
                # Add to Chart Data
                chart_scenarios.append(name)
                chart_prices.append(avg_price)
                chart_colors.append(color_map[name])

            # --- E. DISPLAY RESULTS ---
            
            # 1. Table
            st.dataframe(pd.DataFrame(results), use_container_width=True)
            
            # 2. Chart
            fig = go.Figure()
            
            # Add Current Price Bar
            fig.add_trace(go.Bar(
                x=["Current"], y=[price], 
                name="Current", marker_color="#29b5e8", 
                text=[f"${price:.0f}"], textposition="auto"
            ))
            
            # Add Scenario Bars
            fig.add_trace(go.Bar(
                x=chart_scenarios, y=chart_prices, 
                marker_color=chart_colors,
                text=[f"${p:.0f}" for p in chart_prices], 
                textposition="auto"
            ))
            
            fig.update_layout(title="Price Targets vs Current Price", yaxis_title="Stock Price ($)")
            st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error fetching data. Please check the ticker or internet connection. Details: {e}")