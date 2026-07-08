import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
from PIL import Image
import requests
import json

st.set_page_config(page_title="實戰波段部位控管系統", layout="wide")
st.title("📈 實戰波段部位即時控管儀表板")

# 2. Airtable 連線憑證
AIRTABLE_PAT = "patNvk9pkE2vY8uCh.224e2d113ee94d2f505d3149a7d0c496102267aef209975ef47d425eef07d6ef"
BASE_ID = "appQ7xRHJ03llVlm1" 
TABLE_NAME = "History"
TABLE_PORTFOLIO = "Portfolio"

st.sidebar.title("👤 使用者設定")
st.sidebar.info("請先確認目前操作者，系統會自動隔離雙方的部位與績效。")
current_user = st.sidebar.radio("目前操作者：", ["yoru", "bear"])

st.sidebar.markdown("---")
st.sidebar.write(f"🟢 系統目前工作區：**{current_user}**")

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

def load_portfolio_from_cloud():
    url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_PORTFOLIO}"
    headers = {"Authorization": f"Bearer {AIRTABLE_PAT}"}
    portfolio = {"yoru": {}, "bear": {}}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            records = response.json().get('records', [])
            for r in records:
                fields = r.get('fields', {})
                user = fields.get('使用者')
                stock = fields.get('股號')
                data_str = fields.get('資料包')
                rec_id = r.get('id')
                
                if user and stock and data_str:
                    if user not in portfolio:
                        portfolio[user] = {}
                    try:
                        data_dict = json.loads(data_str)
                        data_dict['record_id'] = rec_id # 記錄 Airtable 的專屬 ID
                        data_dict['image'] = None # 雲端不存圖片
                        portfolio[user][stock] = data_dict
                    except:
                        pass
    except:
        pass
    return portfolio

def sync_portfolio_to_cloud(user, stock, trade_data):
    headers = {
        "Authorization": f"Bearer {AIRTABLE_PAT}",
        "Content-Type": "application/json"
    }
    
    # 將數據打包成 JSON 字串 (排除圖片以節省空間)
    save_data = {
        'date': str(trade_data['date']),
        'price': float(trade_data['price']),
        'shares': int(trade_data['shares']),
        'addons': trade_data['addons']
    }
    data_str = json.dumps(save_data)
    record_id = trade_data.get('record_id')
    
    if record_id: # 雲端已有紀錄 -> 更新
        url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_PORTFOLIO}/{record_id}"
        data = {"fields": {"資料包": data_str}}
        requests.patch(url, headers=headers, json=data)
    else: # 雲端無紀錄 -> 新增
        url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_PORTFOLIO}"
        data = {
            "records": [{
                "fields": {
                    "股號": str(stock),
                    "使用者": str(user),
                    "資料包": data_str
                }
            }]
        }
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            try:
                # 把剛建立的 record_id 存回記憶體，下次才會是更新
                new_id = response.json()['records'][0]['id']
                trade_data['record_id'] = new_id
            except:
                pass

def delete_portfolio_from_cloud(record_id):
    if record_id:
        url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_PORTFOLIO}/{record_id}"
        headers = {"Authorization": f"Bearer {AIRTABLE_PAT}"}
        requests.delete(url, headers=headers)

if 'portfolio' not in st.session_state or st.session_state.get('refresh_portfolio', False):
    st.session_state.portfolio = load_portfolio_from_cloud()
    st.session_state.refresh_portfolio = False
    
if 'history' not in st.session_state or st.session_state.get('refresh_history', True):
    st.session_state.history = fetch_airtable_data()
    st.session_state.refresh_history = False

# 取得當前使用者的盤中部位
if current_user not in st.session_state.portfolio:
    st.session_state.portfolio[current_user] = {}
user_portfolio = st.session_state.portfolio[current_user]

# 5. 介面分頁設定
tab_new, tab_monitor, tab_history = st.tabs(["📝 1. 新增母單 (建倉)", "🖥️ 2. 盤中監控與動態加碼", "💰 3. 雲端績效結算與曲線圖"])

