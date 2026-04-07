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
        date_obj = pd.to_datetime(row['date']).date()
        s = sun(obs.observer, date=date_obj)
        sunset_time = s['sunset']
        
        rec_time = pd.to_datetime(f"{row['date']} {row['time']}")
        rec_time = rec_time.replace(tzinfo=datetime.timezone.utc)
        
        diff = (rec_time - sunset_time).total_seconds() / 60
        return diff
    except:
        return None

# --- APP TITLE ---
st.title("🦇 Bat Bioacoustic Data Analysis")
st.markdown("Dashboard untuk menganalisis metadata rekaman kelelawar dari Xeno-Canto.")

# --- SIDEBAR: UPLOAD DATA ---
st.sidebar.header("Upload Data")
uploaded_file = st.sidebar.file_uploader("Upload CSV Xeno-Canto", type=["csv"])

if uploaded_file is not None:
    df_final = pd.read_csv(uploaded_file)
    
    # Pre-processing Dasar
    df_final[['lat', 'lon', 'alt']] = df_final[['lat', 'lon', 'alt']].apply(pd.to_numeric, errors='coerce')
    df_final['duration_sec'] = df_final['length'].apply(length_to_sec)
    df_final['hour'] = pd.to_datetime(df_final['time'], errors='coerce').dt.hour
    
    # Filter Genus untuk memudahkan visualisasi
    all_genera = df_final['gen'].unique().tolist()
    selected_genera = st.sidebar.multiselect("Pilih Genus untuk Dianalisis", all_genera, default=all_genera[:5])
    df_filtered_gen = df_final[df_final['gen'].isin(selected_genera)]

    # --- TAB LAYOUT ---
    tab1, tab2, tab3, tab4 = st.tabs([
        "📍 Spasial & Kualitas", 
        "⏱️ Durasi & Temporal", 
        "🌅 Sunset Analysis", 
        "📈 Activity Patterns"
    ])

    # --- TAB 1: SPASIAL & KUALITAS ---
    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Global Spatial Distribution")
            fig_map = px.scatter_mapbox(
                df_filtered_gen.dropna(subset=['lat', 'lon']), 
                lat="lat", lon="lon", color="gen", hover_name="en",
                zoom=1, mapbox_style="carto-positron", height=500
            )
            st.plotly_chart(fig_map, use_container_width=True)
            
        with col2:
            st.subheader("Elevation Distribution")
            fig_alt, ax_alt = plt.subplots()
            sns.violinplot(data=df_filtered_gen, x='gen', y='alt', inner="quart", ax=ax_alt)
            plt.xticks(rotation=45)
            st.pyplot(fig_alt)

        st.divider()
        st.subheader("Recording Quality (A-E) per Genus")
        quality_pivot = df_filtered_gen.groupby(['gen', 'q']).size().unstack().fillna(0)
        st.bar_chart(quality_pivot)

    # --- TAB 2: DURASI & TEMPORAL ---
    with tab2:
        col3, col4 = st.columns(2)
        
        with col3:
            st.subheader("Acoustic Sampling Duration (Log Scale)")
            fig_dur, ax_dur = plt.subplots()
            sns.boxenplot(data=df_filtered_gen, x='gen', y='duration_sec', ax=ax_dur)
            ax_dur.set_yscale('log')
            plt.xticks(rotation=45)
            st.pyplot(fig_dur)
            
        with col4:
            st.subheader("Circadian Distribution (Local Time)")
            fig_hr, ax_hr = plt.subplots()
            sns.kdeplot(data=df_filtered_gen, x='hour', hue='gen', fill=True, bw_adjust=0.5, ax=ax_hr)
            ax_hr.set_xlim(0, 24)
            st.pyplot(fig_hr)

    # --- TAB 3: SUNSET ANALYSIS ---
    with tab3:
        st.subheader("Ecological Activity Relative to Sunset")
        st.info("Menghitung selisih waktu rekaman dengan waktu sunset lokal menggunakan koordinat GPS.")
        
        if st.button("Run Sunset Calculation (Might take a while)"):
            with st.spinner("Calculating sunset times..."):
                df_filtered_gen['min_after_sunset'] = df_filtered_gen.apply(get_minutes_after_sunset, axis=1)
                df_sunset = df_filtered_gen[(df_filtered_gen['min_after_sunset'] > -120) & (df_filtered_gen['min_after_sunset'] < 600)]
                
                fig_ss, ax_ss = plt.subplots(figsize=(10, 5))
                sns.kdeplot(data=df_sunset, x='min_after_sunset', hue='gen', fill=True, bw_adjust=0.6, ax=ax_ss)
                ax_ss.axvline(0, color='orange', linestyle='--', linewidth=2, label='Sunset')
                plt.legend()
                st.pyplot(fig_ss)

    # --- TAB 4: ACTIVITY PATTERNS (HEATMAP) ---
    with tab4:
        st.subheader("Species Activity Heatmap")
        
        # Data Preparation for Heatmaps
        df_hm = df_filtered_gen.copy()
        df_hm['time_dt'] = pd.to_datetime(df_hm['time'], format="%H:%M", errors='coerce')
        df_hm = df_hm.dropna(subset=['time_dt'])
        
        # 1. Heatmap Harian (30 min bins)
        st.write("### 24-Hour Activity Pattern")
        # Simplified Logic for Streamlit Heatmap
        df_hm['time_bin'] = df_hm['time_dt'].dt.floor('30T').dt.strftime('%H:%M')
        pivot_daily = df_hm.groupby(['en', 'time_bin']).size().unstack(fill_value=0)
        # Binarize based on 50% threshold logic as per your code
        pivot_bin = pivot_daily.apply(lambda x: (x >= np.percentile(x, 50)).astype(int) if x.max() > 0 else x, axis=1)
        
        fig_hm1, ax_hm1 = plt.subplots(figsize=(12, 4))
        sns.heatmap(pivot_bin, cmap="Set1_r", cbar=False, linewidths=0.1, ax=ax_hm1)
        st.pyplot(fig_hm1)

        # 2. Heatmap Mingguan
        st.write("### Seasonal/Weekly Activity Pattern")
        df_hm['date_dt'] = pd.to_datetime(df_hm['date'], errors='coerce')
        df_hm['week'] = df_hm['date_dt'].dt.isocalendar().week
        df_hm = df_hm.dropna(subset=['week'])
        
        pivot_week = df_hm.groupby(['en', 'week']).size().unstack(fill_value=0)
        # Normalized scaling
        pivot_week_scaled = pivot_week.div(pivot_week.max(axis=1), axis=0).fillna(0)
        
        fig_hm2, ax_hm2 = plt.subplots(figsize=(12, 4))
        sns.heatmap(pivot_week_scaled, cmap="Reds", ax=ax_hm2)
        st.pyplot(fig_hm2)

else:
    st.info("Silakan upload file CSV data Xeno-Canto Anda melalui sidebar.")
