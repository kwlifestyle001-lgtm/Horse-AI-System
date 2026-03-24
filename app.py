import streamlit as st
import pandas as pd
import joblib
import datetime
import os
import re

st.set_page_config(page_title="AI 賽馬帝國神算子", page_icon="🏇", layout="wide")
st.title("🏇 AI 賽馬帝國：終極量化預測系統 V6.4 (絕對防彈版)")
st.markdown("---")

# ==========================================
# 1. 載入雙核心 AI 大腦
# ==========================================
@st.cache_resource
def load_models():
    try:
        model_v1 = joblib.load('hkjc_ai_brain_v1.pkl')
        model_v2 = joblib.load('hkjc_ai_brain_v2_no_odds.pkl')
        return model_v1, model_v2
    except Exception as e:
        st.error(f"找不到 AI 大腦檔案！錯誤: {e}")
        return None, None

model_v1, model_v2 = load_models()

if 'races_db' not in st.session_state:
    st.session_state['races_db'] = {}

# ==========================================
# 2. 核心黑科技：終極雷達文字解析器
# ==========================================
def parse_horse_data(text):
    parsed = []
    # 暴力清理所有可能干擾的換行、空白、箭頭符號
    text = text.replace('\n', ' ').replace('\t', ' ').replace('>', ' ').replace('\xa0', ' ')
    
    # 啟動 1~14 號馬匹的雷達地毯式搜索
    for i in range(1, 15):
        # 鎖定特徵：馬號 (前後不能有數字) + 點或空白 + 中文名字(2~6字)
        pattern = rf'(?<!\d){i}(?!\d)\s*\.?\s*([\u4e00-\u9fa5]{{2,6}})'
        match = re.search(pattern, text)
        
        if match:
            name = match.group(1)
            # 抓取馬名後面的 80 個字元作為「搜索區塊」
            chunk = text[match.end():match.end()+80]
            
            # 在區塊中尋找「檔位(1~14)」和「負磅(110~135)」的組合 (例如 5135 或 5 135)
            dw_wt = re.search(r'(?<!\d)(\d{1,2})\s*(1[1-3]\d)(?!\d)', chunk)
            
            if dw_wt:
                draw = int(dw_wt.group(1))
                wt = int(dw_wt.group(2))
            else:
                # 就算找不到，也會先建表讓你自己填
                draw = 1
                wt = 125
                
            # 盡力尋找獨贏賠率 (尋找獨立的浮點數)
            odds = 10.0
            numbers = re.findall(r'(?<!\d)(\d{1,3}(?:\.\d)?)(?!\d)', chunk)
            
            # 過濾掉已經是檔位和負磅的數字
            ignore_list = [str(draw), str(wt)]
            if dw_wt: ignore_list.append(dw_wt.group(0).replace(" ", ""))
            
            possible_odds = [float(x) for x in numbers if x not in ignore_list]
            
            if possible_odds:
                odds = possible_odds[0]
                # 破解網頁版 154.1 這種黏在一起的怪物數字
                if odds > 100: 
                    odds_str = str(odds)
                    dot_idx = odds_str.find('.')
                    if dot_idx > 1:
                        try: odds = float(odds_str[:dot_idx-1])
                        except: pass
                        
            parsed.append({
                '馬號': i,
                '馬名': name,
                '實際負磅': wt,
                '排位體重': 1100,  # 預設值，可在表格中雙擊修改
                '檔位': draw,
                '獨贏賠率': odds,
                '休息天數': 30    # 預設值，可在表格中雙擊修改
            })
            
    return parsed

# ==========================================
# 3. 側邊欄 (Sidebar)
# ==========================================
st.sidebar.header("⚙️ 賽事基本設定")
race_date = st.sidebar.date_input("選擇賽事日期：", datetime.date.today())
race_no = st.sidebar.radio("選擇場次：", range(1, 11), horizontal=True)
race_key = f"{race_date}_Race{race_no}"

st.sidebar.markdown("---")
st.sidebar.header("📋 一鍵智能建表 (免API)")
st.sidebar.markdown("從馬會網站或 App 複製整頁文字，直接貼在下方：")
pasted_text = st.sidebar.text_area("貼上排位與賠率：", height=200)

if st.sidebar.button("🔄 解析文字並生成表格"):
    if pasted_text:
        with st.sidebar.status("雷達鎖定掃描中..."):
            extracted_data = parse_horse_data(pasted_text)
            
            if extracted_data:
                st.session_state['races_db'][race_key] = pd.DataFrame(extracted_data)
                st.sidebar.success(f"✅ 雷達掃描成功！抓取到 {len(extracted_data)} 匹馬！")
                st.rerun()
            else:
                st.sidebar.error("⚠️ 依然找不到資料！請確保文字中包含「數字+馬匹中文名」。")
    else:
        st.sidebar.warning("請先貼上文字！")

HISTORY_FILE = "my_betting_history.csv"

# ==========================================
# 4. 雙分頁系統
# ==========================================
tab1, tab2 = st.tabs(["🔮 AI 預測大廳", "🏆 賽果覆盤與戰績資料庫"])

