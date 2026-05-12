import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from folium.plugins import AntPath
import math
import plotly.express as px

# 1. RESET DE MEMORIA Y ESTÉTICA "COMMAND CENTER"
st.cache_data.clear() 
st.set_page_config(page_title="Dashboard Logística - Relleno Sanitario", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #e0e0e0; }
    .stMetric { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }
    [data-testid="stSidebar"] { background-color: #0d1117; }
    </style>
    """, unsafe_allow_html=True)

st.title("Dashboard Logística: Proyecto Relleno Sanitario")

def get_route(start_lat, start_lon, end_lat, end_lon):
    import requests
    url = f"http://router.project-osrm.org/route/v1/driving/{start_lon},{start_lat};{end_lon},{end_lat}?overview=full&geometries=geojson"
    try:
        r = requests.get(url, timeout=2).json()
        return [[p[1], p[0]] for p in r['routes'][0]['geometry']['coordinates']]
    except:
        return [[start_lat, start_lon], [end_lat, end_lon]]

try:
    archivo = "datos_logistica_26.xlsx"
    
    # --- CARGA DE DATOS: BATEAS ---
    df_b_raw = pd.read_excel(archivo, sheet_name="BATEAS", header=None)
    mask = df_b_raw.apply(lambda x: x.astype(str).str.contains('DESTINO', case=False, na=False))
    idx_fila = df_b_raw[mask.any(axis=1)].index[0]
    
    df_matriz = pd.read_excel(archivo, sheet_name="BATEAS", skiprows=idx_fila).dropna(axis=1, how='all')
    df_escenarios = df_matriz.set_index(df_matriz.columns[0]).T
    df_escenarios.index = df_escenarios.index.astype(str).str.strip()

    # --- CARGA DE DATOS: PROYECCIONES ---
    df_proy_raw = pd.read_excel(archivo, sheet_name="RESPALDO RESIDUOS", skiprows=1)
    df_proy = df_proy_raw.dropna(subset=[df_proy_raw.columns[0]]).iloc[:, [0, 1, 4, 7]]
    df_proy.columns = ['Año', 'SF_Pop', 'ST_Pop', 'Resto_Pop']
    df_proy['Año_Txt'] = df_proy['Año'].astype(int).astype(str)

    # --- SIDEBAR (CONTROLES) ---
    with st.sidebar:
        st.header("⚙️ Configuración")
        estilo_mapa = st.selectbox("Estilo de Mapa", ["CartoDB dark_matter", "CartoDB Positron", "OpenStreetMap"])
        
        st.markdown("---")
        st.subheader("📍 Radios de Influencia (ET)")
        # Interruptores para los radios
        radio_20 = st.checkbox("Radio 20 km", value=False)
        radio_35 = st.checkbox("Radio 35 km", value=False)
        radio_50 = st.checkbox("Radio 50 km", value=False)
        
        st.markdown("---")
        lista_anios = df_proy['Año_Txt'].tolist()
        anio_sel = st.select_slider("Año de Proyección:", options=lista_anios, value="2026")
        
        pop_data = df_proy[df_proy['Año_Txt'] == anio_sel].iloc[0]
        tn_totales_anio = (float(pop_data['SF_Pop']) + float(pop_data['ST_Pop']) + float(pop_data['Resto_Pop'])) * 0.001
        
        st.markdown("---")
        escenario_sel = st.selectbox("Seleccionar Escenario:", df_escenarios.index)
        d = df_escenarios.loc[escenario_sel]

    # --- LÓGICA LOGÍSTICA ---
    def clean_val(key):
        c = [col for col in d.index if key.lower() in str(col).lower()]
        return float(d[c[0]]) if c else 0

    viajes_unidad_turno = math.floor(clean_val('Viajes Posibles'))
    viajes_totales_req = math.ceil(tn_totales_anio / 30)
    flota_necesaria = math.ceil((viajes_totales_req / 2) / viajes_unidad_turno) if viajes_unidad_turno > 0 else 0

    # --- MÉTRICAS DE CABECERA ---
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(f"Demanda {anio_sel}", f"{tn_totales_anio:.1f} t/día")
    m2.metric("Viajes Totales Requeridos", f"{int(viajes_totales_req)}")
    m3.metric("Viajes / Unidad (Turno)", f"{int(viajes_unidad_turno)}")
    m4.metric("Flota Necesaria (Turno)", f"{int(flota_necesaria)} Unidades")

    # --- PESTAÑAS ---
    t1, t2, t3, t4 = st.tabs(["🗺️ Mapa Vial Real", "📈 Tendencia de Carga", "📋 Cuadro de Proyección", "📋 Matriz Técnica"])

    with t1:
        st.subheader(f"📍 Ruta Logística: {escenario_sel}")
        # Coordenadas de la ET
        et_lat, et_lon = -31.621, -60.751 
        dest_lat, dest_lon = float(clean_val('Latitud')), float(clean_val('Longitud'))
        
        m = folium.Map(location=[-31.6, -60.8], zoom_start=10, tiles=estilo_mapa)
        
        # --- DIBUJAR RADIOS SI ESTÁN MARCADOS ---
        if radio_20:
            folium.Circle([et_lat, et_lon], radius=20000, color='#00f2ff', fill=True, fill_opacity=0.1, tooltip="Radio 20km").add_to(m)
        if radio_35:
            folium.Circle([et_lat, et_lon], radius=35000, color='#f1c40f', fill=True, fill_opacity=0.07, tooltip="Radio 35km").add_to(m)
        if radio_50:
            folium.Circle([et_lat, et_lon], radius=50000, color='#e74c3c', fill=True, fill_opacity=0.05, tooltip="Radio 50km").add_to(m)

        # Ruta Real
        ruta = get_route(et_lat, et_lon, dest_lat, dest_lon)
        AntPath(locations=ruta, delay=1000, color='#00f2ff', weight=6, opacity=0.8).add_to(m)
        
        folium.Marker([et_lat, et_lon], tooltip="ET Santa Fe", icon=folium.Icon(color='blue', icon='truck', prefix='fa')).add_to(m)
        folium.Marker([dest_lat, dest_lon], tooltip=escenario_sel, icon=folium.Icon(color='red', icon='flag', prefix='fa')).add_to(m)
        
        st_folium(m, width="100%", height=550)

    with t2:
        st.subheader("Evolución de la Carga Diaria (TN/día)")
        df_proy['Carga_TN'] = (df_proy['SF_Pop'] + df_proy['ST_Pop'] + df_proy['Resto_Pop']) * 0.001
        fig = px.line(df_proy, x='Año_Txt', y='Carga_TN', template="plotly_dark", markers=True)
        st.plotly_chart(fig, use_container_width=True)

    with t3:
        st.subheader("Proyección Demográfica")
        st.dataframe(df_proy[['Año_Txt', 'SF_Pop', 'ST_Pop', 'Resto_Pop']].astype(str), use_container_width=True)

    with t4:
        st.subheader("Matriz Técnica Original (Excel)")
        st.dataframe(df_escenarios.T.astype(str), use_container_width=True)

except Exception as e:
    st.error(f"Error detectado: {e}")