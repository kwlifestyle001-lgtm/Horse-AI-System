import streamlit as st
import pandas as pd
import joblib
import datetime
import re
import json
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="AI 賽馬帝國神算子", page_icon="🏇", layout="wide")
st.title("🏇 AI 賽馬帝國 V7.5 (全端指揮中心版)")
st.markdown("---")

# ==========================================
# 0. 初始化 Session State 記憶體
# ==========================================
if 'races_db' not in st.session_state:
    st.session_state['races_db'] = {}
if 'current_prediction' not in st.session_state:
    st.session_state['current_prediction'] = None
if 'temp_payouts' not in st.session_state:
    st.session_state['temp_payouts'] = {}
if 'temp_profit' not in st.session_state:
    st.session_state['temp_profit'] = 0.0

# ==========================================
# 1. 連接 Google Sheets 雲端資料庫
# ==========================================
@st.cache_resource
def get_gspread_client():
    if "gcp_service_account_json" in st.secrets:
        try:
            creds_info = json.loads(st.secrets["gcp_service_account_json"])
            scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
            creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
            return gspread.authorize(creds)
        except Exception as e:
            st.error(f"Google 雲端連線失敗: {e}")
            return None
    return None

gc = get_gspread_client()

# ==========================================
# 2. 載入三核心 AI 大腦
# ==========================================
@st.cache_resource
def load_models():
    try:
        model_v1 = joblib.load('hkjc_ai_brain_v1.pkl')
        model_v2 = joblib.load('hkjc_ai_brain_v2_no_odds.pkl')
        model_v3 = joblib.load('hkjc_ai_brain_v3_holygrail.pkl')
        return model_v1, model_v2, model_v3
    except Exception as e:
        st.error(f"找不到 AI 大腦檔案！請確認 .pkl 都已上傳: {e}")
        return None, None, None

model_v1, model_v2, model_v3 = load_models()

# ==========================================
# 3. 核心黑科技：終極雷達 (抗干擾)
# ==========================================
def parse_horse_data(text):
    text = re.sub(r'[\(（]\-\d+[\)）]', '', text) 
    parsed = []
    text = text.replace('\n', ' ').replace('\t', ' ').replace('>', ' ').replace('\xa0', ' ')
    
    for i in range(1, 15):
        pattern = rf'(?<!\d){i}(?!\d)\s*\.?\s*([\u4e00-\u9fa5]{{2,6}})'
        match = re.search(pattern, text)
        if match:
            name = match.group(1)
            next_pattern = rf'(?<!\d){i+1}(?!\d)\s*\.?\s*[\u4e00-\u9fa5]'
            next_match = re.search(next_pattern, text[match.end():])
            end_pos = match.end() + next_match.start() if next_match else match.end() + 60
            chunk = text[match.end():end_pos]
            
            dw_wt = re.search(r'(?<!\d)(\d{1,2})\s*(1[1-3]\d)(?!\d)', chunk)
            if dw_wt:
                draw = int(dw_wt.group(1))
                wt = int(dw_wt.group(2))
            else:
                draw, wt = 1, 125
                
            chinese_blocks = re.findall(r'[\u4e00-\u9fa5]+', chunk[:40])
            j_t_list = [word for word in chinese_blocks if word != name and word != "倍" and word != "自"]
            jockey = j_t_list[0] if len(j_t_list) > 0 else "未知"
            trainer = j_t_list[1] if len(j_t_list) > 1 else "未知"
                
            odds = 10.0
            numbers = re.findall(r'(?<!\d)(\d{1,3}(?:\.\d)?)(?!\d)', chunk)
            ignore_list = [str(draw), str(wt)]
            if dw_wt: ignore_list.append(dw_wt.group(0).replace(" ", ""))
            
            possible_odds = [float(x) for x in numbers if x not in ignore_list]
            if possible_odds:
                odds = possible_odds[0]
                if odds > 100: 
                    odds_str = str(odds)
                    dot_idx = odds_str.find('.')
                    if dot_idx > 1:
                        try: odds = float(odds_str[:dot_idx-1])
                        except: pass
                        
            parsed.append({
                '馬號': i, '馬名': name, '騎師': jockey, '練馬師': trainer,
                '實際負磅': wt, '排位體重': 1100, '檔位': draw, 
                '獨贏賠率': odds, '休息天數': 30
            })
    return parsed

