import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from folium.plugins import AntPath
import math
import plotly.express as px

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="GIRSU - Control de Operaciones", layout="wide")

# Estilo para visibilidad de métricas y diseño limpio
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { color: #1a1a1a !important; font-weight: bold !important; }
    [data-testid="stMetricLabel"] { color: #4a4a4a !important; }
    div[data-testid="stMetric"] { background-color: #f0f2f6; padding: 15px; border-radius: 10px; border: 1px solid #d1d5db; }
    </style>
    """, unsafe_allow_html=True)

st.title("Control de Operaciones: Proyecto Relleno Sanitario")

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
    
    # --- CARGA DE DATOS ---
    df_b_raw = pd.read_excel(archivo, sheet_name="BATEAS", header=None)
    mask = df_b_raw.apply(lambda x: x.astype(str).str.contains('DESTINO', case=False, na=False))
    idx_fila = df_b_raw[mask.any(axis=1)].index[0]
    df_matriz = pd.read_excel(archivo, sheet_name="BATEAS", skiprows=idx_fila).dropna(axis=1, how='all')
    df_escenarios = df_matriz.set_index(df_matriz.columns[0]).T
    df_escenarios.index = df_escenarios.index.astype(str).str.strip()

    df_proy_raw = pd.read_excel(archivo, sheet_name="RESPALDO RESIDUOS", skiprows=1)
    df_proy = df_proy_raw.dropna(subset=[df_proy_raw.columns[0]]).iloc[:, [0, 1, 4, 7]]
    df_proy.columns = ['Año', 'SF_Pop', 'ST_Pop', 'Resto_Pop']
    df_proy['Año_Txt'] = df_proy['Año'].astype(int).astype(str)

    # --- SIDEBAR (CONFIGURACIÓN REORGANIZADA) ---
    with st.sidebar:
        st.header("⚙️ Configuración")
        
        # 1. Escenario primero
        st.subheader("📍 Escenario")
        escenario_sel = st.selectbox("Seleccionar Escenario de Destino:", df_escenarios.index)
        d = df_escenarios.loc[escenario_sel]
        
        # 2. Año segundo
        st.subheader("📅 Horizonte Temporal")
        anio_sel = st.select_slider("Año de Proyección:", options=df_proy['Año_Txt'].tolist(), value="2026")
        pop_data = df_proy[df_proy['Año_Txt'] == anio_sel].iloc[0]
        tn_totales_anio = (float(pop_data['SF_Pop']) + float(pop_data['ST_Pop']) + float(pop_data['Resto_Pop'])) * 0.001
        
        # 3. Capacidad tercero
        st.subheader("🚛 Equipo")
        capacidad_t = st.selectbox("Capacidad de la Batea (TN):", [30, 25, 20])

        st.markdown("---")
        
        # 4. El resto de la configuración
        st.subheader("💰 Parámetros de Costo")
        precio_litro = st.number_input("Precio Litro Gasoil ($):", value=1100.0)
        cons_cargado = st.number_input("Consumo Ida - Cargado (L/km):", value=0.52)
        cons_vacio = st.number_input("Consumo Vuelta - Vacío (L/km):", value=0.30)
        
        st.markdown("---")
        st.subheader("🗺️ Visualización del Mapa")
        estilo_mapa = st.radio("Estilo de vista:", ["Claro (Calles)", "Satelital (Híbrido)"])
        tile_provider = "OpenStreetMap" if estilo_mapa == "Claro (Calles)" else "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}"
        attr = "OpenStreetMap" if estilo_mapa == "Claro (Calles)" else "Google Maps"
        
        radio_20 = st.checkbox("Mostrar Radio 20 km", value=False)
        radio_35 = st.checkbox("Mostrar Radio 35 km", value=False)
        radio_50 = st.checkbox("Mostrar Radio 50 km", value=False)

    # --- LÓGICA DE CÁLCULO ---
    def clean_val(key):
        c = [col for col in d.index if key.lower() in str(col).lower()]
        return float(d[c[0]]) if c else 0

    distancia_ida = clean_val('Km')
    dist_total_vuelta = distancia_ida * 2
    viajes_posibles_unidad = math.floor(clean_val('Viajes Posibles'))
    tiempo_ciclo = clean_val('Ciclo') 
    
    viajes_totales_req = math.ceil(tn_totales_anio / capacidad_t)
    flota_necesaria = math.ceil((viajes_totales_req / 2) / viajes_posibles_unidad) if viajes_posibles_unidad > 0 else 0
    km_totales_unidad = dist_total_vuelta * viajes_posibles_unidad
    costo_por_viaje = (distancia_ida * cons_cargado + distancia_ida * cons_vacio) * precio_litro
    km_totales_sistema = dist_total_vuelta * viajes_totales_req
    costo_total_diario = costo_por_viaje * viajes_totales_req

    # --- 1. MAPA (CABECERA) ---
    et_lat, et_lon = -31.621, -60.751 
    dest_lat, dest_lon = float(clean_val('Latitud')), float(clean_val('Longitud'))
    m = folium.Map(location=[-31.6, -60.8], zoom_start=10, tiles=tile_provider, attr=attr)
    
    # Dibujo de radios
    if radio_20: folium.Circle([et_lat, et_lon], radius=20000, color='blue', fill=True, fill_opacity=0.1).add_to(m)
    if radio_35: folium.Circle([et_lat, et_lon], radius=35000, color='orange', fill=True, fill_opacity=0.07).add_to(m)
    if radio_50: folium.Circle([et_lat, et_lon], radius=50000, color='red', fill=True, fill_opacity=0.05).add_to(m)
    
    ruta = get_route(et_lat, et_lon, dest_lat, dest_lon)
    AntPath(locations=ruta, delay=1000, color='blue', weight=6).add_to(m)
    folium.Marker([et_lat, et_lon], icon=folium.Icon(color='blue', icon='truck', prefix='fa'), tooltip="E. Transferencia").add_to(m)
    folium.Marker([dest_lat, dest_lon], icon=folium.Icon(color='red', icon='flag', prefix='fa'), tooltip=escenario_sel).add_to(m)
    
    st_folium(m, width="100%", height=450, key="mapa_operativo")

    st.markdown("---")

    # --- 2. INDICADORES ---
    st.subheader(f"📊 Resumen Logístico ({anio_sel} - Bateas {capacidad_t} TN)")
    g1, g2, g3, g4 = st.columns(4)
    g1.metric("DEMANDA", f"{tn_totales_anio:.1f} t/día")
    g2.metric("DISTANCIA TOTAL", f"{dist_total_vuelta:.1f} km")
    g3.metric("VIAJES DÍA", f"{int(viajes_totales_req)}")
    g4.metric("FLOTA TOTAL", f"{int(flota_necesaria)} Unidades")

    st.markdown("---")
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### 🚛 Rendimiento por Unidad")
        o1, o2 = st.columns(2)
        o1.metric("VIAJES/TURNO", f"{int(viajes_posibles_unidad)}")
        o2.metric("COSTO POR VIAJE", f"$ {costo_por_viaje:,.0f}")
    with c2:
        st.markdown("##### 💰 Impacto Operativo Diario")
        s1, s2 = st.columns(2)
        s1.metric("KM TOTALES", f"{int(km_totales_sistema)} km")
        s2.metric("GASTO TOTAL", f"$ {costo_total_diario:,.0f}")

    st.markdown("---")

    # --- 3. PESTAÑAS DE DATOS ---
    t1, t2, t3, t4 = st.tabs(["📈 Gráfico Carga", "📋 Población", "📋 Matriz Escenarios", "📖 Memoria Técnica"])
    with t1:
        df_proy['Carga_TN'] = (df_proy['SF_Pop'] + df_proy['ST_Pop'] + df_proy['Resto_Pop']) * 0.001
        fig = px.line(df_proy, x='Año_Txt', y='Carga_TN', markers=True, title="Crecimiento Proyectado")
        st.plotly_chart(fig, use_container_width=True)
    with t2:
        st.dataframe(df_proy[['Año_Txt', 'SF_Pop', 'ST_Pop', 'Resto_Pop']].astype(str), use_container_width=True)
    with t3:
        st.dataframe(df_escenarios.T.astype(str), use_container_width=True)
    with t4:
        st.info(f"**Cálculo:** {dist_total_vuelta} km/viaje × {int(viajes_totales_req)} fletes = {int(km_totales_sistema)} km totales por jornada.")

except Exception as e:
    st.error(f"Hubo un inconveniente con los datos: {e}")