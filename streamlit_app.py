import streamlit as st
import pandas as pd
import datetime

# 頁面基本設定
st.set_page_config(page_title="實戰波段部位控管系統", layout="wide")
st.title("📈 實戰波段部位即時控管儀表板")

# 建立左右兩大區塊：左邊輸入，右邊看即時結果
col_input, col_dashboard = st.columns([1, 1.2])

with col_input:
    st.header("1. 部位即時編輯區")
    
    # 紀錄日期與股號 (方便截圖或紀錄)
    c1, c2 = st.columns(2)
    with c1:
        trade_date = st.date_input("📝 紀錄日期", datetime.date.today())
    with c2:
        stock_input = st.text_input("🏷️ 股號", placeholder="例如: 2330")

    st.markdown("---")
    
    # ================= 母單設定 =================
    st.subheader("🔹 母單設定")
    init_price = st.number_input("母單進場價格", min_value=0.0, step=0.5, format="%.2f")
    init_shares = st.number_input("母單股數", min_value=0, step=1000)
    
    # 計算初始停損價 (母單的 -20%)
    if init_price > 0:
        initial_sl_price = init_price * 0.8
        st.markdown(f"🚨 **母單原始停損防線 (-20%):** :red[{initial_sl_price:.2f}]")

    st.markdown("---")
    
    # ================= 加碼單設定 =================
    st.subheader("🔸 加碼單動態設定")
    st.caption("勾選以啟用加碼單，可隨時修改價格與股數")
    
    add_on_data = []
    
    for i in range(1, 5):
        # 使用 toggle (開關) 讓介面更現代
        is_active = st.toggle(f"啟用加碼 {i}", key=f"toggle_{i}")
        
        if is_active:
            col_p, col_s = st.columns(2)
            with col_p:
                a_price = st.number_input(f"加碼 {i} 價格", min_value=0.0, step=0.5, format="%.2f", key=f"price_{i}")
            with col_s:
                a_shares = st.number_input(f"加碼 {i} 股數", min_value=0, step=1000, key=f"shares_{i}")
                
            if init_price > 0 and a_price > 0:
                # 即時計算這筆加碼與母單的距離
                diff_pct = ((a_price - init_price) / init_price) * 100
                if diff_pct > 0:
                    st.caption(f"📈 屬於右側加碼 (距離母單 +{diff_pct:.2f}%)")
                else:
                    st.caption(f"📉 屬於左側加碼 (距離母單 {diff_pct:.2f}%)")
                    
            add_on_data.append({'price': a_price, 'shares': a_shares})


with col_dashboard:
    st.header("2. 即時部位與風險總結")
    
    # ================= 核心邏輯計算 =================
    total_shares = init_shares
    total_cost = init_price * init_shares
    
    for add_on in add_on_data:
        total_shares += add_on['shares']
        total_cost += (add_on['price'] * add_on['shares'])
        
    avg_price = total_cost / total_shares if total_shares > 0 else 0
    
    # 顯示整體部位狀態
    st.info(f"### 📊 最新平均成本: **{avg_price:.2f}**")
    
    m1, m2 = st.columns(2)
    m1.metric("總持股數", f"{total_shares:,} 股")
    m2.metric("總投入本金", f"${total_cost:,.0f}")
    
    st.markdown("---")
    
    # ================= 嚴格停損位子計算 =================
    st.subheader("🛡️ 動態風險與停損防線")
    
    if total_shares > 0 and init_price > 0:
        # 計算一：如果維持「母單 -20%」作為極限停損點
        loss_at_initial_sl = (initial_sl_price - avg_price) * total_shares
        
        # 計算二：如果改以「最新均價的 -20%」作為停損點
        dynamic_sl_price = avg_price * 0.8
        loss_at_dynamic_sl = (dynamic_sl_price - avg_price) * total_shares
        
        st.error(f"**【策略 A】防守母單極限點位**")
        st.write(f"若跌至母單停損價 **{initial_sl_price:.2f}** 全部出場：")
        st.write(f"👉 預估總虧損金額：**{loss_at_initial_sl:,.0f}** 元")
        
        st.warning(f"**【策略 B】防守最新均價極限點位**")
        st.write(f"若改以當前總部位均價的 -20% (**{dynamic_sl_price:.2f}**) 全部出場：")
        st.write(f"👉 預估總虧損金額：**{loss_at_dynamic_sl:,.0f}** 元")
        
        # 進階：手動推演移動停損
        st.markdown("##### 🔍 試算移動停損")
        custom_sl = st.number_input("手動輸入預定停損/停利價 (試算結果)", value=float(initial_sl_price), step=0.5)
        custom_pnl = (custom_sl - avg_price) * total_shares
        
        if custom_pnl > 0:
            st.success(f"若在此價位出場，預估將 **獲利 {custom_pnl:,.0f}** 元")
        else:
            st.error(f"若在此價位出場，預估將 **虧損 {custom_pnl:,.0f}** 元")
            
    else:
        st.write("請在左側輸入母單資料以啟動計算...")