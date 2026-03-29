import streamlit as st
import pandas as pd
import joblib
import datetime
import re
import json
import gspread
import io
from google.oauth2.service_account import Credentials

# 網頁 UI 設定
st.set_page_config(page_title="AI 賽馬帝國 V8.0.1 抗壓版", page_icon="🏇", layout="wide")
st.title("🌪️ AI 賽馬帝國 V8.0.1 (抗賠率波動版)")
st.markdown("---")

# 0. 雲端連線
@st.cache_resource
def get_gspread_client():
    if "gcp_service_account_json" in st.secrets:
        try:
            creds_info = json.loads(st.secrets["gcp_service_account_json"])
            scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
            creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
            return gspread.authorize(creds)
        except Exception: return None
    return None

gc = get_gspread_client()

# 1. 資源載入
@st.cache_resource
def load_resources():
    try:
        m1 = joblib.load('hkjc_ai_brain_v1.pkl')
        m2 = joblib.load('hkjc_ai_brain_v2_no_odds.pkl')
        m4 = joblib.load('hkjc_ai_brain_v4_synergy.pkl')
        df_v4_ref = pd.read_csv('5_years_master_db_v4.csv', low_memory=False)
        synergy_map = df_v4_ref.drop_duplicates(subset=['騎師', '練馬師']).set_index(['騎師', '練馬師'])['騎練前四率'].to_dict()
        return m1, m2, m4, synergy_map
    except Exception as e:
        st.error(f"資源載入失敗: {e}")
        return None, None, None, None

m1, m2, m4, synergy_map = load_resources()

# 2. 側邊欄與解析 (略，維持原功能)
st.sidebar.header("⚙️ 賽事設定")
race_date = st.sidebar.date_input("日期", datetime.date.today())
race_no = st.sidebar.radio("場次", range(1, 15), horizontal=True)
pasted_text = st.sidebar.text_area("貼上排位資料", height=150)

# 解析函數 (與之前一致)
def parse_data(text):
    text = re.sub(r'[\(（]\-\d+[\)）]', '', text).replace('\n', ' ').replace('\xa0', ' ')
    parsed = []
    for i in range(1, 15):
        pattern = rf'(?<!\d){i}(?!\d)\s*\.?\s*([\u4e00-\u9fa5]{{2,6}})'
        match = re.search(pattern, text)
        if match:
            name = match.group(1)
            chunk = text[match.end():match.end()+100]
            dw_wt = re.search(r'(?<!\d)(\d{1,2})\s*(1[1-3]\d)(?!\d)', chunk)
            draw, wt = (int(dw_wt.group(1)), int(dw_wt.group(2))) if dw_wt else (1, 125)
            j_t = re.findall(r'[\u4e00-\u9fa5]+', chunk[:50])
            j_t = [w for w in j_t if w not in [name, "倍", "自"]]
            odds_m = re.findall(r'(?<!\d)(\d{1,3}(?:\.\d)?)(?!\d)', chunk)
            odds = float(odds_m[0]) if odds_m else 10.0
            parsed.append({'馬號': i, '馬名': name, '騎師': j_t[0] if j_t else "未知", '練馬師': j_t[1] if len(j_t)>1 else "未知", '實際負磅': wt, '排位體重': 1100, '檔位': draw, '獨贏賠率': odds, '休息天數': 30})
    return parsed

if st.sidebar.button("🔄 生成表格"):
    if pasted_text: st.session_state['df'] = pd.DataFrame(parse_data(pasted_text)); st.rerun()

# 3. 核心預測與抗壓測試
if 'df' in st.session_state:
    df = st.data_editor(st.session_state['df'], num_rows="dynamic", use_container_width=True)
    
    if st.button("🚀 啟動 V4 抗壓預測", type="primary"):
        def predict_core(input_df, odds_adj=1.0):
            temp = input_df.copy()
            temp['獨贏賠率'] = temp['獨贏賠率'] * odds_adj
            temp['負磅比率'] = temp['實際負磅'] / temp['排位體重']
            f1 = ['實際負磅', '排位體重', '獨贏賠率', '負磅比率', '休息天數', '檔位']
            f2 = ['實際負磅', '排位體重', '負磅比率', '休息天數', '檔位']
            temp['V1_P'] = m1.predict_proba(temp[f1])[:, 1]
            temp['V2_P'] = m2.predict_proba(temp[f2])[:, 1]
            temp['錯價'] = temp['V2_P'] - (1/temp['獨贏賠率'])
            temp['默契'] = temp.apply(lambda r: synergy_map.get((str(r['騎師']).strip(), str(r['練馬師']).strip()), 0.3), axis=1)
            v4_f = ['V1_P', 'V2_P', '錯價', '獨贏賠率', '實際負磅', '檔位', '默契']
            return m4.predict_proba(temp[v4_f].apply(pd.to_numeric, errors='coerce').fillna(0))[:, 1]

        # 進行三種情境測試
        df['現時機率'] = predict_core(df, 1.0)
        df['大戶入票後(-20%)'] = predict_core(df, 0.8)
        df['回冷後(+20%)'] = predict_core(df, 1.2)
        
        # 標記穩固度
        top2_now = set(df.nlargest(2, '現時機率')['馬號'])
        top2_hot = set(df.nlargest(2, '大戶入票後(-20%)')['馬號'])
        top2_cold = set(df.nlargest(2, '回冷後(+20%)')['馬號'])
        
        def check_stable(m_no):
            count = (1 if m_no in top2_now else 0) + (1 if m_no in top2_hot else 0) + (1 if m_no in top2_cold else 0)
            if count == 3: return "💎 鋼鐵穩膽 (無視波動)"
            if count >= 1 and m_no in top2_now: return "✅ 推薦 (受賠率影響)"
            return ""

        df['穩定度分析'] = df['馬號'].apply(check_stable)
        st.session_state['res'] = df.sort_values('現時機率', ascending=False)

    if 'res' in st.session_state:
        res = st.session_state['res']
        st.dataframe(res[['馬號', '馬名', '現時機率', '穩定度分析', '獨贏賠率', '騎師', '練馬師']].style.format({'現時機率': '{:.1f}%'}).background_gradient(subset=['現時機率'], cmap='Greens'), use_container_width=True)
        
        # 4. 戰術指令
        h = res['馬號'].astype(int).astype(str).tolist()
        st.subheader("🏁 終極下注指令 (最後 1 分鐘適用)")
        c1, c2 = st.columns(2)
        c1.success(f"🏆 **四重彩 (1, 2 名互換複式)**\n\n雙膽：{h[0]}, {h[1]}\n配腳：{', '.join(h[2:8])}")
        c2.info(f"🛡️ **避險建議**\n\n若第一名顯示為『受賠率影響』，建議加大配腳範圍至第 9 名。")
