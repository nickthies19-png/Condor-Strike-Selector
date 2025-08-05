import streamlit as st
import yfinance as yf
import numpy as np
from scipy.stats import norm
from datetime import datetime, timedelta

# ----------------------------
# FUNCTIONS
# ----------------------------
from scipy.stats import norm
import numpy as np

def prob_touch(S, K, T, sigma):
    if T <= 0 or sigma <= 0:
        return 0
    from math import log, sqrt, exp
    from scipy.stats import norm

    return 2 * (1 - norm.cdf(abs(log(S / K)) / (sigma * sqrt(T))))

# ----------------------------
# STREAMLIT UI
# ----------------------------
st.title("Condor/Short Call/Short Put Probability of Touch (POT) Calculator")
st.caption("This tool estimates the probability that the underlying's price will touch your short strike(s) at any time before the contracts expire. This is not the same as the probability that your short strike(s) expire in-the-money, as price may touch your short strike(s) and and still expire out-of-the-money. For probability that your strikes expire in-the-money, see the Delta of the contract your are considering. A delta of .30 = a 30% chance that the strikes expires in-the-money")

with st.sidebar:
    st.sidebar.header("Inputs")
    strategy = st.sidebar.selectbox("Select Strategy", ["Iron Condor", "Short Put", "Short Call"])
    ticker_symbol = st.sidebar.text_input("Ticker Symbol", "^NDX")
    st.caption("Enter stock/ETF ticker (e.g. TSLA) or index symbol (e.g. ^SPX for S&P 500).")
    # Sidebar checkbox for custom input
    use_custom_strikes = st.sidebar.checkbox("Enter my own strike(s)")
    if use_custom_strikes:
        custom_call_strike = st.sidebar.number_input("Custom Call Strike", value=100.0, step=1.0)
        custom_put_strike = st.sidebar.number_input("Custom Put Strike", value=100.0, step=1.0)
    else:
        pct_OTM = st.sidebar.number_input("Percent OTM)", value=2.0, step=0.1, format="%.1f")

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

    # Pull option chain
    opt_chain = ticker.option_chain(expiration_date_str)
    calls = opt_chain.calls
    puts = opt_chain.puts

    #Find closest strike
    if use_custom_strikes:
        call_target = custom_call_strike
        put_target = custom_put_strike
    else:
        call_target = S * (1 + pct_OTM)
        put_target = S * (1 - pct_OTM)
    
        call_strike = calls['strike'].iloc[(calls['strike'] - call_target).abs().argsort()[0]]
        put_strike = puts['strike'].iloc[(puts['strike'] - put_target).abs().argsort()[0]]

        call_target = min(call_strike, key=lambda x: abs(x - call_target_price))
        put_target = min(put_strike, key=lambda x: abs(x - put_target_price))

    call_row = calls[calls['strike'] == call_strike]
    put_row = puts[puts['strike'] == put_strike]

    #Pull data for suggested strikes
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

    if use_custom_strikes:
        
        pot_call = prob_touch(S, custom_call_strike, T, call_iv)
        pot_put = prob_touch(S, custom_put_strike, T, put_iv)

        call_strike = custom_call_strike
        put_strike = custom_put_strike
    
    else:
        pot_call = prob_touch(S, call_strike, T, call_iv)
        pot_put = prob_touch(S, put_strike, T, put_iv)
    
    # Clamp
    pot_call = min(max(pot_call, 0), 1)
    pot_put = min(max(pot_put, 0), 1)
        
    # Combined logic
    prob_either_touch = pot_call + pot_put - (pot_call * pot_put)
    prob_neither_touch = 1 - prob_either_touch

# ----------------------------
# DISPLAY RESULTS
# ----------------------------
    col1, col2 = st.columns(2)
    #display strategy results
    with col1:
        st.markdown("### Strategy Results")

        if strategy == "Iron Condor":
            m1, m2 = st.columns(2)
            with m1:
                st.metric("Short Call Strike", f"{call_strike}")
                st.write(f"**Short Call POT:** {pot_call:.1%}")
            with m2:
                st.metric("Short Put Strike", f"{put_strike}")
                st.write(f"**Short Put POT:** {pot_put:.1%}")
            st.markdown("---")
            st.subheader(f"**Probability Neither Strike Touches:** :red[{prob_neither_touch:.1%}]")

        elif strategy == "Short Put":
            st.metric("Short Put Strike", f"{put_strike}")
            st.subheader(f"**Short Put POT:** :red[{pot_put:.1%}]")

        elif strategy == "Short Call":
            st.metric("Short Call Strike", f"{call_strike}")
            st.subheader(f"**Short Call POT:** :red[{pot_call:.1%}]")

    with col2:
        st.markdown("### Underlying Info")
        st.metric("Current Value", f"{S:,.2f}")
        st.write(f"**Strategy Expiry:** {closest_expiration.strftime('%b %d, %Y')} ({actual_days_to_expiration} DTE)")
    
    #Display suggested option stats if checkbox is checked
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
    st.caption("Disclaimer: his tool is for educational and informational purposes only. It is not financial advice, and nothing displayed here should be taken as a recommendation to buy or sell any security or options contract. Market data is provided by Yahoo Finance and may be delayed or inaccurate. Probabilities shown are calculations based on simplified models (e.g., Black‑Scholes) and assumptions (e.g., volatility, risk‑free rate) that may not reflect real market conditions. Options trading involves significant risk and is not suitable for all investors. You are solely responsible for any financial decisions made based on the information from this tool.")

except Exception as e:
    st.error(f"An error occurred: {e}")