with tab1:
    mode = st.radio("選擇 AI 預測模式：", ("💰 殺莊模式 (包含即時賠率)", "💪 物理模式 (純看客觀實力)"), horizontal=True)
    col1, col2 = st.columns([2, 1]) 
    
    with col1:
        st.subheader(f"🏆 正在分析：{race_date} ｜ 第 {race_no} 場")
        if race_key in st.session_state['races_db']:
            df = st.session_state['races_db'][race_key]
            
            # 這裡改成 st.data_editor 讓你可以自由修改任何辨識錯的數字！
            st.info("💡 **小提示：** 如果有賠率或體重辨識不準確，可直接雙擊表格內進行修改。")
            edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
            st.session_state['races_db'][race_key] = edited_df
            
            if st.button("🚀 啟動 AI 預測！", type="primary"):
                with st.spinner('AI 大腦高速運算中...'):
                    edited_df['負磅比率'] = edited_df['實際負磅'] / edited_df['排位體重']
                    features = ['實際負磅', '排位體重', '獨贏賠率', '負磅比率', '休息天數', '檔位'] if "殺莊" in mode else ['實際負磅', '排位體重', '負磅比率', '休息天數', '檔位']
                    model = model_v1 if "殺莊" in mode else model_v2
                    probabilities = model.predict_proba(edited_df[features])[:, 1]
                    edited_df['AI預測入位率(%)'] = probabilities * 100
                    final_df = edited_df.sort_values(by='AI預測入位率(%)', ascending=False).reset_index(drop=True)
                    
                    def get_tag(row):
                        prob = row['AI預測入位率(%)']
                        odds = row['獨贏賠率']
                        if prob > 60: return "🔥🔥 鐵膽"
                        elif prob > 35 and odds >= 10.0: return "💎 價值冷門"
                        elif prob < 20: return "⚠️ 避開"
                        else: return ""
                    
                    final_df['AI 評語'] = final_df.apply(get_tag, axis=1)
                    st.success("✅ 預測完成！")
                    st.dataframe(
                        final_df[['馬號', '馬名', '檔位', '實際負磅', '獨贏賠率', 'AI預測入位率(%)', 'AI 評語']].style.format({'AI預測入位率(%)': '{:.1f}%', '獨贏賠率': '{:.1f}'})
                        .background_gradient(subset=['AI預測入位率(%)'], cmap='Blues'),
                        use_container_width=True, height=500
                    )
        else:
            st.warning("👈 尚未載入資料！請從左側欄貼上馬會文字，並點擊「解析文字並生成表格」。")
            
    with col2:
        st.subheader("🧮 智能注碼分配機")
        with st.expander("點擊展開計算機", expanded=True):
            total_budget = st.number_input("💰 總預算 ($)：", min_value=10, value=1000, step=10)
            odds1 = st.number_input("馬匹 A 賠率：", min_value=1.01, value=5.5, step=0.1)
            odds2 = st.number_input("馬匹 B 賠率：", min_value=1.01, value=12.0, step=0.1)
            odds3 = st.number_input("馬匹 C 賠率 (不買填 0)：", min_value=0.0, value=0.0, step=0.1)
            if st.button("⚖️ 計算注碼分配"):
                prob1, prob2 = 1/odds1, 1/odds2
                prob3 = 1/odds3 if odds3 > 0 else 0
                total_prob = prob1 + prob2 + prob3
                bet1, bet2 = (total_budget * prob1) / total_prob, (total_budget * prob2) / total_prob
                bet3 = (total_budget * prob3) / total_prob if odds3 > 0 else 0
                st.success(f"✅ 保底淨利潤：${(bet1 * odds1) - total_budget:.0f}")
                st.write(f"💵 買 馬匹 A：${bet1:.0f} | 買 馬匹 B：${bet2:.0f}" + (f" | 買 馬匹 C：${bet3:.0f}" if odds3>0 else ""))

with tab2:
    st.header(f"📝 紀錄賽果：{race_date} ｜ 第 {race_no} 場")
    with st.form("result_form"):
        col_r1, col_r2, col_r3, col_r4 = st.columns(4)
        first = col_r1.number_input("🥇 冠軍 (馬號)", min_value=1, max_value=14, step=1, value=1)
        second = col_r2.number_input("🥈 亞軍 (馬號)", min_value=1, max_value=14, step=1, value=2)
        third = col_r3.number_input("🥉 季軍 (馬號)", min_value=1, max_value=14, step=1, value=3)
        fourth = col_r4.number_input("🏅 殿軍 (馬號)", min_value=1, max_value=14, step=1, value=4)
        st.markdown("---")
        profit_loss = st.number_input("💰 本場實際盈虧 ($)：(贏錢填正數，輸錢填負數，沒買填 0)", value=0.0, step=10.0)
        notes = st.text_input("📝 賽後筆記：")
        
        if st.form_submit_button("💾 儲存賽果至資料庫"):
            new_record = pd.DataFrame([{
                "日期": str(race_date), "場次": f"第 {race_no} 場",
                "冠軍": first, "亞軍": second, "季軍": third, "殿軍": fourth,
                "本場盈虧": profit_loss, "筆記": notes
            }])
            if not os.path.exists(HISTORY_FILE): new_record.to_csv(HISTORY_FILE, index=False, encoding='utf-8-sig')
            else: new_record.to_csv(HISTORY_FILE, mode='a', header=False, index=False, encoding='utf-8-sig')
            st.success(f"✅ 第 {race_no} 場賽果已成功儲存入庫！")

    st.markdown("---")
    st.header("📈 你的專屬獲利儀表板")
    if os.path.exists(HISTORY_FILE):
        history_df = pd.read_csv(HISTORY_FILE)
        st.metric(label="累積總盈虧", value=f"{'+' if history_df['本場盈虧'].sum() > 0 else ''}${history_df['本場盈虧'].sum():,.1f}")
        st.line_chart(history_df['本場盈虧'].cumsum())
        st.dataframe(history_df, use_container_width=True)