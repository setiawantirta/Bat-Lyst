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
            parts = str(text).split(':')
            if len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
        return float(text)
    except: return None

def get_minutes_after_sunset(row):
    try:
        obs = LocationInfo("", "", "UTC", row['lat'], row['lon'])
        date_obj = pd.to_datetime(row['date']).date()
        s = sun(obs.observer, date=date_obj)
        sunset_time = s['sunset']
        rec_time = pd.to_datetime(f"{row['date']} {row['time']}", errors='coerce').tz_localize('UTC')
        return (rec_time - sunset_time).total_seconds() / 60
    except: return None

# --- APP TITLE ---
st.title("Bat Bioacoustic Data Analysis 🦇")

# --- SIDEBAR ---
st.sidebar.header("Data Source")
uploaded_file = st.sidebar.file_uploader("Upload CSV Xeno-Canto", type=["csv"])

if uploaded_file is not None:
    # Load Data
    df_raw = pd.read_csv(uploaded_file)
    
    # Cleaning & Pre-processing
    df_final = df_raw.copy()
    df_final[['lat', 'lon', 'alt']] = df_final[['lat', 'lon', 'alt']].apply(pd.to_numeric, errors='coerce')
    df_final['duration_sec'] = df_final['length'].apply(length_to_sec)
    df_final['hour'] = pd.to_datetime(df_final['time'], format='%H:%M', errors='coerce').dt.hour
    
    # Dropna untuk kolom kritikal agar plot muncul
    df_plot = df_final.dropna(subset=['gen', 'en'])

    # Filter Sidebar
    all_genera = sorted(df_plot['gen'].unique().tolist())
    selected_genera = st.sidebar.multiselect("Pilih Genus", all_genera, default=all_genera[:3])
    df_filtered = df_plot[df_plot['gen'].isin(selected_genera)]

    # --- TABS ---
    tab1, tab2, tab3, tab4 = st.tabs(["📍 Geospatial", "📊 Quality & Duration", "🌅 Sunset Analysis", "🔥 Activity Heatmaps"])

    # --- TAB 1: GEOSPATIAL ---
    with tab1:
        st.subheader("Spatial Distribution")
        df_map = df_filtered.dropna(subset=['lat', 'lon'])
        if not df_map.empty:
            fig_map = px.scatter_map(
                df_map, lat="lat", lon="lon", color="gen", 
                hover_name="en", zoom=1, height=600
            )
            st.plotly_chart(fig_map, width='stretch')
        else:
            st.warning("Data koordinat (lat, lon) tidak ditemukan.")

    # --- TAB 2: QUALITY & DURATION ---
    with tab2:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Recording Quality")
            quality_pivot = df_filtered.groupby(['gen', 'q']).size().unstack(fill_value=0)
            if not quality_pivot.empty:
                fig_q, ax_q = plt.subplots()
                quality_pivot.plot(kind='bar', stacked=True, ax=ax_q)
                plt.xticks(rotation=45)
                st.pyplot(fig_q)
        
        with col2:
            st.subheader("Elevation by Genus")
            if not df_filtered['alt'].dropna().empty:
                fig_alt, ax_alt = plt.subplots()
                sns.violinplot(data=df_filtered, x='gen', y='alt', ax=ax_alt)
                plt.xticks(rotation=45)
                st.pyplot(fig_alt)

        st.divider()
        st.subheader("Sampling Duration (Log Scale)")
        fig_dur, ax_dur = plt.subplots(figsize=(10, 4))
        sns.boxenplot(data=df_filtered, x='gen', y='duration_sec', ax=ax_dur)
        ax_dur.set_yscale('log')
        st.pyplot(fig_dur)

    # --- TAB 3: SUNSET ---
    with tab3:
        st.subheader("Ecological Activity (Relative to Sunset)")
        if st.button("Calculate Sunset Offset"):
            with st.spinner("Processing..."):
                df_filtered['min_after_sunset'] = df_filtered.apply(get_minutes_after_sunset, axis=1)
                df_ss = df_filtered.dropna(subset=['min_after_sunset'])
                
                if not df_ss.empty:
                    fig_ss, ax_ss = plt.subplots(figsize=(10, 5))
                    sns.kdeplot(data=df_ss, x='min_after_sunset', hue='gen', fill=True, bw_adjust=0.6, ax=ax_ss)
                    ax_ss.axvline(0, color='orange', linestyle='--', label='Sunset')
                    plt.legend()
                    st.pyplot(fig_ss)
                else:
                    st.error("Gagal menghitung sunset. Pastikan kolom 'lat', 'lon', 'date', dan 'time' lengkap.")

    # --- TAB 4: HEATMAPS ---
    with tab4:
        st.subheader("Species Activity Patterns")
        
        # Data Prep
        df_hm = df_filtered.copy()
        df_hm['time_dt'] = pd.to_datetime(df_hm['time'], format="%H:%M", errors='coerce')
        df_hm = df_hm.dropna(subset=['time_dt', 'en'])

        if not df_hm.empty:
            # 24H Heatmap
            df_hm['time_bin'] = df_hm['time_dt'].dt.floor('30min').dt.strftime('%H:%M')
            pivot_daily = df_hm.groupby(['en', 'time_bin']).size().unstack(fill_value=0)
            
            if not pivot_daily.empty:
                st.write("### 24-Hour Relative Activity (Binary Threshold)")
                # Logic binarization
                pivot_bin = pivot_daily.apply(lambda x: (x >= np.percentile(x, 50)).astype(int) if x.max() > 0 else x, axis=1)
                fig_h1, ax_h1 = plt.subplots(figsize=(12, 5))
                sns.heatmap(pivot_bin, cmap="YlGnBu", ax=ax_h1, cbar=False)
                st.pyplot(fig_h1)

            # Weekly Heatmap
            st.divider()
            st.write("### Seasonal Weekly Activity")
            df_hm['date_dt'] = pd.to_datetime(df_hm['date'], errors='coerce')
            df_hm['week'] = df_hm['date_dt'].dt.isocalendar().week
            pivot_week = df_hm.groupby(['en', 'week']).size().unstack(fill_value=0)
            
            if not pivot_week.empty:
                pivot_week_scaled = pivot_week.div(pivot_week.max(axis=1), axis=0).fillna(0)
                fig_h2, ax_h2 = plt.subplots(figsize=(12, 5))
                sns.heatmap(pivot_week_scaled, cmap="Reds", ax=ax_h2)
                st.pyplot(fig_h2)
        else:
            st.info("Data waktu tidak valid untuk heatmap.")

else:
    st.info("👋 Selamat datang! Silakan unggah file CSV hasil ekspor Xeno-Canto Anda di sidebar.")
