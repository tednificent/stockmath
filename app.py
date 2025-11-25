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
        price = info.get('currentPrice', 0)
        
        pe = info.get('trailingPE')
        if pe is None: pe = 0
            
        margin = info.get('profitMargins', 0) * 100
        
        # FCF Calculation
        mcap = info.get('marketCap', 1)
        rev = info.get('totalRevenue', 1)
        fcf = info.get('freeCashflow')
        
        # Fallback
        if fcf is None:
            ocf = info.get('operatingCashflow', 0)
            fcf = ocf 
            
        fcf_yield = (fcf / mcap) * 100 if mcap else 0
        fcf_margin = (fcf / rev) * 100 if rev else 0
        
        # --- B. DASHBOARD HEADER ---
        st.title(f"Analysis: {info.get('longName', ticker)}")
        
        # Display Top Metrics
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Price", f"${price:.2f}")
        col2.metric("P/E Ratio", f"{pe:.2f}")
        col3.metric("Profit Margin", f"{margin:.1f}%")
        col4.metric("FCF Yield", f"{fcf_yield:.2f}%")
        col5.metric("FCF Margin", f"{fcf_margin:.1f}%")
        
        st.divider()

        # --- C. SCENARIO ENGINE ---
        st.subheader("Scenario Assumptions")
        
        c_bear, c_base, c_bull = st.columns(3)
        
        # Updated Helper with BORDER BOX
        def make_inputs(col, name, d_growth, d_pm, d_fcfm, d_pe, d_fcfy):
            with col:
                # This creates the visual box around the inputs
                with st.container(border=True):
                    st.markdown(f"### {name} Case")
                    
                    # 1. Revenue Growth
                    g = st.number_input(f"Rev Growth %", key=f"g_{name}", value=float(d_growth))
                    
                    st.divider() # Visual separator
                    
                    # 2. Earnings Block
                    st.caption(f"Earnings Logic")
                    pm = st.number_input(f"Target Profit Margin %", key=f"pm_{name}", value=float(d_pm))
                    pe = st.number_input(f"Exit P/E", key=f"pe_{name}", value=float(d_pe))
                    
                    st.divider() # Visual separator
                    
                    # 3. Cash Flow Block
                    st.caption(f"Cash Flow Logic")
                    fcfm = st.number_input(f"Target FCF Margin %", key=f"fcfm_{name}", value=float(d_fcfm))
                    yld = st.number_input(f"Exit FCF Yield %", key=f"yld_{name}", value=float(d_fcfy))
                    
                    return g, pm, fcfm, pe, yld

        # Define Defaults
        bear_inputs = make_inputs(c_bear, "Bear", 5.0, margin-5, fcf_margin-5, 15.0, 6.0)
        base_inputs = make_inputs(c_base, "Base", 10.0, margin, fcf_margin, 20.0, 4.0)
        bull_inputs = make_inputs(c_bull, "Bull", 15.0, margin+5, fcf_margin+5, 25.0, 3.0)

        # --- D. CALCULATION ENGINE ---
        st.divider() # Separate inputs from button
        if st.button("Run Projection", type="primary"):
            results = []
            scenarios = [("Bear", bear_inputs), ("Base", base_inputs), ("Bull", bull_inputs)]
            
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
                
                # 2. Calculate Exit Valuations
                target_mcap_eps = future_earnings * t_pe
                target_mcap_fcf = future_fcf / (t_yld/100) if t_yld > 0 else 0
                
                # 3. Share Price Conversion
                shares = mcap / price
                if shares == 0: shares = 1 
                
                price_eps = target_mcap_eps / shares
                price_fcf = target_mcap_fcf / shares
                avg_price = (price_eps + price_fcf) / 2
                
                # 4. CAGR Calculations
                if price > 0:
                    cagr_eps = ((price_eps / price)**(1/years)) - 1
                    cagr_fcf = ((price_fcf / price)**(1/years)) - 1
                    cagr_avg = ((avg_price / price)**(1/years)) - 1
                else:
                    cagr_eps = 0
                    cagr_fcf = 0
                    cagr_avg = 0
                
                # Add to Results
                results.append({
                    "Scenario": name,
                    "EPS Target": f"${price_eps:.2f}",
                    "EPS CAGR": f"{cagr_eps:.2%}",
                    "FCF Target": f"${price_fcf:.2f}",
                    "FCF CAGR": f"{cagr_fcf:.2%}",
                    "Avg Target": f"${avg_price:.2f}",
                })
                
                chart_scenarios.append(name)
                chart_prices.append(avg_price)
                chart_colors.append(color_map[name])

            # --- E. DISPLAY RESULTS ---
            st.dataframe(pd.DataFrame(results), use_container_width=True)
            
            # Chart
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=["Current"], y=[price], 
                name="Current", marker_color="#29b5e8", 
                text=[f"${price:.0f}"], textposition="auto"
            ))
            fig.add_trace(go.Bar(
                x=chart_scenarios, y=chart_prices, 
                marker_color=chart_colors,
                text=[f"${p:.0f}" for p in chart_prices], 
                textposition="auto"
            ))
            fig.update_layout(title="Average Price Targets vs Current Price", yaxis_title="Stock Price ($)")
            st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error fetching data: {e}")