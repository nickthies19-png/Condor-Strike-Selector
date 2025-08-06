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
    # User Input for strategy type
    strategy = st.sidebar.selectbox("Select Strategy", ["Iron Condor", "Short Put", "Short Call"])
    # User input for ticker
    ticker_symbol = st.sidebar.text_input("Ticker Symbol", "^NDX")
    st.caption("Enter stock/ETF ticker (e.g. TSLA) or index symbol (e.g. ^SPX for S&P 500)")
    # Checkbox giving user option to enter their own strike(s) (custom strikes)
    use_custom_strikes = st.sidebar.checkbox("Enter my own strike(s)")
    
    # Initialize as None - making sure custom_call_strike and custom_put_strike are defined
    custom_call_strike = None
    custom_put_strike = None

    # Custom strike input fields - only shows fields applicable to the strategy selected above.
    if use_custom_strikes:
        if strategy == "Iron Condor":
            custom_call_strike = st.sidebar.number_input("Custom Call Strike", value=100.0, step=1.0)
            custom_put_strike = st.sidebar.number_input("Custom Put Strike", value=100.0, step=1.0)
        elif strategy == "Short Call":
            custom_call_strike = st.sidebar.number_input("Custom Call Strike", value=100.0, step=1.0)
        elif strategy == "Short Put":
            custom_put_strike = st.sidebar.number_input("Custom Put Strike", value=100.0, step=1.0)
    
    # Standard % OTM field where user selects desired OTM %
    else:
        pct_OTM = st.sidebar.number_input("Percent OTM", value=2.0, step=0.1, format="%.1f")
        st.caption("Define how far out-of-the-money (expressed as a %) you wish your condor/short call/short put to be")

    # Days to expiry input
    days_to_expiration = st.sidebar.number_input("Days to Expiration", value=2, step=1)
    st.caption("Number of calendar days until the options expire")

    # Risk-free rate input (conditional on if user decides to override 5% default)
    risk_free_rate = 0.05
    if st.checkbox("Use Risk-Free Rate Other Than 5%"):
        risk_free_rate_input = st.sidebar.number_input("Risk-Free Rate (decimal)", value=5.0, step=0.1, format="%.1f")
        risk_free_rate = risk_free_rate_input / 100
        st.caption("Default risk free rate of 5% (apprx. current short-term treasury note yield) is applied")

    # Option to show stats, (IV, OI, Bid/Ask, volume, etc.) for suggested or custom strikes
    agree = st.checkbox("Show Stats for Suggested Strikes")
    st.sidebar.markdown("---")
    st.sidebar.write("Change inputs and the calculator updates instantly.")

# ----------------------------
# DATA FETCHING
# ----------------------------
try:
    ticker = yf.Ticker(ticker_symbol)
    S = ticker.info.get('regularMarketPrice', None)
    data = ticker.history(period="1d", interval="1m")
    previous_day_data = yf.download(ticker_symbol, period="2d")
    previous_close = previous_day_data['Close'].iloc[-2]
    percentage_change = ((S - previous_close) / previous_close) * 100

    if S is None:
        st.error("\u26a0\ufe0f Could not fetch live price for this ticker.")
        st.stop()

    expirations = ticker.options
    if not expirations:
        st.error("\u26a0\ufe0f No options data found for this ticker.")
        st.stop()

    target_expiration_date = datetime.today().date() + timedelta(days=days_to_expiration)
    expiration_dates = [datetime.strptime(date, "%Y-%m-%d").date() for date in expirations]
    future_expirations = [d for d in expiration_dates if d >= datetime.today().date()]
    if not future_expirations:
        st.error("\u26a0\ufe0f No future expiration dates available.")
        st.stop()

    closest_expiration = min(future_expirations, key=lambda d: abs(d - target_expiration_date))
    actual_days_to_expiration = (closest_expiration - datetime.today().date()).days
    expiration_date_str = closest_expiration.strftime("%Y-%m-%d")

    # Pull option chain for selected ticker
    opt_chain = ticker.option_chain(expiration_date_str)
    calls = opt_chain.calls
    puts = opt_chain.puts

    # Choose custom or calculated strikes
    if use_custom_strikes:
        call_strike = float(custom_call_strike) if custom_call_strike is not None else None
        put_strike = float(custom_put_strike) if custom_put_strike is not None else None
    else:
        call_target = S * (1 + pct_OTM / 100)
        put_target = S * (1 - pct_OTM / 100)
        call_strike = calls['strike'].iloc[(calls['strike'] - call_target).abs().argsort()[0]]
        put_strike = puts['strike'].iloc[(puts['strike'] - put_target).abs().argsort()[0]]

    # Filter for available strikes
    call_row = calls[calls['strike'] == call_strike] if call_strike is not None else None
    put_row = puts[puts['strike'] == put_strike] if put_strike is not None else None

    if (strategy in ["Iron Condor", "Short Call"] and (call_row is None or call_row.empty)) or \
       (strategy in ["Iron Condor", "Short Put"] and (put_row is None or put_row.empty)):
        st.error("\u26a0\ufe0f One or more of the strikes entered is not available in the options chain for this ticker")
        st.stop()

    # Pull implied Volatility & Market Data
    call_iv = call_row['impliedVolatility'].iloc[0] if call_row is not None else None
    put_iv = put_row['impliedVolatility'].iloc[0] if put_row is not None else None

    call_volume = call_row['volume'].iloc[0] if call_row is not None else None
    put_volume = put_row['volume'].iloc[0] if put_row is not None else None

    call_oi = call_row['openInterest'].iloc[0] if call_row is not None else None
    put_oi = put_row['openInterest'].iloc[0] if put_row is not None else None

    call_bid = call_row['bid'].iloc[0] if call_row is not None else None
    call_ask = call_row['ask'].iloc[0] if call_row is not None else None
    put_bid = put_row['bid'].iloc[0] if put_row is not None else None
    put_ask = put_row['ask'].iloc[0] if put_row is not None else None

    T = actual_days_to_expiration / 365.0

    pot_call = prob_touch(S, call_strike, T, call_iv) if call_iv is not None else 0
    pot_put = prob_touch(S, put_strike, T, put_iv) if put_iv is not None else 0

    pot_call = min(max(pot_call, 0), 1)
    pot_put = min(max(pot_put, 0), 1)

    prob_either_touch = pot_call + pot_put - (pot_call * pot_put)
    prob_neither_touch = 1 - prob_either_touch

# ----------------------------
# DISPLAY RESULTS
# ----------------------------
    # Create 2 columns
    col1, col2 = st.columns(2)

    # Column 1 displays strategy results (POT) 
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

    # Column 2 displays info of the underlying
    with col2:
        st.markdown("### Underlying Info")
        st.metric("Current Value", f"{S:,.2f}")
        st.write(f"**Strategy Expiry:** {closest_expiration.strftime('%b %d, %Y')} ({actual_days_to_expiration} DTE)")

    # Displays 2 additional fields of data with suggested or custom strike data (IV, OI, Bid/Ask, volume, etc.)
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
    st.caption("Disclaimer: This tool is for educational and informational purposes only. It is not financial advice, and nothing displayed here should be taken as a recommendation to buy or sell any security or options contract. Market data is provided by Yahoo Finance and may be delayed or inaccurate. Probabilities shown are calculations based on simplified models (e.g., Black‑Scholes) and assumptions (e.g., volatility, risk‑free rate) that may not reflect real market conditions. Options trading involves significant risk and is not suitable for all investors. You are solely responsible for any financial decisions made based on the information from this tool.")
    
except Exception as e:
    st.error(f"Something went wrong: {e}")