# ==========================================
# 4. 側邊欄 (支援 14 場賽事)
# ==========================================
st.sidebar.header("⚙️ 賽事設定")
race_date = st.sidebar.date_input("賽事日期：", datetime.date.today())
race_no = st.sidebar.radio("選擇場次：", range(1, 15), horizontal=True)
race_key = f"{race_date}_Race{race_no}"

st.sidebar.markdown("---")
st.sidebar.header("📋 一鍵智能建表")
pasted_text = st.sidebar.text_area("貼上排位與賠率：", height=200)

if st.sidebar.button("🔄 解析文字並生成表格"):
    if pasted_text:
        with st.sidebar.status("雷達鎖定掃描中..."):
            extracted_data = parse_horse_data(pasted_text)
            if extracted_data:
                st.session_state['races_db'][race_key] = pd.DataFrame(extracted_data)
                st.sidebar.success(f"✅ 抓取到 {len(extracted_data)} 匹馬！")
                st.rerun()
            else:
                st.sidebar.error("⚠️ 找不到資料！")

# ==========================================
# 5. 三大分頁系統
# ==========================================
tab1, tab2, tab3 = st.tabs(["🔮 AI 預測大廳", "🏆 財務對帳台", "📚 過往完整資料庫"])

# ----------------- 分頁 1：預測與派彩輸入 -----------------
with tab1:
    mode = st.radio("選擇作戰大腦：", ("🏆 聖杯大腦 (V3 終極融合)", "💰 殺莊大腦 (V1 穩陣)", "💪 物理大腦 (V2 尋寶)"), horizontal=True)
    col1, col2 = st.columns([2, 1]) 
    
    with col1:
        st.subheader(f"🏆 {race_date} ｜ 第 {race_no} 場")
        if race_key in st.session_state['races_db']:
            df = st.session_state['races_db'][race_key]
            edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
            st.session_state['races_db'][race_key] = edited_df
            
            if st.button("🚀 啟動 AI 預測！", type="primary"):
                with st.spinner('大腦高速運算中...'):
                    edited_df['負磅比率'] = edited_df['實際負磅'] / edited_df['排位體重']
                    features_v1 = ['實際負磅', '排位體重', '獨贏賠率', '負磅比率', '休息天數', '檔位']
                    features_v2 = ['實際負磅', '排位體重', '負磅比率', '休息天數', '檔位']
                    
                    if "聖杯大腦" in mode:
                        edited_df['V1_機率'] = model_v1.predict_proba(edited_df[features_v1])[:, 1]
                        edited_df['V2_機率'] = model_v2.predict_proba(edited_df[features_v2])[:, 1]
                        edited_df['莊家機率'] = 1 / edited_df['獨贏賠率']
                        edited_df['錯價指數'] = edited_df['V2_機率'] - edited_df['莊家機率']
                        v3_features = ['V1_機率', 'V2_機率', '錯價指數', '獨贏賠率', '實際負磅', '檔位']
                        probabilities = model_v3.predict_proba(edited_df[v3_features])[:, 1]
                        edited_df['AI預測入位率(%)'] = probabilities * 100
                    elif "殺莊大腦" in mode:
                        probabilities = model_v1.predict_proba(edited_df[features_v1])[:, 1]
                        edited_df['AI預測入位率(%)'] = probabilities * 100
                    elif "物理大腦" in mode:
                        probabilities = model_v2.predict_proba(edited_df[features_v2])[:, 1]
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
                    
                    st.session_state['current_prediction'] = final_df
                    st.success("✅ 預測完畢！")
            
            if st.session_state['current_prediction'] is not None:
                final_df = st.session_state['current_prediction']
                st.dataframe(
                    final_df[['馬號', '馬名', '騎師', '練馬師', '檔位', '實際負磅', '獨贏賠率', 'AI預測入位率(%)', 'AI 評語']].style.format({'AI預測入位率(%)': '{:.1f}%', '獨贏賠率': '{:.1f}'}).background_gradient(subset=['AI預測入位率(%)'], cmap='Blues'),
                    use_container_width=True, height=500
                )
                
                # 儲存完整排位到資料庫
                if st.button("💾 將本場【完整排位與預測】存入歷史庫"):
                    if gc:
                        try:
                            try:
                                full_sheet = gc.open("Horse_AI_Database").worksheet("完整排位庫")
                            except gspread.exceptions.WorksheetNotFound:
                                full_sheet = gc.open("Horse_AI_Database").add_worksheet(title="完整排位庫", rows="1000", cols="20")
                                full_sheet.append_row(["日期", "場次", "馬號", "馬名", "騎師", "練馬師", "檔位", "實際負磅", "獨贏賠率", "AI預測機率", "AI評語"])
                            
                            save_df = final_df[['馬號', '馬名', '騎師', '練馬師', '檔位', '實際負磅', '獨贏賠率', 'AI預測入位率(%)', 'AI 評語']].copy()
                            save_df.insert(0, '場次', f"第 {race_no} 場")
                            save_df.insert(0, '日期', str(race_date))
                            
                            full_sheet.append_rows(save_df.values.tolist())
                            st.success("✅ 完整資料已安全存入雲端！可至『過往完整資料庫』查看。")
                        except Exception as e:
                            st.error(f"存檔失敗: {e}")
                    else:
                        st.error("⚠️ 未連線到 Google Sheets！")
        else:
            st.warning("👈 尚未載入資料！請從左側欄貼上文字。")
            
    with col2:
        st.subheader("🏁 當日賽果與派彩")
        st.info("建議直接手動輸入最穩定！")
            
        with st.form("payout_form"):
            st.markdown("##### 📝 快速紀錄全部派彩")
            
            # 第 1 排：獨贏、連贏、單T
            c1, c2, c3 = st.columns(3)
            f_win = c1.number_input("獨贏 ($)", min_value=0.0, step=1.0)
            f_qin = c2.number_input("連贏 ($)", min_value=0.0, step=1.0)
            f_tri = c3.number_input("單T ($)", min_value=0.0, step=10.0)
            
            # 第 2 排：位置 (分開 3 格)
            st.markdown("###### 位置 ($)")
            pc1, pc2, pc3 = st.columns(3)
            f_pla_1 = pc1.number_input("第1名", min_value=0.0, step=1.0, key="p1")
            f_pla_2 = pc2.number_input("第2名", min_value=0.0, step=1.0, key="p2")
            f_pla_3 = pc3.number_input("第3名", min_value=0.0, step=1.0, key="p3")
            
            # 第 3 排：位置Q (分開 3 格)
            st.markdown("###### 位置Q ($)")
            qc1, qc2, qc3 = st.columns(3)
            f_qpl_1 = qc1.number_input("1-2名", min_value=0.0, step=1.0, key="q1")
            f_qpl_2 = qc2.number_input("1-3名", min_value=0.0, step=1.0, key="q2")
            f_qpl_3 = qc3.number_input("2-3名", min_value=0.0, step=1.0, key="q3")
            
            # 第 4 排：其他彩池
            c4, c5, c6 = st.columns(3)
            f_fc = c4.number_input("二重彩 ($)", min_value=0.0, step=10.0)
            f_tce = c5.number_input("三重彩 ($)", min_value=0.0, step=10.0)
            f_f4 = c6.number_input("四連環 ($)", min_value=0.0, step=10.0)
            
            # 第 5 排：四重彩與盈虧
            f_qtt = st.number_input("四重彩 ($)", min_value=0.0, step=100.0)
            st.markdown("---")
            my_profit = st.number_input("💰 本場我的實際盈虧 ($)", step=10.0)
            
            if st.form_submit_button("💾 更新至財務對帳台"):
                st.success("✅ 數據已準備好，請至『財務對帳台』確認上傳雲端！")
                st.session_state['temp_profit'] = my_profit
                
                # 🌟 獨立儲存 13 個派彩變數！
                st.session_state['temp_payouts'] = {
                    "獨贏": f_win, 
                    "位置1": f_pla_1, "位置2": f_pla_2, "位置3": f_pla_3,
                    "連贏": f_qin, 
                    "位置Q1": f_qpl_1, "位置Q2": f_qpl_2, "位置Q3": f_qpl_3,
                    "二重彩": f_fc, "三重彩": f_tce, "單T": f_tri, 
                    "四連環": f_f4, "四重彩": f_qtt
                }

