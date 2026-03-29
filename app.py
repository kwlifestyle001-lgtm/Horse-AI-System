import streamlit as st
import pandas as pd
import joblib
import datetime
import os
import re
import json
import gspread
import io
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="AI 賽馬帝國 V8.0 情報整合版", page_icon="🏇", layout="wide")
st.title("🌪️ AI 賽馬帝國 V8.0 (情報整合指揮中心)")
st.markdown("**(搭載 V4 騎練情報大腦 + Google Sheets 雲端連線)**")
st.markdown("---")

# ==========================================
# 0. 連接 Google Sheets 雲端資料庫
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
# 1. 載入四核心 AI 大腦 與 V4 情報庫
# ==========================================
@st.cache_resource
def load_resources():
    try:
        m1 = joblib.load('hkjc_ai_brain_v1.pkl')
        m2 = joblib.load('hkjc_ai_brain_v2_no_odds.pkl')
        m3 = joblib.load('hkjc_ai_brain_v3_holygrail.pkl')
        m4 = joblib.load('hkjc_ai_brain_v4_synergy.pkl') # 🌟 V4 核心
        
        # 載入 V4 特徵庫以進行騎練默契查表
        df_v4_ref = pd.read_csv('5_years_master_db_v4.csv', low_memory=False)
        synergy_map = df_v4_ref.drop_duplicates(subset=['騎師', '練馬師']).set_index(['騎師', '練馬師'])['騎練前四率'].to_dict()
        
        return m1, m2, m3, m4, synergy_map
    except Exception as e:
        st.error(f"資源載入失敗！請確認 .pkl 與 .csv 檔案皆已上傳: {e}")
        return None, None, None, None, None

model_v1, model_v2, model_v3, model_v4, synergy_map = load_resources()

if 'races_db' not in st.session_state:
    st.session_state['races_db'] = {}
if 'current_prediction' not in st.session_state:
    st.session_state['current_prediction'] = None

# ==========================================
# 2. 核心黑科技：終極雷達 (優化版)
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
                draw, wt = int(dw_wt.group(1)), int(dw_wt.group(2))
            else:
                draw, wt = 1, 125
                
            chinese_blocks = re.findall(r'[\u4e00-\u9fa5]+', chunk[:40])
            j_t_list = [word for word in chinese_blocks if word != name and word != "倍" and word != "自"]
            jockey = j_t_list[0] if len(j_t_list) > 0 else "未知"
            trainer = j_t_list[1] if len(j_t_list) > 1 else "未知"
                
            odds = 10.0
            numbers = re.findall(r'(?<!\d)(\d{1,3}(?:\.\d)?)(?!\d)', chunk)
            possible_odds = [float(x) for x in numbers if x not in [str(draw), str(wt)]]
            if possible_odds: odds = possible_odds[0]
                        
            parsed.append({
                '馬號': i, '馬名': name, '騎師': jockey, '練馬師': trainer,
                '實際負磅': wt, '排位體重': 1100, '檔位': draw, 
                '獨贏賠率': odds, '休息天數': 30
            })
    return parsed

# ==========================================
# 3. 側邊欄
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
        with st.sidebar.status("情報雷達掃描中..."):
            extracted_data = parse_horse_data(pasted_text)
            if extracted_data:
                st.session_state['races_db'][race_key] = pd.DataFrame(extracted_data)
                st.sidebar.success(f"✅ 抓取到 {len(extracted_data)} 匹馬！")
                st.rerun()
            else:
                st.sidebar.error("⚠️ 無法識別資料！")

# ==========================================
# 4. 三大分頁系統
# ==========================================
tab1, tab2, tab3 = st.tabs(["🔮 AI 預測大廳", "🏆 財務對帳台", "📚 過往完整資料庫"])

