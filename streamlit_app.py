import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
from PIL import Image
import requests
import math

# 1. 頁面基本設定
st.set_page_config(page_title="實戰波段部位控管系統", layout="wide")
st.title("📈 實戰波段部位即時控管儀表板")

# 2. Airtable 連線憑證
AIRTABLE_PAT = "patNvk9pkE2vY8uCh.224e2d113ee94d2f505d3149a7d0c496102267aef209975ef47d425eef07d6ef"
BASE_ID = "appQ7xRHJ03llVlm1" 
TABLE_NAME = "History"

# ================= 側邊欄：使用者切換 =================
st.sidebar.title("👤 使用者設定")
current_user = st.sidebar.radio("目前操作者：", ["yoru", "bear"])
st.sidebar.markdown("---")
st.sidebar.write(f"🟢 系統目前工作區：**{current_user}**")

# 3. Airtable 讀寫功能
def fetch_airtable_data():
    url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME}"
    headers = {"Authorization": f"Bearer {AIRTABLE_PAT}"}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            records = response.json().get('records', [])
            data = []
            for r in records:
                fields = r.get('fields', {})
                data.append({
                    '日期': fields.get('日期', ''),
                    '使用者': fields.get('使用者', ''),
                    '股號': fields.get('股號', ''),
                    '類型': fields.get('類型', ''),
                    '損益金額': fields.get('損益金額', 0)
                })
            return pd.DataFrame(data)
        else:
            return pd.DataFrame(columns=['日期', '使用者', '股號', '類型', '損益金額'])
    except Exception:
        return pd.DataFrame(columns=['日期', '使用者', '股號', '類型', '損益金額'])

def add_airtable_record(date_str, user, stock, close_type, pnl):
    url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_PAT}",
        "Content-Type": "application/json"
    }
    data = {
        "records": [{
            "fields": {
                "日期": str(date_str),
                "使用者": str(user),
                "股號": str(stock),
                "類型": str(close_type),
                "損益金額": float(pnl)
            }
        }]
    }
    requests.post(url, headers=headers, json=data)

# 4. 暫存狀態管理
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = {"yoru": {}, "bear": {}}
if 'history' not in st.session_state or st.session_state.get('refresh_history', True):
    st.session_state.history = fetch_airtable_data()
    st.session_state.refresh_history = False

user_portfolio = st.session_state.portfolio[current_user]

# ================= 共用計算 Helper =================
# 用於處理資金與股價變動時，即時推算股數 (無條件捨去至整數)
def calc_shares(capital, price):
    if price > 0:
        return math.floor(capital / price)
    return 0

# 5. 介面分頁設定
tab_new, tab_monitor, tab_history = st.tabs(["📝 1. 新增母單 (建倉)", "🖥️ 2. 盤中監控與動態加碼", "💰 3. 雲端績效結算與曲線圖"])

# ================= 分頁 1: 新增母單 =================
with tab_new:
    st.header(f"建立新部位 ({current_user} 的工作區)")
    col1, col2 = st.columns(2)
    
    with col1:
        new_date = st.date_input("進場日期", datetime.date.today(), key="new_date")
        new_stock = st.text_input("🏷️ 股號 (必填)", placeholder="例如: 2330")
        
        st.markdown("##### 資金與部位設定")
        # 母單動態計算區
        new_capital = st.number_input("💰 預定投入資金 (元)", min_value=0, value=25000, step=1000, key="new_cap")
        new_price = st.number_input("進場價格", min_value=0.0, step=0.5, format="%.2f", key="new_pri")
        
        # 顯示自動計算建議股數，但允許使用者手動修改
        suggested_shares = calc_shares(new_capital, new_price)
        st.caption(f"💡 系統試算：依此價格與資金，最多可買 **{suggested_shares:,}** 股")
        new_shares = st.number_input("實際買進股數", min_value=0, value=suggested_shares, step=1, key="new_sha")
        
    with col2:
        st.info("💡 提示：點擊下方虛線框框內任意處，即可使用 Ctrl+V 貼上截圖。")
        uploaded_file = st.file_uploader("📸 上傳進場位置截圖", type=['png', 'jpg', 'jpeg'])
        if uploaded_file is not None:
            st.image(Image.open(uploaded_file), caption="進場截圖預覽", use_container_width=True)
            
    if st.button("💾 儲存母單並加入監控", type="primary"):
        if new_stock:
            user_portfolio[new_stock] = {
                'date': new_date,
                'price': new_price,
                'shares': new_shares,
                'image': uploaded_file,
                # 每個加碼包含 capital 供動態計算
                'addons': [{'active': False, 'capital': 10000, 'price': 0.0, 'shares': 0} for _ in range(4)]
            }
            st.success(f"股號 {new_stock} 已成功加入 {current_user} 的盤中監控清單！")
        else:
            st.error("請輸入股號！")

