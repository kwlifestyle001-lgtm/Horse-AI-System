import streamlit as st
import pandas as pd
import joblib
import numpy as np

# ==========================================
# 網頁 UI 設定 (維持你最熟悉的舊版風格！)
# ==========================================
st.set_page_config(page_title="賽馬 V4 引擎指揮中心", layout="wide")
st.title("🌪️ AI 賽馬帝國：終極指揮中心")
st.markdown("**(熟悉的介面，搭載最新 V4 騎練情報大腦！)**")

# ==========================================
# 側邊欄：凱利資金控管 (原封不動保留)
# ==========================================
st.sidebar.header("🏦 戰備資金設定")
total_capital = st.sidebar.number_input("今日預備作戰總本金 ($)", min_value=100, max_value=100000, value=2000, step=100)
st.sidebar.markdown("---")
st.sidebar.markdown("### 💡 系統建議策略：")
if total_capital < 1500:
    st.sidebar.success("🛡️ 建議採用：【1 膽 5 腳】(每場 $100)")
elif total_capital < 4000:
    st.sidebar.warning("⚖️ 建議採用：【2 膽 6 腳】(每場 $150) - 性價比最高！")
else:
    st.sidebar.error("🚀 建議採用：【1 膽 7 腳】(每場 $350) - 撒網轟炸！")

# ==========================================
# 載入 AI 大腦 (偷偷升級成 V4)
# ==========================================
@st.cache_resource
def load_models():
    try:
        v1 = joblib.load('hkjc_ai_brain_v1.pkl')
        v2 = joblib.load('hkjc_ai_brain_v2_no_odds.pkl')
        v4 = joblib.load('hkjc_ai_brain_v4_synergy.pkl') # 換成 V4 大腦
        
        # 建立騎練情報網字典
        df_v4 = pd.read_csv('5_years_master_db_v4.csv', low_memory=False)
        synergy_map = df_v4.drop_duplicates(subset=['騎師', '練馬師']).set_index(['騎師', '練馬師'])['騎練前四率'].to_dict()
        
        return v1, v2, v4, synergy_map
    except Exception as e:
        return None, None, None, None

model_v1, model_v2, model_v4, synergy_map = load_models()

if model_v4 is None:
    st.error("❌ 找不到 AI 模型檔案！請確認 GitHub 上有 V4 的 .pkl 與 .csv 檔案。")
    st.stop()

# ==========================================
# 資料輸入區 (只多了騎師和練馬師，其他都不變)
# ==========================================
st.subheader("📋 請貼上今日賽事排位表 (包含：馬號, 騎師, 練馬師, 實際負磅, 排位體重, 獨贏賠率, 休息天數, 檔位)")

default_data = pd.DataFrame(columns=['馬號', '騎師', '練馬師', '實際負磅', '排位體重', '獨贏賠率', '休息天數', '檔位'], index=range(14))
edited_df = st.data_editor(default_data, num_rows="dynamic")

if st.button("🚀 啟動 AI 終極預測與戰術解析", type="primary"):
    df = edited_df.dropna(how='all').copy()
    
    if len(df) < 6:
        st.warning("⚠️ 請至少輸入 6 匹馬的資料才能進行四連環預測！")
    else:
        try:
            # 轉換數字格式
            for col in ['實際負磅', '排位體重', '獨贏賠率', '休息天數', '檔位']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df = df.dropna(subset=['實際負磅', '排位體重', '獨贏賠率', '休息天數', '檔位'])
            df['負磅比率'] = df['實際負磅'] / df['排位體重']
            
            # 獲取騎練默契
            def get_synergy(row):
                return synergy_map.get((row['騎師'], row['練馬師']), 0.3)
            df['騎練前四率'] = df.apply(get_synergy, axis=1)
            
            # 特徵定義
            features_v1 = ['實際負磅', '排位體重', '獨贏賠率', '負磅比率', '休息天數', '檔位']
            features_v2 = ['實際負磅', '排位體重', '負磅比率', '休息天數', '檔位']
            
            # V1, V2 預測
            df['V1_機率'] = model_v1.predict_proba(df[features_v1])[:, 1]
            df['V2_機率'] = model_v2.predict_proba(df[features_v2])[:, 1]
            df['莊家機率'] = 1 / df['獨贏賠率']
            df['錯價指數'] = df['V2_機率'] - df['莊家機率']
            
            # 🌟 V4 預測 (原來的 V3 被升級了)
            v4_features = ['V1_機率', 'V2_機率', '錯價指數', '獨贏賠率', '實際負磅', '檔位', '騎練前四率']
            df['AI_入位率'] = model_v4.predict_proba(df[v4_features])[:, 1]
            
            # 排序與格式化
            df_result = df.sort_values(by='AI_入位率', ascending=False).reset_index(drop=True)
            df_result['預測入位率'] = (df_result['AI_入位率'] * 100).round(1).astype(str) + '%'
            df_result['騎練默契'] = (df_result['騎練前四率'] * 100).round(1).astype(str) + '%'
            
            # 抓取馬號產生戰術
            top_horses = df_result['馬號'].astype(int).astype(str).tolist()
            
            # ==========================================
            # 🏆 實戰戰術儀表板 (你最熟悉的經典三欄位)
            # ==========================================
            st.markdown("---")
            st.header("🏆 【終極實戰下注儀表板】")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.info("### 🛡️ 1膽5腳 (成本 $100)\n**高 ROI 刺客型**")
                st.markdown(f"👑 **鐵膽：** `{top_horses[0]}` 號")
                st.markdown(f"🐎 **配腳：** `{', '.join(top_horses[1:6])}`")
                
            with col2:
                st.success("### ⚖️ 2膽6腳 (成本 $150)\n**完美槓桿平衡型**")
                st.markdown(f"👑 **雙膽：** `{top_horses[0]}`, `{top_horses[1]}` 號")
                st.markdown(f"🐎 **配腳：** `{', '.join(top_horses[2:8])}`")
                
            with col3:
                st.error("### 💰 位置Q 避險 (防斷纜)\n**50% 高勝率保底**")
                st.markdown(f"🎯 **互串：** `{top_horses[0]}` 號 拖 `{top_horses[1]}` 號")
                st.markdown("*建議佔單場總預算 20%*")

            st.markdown("---")
            st.subheader("📊 AI 深度情報預測數據")
            st.dataframe(df_result[['馬號', '騎師', '練馬師', '預測入位率', '騎練默契', '獨贏賠率', '錯價指數', '檔位', '實際負磅']], use_container_width=True)

        except Exception as e:
            st.error(f"❌ 運算發生錯誤，請檢查輸入資料格式是否正確。錯誤訊息: {e}")
