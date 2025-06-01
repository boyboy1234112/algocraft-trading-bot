import streamlit as st
import pandas as pd
import ccxt
import plotly.express as px
import plotly.graph_objects as go

# 1. 獲取歷史數據（使用 Binance API）
@st.cache_data
def fetch_binance_data(symbol='BTC/USDT', timeframe='1h', limit=1000):
    try:
        exchange = ccxt.binance({'enableRateLimit': True})  # 啟用速率限制
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        return df
    except ccxt.NetworkError as e:
        st.error(f"Network error while fetching data from Binance: {str(e)}")
        return pd.DataFrame()  # 返回空 DataFrame，防止應用崩潰
    except ccxt.ExchangeError as e:
        st.error(f"Exchange error: {str(e)}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")
        return pd.DataFrame()

# 以下是原始程式碼的其他部分（calculate_sma, generate_signals, backtest_strategy, calculate_metrics, main）
# 保持不變，但確保 main() 函數處理空 DataFrame
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

    # 檢查數據是否有效
    if df.empty:
        st.warning("Unable to fetch data. Please try again later or select a different trading pair/timeframe.")
        return

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

if __name__ == "__main__":
    main()