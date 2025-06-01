import streamlit as st
import pandas as pd
import ccxt
import plotly.express as px
import plotly.graph_objects as go

# 1. 獲取歷史數據（使用 Binance API）
@st.cache_data
def fetch_binance_data(symbol='BTC/USDT', timeframe='1h', limit=1000):
    exchange = ccxt.binance()
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    return df

# 2. 計算簡單移動平均線（SMA）
def calculate_sma(df, short_window, long_window):
    df['short_sma'] = df['close'].rolling(window=short_window).mean()
    df['long_sma'] = df['close'].rolling(window=long_window).mean()
    return df

# 3. 產生交易信號
def generate_signals(df):
    df['signal'] = 0  # 0: 無信號, 1: 買入, -1: 賣出
    df['signal'][df['short_sma'] > df['long_sma']] = 1  # 短均線上穿長均線 -> 買入
    df['signal'][df['short_sma'] < df['long_sma']] = -1  # 短均線下穿長均線 -> 賣出
    return df

# 4. 模擬交易並計算回報
def backtest_strategy(df, initial_cash=10000):
    position = 0  # 當前持倉（0: 無持倉, 1: 持有多頭）
    cash = initial_cash
    portfolio = []
    trades = []
    
    for i in range(1, len(df)):
        if df['signal'].iloc[i] == 1 and position == 0:  # 買入信號
            position = cash / df['close'].iloc[i]
            cash = 0
            trades.append(f"Buy at {df.index[i]}: Price = ${df['close'].iloc[i]:.2f}")
        elif df['signal'].iloc[i] == -1 and position > 0:  # 賣出信號
            cash = position * df['close'].iloc[i]
            position = 0
            trades.append(f"Sell at {df.index[i]}: Price = ${df['close'].iloc[i]:.2f}")
        portfolio_value = cash + position * df['close'].iloc[i]
        portfolio.append(portfolio_value)
    
    df['portfolio_value'] = pd.Series([initial_cash] + portfolio, index=df.index)
    return df, trades

# 5. 計算回測指標
def calculate_metrics(df, trades):
    total_trades = len(trades) // 2  # 每買賣一對算一次交易
    winning_trades = sum(1 for i in range(1, len(trades), 2) if float(trades[i].split('$')[1]) > float(trades[i-1].split('$')[1]))
    win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0
    max_drawdown = (df['portfolio_value'].max() - df['portfolio_value'].min()) / df['portfolio_value'].max() * 100
    return total_trades, win_rate, max_drawdown

# 6. Streamlit 前端
def main():
    st.title("📈 AlgoCraft Trading Bot Demo: SMA Strategy")
    st.write("Explore this demo of a trading bot using Simple Moving Average (SMA) strategy. Adjust parameters to see backtest results for your chosen trading pair and timeframe!")

    # 側邊欄：用戶輸入參數
    st.sidebar.header("Backtest Parameters")
    symbol = st.sidebar.selectbox("Select Trading Pair", ["BTC/USDT", "ETH/USDT", "BNB/USDT"])
    timeframe = st.sidebar.selectbox("Select Timeframe", ["1h", "4h", "1d"])
    short_window = st.sidebar.slider("Short SMA Window", 5, 50, 20)
    long_window = st.sidebar.slider("Long SMA Window", 10, 100, 50)
    initial_cash = st.sidebar.number_input("Initial Cash ($)", 1000, 100000, 10000)

    # 獲取數據
    with st.spinner(f"Fetching {symbol} data from Binance..."):
        df = fetch_binance_data(symbol=symbol, timeframe=timeframe)

    # 計算 SMA 和交易信號
    df = calculate_sma(df, short_window, long_window)
    df = generate_signals(df)

    # 執行回測
    df, trades = backtest_strategy(df, initial_cash)

    # 計算回測指標
    total_trades, win_rate, max_drawdown = calculate_metrics(df, trades)

    # 顯示回報和指標
    st.subheader("Backtest Results")
    final_value = df['portfolio_value'].iloc[-1]
    profit = final_value - initial_cash
    profit_pct = (final_value / initial_cash - 1) * 100
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Initial Cash", f"${initial_cash:,.2f}")
    col2.metric("Final Portfolio Value", f"${final_value:,.2f}")
    col3.metric("Profit", f"${profit:,.2f} ({profit_pct:.2f}%)")
    col4.metric("Total Trades", total_trades)
    col1.metric("Win Rate", f"{win_rate:.2f}%")
    col2.metric("Max Drawdown", f"{max_drawdown:.2f}%")

    # 繪製價格和 SMA 圖表（含買賣信號）
    st.subheader("Price and SMA Chart")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df['close'], name='Price', line=dict(color='blue')))
    fig.add_trace(go.Scatter(x=df.index, y=df['short_sma'], name=f'Short SMA ({short_window})', line=dict(color='orange')))
    fig.add_trace(go.Scatter(x=df.index, y=df['long_sma'], name=f'Long SMA ({long_window})', line=dict(color='green')))
    # 添加買入信號
    buy_signals = df[df['signal'] == 1]
    fig.add_trace(go.Scatter(
        x=buy_signals.index, y=buy_signals['close'],
        mode='markers', name='Buy Signal',
        marker=dict(symbol='triangle-up', size=10, color='green')
    ))
    # 添加賣出信號
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

    # 繪製投資組合價值圖表
    st.subheader("Portfolio Value")
    fig_portfolio = px.line(df, x=df.index, y='portfolio_value', title="Portfolio Value Over Time")
    fig_portfolio.update_layout(template="plotly_white")
    st.plotly_chart(fig_portfolio)

    # 顯示交易記錄
    st.subheader("Trade History")
    for trade in trades:
        st.write(trade)

# 運行 Streamlit
if __name__ == "__main__":
    main()