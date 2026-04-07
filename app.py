import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import matplotlib.pyplot as plt
import seaborn as sns
import datetime
from astral import LocationInfo
from astral.sun import sun

# Set Page Config
st.set_page_config(page_title="Bat Bioacoustic Analyzer", layout="wide")

# --- HELPER FUNCTIONS ---
def length_to_sec(text):
    try:
        if ':' in str(text):
            m, s = str(text).split(':')
            return int(m) * 60 + int(s)
        return float(text)
    except: return None

def get_minutes_after_sunset(row):
    try:
        obs = LocationInfo("", "", "UTC", row['lat'], row['lon'])
        # Perbaikan format tanggal agar konsisten
        date_obj = pd.to_datetime(row['date'], format='ISO8601').date()
        s = sun(obs.observer, date=date_obj)
        sunset_time = s['sunset']
        
        # Perbaikan format waktu
        rec_time = pd.to_datetime(f"{row['date']} {row['time']}", format='mixed')
        rec_time = rec_time.replace(tzinfo=datetime.timezone.utc)
        
        diff = (rec_time - sunset_time).total_seconds() / 60
        return diff
    except:
        return None

# --- APP TITLE ---
st.title("🦇 Bat Bioacoustic Data Analysis")

# --- SIDEBAR ---
st.sidebar.header("Upload Data")
uploaded_file = st.sidebar.file_uploader("Upload CSV Xeno-Canto", type=["csv"])

if uploaded_file is not None:
    df_final = pd.read_csv(uploaded_file)
    
    # 1. Perbaikan UserWarning pd.to_datetime: tentukan format atau gunakan 'mixed'
    df_final[['lat', 'lon', 'alt']] = df_final[['lat', 'lon', 'alt']].apply(pd.to_numeric, errors='coerce')
    df_final['duration_sec'] = df_final['length'].apply(length_to_sec)
    df_final['hour'] = pd.to_datetime(df_final['time'], format='%H:%M', errors='coerce').dt.hour
    
    all_genera = df_final['gen'].unique().tolist()
    selected_genera = st.sidebar.multiselect("Pilih Genus", all_genera, default=all_genera[:5])
    df_filtered_gen = df_final[df_final['gen'].isin(selected_genera)]

    tab1, tab2, tab3, tab4 = st.tabs(["📍 Spasial", "⏱️ Temporal", "🌅 Sunset", "📈 Heatmap"])

    with tab1:
        # 2. Perbaikan DeprecationWarning: Ganti scatter_mapbox menjadi scatter_map
        st.subheader("Global Spatial Distribution")
        fig_map = px.scatter_map(
            df_filtered_gen.dropna(subset=['lat', 'lon']), 
            lat="lat", lon="lon", color="gen", hover_name="en",
            zoom=1, height=500
        )
        # 3. Perbaikan use_container_width: Ganti menjadi width='stretch'
        st.plotly_chart(fig_map, width='stretch')

    with tab4:
        st.subheader("Species Activity Heatmap")
        
        df_hm = df_filtered_gen.copy()
        df_hm['time_dt'] = pd.to_datetime(df_hm['time'], format="%H:%M", errors='coerce')
        df_hm = df_hm.dropna(subset=['time_dt'])
        
        st.write("### 24-Hour Activity Pattern")
        
        # 4. PERBAIKAN UTAMA: Ganti '30T' menjadi '30min'
        df_hm['time_bin'] = df_hm['time_dt'].dt.floor('30min').dt.strftime('%H:%M')
        
        pivot_daily = df_hm.groupby(['en', 'time_bin']).size().unstack(fill_value=0)
        
        if not pivot_daily.empty:
            pivot_bin = pivot_daily.apply(lambda x: (x >= np.percentile(x, 50)).astype(int) if x.max() > 0 else x, axis=1)
            fig_hm1, ax_hm1 = plt.subplots(figsize=(12, 4))
            sns.heatmap(pivot_bin, cmap="Set1_r", cbar=False, linewidths=0.1, ax=ax_hm1)
            st.pyplot(fig_hm1)
        else:
            st.warning("Data tidak cukup untuk membuat heatmap.")

else:
    st.info("Upload file CSV untuk memulai.")
