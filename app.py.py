import streamlit as st
import yfinance as yf
import numpy as np
from scipy.stats import norm
from datetime import datetime, timedelta

# ----------------------------
# FUNCTIONS
# ----------------------------
def black_scholes_pot(S, K, T, r, sigma, option_type='call'):
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0.0
    
    try:
        if option_type == 'call' and K > S:
            z = (np.log(K / S) - (r - 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
            return 2 * norm.cdf(z)
        elif option_type == 'put' and K < S:
            z = (np.log(S / K) - (r - 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
            return 2 * norm.cdf(z)
        else:
            return 0.0  # for ITM options, touch is guaranteed so POT = 100%
    except:
        return 0.0

# ----------------------------
# STREAMLIT UI
# ----------------------------
st.title("Condor/Short Call/Short Put Probability of Touch (POT) Calculator")
st.caption("This tool estimates the probability that the underlying's price will touch your short strike(s) at any time before the contracts expire...")

with st.sidebar:
    st.sidebar.header("Inputs")
    strategy = st.sidebar.selectbox("Select Strategy", ["Iron Condor", "Short Put", "Short Call"])
    ticker_symbol = st.sidebar.text_input("Ticker Symbol", "^NDX")
    st.caption("Enter stock/ETF ticker (e.g. TSLA) or index symbol (e.g. ^SPX for S&P 500).")
    pct_OTM_input = st.sidebar.number_input("Percent OTM)", value=2.0, step=0.1, format="%.1f")
    st.caption("Distance from current price for short strikes.")
    pct_OTM = pct_OTM_input / 100

    days_to_expiration = st.sidebar.number_input("Days to Expiration", value=2, step=1)
    st.caption("Number of calendar days until the option expires.")

    risk_free_rate = 0.05
    if st.checkbox("Use Risk-Free Rate Other Than 5%"):
        risk_free_rate_input = st.sidebar.number_input("Risk-Free Rate (decimal)", value=5.0, step=0.1, format="%.1f")
        risk_free_rate = risk_free_rate_input / 100

    agree = st.checkbox("Show Stats for Suggested Strikes")
    st.sidebar.markdown("---")
    st.sidebar.write("Change inputs and the calculator updates instantly.")

# ----------------------------
# DATA FETCHING
# ----------------------------
try:
    ticker = yf.Ticker(ticker_symbol)
    S = ticker.info.get('regularMarketPrice', None)

    if S is None:
        st.error("⚠️ Could not fetch live price for this ticker.")
        st.stop()

    expirations = ticker.options
    if not expirations:
        st.error("⚠️ No options data found for this ticker.")
        st.stop()

    # Find closest valid expiration >= desired target date
    target_expiration_date = datetime.today().date() + timedelta(days=days_to_expiration)
    expiration_dates = [datetime.strptime(date, "%Y-%m-%d").date() for date in expirations]
    future_expirations = [d for d in expiration_dates if d >= datetime.today().date()]
    if not future_expirations:
        st.error("⚠️ No future expiration dates available.")
        st.stop()

    closest_expiration = min(future_expirations, key=lambda d: abs(d - target_expiration_date))
    actual_days_to_expiration = (closest_expiration - datetime.today().date()).days
    expiration_date_str = closest_expiration.strftime("%Y-%m-%d")

    opt_chain = ticker.option_chain(expiration_date_str)
    calls = opt_chain.calls
    puts = opt_chain.puts

    call_target = round(S * (1 + pct_OTM) / 10) * 10
    put_target = round(S * (1 - pct_OTM) / 10) * 10

    call_strike = calls['strike'].iloc[(calls['strike'] - call_target).abs().argsort()[0]]
    put_strike = puts['strike'].iloc[(puts['strike'] - put_target).abs().argsort()[0]]

    call_row = calls[calls['strike'] == call_strike]
    put_row = puts[puts['strike'] == put_strike]

    call_iv = call_row['impliedVolatility'].iloc[0]
    put_iv = put_row['impliedVolatility'].iloc[0]

    call_volume = call_row['volume'].iloc[0]
    put_volume = put_row['volume'].iloc[0]

    call_oi = call_row['openInterest'].iloc[0]
    put_oi = put_row['openInterest'].iloc[0]

    call_bid = call_row['bid'].iloc[0]
    call_ask = call_row['ask'].iloc[0]
    put_bid = put_row['bid'].iloc[0]
    put_ask = put_row['ask'].iloc[0]

    T = actual_days_to_expiration / 365.0

    pot_call = black_scholes_pot(S, K, T, r, sigma, option_type='call')
    pot_put = black_scholes_pot(S, K, T, r, sigma, option_type='put')

    prob_either_touch = pot_call + pot_put - (pot_call * pot_put)
    prob_neither_touch = 1 - prob_either_touch


# ----------------------------
# DISPLAY RESULTS
# ----------------------------
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Strategy Results")

        if strategy == "Iron Condor":
            m1, m2 = st.columns(2)
            with m1:
                st.metric("Short Call Strike", f"{call_strike}")
                st.write(f"**Short Call POT:** {call_pot:.1%}")
            with m2:
                st.metric("Short Put Strike", f"{put_strike}")
                st.write(f"**Short Put POT:** {put_pot:.1%}")
            st.markdown("---")
            st.subheader(f"**Probability Neither Strike Touches:** :red[{prob_neither_touch:.1%}]")

        elif strategy == "Short Put":
            st.metric("Short Put Strike", f"{put_strike}")
            st.subheader(f"**Short Put POT:** :red[{put_pot:.1%}]")

        elif strategy == "Short Call":
            st.metric("Short Call Strike", f"{call_strike}")
            st.subheader(f"**Short Call POT:** :red[{call_pot:.1%}]")

    with col2:
        st.markdown("### Underlying Info")
        st.metric("Current Value", f"{S:,.2f}")
        st.write(f"**Strategy Expiry:** {closest_expiration.strftime('%b %d, %Y')} ({actual_days_to_expiration} DTE)")

    if agree:
        col3, col4 = st.columns(2)

        with col3:
            st.markdown("### Short Call Stats")
            if strategy in ["Iron Condor", "Short Call"]:
                st.write(f"**IV:** {call_iv:.2%}")
                st.write(f"**Volume:** {call_volume}")
                st.write(f"**Open Interest:** {call_oi}")
                st.write(f"**Bid:** {call_bid}")
                st.write(f"**Ask:** {call_ask}")
            else:
                st.info("No Short Call position for this strategy.")

        with col4:
            st.markdown("### Short Put Stats")
            if strategy in ["Iron Condor", "Short Put"]:
                st.write(f"**IV:** {put_iv:.2%}")
                st.write(f"**Volume:** {put_volume}")
                st.write(f"**Open Interest:** {put_oi}")
                st.write(f"**Bid:** {put_bid}")
                st.write(f"**Ask:** {put_ask}")
            else:
                st.info("No Short Put position for this strategy.")

    st.markdown("---")
    st.caption("POT is calculated using the Black-Scholes model...")
    st.caption("Disclaimer: This tool is for educational and informational purposes only...")

except Exception as e:
    st.error(f"An error occurred: {e}")