# ================= 分頁 2: 盤中監控 =================
with tab_monitor:
    if not user_portfolio:
        st.info(f"目前 {current_user} 沒有持倉紀錄。請先到「新增母單」建立部位。")
    else:
        st.header(f"盤中持倉動態控管 ({current_user})")
        stock_list = list(user_portfolio.keys())
        selected_stock = st.selectbox("🔍 選擇要監控/編輯的持倉", stock_list)
        
        if selected_stock:
            trade_data = user_portfolio[selected_stock]
            c_left, c_right = st.columns([1.2, 1])
            
            with c_left:
                st.subheader("🔹 原始母單資訊")
                st.write(f"**進場日:** {trade_data['date']} | **價格:** {trade_data['price']:.2f} | **股數:** {trade_data['shares']}")
                if trade_data['price'] > 0:
                    mother_sl_price = trade_data['price'] * 0.8
                    st.markdown(f"🚨 **母單原始停損 (-20%):** :red[{mother_sl_price:.2f}]")
                else:
                    mother_sl_price = 0.0
                
                if trade_data['image'] is not None:
                    with st.expander("展開查看進場截圖"):
                        st.image(Image.open(trade_data['image']), use_container_width=True)
                
                st.markdown("---")
                st.subheader("🔸 加碼單動態設定")
                
                for i in range(4):
                    addon = trade_data['addons'][i]
                    is_active = st.toggle(f"啟用加碼 {i+1}", value=addon['active'], key=f"t_{current_user}_{selected_stock}_{i}")
                    
                    if is_active:
                        col_c, col_p, col_s = st.columns([1, 1, 1])
                        with col_c:
                            a_cap = st.number_input("預定資金", min_value=0, step=1000, value=addon['capital'], key=f"c_{current_user}_{selected_stock}_{i}")
                        with col_p:
                            a_price = st.number_input("價格", min_value=0.0, step=0.5, format="%.2f", value=float(addon['price']), key=f"p_{current_user}_{selected_stock}_{i}")
                        
                        # 核心修正：動態提供預設股數，但不鎖死
                        sugg_a_shares = calc_shares(a_cap, a_price)
                        # 如果使用者之前沒有存過股數 (0)，就填入系統建議的；否則維持他上次存的。
                        init_s_val = addon['shares'] if addon['shares'] > 0 else sugg_a_shares
                        
                        with col_s:
                            a_shares = st.number_input(f"股數 (建議:{sugg_a_shares})", min_value=0, step=1, value=init_s_val, key=f"s_{current_user}_{selected_stock}_{i}")
                        
                        # 即時存檔
                        trade_data['addons'][i] = {'active': True, 'capital': a_cap, 'price': a_price, 'shares': a_shares}
                    else:
                        trade_data['addons'][i]['active'] = False

            with c_right:
                st.subheader("🛡️ 即時部位與風險推算")
                
                # 計算總部位狀態
                total_shares = trade_data['shares']
                total_cost = trade_data['price'] * trade_data['shares']
                
                for addon in trade_data['addons']:
                    if addon['active']:
                        total_shares += addon['shares']
                        total_cost += (addon['price'] * addon['shares'])
                        
                avg_price = total_cost / total_shares if total_shares > 0 else 0
                
                st.info(f"### 📊 最新平均成本: **{avg_price:.2f}**")
                m1, m2 = st.columns(2)
                m1.metric("總持股數", f"{total_shares:,} 股")
                m2.metric("總投入本金", f"${total_cost:,.0f}")
                
                st.markdown("---")
                
                # 修正需求 3：跌到母單-20%時全數出清會賠多少
                if total_shares > 0 and trade_data['price'] > 0:
                    st.warning("⚠️ **極限防守試算 (防守母單)**")
                    est_loss_at_mother_sl = (mother_sl_price - avg_price) * total_shares
                    st.write(f"若現有部位跌至母單停損價 **{mother_sl_price:.2f}** 全部出場：")
                    st.write(f"👉 預估將虧損：**{est_loss_at_mother_sl:,.0f}** 元")
                
                st.markdown("---")
                
                # 修正需求 2：手動輸入預定停利價，試算獲利
                st.success("🎯 **預期停利/停損試算區**")
                target_price = st.number_input("手動輸入預期出場價格", min_value=0.0, value=float(avg_price * 1.1), step=0.5, format="%.2f", key=f"tp_{current_user}_{selected_stock}")
                est_pnl = (target_price - avg_price) * total_shares
                
                if est_pnl > 0:
                    st.write(f"🎉 若在此價格全部出場，預估將 **獲利 {est_pnl:,.0f}** 元")
                elif est_pnl < 0:
                    st.write(f"💸 若在此價格全部出場，預估將 **虧損 {est_pnl:,.0f}** 元")
                else:
                    st.write(f"⚖️ 若在此價格全部出場，預估將 **損益兩平**")
                
                st.markdown("---")
                st.subheader("💰 部位平倉結算")
                with st.form(key=f"close_form_{current_user}_{selected_stock}"):
                    close_type = st.selectbox("出場類型", ["停利出場", "停損出場", "保本出場"])
                    # 自動帶入剛剛試算好的獲利/虧損金額
                    close_pnl = st.number_input("此筆交易總損益金額", step=1000, value=int(est_pnl))
                    
                    if st.form_submit_button(f"出清部位並寫入 {current_user} 的績效"):
                        add_airtable_record(datetime.date.today(), current_user, selected_stock, close_type, close_pnl)
                        st.session_state.refresh_history = True
                        del user_portfolio[selected_stock]
                        st.success(f"{selected_stock} 已結算！已同步至 {current_user} 的專屬雲端紀錄。")
                        st.rerun()

