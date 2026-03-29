import streamlit as st
import pandas as pd
import joblib
import numpy as np

# ==========================================
# 網頁 UI 設定
# ==========================================
st.set_page_config(page_title="賽馬 V8.0 終極指揮中心", layout="wide", page_icon="🏇")
st.title("🌪️ AI 賽馬帝國：V8.0 終極指揮中心")
st.markdown("**(搭載 V4 情報大腦 + 自動騎練默契解碼 + 2膽6腳 終極儀表板)**")

# ==========================================
# 側邊欄：資金控管
# ==========================================
st.sidebar.header("🏦 戰備資金設定")
total_capital = st.sidebar.number_input("今日預備作戰總本金 ($)", min_value=100, max_value=100000, value=2000, step=100)
st.sidebar.markdown("---")
st.sidebar.markdown("### 💡 V4 大腦戰術建議：")
st.sidebar.success("🥇 **首選：【2膽6腳】(每場 $150)**\n勝率高達 63%，淨利潤 80 萬的最強陣型！")
st.sidebar.warning("🥈 **次選：【1膽5腳】(每場 $100)**\n適合極度保守的小資試水溫。")
st.sidebar.error("🥉 **避險：【位置Q】(佔預算 20%)**\n雙膽互串，勝率極高，防止斷纜破產。")

# ==========================================
# 載入 V4 大腦與情報網
# ==========================================
@st.cache_resource
def load_resources():
    try:
        v1 = joblib.load('hkjc_ai_brain_v1.pkl')
        v2 = joblib.load('hkjc_ai_brain_v2_no_odds.pkl')
        v4 = joblib.load('hkjc_ai_brain_v4_synergy.pkl')
        
        # 讀取 V4 資料庫來建立「騎練默契字典」
        df_v4 = pd.read_csv('5_years_master_db_v4.csv', low_memory=False)
        # 製作查表字典 {(騎師, 練馬師): 默契指數}
        synergy_map = df_v4.drop_duplicates(subset=['騎師', '練馬師']).set_index(['騎師', '練馬師'])['騎練前四率'].to_dict()
        
        return v1, v2, v4, synergy_map
    except Exception as e:
        return None, None, None, None

model_v1, model_v2, model_v4, synergy_map = load_resources()

if model_v4 is None:
    st.error("❌ 找不到 V4 大腦或情報網檔案！請確認 GitHub 已上傳 `hkjc_ai_brain_v4_synergy.pkl` 與 `5_years_master_db_v4.csv`。")
    st.stop()

# ==========================================
# 資料輸入區 (⚠️ 新增騎師與練馬師欄位)
# ==========================================
st.subheader("📋 請貼上今日賽事排位表")
st.markdown("*(必須包含：馬號, **騎師**, **練馬師**, 實際負磅, 排位體重, 獨贏賠率, 休息天數, 檔位)*")

default_data = pd.DataFrame(columns=['馬號', '騎師', '練馬師', '實際負磅', '排位體重', '獨贏賠率', '休息天數', '檔位'], index=range(14))
edited_df = st.data_editor(default_data, num_rows="dynamic")

if st.button("🚀 啟動 V4 情報大腦與戰術解析", type="primary"):
    df = edited_df.dropna(how='all').copy()
    
    if len(df) < 6:
        st.warning("⚠️ 請至少輸入 6 匹馬的資料才能進行四連環預測！")
    else:
        try:
            # 清洗數字欄位
            for col in ['實際負磅', '排位體重', '獨贏賠率', '休息天數', '檔位']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df = df.dropna(subset=['實際負磅', '排位體重', '獨贏賠率', '休息天數', '檔位'])
            df['負磅比率'] = df['實際負磅'] / df['排位體重']
            
            # 🔍 自動匹配「騎練默契指數」
            def get_synergy(row):
                return synergy_map.get((row['騎師'], row['練馬師']), 0.3) # 找不到的新組合預設給 0.3
            
            df['騎練前四率'] = df.apply(get_synergy, axis=1)
            
            # 特徵定義
            features_v1 = ['實際負磅', '排位體重', '獨贏賠率', '負磅比率', '休息天數', '檔位']
            features_v2 = ['實際負磅', '排位體重', '負磅比率', '休息天數', '檔位']
            
            # V1, V2 基礎預測
            df['V1_機率'] = model_v1.predict_proba(df[features_v1])[:, 1]
            df['V2_機率'] = model_v2.predict_proba(df[features_v2])[:, 1]
            df['莊家機率'] = 1 / df['獨贏賠率']
            df['錯價指數'] = df['V2_機率'] - df['莊家機率']
            
            # 🌟 V4 終極預測 (加入騎練情報)
            v4_features = ['V1_機率', 'V2_機率', '錯價指數', '獨贏賠率', '實際負磅', '檔位', '騎練前四率']
            df['V4_終極勝率'] = model_v4.predict_proba(df[v4_features])[:, 1]
            
            # 排序與格式化
            df_result = df.sort_values(by='V4_終極勝率', ascending=False).reset_index(drop=True)
            df_result['顯示_勝率'] = (df_result['V4_終極勝率'] * 100).round(1).astype(str) + '%'
            df_result['顯示_騎練默契'] = (df_result['騎練前四率'] * 100).round(1).astype(str) + '%'
            
            top_horses = df_result['馬號'].astype(int).astype(str).tolist()
            
            # ==========================================
            # 🏆 實戰戰術儀表板
            # ==========================================
            st.markdown("---")
            st.header("🏆 【V8.0 終極實戰下注儀表板】")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.success("### 👑 2膽6腳 (首選)\n**成本 $150 | 勝率 63%**")
                st.markdown(f"🔥 **雙鐵膽：** `{top_horses[0]}`, `{top_horses[1]}`")
                st.markdown(f"🐎 **拖配腳：** `{', '.join(top_horses[2:8])}`")
                
            with col2:
                st.info("### 🛡️ 1膽5腳 (小資)\n**成本 $100 | 高防禦**")
                st.markdown(f"🔥 **單鐵膽：** `{top_horses[0]}`")
                st.markdown(f"🐎 **拖配腳：** `{', '.join(top_horses[1:6])}`")
                
            with col3:
                st.error("### 💰 位置Q (避險)\n**雙膽合體 | 防斷纜**")
                st.markdown(f"🎯 **互串：** `{top_horses[0]}` 拖 `{top_horses[1]}`")
                st.markdown(f"*(騎練默契：{df_result['顯示_騎練默契'].iloc[0]} & {df_result['顯示_騎練默契'].iloc[1]})*")

            st.markdown("---")
            st.subheader("📊 V4 大腦深度情報數據")
            # 顯示給使用者看的報表
            display_cols = ['馬號', '騎師', '練馬師', '顯示_勝率', '顯示_騎練默契', '獨贏賠率', '錯價指數', '實際負磅', '檔位']
            st.dataframe(df_result[display_cols], use_container_width=True)

        except Exception as e:
            st.error(f"❌ 運算發生錯誤，請檢查數字欄位是否正確填寫。錯誤訊息: {e}")
