import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from folium.plugins import AntPath
import math
import plotly.express as px
from pathlib import Path
import unicodedata

st.set_page_config(page_title="GIRSU - Nuevo Modelo Logístico", layout="wide")

st.markdown("""
<style>
[data-testid="stMetricValue"] { color: #1a1a1a !important; font-weight: bold !important; }
[data-testid="stMetricLabel"] { color: #4a4a4a !important; }
div[data-testid="stMetric"] {
    background-color: #f0f2f6;
    padding: 15px;
    border-radius: 10px;
    border: 1px solid #d1d5db;
}
.semaforo-card {
    background: #ffffff;
    border-radius: 14px;
    padding: 14px 16px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.08);
    border: 1px solid #e5e7eb;
    margin-bottom: 12px;
}
.semaforo-title {
    font-size: 18px;
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 10px;
}
.semaforo-localidad {
    font-size: 16px;
    font-weight: 700;
    color: #111827;
    margin-bottom: 8px;
}
.semaforo-chip {
    display: inline-block;
    padding: 6px 10px;
    border-radius: 999px;
    font-weight: 700;
    color: #111827;
    margin-bottom: 10px;
}
.semaforo-linea {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: #374151;
    margin: 5px 0;
}
.semaforo-luz {
    width: 16px;
    height: 16px;
    border-radius: 50%;
    border: 1px solid #555;
    display: inline-block;
}
.semaforo-comment {
    font-size: 14px;
    line-height: 1.45;
    color: #374151;
    margin-top: 10px;
}
</style>
""", unsafe_allow_html=True)

st.title("GIRSU - DASHBOARD")
st.caption("Escenarios con Estaciones de Transferencia, Planta de Energía y alternativas de Futuro Relleno Sanitario")

# Archivo de datos: busca primero la base nueva y, si no está, usa nombres anteriores.
base_path = Path(__file__).parent
candidatos_archivo = [
    base_path / "datos_logistica_v28_coordenadas_ET.xlsx",
    base_path / "datos_logistica_27_nuevo_modelo_con_distancias.xlsx",
    base_path / "datos_logistica_26.xlsx",
    base_path / "datos_logistica.xlsx",
]
archivo = next((p for p in candidatos_archivo if p.exists()), candidatos_archivo[0])

