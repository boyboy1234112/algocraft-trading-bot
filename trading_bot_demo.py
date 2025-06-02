import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np
import time

# Streamlit 頁面配置
st.set_page_config(page_title="AlgoCraft Trading Bot Demo", layout="wide")
st.title("📈 AlgoCraft Trading Bot Demo: Enhanced SMA Strategy")
st.write("使用 CoinGecko API 獲取加密貨幣價格數據，支援 SMA、RSI 和布林帶策略")

# 定義 CoinGecko API 函數
@st.cache_data(ttl=60)
def get_coingecko_data(coin_id="bitcoin", vs_currency="usd", days=90):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {
        "vs_currency": vs_currency,
        "days": days,
        "interval": "daily"
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        prices = data["prices"]
        df = pd.DataFrame(prices, columns=["timestamp", "price"])
        df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df[["date", "price"]].set_index("date")
        return df
    except Exception as e:
        st.error(f"無法從 CoinGecko API 獲取數據: {e}")
        return None

# 實時價格
def get_current_price(coin_id="bitcoin", vs_currency="usd"):
    url = f"https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": coin_id, "vs_currencies": vs_currency}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()[coin_id][vs_currency]
    except Exception as e:
        st.error(f"無法獲取實時價格: {e}")
        return None

# 計算技術指標
def calculate_indicators(df, short_window=20, long_window=50, rsi_period=14, bb_window=20, bb_std=2):
    # SMA
    df["SMA_short"] = df["price"].rolling(window=short_window).mean()
    df["SMA_long"] = df["price"].rolling(window=long_window).mean()
    
    # RSI
    delta = df["price"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))
    
    # 布林帶
    df["BB_middle"] = df["price"].rolling(window=bb_window).mean()
    df["BB_std"] = df["price"].rolling(window=bb_window).std()
    df["BB_upper"] = df["BB_middle"] + bb_std * df["BB_std"]
    df["BB_lower"] = df["BB_middle"] - bb_std * df["BB_std"]
    
    return df

# 生成交易信號
def generate_signals(df, strategy="sma", rsi_overbought=70, rsi_oversold=30):
    df["Signal"] = 0
    if strategy == "sma":
        df["Signal"][(df["SMA_short"] > df["SMA_long"]) & (df["SMA_short"].shift(1) <= df["SMA_long"].shift(1))] = 1
        df["Signal"][(df["SMA_short"] < df["SMA_long"]) & (df["SMA_short"].shift(1) >= df["SMA_long"].shift(1))] = -1
    elif strategy == "rsi":
        df["Signal"][df["RSI"] < rsi_oversold] = 1
        df["Signal"][df["RSI"] > rsi_overbought] = -1
    elif strategy == "bollinger":
        df["Signal"][df["price"] < df["BB_lower"]] = 1
        df["Signal"][df["price"] > df["BB_upper"]] = -1
    return df

# 模擬交易
def simulate_trading(df, initial_cash=10000, fee_rate=0.001, stop_loss=0.1, take_profit=0.2):
    cash = initial_cash
    holdings = 0
    trades = []
    entry_price = 0
    
    for index, row in df.iterrows():
        portfolio_value = cash + holdings * row["price"]
        
        if row["Signal"] == 1 and cash > 0:  # 買入
            holdings = cash / row["price"] * (1 - fee_rate)
            cash = 0
            entry_price = row["price"]
            trades.append({"date": index, "type": "買入", "price": row["price"], "holdings": holdings, "cash": cash, "portfolio_value": portfolio_value})
        elif row["Signal"] == -1 and holdings > 0:  # 賣出
            cash = holdings * row["price"] * (1 - fee_rate)
            holdings = 0
            trades.append({"date": index, "type": "賣出", "price": row["price"], "holdings": holdings, "cash": cash, "portfolio_value": portfolio_value})
        elif holdings > 0:  # 止損/止盈
            price_change = (row["price"] - entry_price) / entry_price
            if price_change <= -stop_loss:
                cash = holdings * row["price"] * (1 - fee_rate)
                holdings = 0
                trades.append({"date": index, "type": "止損", "price": row["price"], "holdings": holdings, "cash": cash, "portfolio_value": portfolio_value})
            elif price_change >= take_profit:
                cash = holdings * row["price"] * (1 - fee_rate)
                holdings = 0
                trades.append({"date": index, "type": "止盈", "price": row["price"], "holdings": holdings, "cash": cash, "portfolio_value": portfolio_value})
        
        df.loc[index, "portfolio_value"] = portfolio_value
    
    return df, pd.DataFrame(trades)

# 計算績效指標
def calculate_metrics(df, initial_cash):
    returns = df["portfolio_value"].pct_change().dropna()
    annualized_return = returns.mean() * 252 * 100
    annualized_volatility = returns.std() * np.sqrt(252) * 100
    sharpe_ratio = annualized_return / annualized_volatility if annualized_volatility != 0 else 0
    max_drawdown = ((df["portfolio_value"].cummax() - df["portfolio_value"]) / df["portfolio_value"].cummax()).max() * 100
    return annualized_return, annualized_volatility, sharpe_ratio, max_drawdown

