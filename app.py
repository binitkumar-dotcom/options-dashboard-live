import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import pandas_ta as ta
import plotly.graph_objects as go
import yoptions as yo

# --- 1. PAGE SETUP ---
st.set_page_config(page_title="Indian Options Dashboard", layout="wide")

# --- 2. SIDEBAR INPUTS ---
st.sidebar.header("Dashboard Settings")

st.sidebar.subheader("Module 1: Market Scanner")
tickers_string = st.sidebar.text_area(
    "Enter Tickers (use .NS suffix, e.g., RELIANCE.NS)", 
    "RELIANCE.NS, TCS.NS, INFY.NS, HDFCBANK.NS, ICICIBANK.NS, SBIN.NS"
)
ticker_list = [s.strip().upper() for s in tickers_string.split(',') if s.strip()]

st.sidebar.subheader("Module 2/3/4: Deep Dive")
deep_dive_ticker = st.sidebar.text_input("Enter a Single Ticker for Analysis", "RELIANCE.NS").upper()


# --- 3. MODULE 1: MARKET & VOLATILITY SCANNER ---
st.title("Module 1: Market & Volatility Scanner (NSE)")
st.info("ℹ️ Remember to use the .NS suffix for all Indian stocks (e.g., INFY.NS for Infosys).")

@st.cache_data(ttl=600)
def get_scan_data(ticker_list):
    scan_results = []
    progress_bar = st.progress(0, text="Running Scan...")
    
    for i, ticker in enumerate(ticker_list):
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            current_price = info.get('currentPrice', info.get('regularMarketPrice', 0))
            avg_volume = info.get('averageVolume', 1)
            current_volume = info.get('volume', 0)
            volume_ratio = f"{(current_volume / avg_volume):.2f}x" if avg_volume > 0 else "N/A"

            atm_iv = 0
            exp_dates = stock.options
            if exp_dates:
                chain = stock.option_chain(exp_dates[0])
                if current_price > 0 and not chain.calls.empty:
                    atm_call = chain.calls.iloc[(chain.calls['strike'] - current_price).abs().argsort()[0]]
                    atm_iv = atm_call.get('impliedVolatility', 0) * 100

            scan_results.append({
                'Ticker': ticker, 'Price': f"₹{current_price:.2f}",
                'ATM IV %': f"{atm_iv:.1f}%", 'Stock Vol. Ratio': volume_ratio
            })
        except Exception:
            scan_results.append({'Ticker': ticker, 'Price': "N/A", 'ATM IV %': "N/A", 'Stock Vol. Ratio': "N/A"})
        
        progress_bar.progress((i + 1) / len(ticker_list), text=f"Scanning {ticker}...")
    progress_bar.empty()
    return pd.DataFrame(scan_results)

if ticker_list:
    df_scan = get_scan_data(ticker_list)
    st.subheader("Scan Results")
    st.dataframe(df_scan, width='stretch')


# --- 4. MODULES 2, 3, & 4: DEEP DIVE SECTION ---
st.title("---")
st.title(f"Deep Dive: {deep_dive_ticker}")

if not deep_dive_ticker:
    st.info("Enter a ticker in the sidebar (Module 2/3/4) for a deep dive.")
