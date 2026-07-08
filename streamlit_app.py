# ... existing code ...
import pandas as pd
import datetime
import plotly.express as px
from PIL import Image
import requests
import json

# 1. 頁面基本設定
st.set_page_config(page_title="實戰波段部位控管系統", layout="wide")
st.title("📈 實戰波段部位即時控管儀表板")

# 2. Airtable 連線憑證
AIRTABLE_PAT = "patNvk9pkE2vY8uCh.224e2d113ee94d2f505d3149a7d0c496102267aef209975ef47d425eef07d6ef"
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
                "使用者": str(user),  # 寫入使用者
                "股號": str(stock),
                "類型": str(close_type),
                "損益金額": float(pnl)
            }
        }]
    }
    requests.post(url, headers=headers, json=data)

# =============== 新增：盤中部位的雲端同步功能 ===============
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
                        data_dict['record_id'] = rec_id # 記錄 Airtable ID
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
    
    if record_id: # 如果雲端已經有紀錄，就更新它
        url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_PORTFOLIO}/{record_id}"
        data = {"fields": {"資料包": data_str}}
        requests.patch(url, headers=headers, json=data)
    else: # 如果雲端沒有紀錄，就新增一筆
        url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_PORTFOLIO}"
        data = {
            "records": [{
                "fields": {
                    "股號": str(stock),
                    "使用者": str(user),
                    "資料包": data_str
# ================= 分頁 1: 新增母單 =================
with tab_new:
    st.header(f"建立新部位 ({current_user} 的工作區)")
    col1, col2 = st.columns(2)
    
    with col1:
        new_date = st.date_input("進場日期", datetime.date.today(), key="new_date")
        new_stock = st.text_input("🏷️ 股號 (必填)", placeholder="例如: 2330")
        
        st.markdown("##### 資金與股數設定")
        new_capital = st.number_input("💰 母單預算資金 (元)", min_value=0, value=25000, step=1000)
        new_price = st.number_input("母單進場價格", min_value=0.0, step=0.5, format="%.2f")
        
        calc_shares = int(new_capital / new_price) if new_price > 0 else 0
        st.caption(f"💡 系統試算：依此價格與資金，最多可買 **{calc_shares:,}** 股")
        new_shares = st.number_input("實際買進股數", min_value=0, value=calc_shares, step=1, key="new_sha")
    
    with col2:
        st.info("💡 提示：因瀏覽器安全限制無法直接 Ctrl+V。請使用截圖軟體後，直接「拖曳」圖片到下方虛線框，或先存檔再上傳。")
        uploaded_file = st.file_uploader("📸 上傳進場位置截圖", type=['png', 'jpg', 'jpeg'])
        if uploaded_file is not None:
            st.image(Image.open(uploaded_file), caption="進場截圖預覽", use_container_width=True)
            
    if st.button("💾 儲存母單並加入監控", type="primary"):
        if new_stock:
            new_data = {
                'date': str(new_date),
                'price': float(new_price),
                'shares': int(new_shares),
                'image': uploaded_file,
                'addons': [{'active': False, 'capital': 5000, 'price': 0.0, 'shares': 0} for _ in range(4)]
            }
            user_portfolio[new_stock] = new_data
            # 觸發同步到雲端
            sync_portfolio_to_cloud(current_user, new_stock, new_data)
            st.success(f"股號 {new_stock} 已成功加入 {current_user} 的盤中監控清單並同步至雲端！")
        else:
            st.error("請輸入股號！")

# ================= 分頁 2: 盤中監控 =================
# ... existing code ...
            with c_left:
                st.subheader("🔹 原始母單資訊")
                st.write(f"**進場日:** {trade_data['date']} | **價格:** {trade_data['price']} | **股數:** {trade_data['shares']}")
                if trade_data['price'] > 0:
                    st.markdown(f"🚨 **母單原始停損 (-20%):** :red[{trade_data['price'] * 0.8:.2f}]")
                
                # 使用 .get() 避免重整後沒有 image 欄位報錯
                if trade_data.get('image') is not None:
                    with st.expander("展開查看進場截圖"):
                        st.image(Image.open(trade_data['image']), use_container_width=True)
                
                st.markdown("---")
# ... existing code ...
                        trade_data['addons'][i] = {'active': True, 'capital': a_cap, 'price': a_price, 'shares': a_shares}
                    else:
                        trade_data['addons'][i]['active'] = False
                        
                st.markdown("---")
                if st.button(f"💾 同步更新 {selected_stock} 加碼設定至雲端", type="primary"):
                    sync_portfolio_to_cloud(current_user, selected_stock, trade_data)
                    st.success("加碼設定已成功同步至雲端！重整網頁也不會消失了。")

            with c_right:
                st.subheader("🛡️ 即時部位與風險推算")
# ... existing code ...
                with st.form(key=f"close_form_{current_user}_{selected_stock}"):
                    close_type = st.selectbox("出場類型", ["停利出場", "停損出場", "保本出場"])
                    close_pnl = st.number_input("此筆交易總損益金額", step=1000)
                    
                    if st.form_submit_button(f"出清部位並寫入 {current_user} 的績效"):
                        # 1. 寫入 Airtable 歷史紀錄
                        add_airtable_record(datetime.date.today(), current_user, selected_stock, close_type, close_pnl)
                        
                        # 2. 刪除 Airtable 盤中紀錄
                        rec_id = user_portfolio[selected_stock].get('record_id')
                        delete_portfolio_from_cloud(rec_id)
                        
                        st.session_state.refresh_history = True
                        st.session_state.refresh_portfolio = True
                        del user_portfolio[selected_stock]
                        st.success(f"{selected_stock} 已結算！已同步至 {current_user} 的專屬雲端紀錄。")
                        st.rerun()

# ================= 分頁 3: 歷史紀錄 =================
# ... existing code ...