# ================= 分頁 3: 歷史紀錄 =================
with tab_history:
    st.header(f"雲端歷史績效與成長曲線 ({current_user})")
        
    df = st.session_state.history.copy()
    
    if not df.empty and '使用者' in df.columns:
        user_df = df[df['使用者'] == current_user].copy()
    else:
        user_df = pd.DataFrame()
        
    if not user_df.empty:
        user_df['日期'] = pd.to_datetime(user_df['日期'], errors='coerce')
        user_df['損益金額'] = pd.to_numeric(user_df['損益金額'], errors='coerce').fillna(0)
        user_df = user_df.sort_values('日期')
        user_df['累積損益'] = user_df['損益金額'].cumsum()
        
        total_profit = user_df['損益金額'].sum()
        st.metric(label=f"{current_user} 累積總損益", value=f"{total_profit:,.0f} 元")
        
        fig = px.line(user_df, x='日期', y='累積損益', title=f"{current_user} 的帳戶淨值曲線", markers=True)
        fig.update_layout(xaxis_title="結算時間", yaxis_title="累積金額", hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("交易明細 (已同步至 Airtable)")
        display_df = user_df.drop(columns=['使用者']) if '使用者' in user_df.columns else user_df
        st.dataframe(display_df, use_container_width=True)
    else:
        st.info(f"目前 {current_user} 尚無結算紀錄。當部位出清後，專屬資料就會在此產生。")