# 繪製圖表
def plot_data(df, trades, strategy, coin_id):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df["price"], name=f"{coin_id.upper()} 價格", line=dict(color="blue")))
    
    if strategy in ["sma", "all"]:
        fig.add_trace(go.Scatter(x=df.index, y=df["SMA_short"], name="SMA 20", line=dict(color="orange")))
        fig.add_trace(go.Scatter(x=df.index, y=df["SMA_long"], name="SMA 50", line=dict(color="green")))
    if strategy in ["bollinger", "all"]:
        fig.add_trace(go.Scatter(x=df.index, y=df["BB_middle"], name="布林帶中軌", line=dict(color="purple")))
        fig.add_trace(go.Scatter(x=df.index, y=df["BB_upper"], name="布林帶上軌", line=dict(dash="dash", color="purple")))
        fig.add_trace(go.Scatter(x=df.index, y=df["BB_lower"], name="布林帶下軌", line=dict(dash="dash", color="purple")))
    if strategy in ["rsi", "all"]:
        fig_rsi = go.Figure()
        fig_rsi.add_trace(go.Scatter(x=df.index, y=df["RSI"], name="RSI", line=dict(color="red")))
        fig_rsi.add_hline(y=70, line_dash="dash", line_color="gray", annotation_text="超買")
        fig_rsi.add_hline(y=30, line_dash="dash", line_color="gray", annotation_text="超賣")
        fig_rsi.update_layout(title="RSI 指標", xaxis_title="日期", yaxis_title="RSI", template="plotly_dark")
        st.plotly_chart(fig_rsi, use_container_width=True)
    
    buy_signals = df[df["Signal"] == 1]
    sell_signals = df[df["Signal"] == -1]
    fig.add_trace(go.Scatter(x=buy_signals.index, y=buy_signals["price"], name="買入信號", mode="markers", marker=dict(symbol="triangle-up", size=10, color="green")))
    fig.add_trace(go.Scatter(x=sell_signals.index, y=sell_signals["price"], name="賣出信號", mode="markers", marker=dict(symbol="triangle-down", size=10, color="red")))
    
    fig.update_layout(title=f"{coin_id.upper()} 價格與技術指標", xaxis_title="日期", yaxis_title="價格 (USD)", template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)
    
    fig_portfolio = go.Figure()
    fig_portfolio.add_trace(go.Scatter(x=df.index, y=df["portfolio_value"], name="投資組合價值", line=dict(color="purple")))
    fig_portfolio.update_layout(title="模擬投資組合價值", xaxis_title="日期", yaxis_title="價值 (USD)", template="plotly_dark")
    st.plotly_chart(fig_portfolio, use_container_width=True)

# 主程序
def main():
    st.sidebar.header("設置")
    coin_id = st.sidebar.selectbox("加密貨幣", ["bitcoin", "ethereum", "binancecoin"], format_func=lambda x: x.upper())
    days = st.sidebar.slider("數據天數", 30, 365, 90)
    strategy = st.sidebar.selectbox("交易策略", ["sma", "rsi", "bollinger", "all"])
    short_window = st.sidebar.slider("短期 SMA 窗口", 5, 50, 20)
    long_window = st.sidebar.slider("長期 SMA 窗口", 10, 100, 50)
    rsi_period = st.sidebar.slider("RSI 周期", 5, 30, 14)
    rsi_overbought = st.sidebar.slider("RSI 超買閾值", 50, 90, 70)
    rsi_oversold = st.sidebar.slider("RSI 超賣閾值", 10, 50, 30)
    bb_window = st.sidebar.slider("布林帶窗口", 10, 50, 20)
    bb_std = st.sidebar.slider("布林帶標準差倍數", 1.0, 3.0, 2.0)
    initial_cash = st.sidebar.number_input("初始資金 (USD)", 1000, 100000, 10000)
    fee_rate = st.sidebar.number_input("交易費用 (%)", 0.0, 1.0, 0.1) / 100
    stop_loss = st.sidebar.number_input("止損 (%)", 0.0, 50.0, 10.0) / 100
    take_profit = st.sidebar.number_input("止盈 (%)", 0.0, 50.0, 20.0) / 100
    auto_refresh = st.sidebar.checkbox("自動更新數據 (每分鐘)", False)
    
    if long_window <= short_window:
        st.error("長期 SMA 窗口必須大於短期 SMA 窗口")
        return
    if rsi_overbought <= rsi_oversold:
        st.error("RSI 超買閾值必須大於超賣閾值")
        return
    
    # 實時價格
    st.subheader("實時價格")
    current_price = get_current_price(coin_id)
    if current_price:
        st.write(f"{coin_id.upper()} 當前價格: ${current_price:.2f}")
    
    # 自動更新
    if auto_refresh:
        st.experimental_rerun()
        time.sleep(60)
    
    # 獲取數據
    with st.spinner("正在從 CoinGecko 獲取數據..."):
        df = get_coingecko_data(coin_id, days=days)
    
    if df is not None:
        # 計算指標和信號
        df = calculate_indicators(df, short_window, long_window, rsi_period, bb_window, bb_std)
        df = generate_signals(df, strategy, rsi_overbought, rsi_oversold)
        
        # 模擬交易
        df, trades = simulate_trading(df, initial_cash, fee_rate, stop_loss, take_profit)
        
        # 計算績效
        annualized_return, annualized_volatility, sharpe_ratio, max_drawdown = calculate_metrics(df, initial_cash)
        
        # 顯示結果
        st.subheader("交易概況")
        final_value = df["portfolio_value"].iloc[-1]
        st.write(f"初始資金: ${initial_cash:.2f}")
        st.write(f"最終投資組合價值: ${final_value:.2f}")
        st.write(f"收益率: {((final_value - initial_cash) / initial_cash * 100):.2f}%")
        st.write(f"年化收益率: {annualized_return:.2f}%")
        st.write(f"年化波動率: {annualized_volatility:.2f}%")
        st.write(f"夏普比率: {sharpe_ratio:.2f}")
        st.write(f"最大回撤: {max_drawdown:.2f}%")
        
        # 交易日誌
        st.subheader("交易日誌")
        if not trades.empty:
            st.dataframe(trades)
        else:
            st.write("無交易記錄")
        
        # 繪製圖表
        plot_data(df, trades, strategy, coin_id)

if __name__ == "__main__":
    main()