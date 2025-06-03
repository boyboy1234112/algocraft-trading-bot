import streamlit as st
import pandas as pd
import ccxt
import plotly.express as px
import plotly.graph_objects as go

# 1. Fetch historical data (using OKX API)
@st.cache_data
def fetch_okx_data(symbol='BTC-USDT', timeframe='1h', limit=1000):
    try:
        exchange = ccxt.okx()
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        return df
    except ccxt.base.errors.ExchangeNotAvailable as e:
        st.error(f"Unable to connect to OKX API: {str(e)}. Please check network or try again later.")
        return None
    except Exception as e:
        st.error(f"Error fetching data: {str(e)}")
        return None

# 2. Calculate Simple Moving Averages (SMA)
def calculate_sma(df, short_window, long_window):
    df['short_sma'] = df['close'].rolling(window=short_window).mean()
    df['long_sma'] = df['close'].rolling(window=long_window).mean()
    return df

# 3. Generate trading signals
def generate_signals(df):
    df['signal'] = 0  # 0: No signal, 1: Buy, -1: Sell
    df['signal'][df['short_sma'] > df['long_sma']] = 1  # Short SMA crosses above long SMA -> Buy
    df['signal'][df['short_sma'] < df['long_sma']] = -1  # Short SMA crosses below long SMA -> Sell
    return df

# 4. Simulate trading and calculate returns
def backtest_strategy(df, initial_cash=10000):
    position = 0  # Current position (0: No position, >0: Long position)
    cash = initial_cash
    portfolio = []
    trades = []
    
    for i in range(1, len(df)):
        if df['signal'].iloc[i] == 1 and position == 0:  # Buy signal
            position = cash / df['close'].iloc[i]
            cash = 0
            trades.append(f"Buy at {df.index[i]}: Price = ${df['close'].iloc[i]:.2f}")
        elif df['signal'].iloc[i] == -1 and position > 0:  # Sell signal
            cash = position * df['close'].iloc[i]
            position = 0
            trades.append(f"Sell at {df.index[i]}: Price = ${df['close'].iloc[i]:.2f}")
        portfolio_value = cash + position * df['close'].iloc[i]
        portfolio.append(portfolio_value)
    
    df['portfolio_value'] = pd.Series([initial_cash] + portfolio, index=df.index)
    return df, trades

# 5. Calculate backtest metrics
def calculate_metrics(df, trades):
    total_trades = len(trades) // 2  # Each buy-sell pair counts as one trade
    winning_trades = sum(1 for i in range(1, len(trades), 2) if float(trades[i].split('$')[1]) > float(trades[i-1].split('$')[1]))
    win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0
    max_drawdown = (df['portfolio_value'].max() - df['portfolio_value'].min()) / df['portfolio_value'].max() * 100
    return total_trades, win_rate, max_drawdown

# 6. Streamlit frontend
def main():
    st.title("📈 AlgoCraft Trading Bot Demo: SMA Strategy")
    st.write("Explore this trading bot demo based on the Simple Moving Average (SMA) strategy. Adjust parameters to see backtest results for your chosen trading pair and timeframe!")

    # Sidebar: User input parameters
    st.sidebar.header("Backtest Parameters")
    symbol = st.sidebar.selectbox("Select Trading Pair", ["BTC-USDT", "ETH-USDT", "BNB-USDT"])
    timeframe = st.sidebar.selectbox("Select Timeframe", ["1h", "4h", "1d"])
    short_window = st.sidebar.slider("Short SMA Window", 5, 50, 20)
    long_window = st.sidebar.slider("Long SMA Window", 10, 100, 50)
    initial_cash = st.sidebar.number_input("Initial Capital ($)", 1000, 100000, 10000)

    # Fetch data
    with st.spinner(f"Fetching {symbol} data from OKX..."):
        df = fetch_okx_data(symbol=symbol, timeframe=timeframe)
    
    # Check if data was successfully fetched
    if df is None:
        st.stop()

    # Calculate SMA and trading signals
    df = calculate_sma(df, short_window, long_window)
    df = generate_signals(df)

    # Perform backtest
    df, trades = backtest_strategy(df, initial_cash)

    # Calculate backtest metrics
    total_trades, win_rate, max_drawdown = calculate_metrics(df, trades)

    # Display returns and metrics
    st.subheader("Backtest Results")
    final_value = df['portfolio_value'].iloc[-1]
    profit = final_value - initial_cash
    profit_pct = (final_value / initial_cash - 1) * 100
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Initial Capital", f"${initial_cash:,.2f}")
    col2.metric("Final Portfolio Value", f"${final_value:,.2f}")
    col3.metric("Profit", f"${profit:,.2f} ({profit_pct:.2f}%)")
    col4.metric("Total Trades", total_trades)
    col1.metric("Win Rate", f"{win_rate:.2f}%")
    col2.metric("Max Drawdown", f"{max_drawdown:.2f}%")

    # Plot price and SMA chart (with buy/sell signals)
    st.subheader("Price and SMA Chart")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df['close'], name='Price', line=dict(color='blue')))
    fig.add_trace(go.Scatter(x=df.index, y=df['short_sma'], name=f'Short SMA ({short_window})', line=dict(color='orange')))
    fig.add_trace(go.Scatter(x=df.index, y=df['long_sma'], name=f'Long SMA ({long_window})', line=dict(color='green')))
    # Add buy signals
    buy_signals = df[df['signal'] == 1]
    fig.add_trace(go.Scatter(
        x=buy_signals.index, y=buy_signals['close'],
        mode='markers', name='Buy Signal',
        marker=dict(symbol='triangle-up', size=10, color='green')
    ))
    # Add sell signals
    sell_signals = df[df['signal'] == -1]
    fig.add_trace(go.Scatter(
        x=sell_signals.index, y=sell_signals['close'],
        mode='markers', name='Sell Signal',
        marker=dict(symbol='triangle-down', size=10, color='red')
    ))
    fig.update_layout(
        title=f"{symbol} SMA Trading Strategy (Short: {short_window} | Long: {long_window})",
        xaxis_title="Date",
        yaxis_title="Price (USDT)",
        template="plotly_white"
    )
    st.plotly_chart(fig)

    # Plot portfolio value chart
    st.subheader("Portfolio Value")
    fig_portfolio = px.line(df, x=df.index, y='portfolio_value', title="Portfolio Value Over Time")
    fig_portfolio.update_layout(template="plotly_white")
    st.plotly_chart(fig_portfolio)

    # Display trade history
    st.subheader("Trade History")
    for trade in trades:
        st.write(trade)

# Run Streamlit
if __name__ == "__main__":
    main()