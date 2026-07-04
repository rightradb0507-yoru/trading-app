import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
from PIL import Image

# 頁面基本設定
st.set_page_config(page_title="實戰波段部位控管系統", layout="wide")
st.title("📈 實戰波段部位即時控管儀表板")

# ================= 1. 初始化資料庫 (Session State) =================
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = {}  # 存放盤中持倉 (字典格式：股號 -> 資料)
if 'history' not in st.session_state:
    st.session_state.history = pd.DataFrame(columns=['日期', '股號', '類型', '損益金額'])

# 建立三大分頁
tab_new, tab_monitor, tab_history = st.tabs(["📝 1. 新增母單 (建倉)", "🖥️ 2. 盤中監控與動態加碼 (持倉)", "💰 3. 績效結算與曲線圖"])

# ================= 分頁 1：新增母單 =================
with tab_new:
    st.header("建立新部位")
    col1, col2 = st.columns(2)
    
    with col1:
        new_date = st.date_input("進場日期", datetime.date.today(), key="new_date")
        new_stock = st.text_input("🏷️ 股號 (必填)", placeholder="例如: 2330")
        new_price = st.number_input("母單進場價格", min_value=0.0, step=0.5, format="%.2f")
        new_shares = st.number_input("母單股數", min_value=0, step=1000)
    
    with col2:
        uploaded_file = st.file_uploader("📸 上傳進場位置截圖 (支援 Ctrl+V)", type=['png', 'jpg', 'jpeg'])
        if uploaded_file is not None:
            st.image(Image.open(uploaded_file), caption="進場截圖預覽", use_container_width=True)
            
    if st.button("💾 儲存母單並加入監控", type="primary"):
        if new_stock:
            # 將資料存入 session_state
            st.session_state.portfolio[new_stock] = {
                'date': new_date,
                'price': new_price,
                'shares': new_shares,
                'image': uploaded_file,
                # 預留加碼欄位
                'addons': [{'active': False, 'price': 0.0, 'shares': 0} for _ in range(4)]
            }
            st.success(f"股號 {new_stock} 已成功加入盤中監控清單！")
        else:
            st.error("請輸入股號！")

# ================= 分頁 2：盤中監控與動態加碼 =================
with tab_monitor:
    if not st.session_state.portfolio:
        st.info("目前沒有持倉紀錄。請先到「新增母單」建立部位。")
    else:
        st.header("盤中持倉動態控管")
        # 選擇要監控的股票
        stock_list = list(st.session_state.portfolio.keys())
        selected_stock = st.selectbox("🔍 選擇要監控/編輯的持倉", stock_list)
        
        if selected_stock:
            trade_data = st.session_state.portfolio[selected_stock]
            
            c_left, c_right = st.columns([1, 1.2])
            
            with c_left:
                st.subheader("🔹 原始母單資訊")
                st.write(f"**進場日:** {trade_data['date']} | **價格:** {trade_data['price']} | **股數:** {trade_data['shares']}")
                if trade_data['price'] > 0:
                    st.markdown(f"🚨 **母單原始停損 (-20%):** :red[{trade_data['price'] * 0.8:.2f}]")
                
                if trade_data['image'] is not None:
                    with st.expander("展開查看進場截圖"):
                        st.image(Image.open(trade_data['image']), use_container_width=True)
                
                st.markdown("---")
                st.subheader("🔸 加碼單動態設定")
                
                # 渲染 4 個加碼欄位，並綁定原本存好的資料
                for i in range(4):
                    addon = trade_data['addons'][i]
                    is_active = st.toggle(f"啟用加碼 {i+1}", value=addon['active'], key=f"t_{selected_stock}_{i}")
                    
                    if is_active:
                        col_p, col_s = st.columns(2)
                        with col_p:
                            a_price = st.number_input(f"價格", min_value=0.0, step=0.5, format="%.2f", value=float(addon['price']), key=f"p_{selected_stock}_{i}")
                        with col_s:
                            a_shares = st.number_input(f"股數", min_value=0, step=1000, value=int(addon['shares']), key=f"s_{selected_stock}_{i}")
                        
                        # 即時更新存檔
                        trade_data['addons'][i] = {'active': True, 'price': a_price, 'shares': a_shares}
                    else:
                        trade_data['addons'][i]['active'] = False

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
                if total_shares > 0 and trade_data['price'] > 0:
                    sl_price = avg_price * 0.8
                    est_loss = (sl_price - avg_price) * total_shares
                    st.warning(f"**動態極限防線 (最新均價 -20%)**")
                    st.write(f"若跌至 **{sl_price:.2f}** 全部出場，預估虧損：**{est_loss:,.0f}** 元")
                
                st.markdown("---")
                # 平倉結算區
                st.subheader("💰 部位平倉結算")
                with st.form(key=f"close_form_{selected_stock}"):
                    close_type = st.selectbox("出場類型", ["停利出場", "停損出場", "保本出場"])
                    close_pnl = st.number_input("此筆交易總損益金額", step=1000)
                    if st.form_submit_button("出清部位並寫入績效"):
                        # 寫入歷史紀錄
                        new_record = pd.DataFrame([{
                            '日期': datetime.date.today(), '股號': selected_stock, 
                            '類型': close_type, '損益金額': close_pnl
                        }])
                        st.session_state.history = pd.concat([st.session_state.history, new_record], ignore_index=True)
                        # 從監控清單移除
                        del st.session_state.portfolio[selected_stock]
                        st.success(f"{selected_stock} 已結算！請切換分頁查看績效。")
                        st.rerun()

# ================= 分頁 3：績效結算與曲線圖 =================
with tab_history:
    st.header("歷史績效與成長曲線")
    if not st.session_state.history.empty:
        df = st.session_state.history.copy()
        df['日期'] = pd.to_datetime(df['日期'])
        df = df.sort_values('日期')
        df['累積損益'] = df['損益金額'].cumsum()
        
        total_profit = df['損益金額'].sum()
        st.metric(label="累積總損益", value=f"{total_profit:,.0f} 元")
        
        fig = px.line(df, x='日期', y='累積損益', title="帳戶淨值曲線", markers=True)
        fig.update_layout(xaxis_title="結算時間", yaxis_title="累積金額", hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("交易明細")
        st.dataframe(df, use_container_width=True)
    else:
        st.info("尚無結算紀錄。當你在「盤中監控」將部位出清後，圖表就會在此產生。")