else:
    # --- Data Fetching for Deep Dive ---
    try:
        stock_yft = yf.Ticker(deep_dive_ticker)
        info = stock_yft.info
        current_price = info.get('currentPrice', info.get('regularMarketPrice'))

        if current_price is None or current_price == 0:
            st.error(f"Could not fetch a valid CURRENT PRICE for {deep_dive_ticker}. Check symbol or yfinance status.")
        else:
            st.header(f"Analysis for: {deep_dive_ticker} (Current Price: ₹{current_price:.2f})")
            
            stock_data = stock_yft.history(period="1y", auto_adjust=True)

            if stock_data.empty:
                st.error(f"Could not download HISTORICAL data for {deep_dive_ticker}.")
            else:
                stock_data.dropna(inplace=True)
                if stock_data.empty:
                    st.error("No valid historical data found after cleaning.")
                else:
                    # --- MODULE 2: TECHNICAL ANALYSIS ---
                    st.subheader("Module 2: Underlying Stock Analysis")
                    
                    # Calculate Technical Indicators
                    stock_data.ta.rsi(append=True)
                    stock_data.ta.macd(append=True)
                    stock_data.ta.bbands(append=True)
                    stock_data.dropna(inplace=True) # Drop NaNs created by TA
                    
                    # --- *** THE FIX IS HERE *** ---
                    # Check if TA columns were created. Requires at least 20 days of data.
                    required_cols = ['BBU_20_2.0', 'BBL_20_2.0', 'RSI_14', 'MACDh_12_26_9']
                    if not all(col in stock_data.columns for col in required_cols):
                        st.error(f"Could not calculate technical indicators for {deep_dive_ticker}.")
                        st.warning("This usually means there is not enough historical data (less than 20 days) for this ticker.")
                    # --- *** END OF FIX *** ---
                    
                    else:
                        # This code now only runs if all TA columns exist
                        last_row = stock_data.iloc[-1]

                        # Plot Price & Bollinger Bands
                        fig = go.Figure()
                        fig.add_trace(go.Candlestick(x=stock_data.index,
                                                     open=stock_data['Open'], high=stock_data['High'],
                                                     low=stock_data['Low'], close=stock_data['Close'], name="Price"))
                        fig.add_trace(go.Scatter(x=stock_data.index, y=stock_data['BBU_20_2.0'], 
                                                 line=dict(color='rgba(255, 165, 0, 0.5)', width=1), name="Upper Band"))
                        fig.add_trace(go.Scatter(x=stock_data.index, y=stock_data['BBL_20_2.0'], 
                                                 line=dict(color='rgba(255, 165, 0, 0.5)', width=1), 
                                                 name="Lower Band", fill='tonexty', fillcolor='rgba(255, 165, 0, 0.1)'))
                        fig.update_layout(title="Price & Bollinger Bands", xaxis_rangeslider_visible=False)
                        st.plotly_chart(fig, use_container_width=True)

                        # Plot RSI & MACD
                        col1, col2 = st.columns(2)
                        with col1:
                            fig_rsi = go.Figure()
                            fig_rsi.add_trace(go.Scatter(x=stock_data.index, y=stock_data['RSI_14'], name='RSI'))
                            fig_rsi.add_hline(y=70, line_dash="dash", line_color="red")
                            fig_rsi.add_hline(y=30, line_dash="dash", line_color="green")
                            fig_rsi.update_layout(title="RSI (Overbought > 70, Oversold < 30)")
                            st.plotly_chart(fig_rsi, use_container_width=True)
                        with col2:
                            fig_macd = go.Figure()
                            fig_macd.add_trace(go.Scatter(x=stock_data.index, y=stock_data['MACD_12_26_9'], name='MACD Line', line_color='blue'))
                            fig_macd.add_trace(go.Scatter(x=stock_data.index, y=stock_data['MACDs_12_26_9'], name='Signal Line', line_color='orange'))
                            fig_macd.add_bar(x=stock_data.index, y=stock_data['MACDh_12_26_9'], name='Histogram')
                            fig_macd.update_layout(title="MACD (Crossover Indicator)")
                            st.plotly_chart(fig_macd, use_container_width=True)
                        
                        # Technical Summary
                        st.subheader("Technical Status Summary")
                        cols_summary = st.columns(3)
                        if last_row['Close'] > last_row['BBU_20_2.0']: band_status = "At Upper Band (Bearish 🐻)"
                        elif last_row['Close'] < last_row['BBL_20_2.0']: band_status = "At Lower Band (Bullish 🐂)"
                        else: band_status = "In Channel (Neutral ➖)"
                        
                        if last_row['RSI_14'] > 70: rsi_status = "Overbought (Bearish 🐻)"
                        elif last_row['RSI_14'] < 30: rsi_status = "Oversold (Bullish 🐂)"
                        else: rsi_status = "Neutral ➖"

                        if last_row['MACDh_12_26_9'] > 0: macd_status = "Bullish Crossover (Bullish 🐂)"
                        else: macd_status = "Bearish Crossover (Bearish 🐻)"
                        
                        cols_summary[0].metric("Price vs. Bands", band_status)
                        cols_summary[1].metric("RSI (14)", rsi_status)
                        cols_summary[2].metric("MACD Status", macd_status)

                        
                        # --- MODULE 4: STRATEGY & SUGGESTION ENGINE ---
                        st.title("Module 4: Trade Suggestion Engine")
                        try:
                            exp_dates = stock_yft.options
                            
                            if not exp_dates:
                                st.error(f"No option expiration dates found for {deep_dive_ticker}. yfinance may not support options for this ticker.")
                            else:
                                chain = stock_yft.option_chain(exp_dates[0])
                                atm_call = chain.calls.iloc[(chain.calls['strike'] - current_price).abs().argsort()[0]]
                                current_atm_iv = atm_call.get('impliedVolatility', 0) * 100
                                st.metric("Current ATM Implied Volatility (Nearest Expiry)", f"{current_atm_iv:.1f}%")

                                # Suggestion Logic
                                suggestion, reasoning = "", ""
                                
                                if current_atm_iv > 60:
                                    if rsi_status.startswith("Oversold"):
                                        suggestion = "💡 Strategy: Sell Put Option (PE)"
                                        reasoning = f"**Why:** IV is high ({current_atm_iv:.1f}%), so premium is rich. The stock is **Oversold**, suggesting a bounce. Selling a PE collects this premium (Bullish)."
                                    elif rsi_status.startswith("Overbought"):
                                        suggestion = "💡 Strategy: Sell Call Option (CE)"
                                        reasoning = f"**Why:** IV is high ({current_atm_iv:.1f}%), so premium is rich. The stock is **Overbought**, suggesting a pullback. Selling a CE collects this premium (Bearish)."
                                    else:
                                        suggestion = "💡 Strategy: Short Strangle (Sell OTM CE & PE)"
                                        reasoning = f"**Why:** IV is very high ({current_atm_iv:.1f}%) and technicals are neutral. This suggests a 'volatility crush' is possible."
                                
                                elif current_atm_iv < 35:
                                    if macd_status.startswith("Bullish"):
                                        suggestion = "💡 Strategy: Buy Call Option (CE)"
                                        reasoning = f"**Why:** IV is low ({current_atm_iv:.1f}%), making options cheap. MACD shows **Bullish Momentum**."
                                    elif macd_status.startswith("Bearish"):
                                        suggestion = "💡 Strategy: Buy Put Option (PE)"
                                        reasoning = f"**Why:** IV is low ({current_atm_iv:.1f}%), making options cheap. MACD shows **Bearish Momentum**."
                                    else:
                                        suggestion = "💡 Strategy: Long Straddle (Buy ATM CE & PE)"
                                        reasoning = f"**Why:** IV is low ({current_atm_iv:.1f}%), making options cheap. This is ideal for betting on a large move."
                                
                                else: # Moderate IV
                                    if macd_status.startswith("Bullish") and rsi_status.startswith("Oversold"):
                                        suggestion = "💡 Strategy: Bull Call Spread (Buy CE, Sell higher CE)"
                                        reasoning = "Technicals are Bullish. A spread defines your risk."
                                    elif macd_status.startswith("Bearish") and rsi_status.startswith("Overbought"):
                                        suggestion = "💡 Strategy: Bear Put Spread (Buy PE, Sell lower PE)"
                                        reasoning = "Technicals are Bearish. A spread defines your risk."
                                    else:
                                        suggestion = "💡 Strategy: No Clear Signal"
                                        reasoning = "Technicals are mixed and IV is moderate. Wait for a clearer setup."

                                st.subheader(suggestion)
                                st.info(reasoning)
                                st.warning("⚠️ **Disclaimer:** This is an automated suggestion. This is not financial advice.")

                                # --- MODULE 3: DEEP OPTION CHAIN (GREEKS) ---
                                st.title("Module 3: Deep Option Chain Analysis")
                                selected_expiry = st.selectbox("Select Expiration Date:", exp_dates, index=0)
                                
                                @st.cache_data(ttl=600)
                                def get_greeks(ticker, expiry):
                                    calls = yo.get_chain_greeks_date(ticker, option_type='c', expiration_date=expiry, risk_free_rate=0.07)
                                    puts = yo.get_chain_greeks_date(ticker, option_type='p', expiration_date=expiry, risk_free_rate=0.07)
                                    return calls, puts

                                call_chain, put_chain = get_greeks(deep_dive_ticker, selected_expiry)
                                
                                display_cols = ['Strike', 'Last Price', 'Impl. Volatility', 'Delta', 'Theta', 'Gamma', 'Vega', 'Open Interest', 'Volume']
                                
                                for df in [call_chain, put_chain]:
                                    if not df.empty:
                                        df['Impl. Volatility'] = (df['Impl. Volatility'] * 100).round(2).astype(str) + '%'
                                        for col in ['Delta', 'Theta', 'Vega', 'Gamma']:
                                            df[col] = df[col].round(3)
                                
                                st.subheader(f"Call Option (CE) Chain (Expiry: {selected_expiry})")
                                st.dataframe(call_chain[display_cols], width='stretch')
                                
                                st.subheader(f"Put Option (PE) Chain (Expiry: {selected_expiry})")
                                st.dataframe(put_chain[display_cols], width='stretch')
                        
                        except Exception as e:
                            st.error(f"An error occurred while fetching OPTIONS data for {deep_dive_ticker}.")
                            st.error("This is common with yfinance for NSE options. The service may be temporarily down.")
                            st.error(f"Here is the exact error: {e}")

    except Exception as e:
        st.error(f"A critical error occurred while fetching initial data: {e}")
        st.error("This can happen if the ticker is invalid or yfinance is unable to retrieve initial data.")