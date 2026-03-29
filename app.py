import streamlit as st
import pandas as pd
import joblib
import datetime
import re
import json
import gspread
from google.oauth2.service_account import Credentials
import warnings
warnings.filterwarnings('ignore')

# ==========================================
# 網頁 UI 設定
# ==========================================
st.set_page_config(page_title="AI 賽馬帝國 V8.0 終極完全體", page_icon="🏇", layout="wide")
st.title("🌪️ AI 賽馬帝國 V8.0 (終極完全體)")
st.markdown("**(一鍵解析 + Google雲端 + V4情報大腦 + 抗壓指示燈)**")
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
# 1. 載入 AI 大腦 與 V4 情報庫
# ==========================================
@st.cache_resource
def load_resources():
    try:
        m1 = joblib.load('hkjc_ai_brain_v1.pkl')
        m2 = joblib.load('hkjc_ai_brain_v2_no_odds.pkl')
        m3 = joblib.load('hkjc_ai_brain_v3_holygrail.pkl')
        m4 = joblib.load('hkjc_ai_brain_v4_synergy.pkl')
        
        df_v4_ref = pd.read_csv('5_years_master_db_v4.csv', low_memory=False)
        synergy_map = df_v4_ref.drop_duplicates(subset=['騎師', '練馬師']).set_index(['騎師', '練馬師'])['騎練前四率'].to_dict()
        
        return m1, m2, m3, m4, synergy_map
    except Exception as e:
        st.error(f"資源載入失敗！請確認模型與資料庫檔案皆已上傳: {e}")
        return None, None, None, None, None

model_v1, model_v2, model_v3, model_v4, synergy_map = load_resources()

if 'races_db' not in st.session_state:
    st.session_state['races_db'] = {}
if 'current_prediction' not in st.session_state:
    st.session_state['current_prediction'] = None

# ==========================================
# 2. 核心黑科技：文字解析雷達
# ==========================================
def parse_horse_data(text):
    text = re.sub(r'[\(（]\-\d+[\)）]', '', text).replace('\n', ' ').replace('\t', ' ').replace('>', ' ').replace('\xa0', ' ')
    parsed = []
    
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
            draw, wt = (int(dw_wt.group(1)), int(dw_wt.group(2))) if dw_wt else (1, 125)
                
            chinese_blocks = re.findall(r'[\u4e00-\u9fa5]+', chunk[:40])
            j_t_list = [word for word in chinese_blocks if word not in [name, "倍", "自"]]
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
# 3. 側邊欄設定
# ==========================================
st.sidebar.header("⚙️ 賽事設定")
race_date = st.sidebar.date_input("賽事日期：", datetime.date.today())
race_no = st.sidebar.radio("選擇場次：", range(1, 15), horizontal=True)
race_key = f"{race_date}_Race{race_no}"

st.sidebar.markdown("---")
st.sidebar.header("📋 一鍵貼上解析")
pasted_text = st.sidebar.text_area("在此貼上排位資料：", height=200)

if st.sidebar.button("🔄 解析並生成表格"):
    if pasted_text:
        with st.sidebar.status("情報雷達掃描中..."):
            extracted_data = parse_horse_data(pasted_text)
            if extracted_data:
                st.session_state['races_db'][race_key] = pd.DataFrame(extracted_data)
                st.rerun()

# ==========================================
# 4. 主分頁系統
# ==========================================
tab1, tab2, tab3 = st.tabs(["🔮 AI 預測大廳", "🏆 財務對帳台", "📚 過往資料庫"])

