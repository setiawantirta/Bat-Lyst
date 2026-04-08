import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import matplotlib.pyplot as plt
import seaborn as sns
import datetime
import io
from astral import LocationInfo
from astral.sun import sun

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Bat Bioacoustic Analyzer", layout="wide", page_icon="🦇")

# --- STANDAR PLOT NATURE Q1 ---
# Nature merekomendasikan font sans-serif, garis tipis, minimalis (tanpa background berlebih/grid tebal)
sns.set_theme(style="ticks")
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'axes.linewidth': 1.0,
    'axes.labelsize': 11,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'pdf.fonttype': 42, # Standar untuk ekspor vektor
    'ps.fonttype': 42
})

# --- FUNGSI HELPER ---
def length_to_sec(text):
    try:
        if ':' in str(text):
            parts = str(text).split(':')
            if len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
        return float(text)
    except: 
        return None

def get_minutes_after_sunset(row):
    try:
        obs = LocationInfo("", "", "UTC", row['lat'], row['lon'])
        date_obj = datetime.datetime.strptime(str(row['date']), '%Y-%m-%d').date()
        s = sun(obs.observer, date=date_obj)
        sunset_time = s['sunset']
        rec_time = datetime.datetime.strptime(f"{row['date']} {row['time']}", '%Y-%m-%d %H:%M')
        rec_time = rec_time.replace(tzinfo=datetime.timezone.utc)
        return (rec_time - sunset_time).total_seconds() / 60
    except:
        return None

def create_download_button(fig, filename):
    """Menyimpan matplotlib figure ke memory dan membuat tombol download Streamlit (300 DPI)"""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=300, bbox_inches="tight")
    buf.seek(0)
    return st.download_button(label=f"📥 Download Plot", data=buf, file_name=filename, mime="image/png")

@st.cache_data
def get_sample_csv():
    """Membuat sample data dummy untuk didownload pengguna."""
    sample_data = {
        'id': [1, 2, 3, 4], 'gen': ['Pteropus', 'Pteropus', 'Rhinolophus', 'Rhinolophus'], 
        'en': ['Large flying fox', 'Large flying fox', 'Horseshoe bat', 'Horseshoe bat'],
        'lat': [-6.2, -6.3, 0.5, 0.6], 'lon': [106.8, 106.9, 110.1, 110.2], 'alt': [100, 150, 50, 60],
        'date': ['2023-05-01', '2023-06-15', '2023-10-20', '2023-10-21'], 
        'time': ['18:30', '19:00', '05:00', '18:45'], 'length': ['01:30', '00:45', '2:00', '1:10'], 
        'q': ['A', 'B', 'A', 'A']
    }
    df = pd.DataFrame(sample_data)
    return df.to_csv(index=False).encode('utf-8')

# --- HEADER APLIKASI ---
st.title("🦇 Bat Bioacoustic Data Dashboard")
st.markdown("Dashboard analisis metadata bioakustik dengan luaran grafik standar jurnal berkualitas (High-Res).")

# --- SIDEBAR ---
st.sidebar.header("📁 Data Source")
uploaded_file = st.sidebar.file_uploader("Upload CSV Xeno-Canto", type=["csv"])

st.sidebar.divider()
st.sidebar.markdown("**Belum punya data?**")
st.sidebar.download_button(
    label="📄 Download Sample CSV", 
    data=get_sample_csv(), 
    file_name="sample_bat_data.csv", 
    mime="text/csv"
)

