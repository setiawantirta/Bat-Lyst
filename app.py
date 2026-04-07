import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import matplotlib.pyplot as plt
import seaborn as sns
import datetime
from astral import LocationInfo
from astral.sun import sun

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Bat Bioacoustic Analyzer", layout="wide", page_icon="🦇")

# --- FUNGSI HELPER ---
def length_to_sec(text):
    """Mengonversi format durasi (MM:SS atau detik) menjadi total detik."""
    try:
        if ':' in str(text):
            parts = str(text).split(':')
            if len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
        return float(text)
    except: 
        return None

def get_minutes_after_sunset(row):
    """Menghitung selisih waktu rekaman dengan waktu sunset lokal."""
    try:
        # 1. Setup Lokasi
        obs = LocationInfo("", "", "UTC", row['lat'], row['lon'])
        
        # 2. Setup Tanggal Rekaman
        date_obj = datetime.datetime.strptime(str(row['date']), '%Y-%m-%d').date()
        
        # 3. Hitung Waktu Matahari (UTC)
        s = sun(obs.observer, date=date_obj)
        sunset_time = s['sunset']
        
        # 4. Gabungkan Tanggal dan Jam Rekaman
        rec_time = datetime.datetime.strptime(f"{row['date']} {row['time']}", '%Y-%m-%d %H:%M')
        rec_time = rec_time.replace(tzinfo=datetime.timezone.utc)
        
        # 5. Hitung Selisih dalam Menit
        diff = (rec_time - sunset_time).total_seconds() / 60
        return diff
    except:
        return None

# --- HEADER APLIKASI ---
st.title("🦇 Bat Bioacoustic Data Dashboard")
st.markdown("Dashboard komprehensif untuk analisis metadata rekaman Xeno-Canto.")

# --- SIDEBAR: UPLOAD & FILTER ---
st.sidebar.header("📁 Data Source")
uploaded_file = st.sidebar.file_uploader("Upload CSV Xeno-Canto", type=["csv"])

