import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
from PIL import Image
# import pytesseract # 若需啟用 OCR 自動辨識股號，需解除註解並安裝 Tesseract 引擎

# 頁面基本設定
st.set_page_config(page_title="波段交易紀錄系統", layout="wide")
st.title("📈 波段交易與部位控管系統")

# 初始化暫存資料 (實戰中需改為連接 SQLite 或 CSV 以持久化儲存)
if 'trade_history' not in st.session_state:
    st.session_state.trade_history = pd.DataFrame(columns=['日期', '股號', '類型', '損益金額'])

col1, col2 = st.columns([1, 1.2])

with col1:
    st.header("新增交易紀錄")
    
    # 3. 紀錄日期
    trade_date = st.date_input("📝 紀錄日期", datetime.date.today())
    
    # 1. 圖片上傳 (現代瀏覽器支援點擊此處後直接 Ctrl+V 貼上截圖)
    uploaded_file = st.file_uploader("📸 貼上或上傳進場位置截圖 (支援 Ctrl+V)", type=['png', 'jpg', 'jpeg'])
    
    # 2. 自動 OCR 股號 (這裡建立欄位，並預留 OCR 邏輯)
    stock_id = ""
    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption="進場截圖", use_column_width=True)
        # OCR 辨識邏輯預留區：
        # stock_id = pytesseract.image_to_string(image, lang='eng').strip() 
        # 實戰中需針對券商軟體截圖區域做精準裁切辨識
        stock_id = "自動辨識結果 (範例: 2330)" 
        
    stock_input = st.text_input("🏷️ 股號", value=stock_id)

    st.markdown("---")
    # 4. 母倉設定與自動計算停損
    st.subheader("🔹 母倉設定")
    init_price = st.number_input("母倉進場價格", min_value=0.0, step=0.1)
    init_shares = st.number_input("母倉股數", min_value=0, step=1000)
    
    total_cost = init_price * init_shares
    total_shares = init_shares

    if init_price > 0:
        sl_price = init_price * 0.8
        # 使用紅色凸顯停損價
        st.markdown(f"### 🚨 應設停損價 (-20%): :red[{sl_price:.2f}]")

    st.markdown("---")
    # 5-1 & 5-2. 動態加碼欄位
    st.subheader("🔸 加碼設定 (最多 4 次)")
    
    for i in range(1, 5):
        if st.checkbox(f"✅ 激活加碼 {i}", key=f"check_{i}"):
            c1, c2 = st.columns(2)
            with c1:
                add_price = st.number_input(f"加碼 {i} 價格", min_value=0.0, step=0.1, key=f"price_{i}")
            with c2:
                add_shares = st.number_input(f"加碼 {i} 股數", min_value=0, step=1000, key=f"shares_{i}")
            
            if init_price > 0 and add_price > 0:
                # 計算距離母倉的 % 數
                diff_pct = ((add_price - init_price) / init_price) * 100
                st.caption(f"此筆加碼距離母倉價格: **{diff_pct:+.2f}%**")
                
                # 累加計算均價
                total_cost += (add_price * add_shares)
                total_shares += add_shares

    # 顯示動態計算的總均價
    if total_shares > 0:
        avg_price = total_cost / total_shares
        st.success(f"📊 目前總部位均價: **{avg_price:.2f}** (總股數: {total_shares})")

with col2:
    st.header("損益結算與績效分析")
    
    # 6. 結算紀錄
    with st.form("pnl_form"):
        st.subheader("💰 新增結算紀錄")
        f_date = st.date_input("結算日期", datetime.date.today())
        f_type = st.selectbox("交易結果", ["停利出場", "停損出場", "保本出場"])
        f_pnl = st.number_input("此筆交易總損益金額", step=1000)
        submit_btn = st.form_submit_button("寫入績效資料庫")
        
        if submit_btn:
            new_record = pd.DataFrame([{
                '日期': f_date, '股號': stock_input, '類型': f_type, '損益金額': f_pnl
            }])
            st.session_state.trade_history = pd.concat([st.session_state.trade_history, new_record], ignore_index=True)
            st.success("紀錄新增成功！")

    # 7. 自動計算總操作損益與繪製曲線圖
    st.markdown("---")
    if not st.session_state.trade_history.empty:
        df = st.session_state.trade_history.copy()
        df['日期'] = pd.to_datetime(df['日期'])
        df = df.sort_values('日期')
        df['累積損益'] = df['損益金額'].cumsum()
        
        total_profit = df['損益金額'].sum()
        st.metric(label="累積總損益", value=f"{total_profit:,.0f} 元")
        
        # 繪製損益曲線圖
        chart_type = st.radio("查看區間", ["每日", "每週", "每月", "自訂 (全部)"], horizontal=True)
        
        if chart_type == "每日":
            plot_df = df.set_index('日期').resample('D')['損益金額'].sum().cumsum().reset_index()
        elif chart_type == "每週":
            plot_df = df.set_index('日期').resample('W')['損益金額'].sum().cumsum().reset_index()
        elif chart_type == "每月":
            plot_df = df.set_index('日期').resample('M')['損益金額'].sum().cumsum().reset_index()
        else:
            plot_df = df
            
        if not plot_df.empty:
            fig = px.line(plot_df, x='日期', y='累積損益', title=f"帳戶淨值曲線 ({chart_type})", markers=True)
            fig.update_layout(xaxis_title="時間", yaxis_title="累積金額", hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("尚無結算紀錄，請在上方新增資料以產生圖表。")