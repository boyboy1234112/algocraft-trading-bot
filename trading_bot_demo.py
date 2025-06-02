import streamlit as st
import pandas as pd
import ccxt
import plotly.express as px
import plotly.graph_objects as go

# 1. 獲取歷史數據（使用 OKX API）
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
        st.error(f"無法連接到 OKX API: {str(e)}。請檢查網絡或稍後重試。")
        return None
    except Exception as e:
        st.error(f"獲取數據時發生錯誤: {str(e)}")
        return None

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
    st.write("探索這個基於簡單移動平均線（SMA）策略的交易機器人演示。調整參數以查看您選擇的交易對和時間框架的回測結果！")

    # 側邊欄：用戶輸入參數
    st.sidebar.header("回測參數")
    symbol = st.sidebar.selectbox("選擇交易對", ["BTC-USDT", "ETH-USDT", "BNB-USDT"])
    timeframe = st.sidebar.selectbox("選擇時間框架", ["1h", "4h", "1d"])
    short_window = st.sidebar.slider("短期 SMA 窗口", 5, 50, 20)
    long_window = st.sidebar.slider("長期 SMA 窗口", 10, 100, 50)
    initial_cash = st.sidebar.number_input("初始資金 ($)", 1000, 100000, 10000)

    # 獲取數據
    with st.spinner(f"正在從 OKX 獲取 {symbol} 數據..."):
        df = fetch_okx_data(symbol=symbol, timeframe=timeframe)
    
    # 檢查數據是否成功獲取
    if df is None:
        st.stop()

    # 計算 SMA 和交易信號
    df = calculate_sma(df, short_window, long_window)
    df = generate_signals(df)

    # 執行回測
    df, trades = backtest_strategy(df, initial_cash)

    # 計算回測指標
    total_trades, win_rate, max_drawdown = calculate_metrics(df, trades)

    # 顯示回報和指標
    st.subheader("回測結果")
    final_value = df['portfolio_value'].iloc[-1]
    profit = final_value - initial_cash
    profit_pct = (final_value / initial_cash - 1) * 100
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("初始資金", f"${initial_cash:,.2f}")
    col2.metric("最終投資組合價值", f"${final_value:,.2f}")
    col3.metric("利潤", f"${profit:,.2f} ({profit_pct:.2f}%)")
    col4.metric("總交易次數", total_trades)
    col1.metric("勝率", f"{win_rate:.2f}%")
    col2.metric("最大回撤", f"{max_drawdown:.2f}%")

    # 繪製價格和 SMA 圖表（含買賣信號）
    st.subheader("價格和 SMA 圖表")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df['close'], name='價格', line=dict(color='blue')))
    fig.add_trace(go.Scatter(x=df.index, y=df['short_sma'], name=f'短期 SMA ({short_window})', line=dict(color='orange')))
    fig.add_trace(go.Scatter(x=df.index, y=df['long_sma'], name=f'長期 SMA ({long_window})', line=dict(color='green')))
    # 添加買入信號
    buy_signals = df[df['signal'] == 1]
    fig.add_trace(go.Scatter(
        x=buy_signals.index, y=buy_signals['close'],
        mode='markers', name='買入信號',
        marker=dict(symbol='triangle-up', size=10, color='green')
    ))
    # 添加賣出信號
    sell_signals = df[df['signal'] == -1]
    fig.add_trace(go.Scatter(
        x=sell_signals.index, y=sell_signals['close'],
        mode='markers', name='賣出信號',
        marker=dict(symbol='triangle-down', size=10, color='red')
    ))
    fig.update_layout(
        title=f"{symbol} SMA 交易策略 (短期: {short_window} | 長期: {long_window})",
        xaxis_title="日期",
        yaxis_title="價格 (USDT)",
        template="plotly_white"
    )
    st.plotly_chart(fig)

    # 繪製投資組合價值圖表
    st.subheader("投資組合價值")
    fig_portfolio = px.line(df, x=df.index, y='portfolio_value', title="投資組合價值隨時間變化")
    fig_portfolio.update_layout(template="plotly_white")
    st.plotly_chart(fig_portfolio)

    # 顯示交易記錄
    st.subheader("交易記錄")
    for trade in trades:
        st.write(trade)

# 運行 Streamlit
if __name__ == "__main__":
    main()