# ----------------- 分頁 2：歷史戰績儲存 -----------------
with tab2:
    st.header(f"📝 財務對帳台 (儲存盈虧與派彩)")
    if gc:
        try:
            sheet = gc.open("Horse_AI_Database").worksheet("戰績歷史")
            
            # 🌟 表頭擴充到 21 欄！
            if not sheet.get_all_values():
                sheet.append_row([
                    "日期", "場次", "冠軍", "亞軍", "季軍", "殿軍", "本場盈虧", 
                    "獨贏派彩", "位置1派彩", "位置2派彩", "位置3派彩", "連贏派彩", 
                    "位置Q1派彩", "位置Q2派彩", "位置Q3派彩", "二重彩派彩", 
                    "三重彩派彩", "單T派彩", "四連環派彩", "四重彩派彩", "筆記"
                ])
                
            with st.form("result_form"):
                col_r1, col_r2, col_r3, col_r4 = st.columns(4)
                first = col_r1.number_input("🥇 冠軍馬號", min_value=1, max_value=14, step=1, value=1)
                second = col_r2.number_input("🥈 亞軍馬號", min_value=1, max_value=14, step=1, value=2)
                third = col_r3.number_input("🥉 季軍馬號", min_value=1, max_value=14, step=1, value=3)
                fourth = col_r4.number_input("🏅 殿軍馬號", min_value=1, max_value=14, step=1, value=4)
                st.markdown("---")
                profit_loss = st.number_input("💰 確認本場盈虧 ($)", value=st.session_state.get('temp_profit', 0.0), step=10.0)
                notes = st.text_input("📝 賽後檢討筆記：")
                
                if st.form_submit_button("💾 正式儲存戰績與派彩至雲端"):
                    payouts = st.session_state.get('temp_payouts', {})
                    
                    # 🌟 完美對應 21 欄資料！
                    row_data = [
                        str(race_date), f"第 {race_no} 場", first, second, third, fourth, profit_loss,
                        payouts.get("獨贏", 0),
                        payouts.get("位置1", 0), payouts.get("位置2", 0), payouts.get("位置3", 0),
                        payouts.get("連贏", 0),
                        payouts.get("位置Q1", 0), payouts.get("位置Q2", 0), payouts.get("位置Q3", 0),
                        payouts.get("二重彩", 0), payouts.get("三重彩", 0), payouts.get("單T", 0),
                        payouts.get("四連環", 0), payouts.get("四重彩", 0),
                        notes
                    ]
                    sheet.append_row(row_data)
                    st.success(f"✅ 戰績與獨立分離的派彩數據已完美儲存！")
            
            st.markdown("---")
            st.header("📈 歷史獲利儀表板")
            records = sheet.get_all_records()
            if records:
                history_df = pd.DataFrame(records)
                if '本場盈虧' in history_df.columns:
                    total_profit = pd.to_numeric(history_df['本場盈虧'], errors='coerce').sum()
                    st.metric(label="累積總盈虧", value=f"{'+' if total_profit > 0 else ''}${total_profit:,.1f}")
                    history_df['累積盈虧'] = pd.to_numeric(history_df['本場盈虧'], errors='coerce').cumsum()
                    st.line_chart(history_df['累積盈虧'])
                    st.markdown("##### 最近 5 場戰績紀錄")
                    st.dataframe(history_df.tail(5), use_container_width=True)
            else:
                st.info("目前還沒有戰績！")
        except Exception as e:
            st.error(f"讀取試算表錯誤：{e}")

# ----------------- 分頁 3：過往完整排位表 -----------------
with tab3:
    st.header("📚 過往完整資料庫 (歷史排位與預測)")
    if gc:
        try:
            full_sheet = gc.open("Horse_AI_Database").worksheet("完整排位庫")
            full_records = full_sheet.get_all_records()
            if full_records:
                full_history_df = pd.DataFrame(full_records)
                unique_dates = full_history_df['日期'].unique().tolist()
                selected_date = st.selectbox("📅 選擇要回顧的日期：", unique_dates)
                
                filtered_df = full_history_df[full_history_df['日期'] == selected_date]
                st.dataframe(filtered_df, use_container_width=True, height=600)
            else:
                st.info("資料庫目前是空的！請在預測大廳按下『儲存完整排位』。")
        except gspread.exceptions.WorksheetNotFound:
            st.info("尚未建立『完整排位庫』。請先在預測大廳儲存一筆資料！")
        except Exception as e:
            st.error(f"讀取資料庫失敗：{e}")