if uploaded_file is not None:
    # Load Data
    df_raw = pd.read_csv(uploaded_file)
    
    # Pre-processing Dasar
    df_final = df_raw.copy()
    df_final[['lat', 'lon', 'alt']] = df_final[['lat', 'lon', 'alt']].apply(pd.to_numeric, errors='coerce')
    df_final['duration_sec'] = df_final['length'].apply(length_to_sec)
    
    # Extract waktu dengan aman
    df_final['time_dt'] = pd.to_datetime(df_final['time'], format='%H:%M', errors='coerce')
    df_final['hour'] = df_final['time_dt'].dt.hour
    
    # Filter Genus (Sidebar)
    # Hapus baris yang tidak punya Genus/Spesies agar grafik tidak error
    df_clean = df_final.dropna(subset=['gen', 'en']).copy()
    all_genera = sorted(df_clean['gen'].unique().tolist())
    
    selected_genera = st.sidebar.multiselect("Pilih Genus untuk Dianalisis", all_genera, default=all_genera[:4] if len(all_genera) >= 4 else all_genera)
    df_filtered = df_clean[df_clean['gen'].isin(selected_genera)].copy()

    # --- NAVIGASI TAB ---
    tab1, tab2, tab3, tab4 = st.tabs([
        "📍 Spasial & Elevasi", 
        "📊 Kualitas & Durasi", 
        "🌅 Analisis Temporal (Sunset & Sirkadian)", 
        "🔥 Activity Patterns (Heatmap)"
    ])

    # ---------------------------------------------------------
    # TAB 1: SPASIAL & ELEVASI
    # ---------------------------------------------------------
    with tab1:
        col1, col2 = st.columns([6, 4])
        
        with col1:
            st.subheader("Global Spatial Distribution")
            df_map = df_filtered.dropna(subset=['lat', 'lon'])
            if not df_map.empty:
                # Menggunakan scatter_map sesuai standar Plotly terbaru
                fig_map = px.scatter_map(
                    df_map, lat="lat", lon="lon", color="gen", 
                    hover_name="en", zoom=1, height=500,
                    title="Titik Perekaman Koordinat"
                )
                st.plotly_chart(fig_map, width='stretch')
            else:
                st.warning("Data koordinat (lat, lon) tidak mencukupi.")
                
        with col2:
            st.subheader("Elevation Distribution")
            df_alt = df_filtered.dropna(subset=['alt'])
            if not df_alt.empty:
                fig_alt, ax_alt = plt.subplots(figsize=(6, 5))
                sns.violinplot(data=df_alt, x='gen', y='alt', inner="quart", ax=ax_alt)
                ax_alt.set_title("Distribusi Ketinggian (MDPL)")
                plt.xticks(rotation=45)
                st.pyplot(fig_alt)
            else:
                st.warning("Data elevasi (alt) tidak mencukupi.")

    # ---------------------------------------------------------
    # TAB 2: KUALITAS & DURASI
    # ---------------------------------------------------------
    with tab2:
        st.subheader("Kualitas Rekaman & Sampling Usaha")
        col3, col4 = st.columns(2)
        
        with col3:
            st.write("**Recording Quality (A-E) Composition per Genus**")
            quality_pivot = df_filtered.groupby(['gen', 'q']).size().unstack(fill_value=0)
            if not quality_pivot.empty:
                fig_q, ax_q = plt.subplots(figsize=(8, 5))
                quality_pivot.plot(kind='bar', stacked=True, colormap='viridis', ax=ax_q)
                ax_q.set_ylabel("Number of Recordings")
                plt.xticks(rotation=45)
                st.pyplot(fig_q)
                
        with col4:
            st.write("**Acoustic Sampling Duration Variability (Log Scale)**")
            df_dur = df_filtered.dropna(subset=['duration_sec'])
            if not df_dur.empty:
                fig_dur, ax_dur = plt.subplots(figsize=(8, 5))
                sns.boxenplot(data=df_dur, x='gen', y='duration_sec', ax=ax_dur)
                ax_dur.set_yscale('log')
                ax_dur.set_ylabel("Duration (Seconds)")
                plt.xticks(rotation=45)
                st.pyplot(fig_dur)

    # ---------------------------------------------------------
    # TAB 3: ANALISIS TEMPORAL (SUNSET & INDONESIA)
    # ---------------------------------------------------------
    with tab3:
        st.subheader("Analisis Aktivitas Ekologis Harian")
        
        # 3A. SUNSET ANALYSIS
        st.write("### 1. Waktu Relatif Terhadap Sunset")
        st.info("Menghitung selisih jam perekaman berdasarkan waktu matahari terbenam persis di lokasi koordinat alat.")
        
        if st.button("Hitung Waktu Sunset & Plot KDE"):
            with st.spinner("Melakukan kalkulasi posisi matahari..."):
                df_filtered['min_after_sunset'] = df_filtered.apply(get_minutes_after_sunset, axis=1)
                df_sunset = df_filtered[(df_filtered['min_after_sunset'] > -120) & (df_filtered['min_after_sunset'] < 600)]
                
                if not df_sunset.empty:
                    fig_ss, ax_ss = plt.subplots(figsize=(12, 6))
                    sns.kdeplot(data=df_sunset, x='min_after_sunset', hue='gen', fill=True, common_norm=False, bw_adjust=0.6, ax=ax_ss)
                    ax_ss.axvline(0, color='orange', linestyle='--', linewidth=2, label='Sunset')
                    ax_ss.set_title("Ecological Activity Pattern: Minutes Relative to Sunset", fontsize=15)
                    ax_ss.set_xlabel("Minutes After Sunset (0 = Sunset Time)", fontsize=12)
                    ax_ss.set_ylabel("Activity Density", fontsize=12)
                    ax_ss.legend()
                    ax_ss.grid(axis='y', alpha=0.3)
                    st.pyplot(fig_ss)
                else:
                    st.error("Gagal menghitung sunset. Pastikan format 'date' (YYYY-MM-DD), 'time' (HH:MM), 'lat', dan 'lon' valid.")

        st.divider()
        
        # 3B. CIRCADIAN (INDONESIA / WIB CONTEXT)
        st.write("### 2. Sirkadian (WIB / Local Time)")
        df_indo = df_filtered.dropna(subset=['hour'])
        
        if not df_indo.empty:
            fig_indo, ax_indo = plt.subplots(figsize=(10, 5))
            sns.kdeplot(data=df_indo, x='hour', hue='gen', fill=True, common_norm=False, bw_adjust=0.5, ax=ax_indo)
            ax_indo.set_xlim(0, 24)
            ax_indo.set_xticks(range(0, 25, 2))
            ax_indo.set_title("Circadian Recording Distribution (Local Time)")
            ax_indo.set_xlabel("Hour of Day (00:00 - 24:00)")
            ax_indo.set_ylabel("Density of Recordings")
            ax_indo.grid(axis='x', linestyle='--', alpha=0.5)
            st.pyplot(fig_indo)

    # ---------------------------------------------------------
    # TAB 4: HEATMAP ACTIVITY
    # ---------------------------------------------------------
    with tab4:
        st.subheader("Species Activity Heatmap")
        
        # 4A. Heatmap Harian (24 Jam) - Bin 30 Menit
        st.write("### 24-Hour Activity Pattern")
        df_hm = df_filtered.dropna(subset=['time_dt', 'en']).copy()
        
        if not df_hm.empty:
            # Menggunakan '30min' sesuai Pandas versi terbaru (memperbaiki error 'T' dan '30T')
            df_hm['time_bin'] = df_hm['time_dt'].dt.floor('30min').dt.strftime('%H:%M')
            pivot_daily = df_hm.groupby(['en', 'time_bin']).size().unstack(fill_value=0)
            
            if not pivot_daily.empty:
                # Logika binarization (50% threshold)
                pivot_bin = pivot_daily.apply(lambda x: (x >= np.percentile(x, 50)).astype(int) if x.max() > 0 else x, axis=1)
                
                fig_hm1, ax_hm1 = plt.subplots(figsize=(11, 4))
                sns.heatmap(pivot_bin, cmap="Set1_r", cbar=False, linewidths=0.1, ax=ax_hm1)
                ax_hm1.set_xlabel("Time (30 min bins)")
                ax_hm1.set_ylabel("Species")
                st.pyplot(fig_hm1)
        
        st.divider()
        
        # 4B. Heatmap Mingguan (Musiman)
        st.write("### Seasonal/Weekly Activity Pattern")
        df_hm['date_dt'] = pd.to_datetime(df_hm['date'], errors='coerce')
        df_hm['week'] = df_hm['date_dt'].dt.isocalendar().week
        df_hm_week = df_hm.dropna(subset=['week']).copy()
        
        if not df_hm_week.empty:
            pivot_week = df_hm_week.groupby(['en', 'week']).size().unstack(fill_value=0)
            
            if not pivot_week.empty:
                # Normalisasi MinMaxScaler analog (skala 0 - 1 per baris/spesies)
                pivot_week_scaled = pivot_week.div(pivot_week.max(axis=1), axis=0).fillna(0)
                
                fig_hm2, ax_hm2 = plt.subplots(figsize=(11, 4))
                sns.heatmap(pivot_week_scaled, cmap="Reds", linewidths=0.5, ax=ax_hm2)
                ax_hm2.set_xlabel("Week Number")
                ax_hm2.set_ylabel("Species")
                st.pyplot(fig_hm2)

else:
    st.info("👋 Selamat datang! Silakan unggah file CSV hasil ekspor data Xeno-Canto melalui menu di sebelah kiri.")