with tab1:
    mode = st.radio("選擇作戰大腦：", ("⚔️ 情報大腦 (V4 終極版)", "🏆 聖杯大腦 (V3 融合)", "💰 殺莊大腦 (V1)", "💪 物理大腦 (V2)"), horizontal=True)
    col1, col2 = st.columns([2, 1]) 
    
    with col1:
        st.subheader(f"🏆 {race_date} ｜ 第 {race_no} 場")
        if race_key in st.session_state['races_db']:
            df = st.session_state['races_db'][race_key]
            edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
            st.session_state['races_db'][race_key] = edited_df
            
            if st.button("🚀 啟動 V4 終極預測！", type="primary"):
                with st.spinner('情報網解碼中...'):
                    # 基礎特徵計算
                    edited_df['負磅比率'] = edited_df['實際負磅'] / edited_df['排位體重']
                    f_v1 = ['實際負磅', '排位體重', '獨贏賠率', '負磅比率', '休息天數', '檔位']
                    f_v2 = ['實際負磅', '排位體重', '負磅比率', '休息天數', '檔位']
                    
                    # 計算中間參數
                    edited_df['V1_機率'] = model_v1.predict_proba(edited_df[f_v1])[:, 1]
                    edited_df['V2_機率'] = model_v2.predict_proba(edited_df[f_v2])[:, 1]
                    edited_df['莊家機率'] = 1 / edited_df['獨贏賠率']
                    edited_df['錯價指數'] = edited_df['V2_機率'] - edited_df['莊家機率']
                    
                    # 🔍 查表騎練默契
                    def get_synergy(row):
                        return synergy_map.get((str(row['騎師']).strip(), str(row['練馬師']).strip()), 0.3)
                    edited_df['騎練默契'] = edited_df.apply(get_synergy, axis=1)

                    # 根據模式決定輸出
                    if "V4" in mode:
                        v4_f = ['V1_機率', 'V2_機率', '錯價指數', '獨贏賠率', '實際負磅', '檔位', '騎練默契']
                        probs = model_v4.predict_proba(edited_df[v4_f])[:, 1]
                    elif "V3" in mode:
                        v3_f = ['V1_機率', 'V2_機率', '錯價指數', '獨贏賠率', '實際負磅', '檔位']
                        probs = model_v3.predict_proba(edited_df[v3_f])[:, 1]
                    elif "V1" in mode:
                        probs = edited_df['V1_機率']
                    else:
                        probs = edited_df['V2_機率']
                    
                    edited_df['AI預測入位率(%)'] = probs * 100
                    final_df = edited_df.sort_values(by='AI預測入位率(%)', ascending=False).reset_index(drop=True)
                    
                    def get_tag(row):
                        prob = row['AI預測入位率(%)']
                        odds = row['獨贏賠率']
                        if prob > 60: return "🔥🔥 鐵膽"
                        elif prob > 35 and odds >= 10.0: return "💎 價值冷門"
                        elif prob < 20: return "⚠️ 避開"
                        return ""
                    final_df['AI 評語'] = final_df.apply(get_tag, axis=1)
                    st.session_state['current_prediction'] = final_df
                    st.success("✅ V4 情報整合完畢！")
            
            if st.session_state['current_prediction'] is not None:
                final_df = st.session_state['current_prediction']
                st.dataframe(
                    final_df[['馬號', '馬名', '騎師', '練馬師', 'AI預測入位率(%)', '騎練默契', '獨贏賠率', '檔位', 'AI 評語']].style.format({'AI預測入位率(%)': '{:.1f}%', '騎練默契': '{:.1f}%', '獨贏賠率': '{:.1f}'}).background_gradient(subset=['AI預測入位率(%)'], cmap='RdYlGn'),
                    use_container_width=True, height=500
                )

                # 🌟 儀表板戰術板
                st.markdown("---")
                h = final_df['馬號'].astype(int).astype(str).tolist()
                c1, c2, c3 = st.columns(3)
                c1.info(f"🛡️ **1膽5腳 ($100)**\n\n膽：{h[0]}\n配：{', '.join(h[1:6])}")
                c2.success(f"⚖️ **2膽6腳 ($150)**\n\n雙膽：{h[0]}, {h[1]}\n配：{', '.join(h[2:8])}")
                c3.error(f"💰 **位置Q 避險**\n\n互串：{h[0]} x {h[1]}")

                if st.button("💾 將完整 V4 預測存入歷史庫"):
                    if gc:
                        try:
                            sheet_db = gc.open("Horse_AI_Database")
                            try:
                                full_sheet = sheet_db.worksheet("完整排位庫")
                            except:
                                full_sheet = sheet_db.add_worksheet(title="完整排位庫", rows="2000", cols="15")
                                full_sheet.append_row(["日期", "場次", "馬號", "馬名", "騎師", "練馬師", "機率", "默契", "賠率", "評語"])
                            
                            save_data = final_df[['馬號', '馬名', '騎師', '練馬師', 'AI預測入位率(%)', '騎練默契', '獨贏賠率', 'AI 評語']].copy()
                            save_data.insert(0, '場次', f"第 {race_no} 場")
                            save_data.insert(0, '日期', str(race_date))
                            full_sheet.append_rows(save_data.values.tolist())
                            st.success("✅ 完整 V4 數據已同步至雲端！")
                        except Exception as e: st.error(f"存檔失敗: {e}")

        else: st.warning("👈 尚未載入資料！請從左側欄貼上排位文字。")

    with col2:
        st.subheader("🏁 賽果與紀錄")
        with st.form("quick_payout"):
            my_p = st.number_input("💰 本場實際盈虧 ($)", step=10.0)
            if st.form_submit_button("💾 暫存盈虧"):
                st.session_state['temp_profit'] = my_p
                st.success("已紀錄，請至對帳台正式存檔。")

with tab2:
    st.header("📝 財務對帳台")
    if gc:
        try:
            sheet = gc.open("Horse_AI_Database").worksheet("戰績歷史")
            with st.form("result_form_v8"):
                r1, r2, r3, r4 = st.columns(4)
                f1 = r1.number_input("🥇 冠軍", 1, 14, 1)
                f2 = r2.number_input("🥈 亞軍", 1, 14, 2)
                f3 = r3.number_input("🥉 季軍", 1, 14, 3)
                f4 = r4.number_input("🏅 殿軍", 1, 14, 4)
                pl = st.number_input("💰 確認盈虧", value=st.session_state.get('temp_profit', 0.0))
                note = st.text_input("📝 筆記")
                if st.form_submit_button("💾 正式儲存"):
                    sheet.append_row([str(race_date), f"第 {race_no} 場", f1, f2, f3, f4, pl, note])
                    st.success("戰績已更新！")
            
            st.markdown("---")
            records = pd.DataFrame(sheet.get_all_records())
            if not records.empty:
                st.metric("累積總盈虧", f"${pd.to_numeric(records['本場盈虧']).sum():,.1f}")
                st.line_chart(pd.to_numeric(records['本場盈虧']).cumsum())
        except Exception as e: st.error(f"連線錯誤: {e}")

with tab3:
    st.header("📚 過往 V4 完整資料庫")
    if gc:
        try:
            full_sheet = gc.open("Horse_AI_Database").worksheet("完整排位庫")
            history_data = pd.DataFrame(full_sheet.get_all_records())
            if not history_data.empty:
                s_date = st.selectbox("📅 選擇日期回顧：", history_data['日期'].unique())
                st.dataframe(history_data[history_data['日期'] == s_date], use_container_width=True)
        except Exception as e: st.info("資料庫尚無資料。")