with tab1:
    mode = st.radio("作戰大腦：", ("⚔️ V4 情報終極版", "🏆 V3 聖杯融合", "💰 V1 殺莊", "💪 V2 物理"), horizontal=True)
    
    if race_key in st.session_state['races_db']:
        df = st.session_state['races_db'][race_key]
        edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
        st.session_state['races_db'][race_key] = edited_df
        
        if st.button("🚀 啟動 AI 終極運算", type="primary"):
            with st.spinner("神經網路運算中..."):
                # 預測核心函數 (完美解決名稱報錯)
                def predict_core(input_df, odds_adj=1.0):
                    temp = input_df.copy()
                    temp['獨贏賠率'] = temp['獨贏賠率'] * odds_adj
                    temp['負磅比率'] = temp['實際負磅'] / temp['排位體重']
                    f1 = ['實際負磅', '排位體重', '獨贏賠率', '負磅比率', '休息天數', '檔位']
                    f2 = ['實際負磅', '排位體重', '負磅比率', '休息天數', '檔位']
                    
                    temp['V1_機率'] = model_v1.predict_proba(temp[f1])[:, 1]
                    temp['V2_機率'] = model_v2.predict_proba(temp[f2])[:, 1]
                    temp['錯價指數'] = temp['V2_機率'] - (1 / temp['獨贏賠率'])
                    temp['騎練前四率'] = temp.apply(lambda r: synergy_map.get((str(r['騎師']).strip(), str(r['練馬師']).strip()), 0.3), axis=1)
                    
                    v4_f = ['V1_機率', 'V2_機率', '錯價指數', '獨贏賠率', '實際負磅', '檔位', '騎練前四率']
                    return temp, model_v4.predict_proba(temp[v4_f].apply(pd.to_numeric, errors='coerce').fillna(0))[:, 1]

                # 進行預測
                if "V4" in mode:
                    # 1. 取得現時基準機率 (1.0x) - 保留爆冷暴利
                    base_df, probs_now = predict_core(edited_df, 1.0)
                    base_df['AI預測入位率(%)'] = probs_now * 100
                    
                    # 2. 進行抗壓測試 (0.8x, 1.2x) 尋找鋼鐵穩膽
                    _, probs_hot = predict_core(edited_df, 0.8)
                    _, probs_cold = predict_core(edited_df, 1.2)
                    
                    base_df['P_hot'] = probs_hot
                    base_df['P_cold'] = probs_cold
                    
                    top2_now = set(base_df.nlargest(2, 'AI預測入位率(%)')['馬號'])
                    top2_hot = set(base_df.nlargest(2, 'P_hot')['馬號'])
                    top2_cold = set(base_df.nlargest(2, 'P_cold')['馬號'])
                    
                    def check_stable(m_no):
                        if m_no in top2_now and m_no in top2_hot and m_no in top2_cold:
                            return "💎 鋼鐵穩膽"
                        elif m_no in top2_now:
                            return "✅ V4 首選"
                        return ""
                    
                    base_df['穩定度分析'] = base_df['馬號'].apply(check_stable)
                    final_df = base_df.sort_values(by='AI預測入位率(%)', ascending=False).reset_index(drop=True)
                else:
                    # 兼容 V1, V2, V3
                    edited_df['負磅比率'] = edited_df['實際負磅'] / edited_df['排位體重']
                    f1 = ['實際負磅', '排位體重', '獨贏賠率', '負磅比率', '休息天數', '檔位']
                    f2 = ['實際負磅', '排位體重', '負磅比率', '休息天數', '檔位']
                    edited_df['V1_機率'] = model_v1.predict_proba(edited_df[f1])[:, 1]
                    edited_df['V2_機率'] = model_v2.predict_proba(edited_df[f2])[:, 1]
                    edited_df['莊家機率'] = 1 / edited_df['獨贏賠率']
                    edited_df['錯價指數'] = edited_df['V2_機率'] - edited_df['莊家機率']
                    
                    if "V3" in mode:
                        v3_f = ['V1_機率', 'V2_機率', '錯價指數', '獨贏賠率', '實際負磅', '檔位']
                        probs = model_v3.predict_proba(edited_df[v3_f])[:, 1]
                    else:
                        probs = edited_df['V1_機率'] if "V1" in mode else edited_df['V2_機率']
                        
                    edited_df['AI預測入位率(%)'] = probs * 100
                    edited_df['騎練前四率'] = 0.0
                    edited_df['穩定度分析'] = ""
                    final_df = edited_df.sort_values(by='AI預測入位率(%)', ascending=False).reset_index(drop=True)

                st.session_state['current_prediction'] = final_df
                st.success("✅ AI 運算完成！")

        if st.session_state['current_prediction'] is not None:
            res = st.session_state['current_prediction']
            
            # 顯示表格 (使用 V4 正確名稱，但介面看起來乾淨)
            display_cols = ['馬號', '馬名', '騎師', '練馬師', 'AI預測入位率(%)', '穩定度分析', '騎練前四率', '獨贏賠率', '檔位']
            st.dataframe(res[display_cols].style.format({'AI預測入位率(%)': '{:.1f}%', '騎練前四率': '{:.1f}%'}).background_gradient(subset=['AI預測入位率(%)'], cmap='RdYlGn'), use_container_width=True)
            
            # ==========================================
            # 🏆 實戰戰術儀表板
            # ==========================================
            st.markdown("---")
            st.header("🏆 【V8.0 實戰下注儀表板】")
            h = res['馬號'].astype(int).astype(str).tolist()
            c1, c2, c3 = st.columns(3)
            
            with c1:
                st.success(f"⚖️ **【基礎】2膽6腳 ($150)**\n\n維持現金流的穩定陣型。\n\n**雙膽：** {h[0]}, {h[1]}\n**配腳：** {', '.join(h[2:8])}")
            with c2:
                st.warning(f"🚀 **【暴利】四重彩 ($600)**\n\n若前兩名有『💎 鋼鐵穩膽』可考慮此陣型！\n\n**1, 2名互換：** {h[0]}, {h[1]}\n**配腳：** {', '.join(h[2:8])}")
            with c3:
                st.error(f"💰 **【避險】位置Q**\n\n**互串：** {h[0]} x {h[1]}")

            if st.button("💾 將本場預測存入雲端歷史庫"):
                if gc:
                    try:
                        sh = gc.open("Horse_AI_Database").worksheet("完整排位庫")
                        save_df = res[['馬號', '馬名', '騎師', '練馬師', 'AI預測入位率(%)', '騎練前四率', '獨贏賠率', '穩定度分析']].copy()
                        save_df.insert(0, '場次', f"第 {race_no} 場")
                        save_df.insert(0, '日期', str(race_date))
                        sh.append_rows(save_df.values.tolist())
                        st.success("✅ 已同步至雲端資料庫！")
                    except Exception as e:
                        st.error(f"存檔失敗，請確認是否已建立分頁: {e}")

with tab2:
    st.header("📝 財務對帳台")
    if gc:
        try:
            sheet = gc.open("Horse_AI_Database").worksheet("戰績歷史")
            with st.form("f_form"):
                p_l = st.number_input("💰 本場實際盈虧 ($)", step=10.0)
                note = st.text_input("📝 賽後檢討筆記")
                if st.form_submit_button("💾 正式儲存戰績"):
                    sheet.append_row([str(race_date), f"第 {race_no} 場", "", "", "", "", p_l, note])
                    st.success("戰績已成功儲存！")
        except Exception as e:
            st.error(f"連線失敗: {e}")

with tab3:
    st.header("📚 過往 V4 完整資料庫")
    if gc:
        try:
            full_data = pd.DataFrame(gc.open("Horse_AI_Database").worksheet("完整排位庫").get_all_records())
            if not full_data.empty:
                d = st.selectbox("📅 選擇回顧日期：", full_data['日期'].unique())
                st.dataframe(full_data[full_data['日期'] == d], use_container_width=True)
        except Exception as e:
            st.info("資料庫目前尚無資料。")