with tab_new:
    st.header(f"建立新部位 ({current_user} 的工作區)")
    col1, col2 = st.columns(2)
    
    with col1:
        new_date = st.date_input("進場日期", datetime.date.today(), key="new_date")
        new_stock = st.text_input("🏷️ 股號 (必填)", placeholder="例如: 2330")
        
        st.markdown("##### 資金與股數設定")
        new_capital = st.number_input("💰 母單預算資金 (元)", min_value=0, value=25000, step=1000)
        new_price = st.number_input("母單進場價格", min_value=0.0, step=0.5, format="%.2f")
        
        suggested_shares = int(new_capital / new_price) if new_price > 0 else 0
        st.caption(f"💡 系統試算：依此價格與資金，最多可買 **{suggested_shares:,}** 股")
        new_shares = st.number_input("實際買進股數", min_value=0, value=suggested_shares, step=1, key="new_sha")
    
    with col2:
        st.info("💡 提示：因瀏覽器安全限制無法直接 Ctrl+V。請使用截圖軟體後，直接「拖曳」圖片到下方虛線框，或先存檔再上傳。")
        uploaded_file = st.file_uploader("📸 上傳進場位置截圖", type=['png', 'jpg', 'jpeg'])
        if uploaded_file is not None:
            st.image(Image.open(uploaded_file), caption="進場截圖預覽", use_container_width=True)
            
    if st.button("💾 儲存母單並同步至雲端", type="primary"):
        if new_stock:
            new_data = {
                'date': str(new_date),
                'price': float(new_price),
                'shares': int(new_shares),
                'image': uploaded_file,
                'addons': [{'active': False, 'capital': 5000, 'price': 0.0, 'shares': 0} for _ in range(4)]
            }
            user_portfolio[new_stock] = new_data
            sync_portfolio_to_cloud(current_user, new_stock, new_data)
            st.success(f"股號 {new_stock} 已成功加入 {current_user} 的盤中監控清單！(已同步雲端)")
        else:
            st.error("請輸入股號！")

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
                st.write(f"**進場日:** {trade_data['date']} | **價格:** {trade_data['price']} | **股數:** {trade_data['shares']}")
                if trade_data['price'] > 0:
                    st.markdown(f"🚨 **母單原始停損 (-20%):** :red[{trade_data['price'] * 0.8:.2f}]")
                
                if trade_data.get('image') is not None:
                    with st.expander("展開查看進場截圖"):
                        try:
                            st.image(Image.open(trade_data['image']), use_container_width=True)
                        except:
                            st.write("圖片無法載入 (網頁重整後暫存圖片會消失，但數據已存於雲端)")
                
                st.markdown("---")
                st.subheader("🔸 加碼單動態設定")
                
                for i in range(4):
                    addon = trade_data['addons'][i]
                    is_active = st.toggle(f"啟用加碼 {i+1}", value=addon['active'], key=f"t_{current_user}_{selected_stock}_{i}")
                    
                    if is_active:
                        col_c, col_p, col_s = st.columns([1, 1, 1])
                        with col_c:
                            a_cap = st.number_input(f"預算資金", min_value=0, step=1000, value=addon['capital'], key=f"c_{current_user}_{selected_stock}_{i}")
                        with col_p:
                            a_price = st.number_input(f"價格", min_value=0.0, step=0.5, format="%.2f", value=float(addon['price']), key=f"p_{current_user}_{selected_stock}_{i}")
                        with col_s:
                            calc_a_shares = int(a_cap / a_price) if a_price > 0 else 0
                            # 如果使用者沒改過股數，就預設帶入系統算好的
                            default_shares = addon['shares'] if addon['shares'] > 0 else calc_a_shares
                            a_shares = st.number_input(f"股數", min_value=0, step=1, value=default_shares, key=f"s_{current_user}_{selected_stock}_{i}")
                        
                        trade_data['addons'][i] = {'active': True, 'capital': a_cap, 'price': a_price, 'shares': a_shares}
                    else:
                        trade_data['addons'][i]['active'] = False
                        
                st.markdown("---")
                if st.button(f"💾 同步更新 {selected_stock} 加碼設定至雲端", type="primary"):
                    sync_portfolio_to_cloud(current_user, selected_stock, trade_data)
                    st.success("加碼設定已成功同步至雲端！重整網頁也不會消失了。")

            with c_right:
                st.subheader("🛡️ 即時部位與風險推算")
                
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
                # 動態極限防守：母單價格 -20%
                mother_price = trade_data['price']
                if mother_price > 0 and total_shares > 0:
                    mother_sl_price = mother_price * 0.8
                    est_sl_loss = (mother_sl_price - avg_price) * total_shares
                    st.warning(f"**🚨 動態極限防線 (母單進場價 -20%)**")
                    st.write(f"若跌至母單停損價 **{mother_sl_price:.2f}** 全數出場，總部位預估虧損：**{est_sl_loss:,.0f}** 元")
                
                st.markdown("---")
                st.subheader("🎯 預期出場試算")
                target_price = st.number_input("請輸入預計停利/停損價格", min_value=0.0, step=0.5, format="%.2f", value=float(avg_price))
                
                est_profit = (target_price - avg_price) * total_shares
                if est_profit > 0:
                    st.success(f"若於 **{target_price:.2f}** 出場，預估獲利：**+{est_profit:,.0f}** 元")
                elif est_profit < 0:
                    st.error(f"若於 **{target_price:.2f}** 出場，預估虧損：**{est_profit:,.0f}** 元")
                else:
                    st.info("尚未產生損益")
                
                st.markdown("---")
                st.subheader("💰 部位平倉結算")
                with st.form(key=f"close_form_{current_user}_{selected_stock}"):
                    close_type = st.selectbox("出場類型", ["停利出場", "停損出場", "保本出場"])
                    # 自動帶入上方試算出來的損益金額
                    close_pnl = st.number_input("此筆交易總損益金額", value=float(est_profit), step=1000.0)
                    
                    if st.form_submit_button(f"出清部位並寫入 {current_user} 的績效"):
                        # 寫入歷史紀錄
                        add_airtable_record(datetime.date.today(), current_user, selected_stock, close_type, close_pnl)
                        # 從雲端盤中監控刪除
                        rec_id = trade_data.get('record_id')
                        delete_portfolio_from_cloud(rec_id)
                        
                        st.session_state.refresh_history = True
                        del user_portfolio[selected_stock]
                        st.success(f"{selected_stock} 已結算！已同步至 {current_user} 的專屬雲端紀錄。")
                        st.rerun()

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