try:
    if not archivo.exists():
        st.error(
            "No se encontró el archivo de datos. Guardá el Excel junto a app.py con alguno de estos nombres: "
            "datos_logistica_27_nuevo_modelo_con_distancias.xlsx, datos_logistica_26.xlsx o datos_logistica.xlsx."
        )
        st.stop()

    # =========================
    # CARGA DE DATOS NUEVOS
    # =========================
    df_residuos = pd.read_excel(archivo, sheet_name="PROYECCION_RESIDUOS").dropna(how="all")
    df_infra = pd.read_excel(archivo, sheet_name="INFRAESTRUCTURA").dropna(how="all")
    df_escenarios = pd.read_excel(archivo, sheet_name="ESCENARIOS").dropna(how="all")
    df_dist = pd.read_excel(archivo, sheet_name="DISTANCIAS").dropna(how="all")
    df_distrib = pd.read_excel(archivo, sheet_name="DISTRIBUCION_INFRAESTRUCTURA").dropna(how="all")
    df_rellenos = pd.read_excel(archivo, sheet_name="FUTUROS_RELLENOS").dropna(how="all")
    df_param = pd.read_excel(archivo, sheet_name="PARAMETROS").dropna(how="all")

    # Limpieza básica
    for df in [df_residuos, df_infra, df_escenarios, df_dist, df_distrib, df_rellenos]:
        df.columns = df.columns.astype(str).str.strip()

    # Normalización visual de nombres
    # La planta de energía debe mostrarse solo como "Planta de Energía"
    # en mapa, etiquetas, tooltips, gráficos y tablas.
    for col in ["NOMBRE", "DESTINO"]:
        if col in df_infra.columns:
            df_infra[col] = df_infra[col].replace({
                "Planta de Energía - Actual RS": "Planta de Energía",
                "Planta de Energia - Actual RS": "Planta de Energía",
                "Planta Energia - Actual RS": "Planta de Energía",
            })
        if col in df_distrib.columns:
            df_distrib[col] = df_distrib[col].replace({
                "Planta de Energía - Actual RS": "Planta de Energía",
                "Planta de Energia - Actual RS": "Planta de Energía",
                "Planta Energia - Actual RS": "Planta de Energía",
            })

    # Coordenadas y toneladas
    df_infra["LATITUD"] = pd.to_numeric(df_infra["LATITUD"], errors="coerce")
    df_infra["LONGITUD"] = pd.to_numeric(df_infra["LONGITUD"], errors="coerce")
    df_rellenos["LATITUD"] = pd.to_numeric(df_rellenos["LATITUD"], errors="coerce")
    df_rellenos["LONGITUD"] = pd.to_numeric(df_rellenos["LONGITUD"], errors="coerce")

    df_residuos["TON_ACTUAL_DIA"] = pd.to_numeric(df_residuos["TON_ACTUAL_DIA"], errors="coerce").fillna(0)
    df_residuos["TON_PROYECTADA_800"] = pd.to_numeric(df_residuos["TON_PROYECTADA_800"], errors="coerce").fillna(0)

    df_dist["KM_LINEAL"] = pd.to_numeric(df_dist["KM_LINEAL"], errors="coerce")
    df_dist["FACTOR_RUTA"] = pd.to_numeric(df_dist["FACTOR_RUTA"], errors="coerce").fillna(1.25)
    df_dist["KM_OPERATIVO"] = pd.to_numeric(df_dist["KM_OPERATIVO"], errors="coerce")
    df_dist["KM_RUTA_REAL"] = pd.to_numeric(df_dist["KM_RUTA_REAL"], errors="coerce")
    # Prioridad: ruta real > km operativo > estimación lineal ajustada por factor de ruta.
    # Esto evita NaN cuando todavía no está cargado KM_RUTA_REAL para los futuros rellenos.
    df_dist["KM_ESTIMADO"] = df_dist["KM_LINEAL"] * df_dist["FACTOR_RUTA"]
    df_dist["KM_USADO"] = df_dist["KM_RUTA_REAL"].fillna(df_dist["KM_OPERATIVO"]).fillna(df_dist["KM_ESTIMADO"])

    # =========================
    # PRIORIZACIÓN SEMAFORIZADA DE FUTUROS RELLENOS
    # =========================
    CRITERIOS_RELLENOS_TABLA = [
        {
            "Localidad": "Colonia San José",
            "Lectura rápida": "Prioridad 1 preliminar",
            "Estado visible": "Favorable en principio",
            "Comentario orientativo": "Buen desempeño logístico y menor presión urbana relativa; debe superar filtros hídricos y dominiales.",
            "Semáforo": "green",
            "Color": "#92D050",
            "Folium": "green",
            "Icono": "check",
        },
        {
            "Localidad": "Empalme San Carlos",
            "Lectura rápida": "Prioridad 2 condicionada",
            "Estado visible": "Condicional / sensible",
            "Comentario orientativo": "Perfil rural favorable, pero el riesgo hídrico asociado al Salado es un condicionante central.",
            "Semáforo": "yellow",
            "Color": "#FFF200",
            "Folium": "orange",
            "Icono": "exclamation-triangle",
        },
        {
            "Localidad": "Sauce Viejo",
            "Lectura rápida": "Alternativa viable condicionada",
            "Estado visible": "Condicional / sensible",
            "Comentario orientativo": "Buena logística, condicionada por aeropuerto, urbanización, hidrología y accesos.",
            "Semáforo": "yellow",
            "Color": "#FFF200",
            "Folium": "orange",
            "Icono": "exclamation-triangle",
        },
    ]

    ALIASES_RELLENOS = {
        "Colonia San José": ["colonia san jose", "colonia san josé"],
        "Empalme San Carlos": ["empalme san carlos", "emp. san carlos", "emp san carlos"],
        "Sauce Viejo": ["sauce viejo"],
    }

    def normalizar_texto(valor):
        valor = "" if pd.isna(valor) else str(valor)
        valor = unicodedata.normalize("NFKD", valor).encode("ascii", "ignore").decode("ascii")
        return valor.lower().strip()

    def obtener_criterio_relleno(nombre):
        default = {
            "Localidad": nombre if nombre else "Sin selección",
            "Lectura rápida": "Sin priorización cargada",
            "Estado visible": "Sin criterio semaforizado",
            "Comentario orientativo": "Esta alternativa todavía no tiene una lectura semaforizada cargada en el tablero.",
            "Semáforo": "gray",
            "Color": "#D9D9D9",
            "Folium": "gray",
            "Icono": "question",
        }

        if nombre is None:
            return default

        nombre_norm = normalizar_texto(nombre)

        for criterio in CRITERIOS_RELLENOS_TABLA:
            localidad = criterio["Localidad"]
            aliases = ALIASES_RELLENOS.get(localidad, [localidad])
            aliases_norm = [normalizar_texto(a) for a in aliases]
            if nombre_norm in aliases_norm or any(a in nombre_norm or nombre_norm in a for a in aliases_norm):
                return criterio

        return default

    def semaforo_streamlit_html(localidad, criterio):
        activo = criterio["Semáforo"]
        verde = "#92D050" if activo == "green" else "#D9D9D9"
        amarillo = "#FFF200" if activo == "yellow" else "#D9D9D9"
        rojo = "#FF3131" if activo == "red" else "#D9D9D9"
        color = criterio["Color"]

        return f'''
        <div class="semaforo-card" style="border-left: 9px solid {color};">
            <div class="semaforo-title">🚦 Semáforo del sitio</div>
            <div class="semaforo-localidad">{localidad}</div>
            <div class="semaforo-chip" style="background:{color};">{criterio['Estado visible']}</div>

            <div class="semaforo-linea">
                <span class="semaforo-luz" style="background:{verde};"></span> Favorable
            </div>
            <div class="semaforo-linea">
                <span class="semaforo-luz" style="background:{amarillo};"></span> Condicional / sensible
            </div>
            <div class="semaforo-linea">
                <span class="semaforo-luz" style="background:{rojo};"></span> Desfavorable
            </div>

            <div class="semaforo-comment">
                <b>{criterio['Lectura rápida']}</b><br>
                {criterio['Comentario orientativo']}
            </div>
        </div>
        '''

    def semaforo_mapa_html(criterio):
        activo = criterio["Semáforo"]
        verde = "#92D050" if activo == "green" else "#D9D9D9"
        amarillo = "#FFF200" if activo == "yellow" else "#D9D9D9"
        rojo = "#FF3131" if activo == "red" else "#D9D9D9"
        color = criterio["Color"]

        return f'''
        <div style="
            background:white;
            border:2px solid {color};
            border-radius:14px;
            padding:10px 12px;
            width:260px;
            box-shadow:0 4px 14px rgba(0,0,0,0.30);
            font-family:Arial, sans-serif;
        ">
            <div style="font-weight:700; font-size:15px; margin-bottom:8px; color:#111827;">
                🚦 Semáforo del sitio
            </div>
            <div style="font-size:13px; margin-bottom:5px;">
                <span style="display:inline-block;width:15px;height:15px;border-radius:50%;background:{verde};border:1px solid #555;margin-right:6px;"></span>Favorable
            </div>
            <div style="font-size:13px; margin-bottom:5px;">
                <span style="display:inline-block;width:15px;height:15px;border-radius:50%;background:{amarillo};border:1px solid #555;margin-right:6px;"></span>Condicional / sensible
            </div>
            <div style="font-size:13px; margin-bottom:8px;">
                <span style="display:inline-block;width:15px;height:15px;border-radius:50%;background:{rojo};border:1px solid #555;margin-right:6px;"></span>Desfavorable
            </div>
            <div style="font-size:12px; line-height:1.35; color:#111827;">
                <b>{criterio['Estado visible']}</b><br>
                {criterio['Comentario orientativo']}
            </div>
        </div>
        '''

    criterio_sel = obtener_criterio_relleno(None)

    # =========================
    # SIDEBAR
    # =========================
    with st.sidebar:
        st.header("⚙️ Configuración")

        st.subheader("📍 Escenario operativo")
        escenarios = df_escenarios["ESCENARIO"].dropna().tolist()
        escenario_sel = st.selectbox("Seleccionar escenario:", escenarios)

        escenario_row = df_escenarios[df_escenarios["ESCENARIO"] == escenario_sel].iloc[0]

        es_actual = escenario_sel == "Actual 600"

        st.subheader("🗺️ Futuro Relleno Sanitario")
        if es_actual:
            relleno_sel = "Actual Relleno Sanitario"
            relleno_id = None
            st.info("En el escenario actual no se selecciona futuro relleno.")
        else:
            relleno_sel = st.selectbox(
                "Seleccionar ubicación:",
                df_rellenos["NOMBRE"].dropna().tolist()
            )
            relleno_id = df_rellenos[df_rellenos["NOMBRE"] == relleno_sel]["ID_RELLENO"].iloc[0]
            criterio_sel = obtener_criterio_relleno(relleno_sel)
            st.markdown(semaforo_streamlit_html(relleno_sel, criterio_sel), unsafe_allow_html=True)

        st.markdown("---")

        st.subheader("🚛 Equipo")
        capacidad_t = st.selectbox("Capacidad de la batea / camión (TN):", [30, 25, 20])

        st.markdown("---")

        st.subheader("💰 Parámetros de costo")
        precio_litro = st.number_input("Precio litro gasoil ($):", value=1100.0)
        cons_cargado = st.number_input("Consumo ida cargado (L/km):", value=0.52)
        cons_vacio = st.number_input("Consumo vuelta vacío (L/km):", value=0.30)

        st.markdown("---")

        st.subheader("🗺️ Visualización del mapa")
        estilo_mapa = st.radio("Estilo de vista:", ["Claro (Calles)", "Satelital (Híbrido)"])

        if estilo_mapa == "Claro (Calles)":
            tile_provider = "OpenStreetMap"
            attr = "OpenStreetMap"
        else:
            tile_provider = "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}"
            attr = "Google Maps"

        mostrar_rutas = st.checkbox("Mostrar líneas de flujo", value=True)
        mostrar_radios = st.checkbox("Mostrar radios desde Actual RS", value=False)

    # =========================
    # DATOS DEL ESCENARIO
    # =========================
    generacion_total = float(escenario_row["GENERACION_TOTAL"])
    ton_relleno = float(escenario_row["TON_A_RELLENO"])
    ton_et = float(escenario_row["TON_A_ET"])
    ton_planta = float(escenario_row["TON_A_PLANTA"])

    if generacion_total == 600:
        col_ton = "TON_ACTUAL_DIA"
    else:
        col_ton = "TON_PROYECTADA_800"

    df_origenes = df_residuos[["ORIGEN", col_ton]].copy()
    df_origenes.columns = ["ORIGEN", "TON_DIA"]
    df_origenes = df_origenes.dropna(subset=["ORIGEN"])
    df_origenes["TON_DIA"] = pd.to_numeric(df_origenes["TON_DIA"], errors="coerce").fillna(0)

    # =========================
    # FUNCIONES AUXILIARES
    # =========================
    def km_lookup(tipo_flujo, origen=None, destino=None, origen_id=None, destino_id=None):
        temp = df_dist[df_dist["TIPO_FLUJO"] == tipo_flujo].copy()

        if origen is not None:
            temp = temp[temp["ORIGEN"] == origen]

        if destino is not None:
            temp = temp[temp["DESTINO"] == destino]

        if origen_id is not None:
            temp = temp[temp["ORIGEN_ID"] == origen_id]

        if destino_id is not None:
            temp = temp[temp["DESTINO_ID"] == destino_id]

        if temp.empty:
            return 0.0

        return float(temp["KM_USADO"].iloc[0])

    def weighted_km_direct_to_relleno():
        if es_actual:
            # Para el escenario actual usamos el Actual RS como destino operativo.
            # Se aproxima con la distancia Origen → ET1.
            total = 0
            for _, r in df_origenes.iterrows():
                km = km_lookup("Origen → ET", origen=r["ORIGEN"], destino_id="ET1")
                total += r["TON_DIA"] * km
            return total / max(df_origenes["TON_DIA"].sum(), 1)

        total = 0
        for _, r in df_origenes.iterrows():
            km = km_lookup("Origen → Futuro RS", origen=r["ORIGEN"], destino_id=relleno_id)
            total += r["TON_DIA"] * km
        return total / max(df_origenes["TON_DIA"].sum(), 1)

    def km_promedio_origen_a_et():
        distrib_esc = df_distrib[df_distrib["ESCENARIO"] == escenario_sel]
        distrib_esc = distrib_esc[distrib_esc["DESTINO_ID"].astype(str).str.startswith("ET")]

        if distrib_esc.empty:
            return 0

        total_ton_km = 0
        total_ton = 0

        for _, dest in distrib_esc.iterrows():
            destino_id = dest["DESTINO_ID"]
            ton_destino = float(dest["TON_DIA"])

            for _, origen in df_origenes.iterrows():
                proporcion = origen["TON_DIA"] / max(df_origenes["TON_DIA"].sum(), 1)
                ton_asignada = ton_destino * proporcion
                km = km_lookup("Origen → ET", origen=origen["ORIGEN"], destino_id=destino_id)
                total_ton_km += ton_asignada * km
                total_ton += ton_asignada

        return total_ton_km / max(total_ton, 1)

    def km_promedio_et_a_relleno():
        if es_actual or relleno_id is None:
            return 0

        distrib_esc = df_distrib[df_distrib["ESCENARIO"] == escenario_sel]
        distrib_esc = distrib_esc[distrib_esc["DESTINO_ID"].astype(str).str.startswith("ET")]

        if distrib_esc.empty:
            return 0

        total_ton_km = 0
        total_ton = 0

        for _, dest in distrib_esc.iterrows():
            origen_id = dest["DESTINO_ID"]
            ton_destino = float(dest["TON_DIA"])
            km = km_lookup("ET → Futuro RS", origen_id=origen_id, destino_id=relleno_id)
            total_ton_km += ton_destino * km
            total_ton += ton_destino

        return total_ton_km / max(total_ton, 1)

    # =========================
    # CÁLCULOS LOGÍSTICOS
    # =========================
    km_directo = weighted_km_direct_to_relleno()
    km_origen_et = km_promedio_origen_a_et()
    km_et_relleno = km_promedio_et_a_relleno()

    km_promedio_ponderado = 0

    if es_actual:
        km_promedio_ponderado = km_directo
    elif escenario_sel == "Futuro 800 - Alternativa 1":
        km_promedio_ponderado = km_directo
    elif escenario_sel == "Futuro 800 - Alternativa 2":
        km_promedio_ponderado = (
            (ton_relleno * km_directo) +
            (ton_et * (km_origen_et + km_et_relleno))
        ) / generacion_total
    elif escenario_sel == "Futuro 800 - Alternativa 3":
        # Se considera ET + Planta como procesamiento intermedio.
        # Para planta se usa Actual RS / PE1.
        km_planta = 0
        for _, origen in df_origenes.iterrows():
            km = km_lookup("Origen → Planta Energía", origen=origen["ORIGEN"], destino_id="PE1")
            km_planta += origen["TON_DIA"] * km
        km_planta = km_planta / max(df_origenes["TON_DIA"].sum(), 1)

        km_promedio_ponderado = (
            (ton_relleno * km_directo) +
            (ton_et * (km_origen_et + km_et_relleno)) +
            (ton_planta * km_planta)
        ) / generacion_total

    # Indicadores de batea: la batea/camión se calcula sobre las toneladas que van al relleno sanitario.
    # No se computa sobre el total del sistema cuando una parte va a ET o planta de energía.
    toneladas_batea = ton_relleno
    km_batea_ida = km_directo

    distancia_viaje_redondo = km_batea_ida * 2
    viajes_dia = math.ceil(toneladas_batea / capacidad_t) if toneladas_batea > 0 else 0

    litros_por_viaje = km_batea_ida * cons_cargado + km_batea_ida * cons_vacio
    costo_por_viaje = litros_por_viaje * precio_litro

    km_totales_dia = distancia_viaje_redondo * viajes_dia
    costo_total_dia = costo_por_viaje * viajes_dia

    porcentaje_relleno = ton_relleno / generacion_total if generacion_total else 0
    porcentaje_et = ton_et / generacion_total if generacion_total else 0
    porcentaje_planta = ton_planta / generacion_total if generacion_total else 0
    porcentaje_valorizacion = porcentaje_planta

    # =========================
    # DISTRIBUCIÓN DE TONELADAS POR DESTINO
    # La distribución se arma por componente según la alternativa seleccionada:
    # Alt. 1: 800 t/día a relleno.
    # Alt. 2: 500 t/día a relleno + 4 ET por 300 t/día.
    # Alt. 3: 400 t/día a relleno + 4 ET por 300 t/día + planta de energía por 100 t/día.
    # =========================
    def construir_distribucion_destinos():
        filas = []

        if es_actual:
            filas.append({
                "Destino": "Actual Relleno Sanitario",
                "Tipo": "Relleno sanitario",
                "Toneladas": ton_relleno,
            })
        else:
            filas.append({
                "Destino": relleno_sel,
                "Tipo": "Futuro relleno sanitario",
                "Toneladas": ton_relleno,
            })

            distrib_esc = df_distrib[df_distrib["ESCENARIO"] == escenario_sel].copy()
            if not distrib_esc.empty:
                for _, r in distrib_esc.iterrows():
                    filas.append({
                        "Destino": r["DESTINO"],
                        "Tipo": r["TIPO"],
                        "Toneladas": float(r["TON_DIA"]),
                    })

        df = pd.DataFrame(filas)
        df["Participación"] = df["Toneladas"] / max(generacion_total, 1)
        return df

    df_distribucion_destinos = construir_distribucion_destinos()

    # =========================
    # MAPA
    # =========================
    m = folium.Map(location=[-31.62, -60.75], zoom_start=10, tiles=tile_provider, attr=attr)

    def agregar_etiqueta_mapa(lat, lon, texto):
        folium.Marker(
            [lat, lon],
            icon=folium.DivIcon(
                html=f"""
                <div style="
                    font-size: 12px;
                    font-weight: 700;
                    color: #1f2937;
                    background: rgba(255, 255, 255, 0.90);
                    border: 1px solid rgba(31, 41, 55, 0.25);
                    border-radius: 6px;
                    padding: 3px 6px;
                    white-space: nowrap;
                    box-shadow: 0 1px 4px rgba(0,0,0,0.25);
                    transform: translate(18px, -12px);
                ">{texto}</div>
                """
            ),
        ).add_to(m)

    if mostrar_radios:
        centro = df_infra[df_infra["ID"] == "ET1"].iloc[0]
        for radio, color in [(20000, "blue"), (35000, "orange"), (50000, "red")]:
            folium.Circle(
                [centro["LATITUD"], centro["LONGITUD"]],
                radius=radio,
                color=color,
                fill=True,
                fill_opacity=0.06
            ).add_to(m)

    # Marcadores de infraestructura fija: solo ET y planta.
    # Los futuros rellenos sanitarios se dibujan aparte únicamente si están seleccionados.
    df_infra_mapa = df_infra[~df_infra["ID"].astype(str).str.startswith("FRS")].copy()
    for _, r in df_infra_mapa.iterrows():
        if pd.isna(r["LATITUD"]) or pd.isna(r["LONGITUD"]):
            continue

        if str(r["TIPO"]).lower() == "planta":
            color = "green"
            icon = "bolt"
        elif str(r["TIPO"]).lower() == "et":
            color = "blue"
            icon = "truck"
        else:
            color = "red"
            icon = "flag"

        folium.Marker(
            [r["LATITUD"], r["LONGITUD"]],
            tooltip=f"{r['ID']} - {r['NOMBRE']}",
            popup=f"{r['NOMBRE']}<br>Tipo: {r['TIPO']}<br>Capacidad: {r['CAPACIDAD_TN_DIA']} t/día",
            icon=folium.Icon(color=color, icon=icon, prefix="fa")
        ).add_to(m)
        agregar_etiqueta_mapa(r["LATITUD"], r["LONGITUD"], r["NOMBRE"])

    # Marcador del futuro relleno seleccionado + semáforo
    if not es_actual:
        rr = df_rellenos[df_rellenos["ID_RELLENO"] == relleno_id].iloc[0]
        criterio_sel = obtener_criterio_relleno(rr["NOMBRE"])

        popup_relleno = (
            f"<b>Futuro Relleno Sanitario</b><br>"
            f"<b>{rr['NOMBRE']}</b><br><br>"
            f"<b>Lectura rápida:</b> {criterio_sel['Lectura rápida']}<br>"
            f"<b>Estado:</b> {criterio_sel['Estado visible']}<br>"
            f"<b>Comentario:</b> {criterio_sel['Comentario orientativo']}"
        )

        folium.CircleMarker(
            [rr["LATITUD"], rr["LONGITUD"]],
            radius=18,
            color=criterio_sel["Color"],
            fill=True,
            fill_color=criterio_sel["Color"],
            fill_opacity=0.75,
            weight=4,
            tooltip=f"{rr['NOMBRE']} - {criterio_sel['Estado visible']}",
            popup=popup_relleno,
        ).add_to(m)

        folium.Marker(
            [rr["LATITUD"], rr["LONGITUD"]],
            tooltip=f"Futuro RS - {rr['NOMBRE']}",
            popup=popup_relleno,
            icon=folium.Icon(color=criterio_sel["Folium"], icon=criterio_sel["Icono"], prefix="fa")
        ).add_to(m)
        agregar_etiqueta_mapa(rr["LATITUD"], rr["LONGITUD"], rr["NOMBRE"])

        folium.Marker(
            [rr["LATITUD"] + 0.025, rr["LONGITUD"] + 0.025],
            icon=folium.DivIcon(html=semaforo_mapa_html(criterio_sel))
        ).add_to(m)

    # Flujos visuales
    if mostrar_rutas:
        origenes_coords = df_dist[df_dist["TIPO_FLUJO"] == "Origen → Futuro RS"][
            ["ORIGEN", "ORIGEN_LAT", "ORIGEN_LON"]
        ].drop_duplicates()

        # Actual y Alt 1: Orígenes al destino principal
        if es_actual:
            destino = df_infra[df_infra["ID"] == "ET1"].iloc[0]
            for _, o in origenes_coords.iterrows():
                AntPath(
                    locations=[[o["ORIGEN_LAT"], o["ORIGEN_LON"]], [destino["LATITUD"], destino["LONGITUD"]]],
                    delay=1000,
                    color="blue",
                    weight=4
                ).add_to(m)

        elif escenario_sel == "Futuro 800 - Alternativa 1":
            rr = df_rellenos[df_rellenos["ID_RELLENO"] == relleno_id].iloc[0]
            for _, o in origenes_coords.iterrows():
                AntPath(
                    locations=[[o["ORIGEN_LAT"], o["ORIGEN_LON"]], [rr["LATITUD"], rr["LONGITUD"]]],
                    delay=1000,
                    color="red",
                    weight=4
                ).add_to(m)

        else:
            # Alternativas 2 y 3: Origenes a ET, ET a futuro relleno
            distrib_esc = df_distrib[df_distrib["ESCENARIO"] == escenario_sel]
            et_ids = distrib_esc[distrib_esc["DESTINO_ID"].astype(str).str.startswith("ET")]["DESTINO_ID"].tolist()

            for et_id in et_ids:
                et = df_infra[df_infra["ID"] == et_id].iloc[0]

                for _, o in origenes_coords.iterrows():
                    AntPath(
                        locations=[[o["ORIGEN_LAT"], o["ORIGEN_LON"]], [et["LATITUD"], et["LONGITUD"]]],
                        delay=1000,
                        color="blue",
                        weight=3
                    ).add_to(m)

                rr = df_rellenos[df_rellenos["ID_RELLENO"] == relleno_id].iloc[0]
                AntPath(
                    locations=[[et["LATITUD"], et["LONGITUD"]], [rr["LATITUD"], rr["LONGITUD"]]],
                    delay=1000,
                    color="red",
                    weight=5
                ).add_to(m)

            if escenario_sel == "Futuro 800 - Alternativa 3":
                planta = df_infra[df_infra["ID"] == "PE1"].iloc[0]
                for _, o in origenes_coords.iterrows():
                    AntPath(
                        locations=[[o["ORIGEN_LAT"], o["ORIGEN_LON"]], [planta["LATITUD"], planta["LONGITUD"]]],
                        delay=1000,
                        color="green",
                        weight=4
                    ).add_to(m)


    # =========================
    # CAPAS GIS SANTA FE (WMS)
    # =========================
    # Las capas quedan disponibles desde el control de capas del mapa.
    wms_url = "https://aswe.santafe.gov.ar/idesf/wms"

    capas_wms = [
        {
            "layers": "areas_de_riesgo_hidrico",
            "name": "🌊 Riesgo hídrico",
        },
        {
            "layers": "ma_otbn_2021",
            "name": "🌳 Bosques nativos",
        },
        {
            "layers": "ind_produccion",
            "name": "🌾 Productividad del suelo",
        },
    ]

    for capa in capas_wms:
        folium.raster_layers.WmsTileLayer(
            url=wms_url,
            layers=capa["layers"],
            name=capa["name"],
            fmt="image/png",
            transparent=True,
            overlay=True,
            control=True,
            show=False,
        ).add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)

    mapa_col, semaforo_col = st.columns([2.2, 1])

    with mapa_col:
        st_folium(m, width="100%", height=520, key="mapa_modelo_nuevo")

    with semaforo_col:
        if es_actual:
            st.info("El escenario actual utiliza el relleno sanitario existente. El semáforo aplica a las alternativas futuras.")
        else:
            st.markdown(semaforo_streamlit_html(relleno_sel, criterio_sel), unsafe_allow_html=True)
            st.caption("El color del marcador del mapa cambia según la alternativa seleccionada.")

    st.markdown("---")

    # =========================
    # INDICADORES PRINCIPALES
    # =========================
    st.subheader("📊 Resumen del escenario seleccionado")

    k1, k2, k3, k4, k5 = st.columns(5)

    k1.metric("Generación total", f"{generacion_total:.0f} t/día")
    k2.metric("A Futuro RS", f"{ton_relleno:.0f} t/día", f"{porcentaje_relleno:.1%}")
    k3.metric("A ET", f"{ton_et:.0f} t/día", f"{porcentaje_et:.1%}")
    k4.metric("A Planta Energía", f"{ton_planta:.0f} t/día", f"{porcentaje_planta:.1%}")
    k5.metric("Valorización energética", f"{porcentaje_valorizacion:.1%}")

    st.markdown("---")


    # =========================
    # DATOS TGI Y PROYECCIÓN
    # Proyección por crecimiento promedio anual compuesto (CAGR) 2020-2025.
    # =========================
    def proyectar_cagr(valor_inicial, valor_final, anios):
        if valor_inicial <= 0 or anios <= 0:
            return 0
        return (valor_final / valor_inicial) ** (1 / anios) - 1

    def fmt_pesos(x):
        return "$ " + f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    tgi_base = pd.DataFrame([
        {"Año": 2020, "Percibido TGI": 1039171542.65, "FOP (30%)": 311751462.80, "TGI (deducido FOP)": 727420079.86, "Recolección y disposición final de residuos": 1584848313.08},
        {"Año": 2021, "Percibido TGI": 1485362780.00, "FOP (30%)": 445608834.00, "TGI (deducido FOP)": 1039753946.00, "Recolección y disposición final de residuos": 2545061356.34},
        {"Año": 2022, "Percibido TGI": 2311592684.49, "FOP (30%)": 693477805.35, "TGI (deducido FOP)": 1618114879.14, "Recolección y disposición final de residuos": 4057914453.20},
        {"Año": 2023, "Percibido TGI": 3838835786.95, "FOP (30%)": 1151650736.09, "TGI (deducido FOP)": 2687185050.87, "Recolección y disposición final de residuos": 9711360572.69},
        {"Año": 2024, "Percibido TGI": 8975181839.67, "FOP (30%)": 2692554551.90, "TGI (deducido FOP)": 6282627287.77, "Recolección y disposición final de residuos": 31540370222.72},
        {"Año": 2025, "Percibido TGI": 19846713091.00, "FOP (30%)": 5954013927.30, "TGI (deducido FOP)": 13892699163.70, "Recolección y disposición final de residuos": 43993074541.00},
    ])

    cagr_tgi = proyectar_cagr(tgi_base.loc[tgi_base["Año"] == 2020, "Percibido TGI"].iloc[0], tgi_base.loc[tgi_base["Año"] == 2025, "Percibido TGI"].iloc[0], 5)
    cagr_costo = proyectar_cagr(tgi_base.loc[tgi_base["Año"] == 2020, "Recolección y disposición final de residuos"].iloc[0], tgi_base.loc[tgi_base["Año"] == 2025, "Recolección y disposición final de residuos"].iloc[0], 5)

    proyecciones = []
    base_2025 = tgi_base[tgi_base["Año"] == 2025].iloc[0]
    for anio_objetivo in [2026, 2030, 2040]:
        n = anio_objetivo - 2025
        percibido = float(base_2025["Percibido TGI"]) * ((1 + cagr_tgi) ** n)
        costo = float(base_2025["Recolección y disposición final de residuos"]) * ((1 + cagr_costo) ** n)
        proyecciones.append({
            "Año": anio_objetivo,
            "Percibido TGI": percibido,
            "FOP (30%)": percibido * 0.30,
            "TGI (deducido FOP)": percibido * 0.70,
            "Recolección y disposición final de residuos": costo,
        })

    tgi_proy = pd.DataFrame(proyecciones)
    tgi_total = pd.concat([tgi_base, tgi_proy], ignore_index=True)
    tgi_total["Incidencia"] = tgi_total["TGI (deducido FOP)"] / tgi_total["Recolección y disposición final de residuos"]
    tgi_total["Tipo"] = tgi_total["Año"].apply(lambda x: "Dato histórico" if x <= 2025 else "Proyección")

    # =========================
    # TABLAS Y GRÁFICOS
    # =========================
    t1, t_tgi, t2, t3, t4, t5, t6 = st.tabs([
        "📈 Distribución",
        "💵 TGI",
        "🏗️ Infraestructura",
        "🚛 Distancias",
        "📋 Proyección residuos",
        "⚙️ Parámetros",
        "🚦 Priorización RS"
    ])

    with t1:
        st.markdown("##### Distribución de toneladas por destino")

        fig = px.bar(
            df_distribucion_destinos,
            x="Destino",
            y="Toneladas",
            color="Tipo",
            text="Toneladas",
            title="Distribución de toneladas por destino según alternativa seleccionada"
        )
        fig.update_traces(texttemplate="%{text:.0f} t/día", textposition="outside")
        fig.update_layout(yaxis_title="Toneladas por día", xaxis_title="Destino")
        st.plotly_chart(fig, use_container_width=True)

        tabla_distribucion = df_distribucion_destinos.copy()
        tabla_distribucion["Toneladas"] = tabla_distribucion["Toneladas"].map(lambda x: f"{x:.0f} t/día")
        tabla_distribucion["Participación"] = tabla_distribucion["Participación"].map(lambda x: f"{x:.1%}")
        st.dataframe(tabla_distribucion, use_container_width=True, hide_index=True)


    with t_tgi:
        st.markdown("##### Recaudación TGI vs costo de recolección y disposición final de residuos")
        st.caption("Datos históricos 2020-2025 y proyección 2026, 2030 y 2040 mediante crecimiento promedio anual compuesto entre 2020 y 2025.")

        m1, m2 = st.columns(2)
        m1.metric("Crecimiento promedio anual TGI percibido", f"{cagr_tgi:.2%}")
        m2.metric("Crecimiento promedio anual costo de residuos", f"{cagr_costo:.2%}")

        tgi_graf = tgi_total[["Año", "TGI (deducido FOP)", "Recolección y disposición final de residuos", "Tipo"]].copy()
        tgi_graf = tgi_graf.melt(
            id_vars=["Año", "Tipo"],
            value_vars=["TGI (deducido FOP)", "Recolección y disposición final de residuos"],
            var_name="Concepto",
            value_name="Monto"
        )

        fig_tgi = px.bar(
            tgi_graf,
            x="Año",
            y="Monto",
            color="Concepto",
            barmode="group",
            text="Monto",
            title="Comparativa anual TGI deducido FOP vs costo de recolección y disposición final"
        )
        fig_tgi.update_traces(texttemplate="$ %{y:,.0f}", textposition="outside")
        fig_tgi.update_layout(yaxis_title="Monto ($)", xaxis_title="Año")
        st.plotly_chart(fig_tgi, use_container_width=True)

        tabla_tgi = tgi_total.copy()
        for col in ["Percibido TGI", "FOP (30%)", "TGI (deducido FOP)", "Recolección y disposición final de residuos"]:
            tabla_tgi[col] = tabla_tgi[col].map(fmt_pesos)
        tabla_tgi["Incidencia"] = tabla_tgi["Incidencia"].map(lambda x: f"{x:.2%}")
        st.dataframe(tabla_tgi, use_container_width=True, hide_index=True)

        st.info("La incidencia se calcula como TGI deducido FOP / costo de recolección y disposición final de residuos.")

    with t2:
        st.dataframe(df_infra, use_container_width=True)

        if escenario_sel in df_distrib["ESCENARIO"].unique():
            st.markdown("##### Utilización de infraestructura en el escenario")
            uso = df_distrib[df_distrib["ESCENARIO"] == escenario_sel].merge(
                df_infra[["ID", "NOMBRE", "CAPACIDAD_TN_DIA"]],
                left_on="DESTINO_ID",
                right_on="ID",
                how="left"
            )
            uso["UTILIZACION_%"] = uso["TON_DIA"] / uso["CAPACIDAD_TN_DIA"]
            st.dataframe(uso, use_container_width=True)

    with t3:
        st.caption("KM_RUTA_REAL, si está completo, reemplaza a KM_OPERATIVO.")
        st.dataframe(df_dist, use_container_width=True)

    with t4:
        st.dataframe(df_residuos, use_container_width=True)

    with t5:
        st.dataframe(df_param, use_container_width=True)

    with t6:
        st.markdown("### Síntesis de priorización semaforizada")
        st.caption("Criterio orientativo incorporado al mapa. Las alternativas en amarillo requieren medidas, verificaciones o restricciones antes de considerarse favorables.")
        df_priorizacion = pd.DataFrame(CRITERIOS_RELLENOS_TABLA)[[
            "Localidad",
            "Lectura rápida",
            "Estado visible",
            "Comentario orientativo",
        ]]
        st.dataframe(df_priorizacion, use_container_width=True, hide_index=True)

    st.markdown("---")

    # =========================
    # INDICADORES LOGÍSTICOS
    # =========================
    st.subheader("🚛 Indicadores logísticos estimados")

    g1, g2, g3, g4 = st.columns(4)

    g1.metric("Km ida batea a RS", f"{km_batea_ida:.1f} km")
    g2.metric("Viaje redondo promedio", f"{distancia_viaje_redondo:.1f} km")
    g3.metric("Viajes diarios a RS", f"{viajes_dia}")
    g4.metric("Km totales diarios", f"{km_totales_dia:,.0f} km")

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("##### 💰 Costos")
        cc1, cc2 = st.columns(2)
        cc1.metric("Costo promedio por viaje", f"$ {costo_por_viaje:,.0f}")
        cc2.metric("Costo diario estimado", f"$ {costo_total_dia:,.0f}")

    with c2:
        st.markdown("##### 📌 Destino seleccionado")
        if es_actual:
            st.info("Escenario actual: operación sobre Actual Relleno Sanitario.")
        else:
            st.success(f"Futuro Relleno Sanitario seleccionado: **{relleno_sel}**")
            st.markdown(semaforo_streamlit_html(relleno_sel, criterio_sel), unsafe_allow_html=True)

    st.markdown("---")


except Exception as e:
    st.error(f"Hubo un inconveniente con los datos: {e}")