if uploaded_file is not None:
    # Load Data
    df_raw = pd.read_csv(uploaded_file)
    
    # Pre-processing Dasar
    df_final = df_raw.copy()
    df_final[['lat', 'lon', 'alt']] = df_final[['lat', 'lon', 'alt']].apply(pd.to_numeric, errors='coerce')
    df_final['duration_sec'] = df_final['length'].apply(length_to_sec)
    df_final['time_dt'] = pd.to_datetime(df_final['time'], format='%H:%M', errors='coerce')
    df_final['hour'] = df_final['time_dt'].dt.hour
    
    # Filter Genus (Hapus data NaN agar plot stabil)
    df_clean = df_final.dropna(subset=['gen', 'en']).copy()
    all_genera = sorted(df_clean['gen'].unique().tolist())
    selected_genera = st.sidebar.multiselect("Pilih Genus untuk Dianalisis", all_genera, default=all_genera[:4] if len(all_genera) >= 4 else all_genera)
    df_filtered = df_clean[df_clean['gen'].isin(selected_genera)].copy()

    # --- NAVIGASI TAB ---
    tab1, tab2, tab3, tab4 = st.tabs([
        "📍 Spasial & Elevasi", 
        "📊 Kualitas & Durasi", 
        "🌅 Temporal & Sunset", 
        "🔥 Activity Heatmap"
    ])

    # --- TAB 1: SPASIAL & ELEVASI ---
    with tab1:
        # 1. Pastikan kolom tanggal berformat datetime untuk filter
        df_filtered['date_dt'] = pd.to_datetime(df_filtered['date'], errors='coerce')
        
        # 2. Buat Expander untuk Custom Filter
        with st.expander("🔍 Custom Filter Spasial (Tanggal, Waktu, Lokasi)", expanded=True):
            f_col1, f_col2, f_col3 = st.columns(3)
            
            # --- Filter Tanggal ---
            # Mengambil tanggal paling awal dan paling akhir dari data
            min_date = df_filtered['date_dt'].min().date() if pd.notna(df_filtered['date_dt'].min()) else datetime.date(2000, 1, 1)
            max_date = df_filtered['date_dt'].max().date() if pd.notna(df_filtered['date_dt'].max()) else datetime.datetime.now().date()
            
            selected_dates = f_col1.date_input(
                "Rentang Tanggal", 
                value=(min_date, max_date), 
                min_value=min_date, 
                max_value=max_date
            )
            
            # --- Filter Waktu (Jam) ---
            selected_hours = f_col2.slider("Rentang Jam (Waktu Lokal)", 0, 23, (0, 23))
            
            # --- Filter Lokasi ---
            # Deteksi apakah menggunakan kolom 'cnt' (Negara) atau 'loc' (Nama Lokasi)
            loc_col = 'cnt' if 'cnt' in df_filtered.columns else ('loc' if 'loc' in df_filtered.columns else None)
            
            if loc_col:
                all_locs = sorted(df_filtered[loc_col].dropna().unique().tolist())
                selected_locs = f_col3.multiselect(f"Pilih Lokasi ({loc_col})", all_locs, default=all_locs)
            else:
                f_col3.info("Kolom lokasi ('cnt' atau 'loc') tidak ditemukan.")
                selected_locs = []

        # 3. Terapkan Filter ke Dataframe
        df_tab1 = df_filtered.copy()
        
        # Eksekusi filter tanggal jika input rentang lengkap (awal dan akhir terpilih)
        if len(selected_dates) == 2:
            start_date, end_date = selected_dates
            df_tab1 = df_tab1[(df_tab1['date_dt'].dt.date >= start_date) & (df_tab1['date_dt'].dt.date <= end_date)]
            
        # Eksekusi filter waktu
        df_tab1 = df_tab1[(df_tab1['hour'] >= selected_hours[0]) & (df_tab1['hour'] <= selected_hours[1])]
        
        # Eksekusi filter lokasi
        if loc_col and selected_locs:
            df_tab1 = df_tab1[df_tab1[loc_col].isin(selected_locs)]

        # 4. Render Plot dengan Data yang Sudah Difilter
        col1, col2 = st.columns([6, 4])
        
        with col1:
            st.subheader("Global Spatial Distribution")
            df_map = df_tab1.dropna(subset=['lat', 'lon'])
            
            if not df_map.empty:
                fig_map = px.scatter_map(
                    df_map, lat="lat", lon="lon", color="gen", 
                    hover_name="en", zoom=1, height=500,
                    title=f"Total Rekaman: {len(df_map)}"
                )
                st.plotly_chart(fig_map, width='stretch')
            else:
                st.warning("⚠️ Tidak ada koordinat yang sesuai dengan filter yang dipilih.")
        
        with col2:
            st.subheader("Elevation Distribution")
            df_alt = df_tab1.dropna(subset=['alt'])
            if not df_alt.empty:
                fig_alt, ax_alt = plt.subplots(figsize=(6, 5))
                sns.violinplot(data=df_alt, x='gen', y='alt', inner="box", ax=ax_alt, linewidth=1)
                ax_alt.set_title("Elevation Profile", weight='bold')
                ax_alt.set_ylabel("Elevation (m a.s.l.)")
                ax_alt.set_xlabel("")
                sns.despine()
                st.pyplot(fig_alt)
                create_download_button(fig_alt, "elevation_plot.png")
            else:
                st.info("Data elevasi (alt) tidak tersedia untuk filter ini.")

    # --- TAB 2: KUALITAS & DURASI ---
    with tab2:
        col3, col4 = st.columns(2)
        with col3:
            st.subheader("Recording Quality")
            quality_pivot = df_filtered.groupby(['gen', 'q']).size().unstack(fill_value=0)
            if not quality_pivot.empty:
                fig_q, ax_q = plt.subplots(figsize=(6, 5))
                quality_pivot.plot(kind='bar', stacked=True, colormap='magma_r', ax=ax_q, edgecolor='black', linewidth=0.5)
                ax_q.set_ylabel("Number of Recordings")
                ax_q.set_xlabel("Genus")
                sns.despine()
                st.pyplot(fig_q)
                create_download_button(fig_q, "quality_composition.png")
                
        with col4:
            st.subheader("Acoustic Sampling Duration")
            df_dur = df_filtered.dropna(subset=['duration_sec'])
            if not df_dur.empty:
                fig_dur, ax_dur = plt.subplots(figsize=(6, 5))
                sns.boxenplot(data=df_dur, x='gen', y='duration_sec', ax=ax_dur, linewidth=1)
                ax_dur.set_yscale('log')
                ax_dur.set_ylabel("Duration (Seconds, Log Scale)")
                ax_dur.set_xlabel("Genus")
                sns.despine()
                st.pyplot(fig_dur)
                create_download_button(fig_dur, "duration_plot.png")

    # --- TAB 3: TEMPORAL (SUNSET & SIRKADIAN) ---
    with tab3:
        st.subheader("Ecological Activity Relative to Sunset")
        if st.button("Hitung Waktu Sunset & Plot (Perlu Kalkulasi)"):
            with st.spinner("Menghitung geometri matahari..."):
                df_filtered['min_after_sunset'] = df_filtered.apply(get_minutes_after_sunset, axis=1)
                df_sunset = df_filtered[(df_filtered['min_after_sunset'] > -120) & (df_filtered['min_after_sunset'] < 600)]
                
                if not df_sunset.empty:
                    fig_ss, ax_ss = plt.subplots(figsize=(8, 4))
                    sns.kdeplot(data=df_sunset, x='min_after_sunset', hue='gen', fill=True, common_norm=False, bw_adjust=0.6, alpha=0.3, ax=ax_ss)
                    ax_ss.axvline(0, color='black', linestyle='--', linewidth=1.5, label='Sunset')
                    ax_ss.set_xlabel("Minutes Relative to Sunset (0 = Sunset)")
                    ax_ss.set_ylabel("Density")
                    sns.despine()
                    st.pyplot(fig_ss)
                    create_download_button(fig_ss, "sunset_activity.png")

        st.divider()
        st.subheader("Circadian Activity (Local Time)")
        df_indo = df_filtered.dropna(subset=['hour'])
        if not df_indo.empty:
            fig_indo, ax_indo = plt.subplots(figsize=(8, 4))
            sns.kdeplot(data=df_indo, x='hour', hue='gen', fill=True, common_norm=False, bw_adjust=0.5, alpha=0.3, ax=ax_indo)
            ax_indo.set_xlim(0, 24)
            ax_indo.set_xticks(range(0, 25, 2))
            ax_indo.set_xlabel("Hour of Day (Local Time)")
            ax_indo.set_ylabel("Density")
            sns.despine()
            st.pyplot(fig_indo)
            create_download_button(fig_indo, "circadian_activity.png")

    # --- TAB 4: HEATMAPS (STANDAR Q1) ---
    with tab4:
        st.subheader("Species Activity Pattern (Heatmaps)")
        
        # 1. 24-Hour Heatmap
        st.write("#### 24-Hour Activity Pattern")
        df_hm = df_filtered.dropna(subset=['time_dt', 'en']).copy()
        
        if not df_hm.empty:
            # Gunakan bin 30 menit
            df_hm['time_bin'] = df_hm['time_dt'].dt.floor('30min').dt.strftime('%H:%M')
            pivot_daily = df_hm.groupby(['en', 'time_bin']).size().unstack(fill_value=0)
            
            # Buat rentang waktu 24 jam utuh (00:00 - 23:30) agar sumbu x konsisten
            full_time_bins = [f"{str(h).zfill(2)}:{str(m).zfill(2)}" for h in range(24) for m in (0, 30)]
            pivot_daily = pivot_daily.reindex(columns=full_time_bins, fill_value=0)
            
            if not pivot_daily.empty:
                fig_hm1, ax_hm1 = plt.subplots(figsize=(12, 3.5))
                # cmap="Reds": 0=Putih, num_besar=Merah terang/pekat
                sns.heatmap(pivot_daily, cmap="Reds", ax=ax_hm1, cbar_kws={'label': 'Recording Count'}, linewidths=0.5, linecolor='whitesmoke')
                ax_hm1.set_xlabel("Time (30 min bins)")
                ax_hm1.set_ylabel("Species")
                plt.xticks(rotation=90)
                st.pyplot(fig_hm1)
                create_download_button(fig_hm1, "24h_heatmap.png")
        
        st.divider()
        
        # 2. Weekly Heatmap
        st.write("#### Seasonal / Weekly Activity Pattern")
        df_hm['date_dt'] = pd.to_datetime(df_hm['date'], errors='coerce')
        df_hm['week'] = df_hm['date_dt'].dt.isocalendar().week
        df_hm_week = df_hm.dropna(subset=['week']).copy()
        
        if not df_hm_week.empty:
            pivot_week = df_hm_week.groupby(['en', 'week']).size().unstack(fill_value=0)
            
            # Memaksa Sumbu X dimulai dari Minggu 1 hingga Minggu 52
            pivot_week = pivot_week.reindex(columns=range(1, 53), fill_value=0)
            
            if not pivot_week.empty:
                # Normalisasi data 0 ke 1 per spesies (Relative Activity)
                pivot_week_scaled = pivot_week.div(pivot_week.max(axis=1), axis=0).fillna(0)
                
                fig_hm2, ax_hm2 = plt.subplots(figsize=(20, 3.5))
                sns.heatmap(pivot_week_scaled, cmap="Reds", ax=ax_hm2, cbar_kws={'label': 'Relative Activity'}, linewidths=0.5, linecolor='whitesmoke')
                ax_hm2.set_xlabel("Week Number (1 - 52)")
                ax_hm2.set_ylabel("Species")
                plt.xticks(rotation=0)
                st.pyplot(fig_hm2)
                create_download_button(fig_hm2, "weekly_heatmap.png")

else:
    st.info("👋 Unggah file CSV di sebelah kiri, atau unduh sample data jika ingin mencoba aplikasinya.")
