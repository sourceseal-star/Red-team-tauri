import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import requests
import json
from typing import List, Dict, Optional
import threading
import time

from kraken.config.settings import settings
from kraken.core.database import db

# ============================================================
# CONFIGURACIÓN
# ============================================================
st.set_page_config(
    page_title="KRAKEN v3.0 Dashboard",
    page_icon="🦈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos personalizados
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #fafafa; }
    .stTextInput, .stSelectbox, .stButton { background-color: #1e293b !important; }
    .stDataframe { background-color: #1e293b !important; }
    .metric-card { background-color: #1e293b; padding: 15px; border-radius: 10px; }
    .critical { color: #ef4444; }
    .high { color: #f97316; }
    .medium { color: #eab308; }
    .low { color: #22c55e; }
    </style>
""", unsafe_allow_html=True)

# ============================================================
# AUTENTICACIÓN
# ============================================================
def check_password():
    """Verifica la contraseña del dashboard."""
    def password_entered():
        if st.session_state["username"] == settings.API_USERNAME and st.session_state["password"] == settings.API_PASSWORD:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # No almacenar la contraseña
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        with st.form(key="login_form"):
            st.session_state["username"] = st.text_input("Usuario", key="username")
            st.session_state["password"] = st.text_input("Contraseña", type="password", key="password")
            st.form_submit_button("Iniciar sesión", on_click=password_entered)
            if "password_correct" in st.session_state and not st.session_state["password_correct"]:
                st.error("🚨 Credenciales inválidas")
            return False
    return True

if not check_password():
    st.stop()

# ============================================================
# FUNCIONES DE DATOS
# ============================================================
@st.cache_data(ttl=60)
def get_priorities() -> List[Dict]:
    """Obtiene las prioridades."""
    return db.get_priorities(limit=10)

@st.cache_data(ttl=30)
def get_exploits(limit: int = 50) -> List[Dict]:
    """Obtiene los exploits recientes."""
    return db.get_exploits(limit=limit)

@st.cache_data(ttl=30)
def get_vulnerabilities(limit: int = 50) -> List[Dict]:
    """Obtiene las vulnerabilidades recientes."""
    return db.get_vulnerabilities(limit=limit)

@st.cache_data(ttl=300)
def get_scan_stats(days: int = 7) -> Dict:
    """Obtiene estadísticas de escaneos."""
    return db.get_scan_stats(days)

@st.cache_data(ttl=300)
def get_hosts() -> List[Dict]:
    """Obtiene todos los hosts."""
    session = db.get_session()
    try:
        query = session.query(HostDB)
        query = query.filter(HostDB.is_active == True)
        query = query.order_by(HostDB.last_seen.desc())
        return [{
            "ip": h.ip,
            "hostname": h.hostname,
            "os": h.os,
            "cvss": h.cvss_score,
            "vulns": h.total_vulns,
            "last_seen": h.last_seen.isoformat() if h.last_seen else None
        } for h in query.all()]
    finally:
        session.close()

# ============================================================
# FUNCIONES DE ACTUALIZACIÓN EN TIEMPO REAL
# ============================================================
def update_data():
    """Actualiza los datos en segundo plano."""
    while True:
        time.sleep(10)
        if "priorities" in st.session_state:
            st.session_state.priorities = get_priorities()
        if "exploits" in st.session_state:
            st.session_state.exploits = get_exploits(limit=20)
        if "stats" in st.session_state:
            st.session_state.stats = get_scan_stats(days=7)

# Iniciar actualización en segundo plano
if "update_thread" not in st.session_state:
    st.session_state.update_thread = threading.Thread(target=update_data, daemon=True)
    st.session_state.update_thread.start()

# ============================================================
# PÁGINA PRINCIPAL
# ============================================================
st.title("🦈 KRAKEN v3.0 Dashboard")
st.markdown("---")

# Inicializar datos
if "priorities" not in st.session_state:
    st.session_state.priorities = get_priorities()
if "exploits" not in st.session_state:
    st.session_state.exploits = get_exploits(limit=20)
if "vulns" not in st.session_state:
    st.session_state.vulns = get_vulnerabilities(limit=20)
if "stats" not in st.session_state:
    st.session_state.stats = get_scan_stats(days=7)
if "hosts" not in st.session_state:
    st.session_state.hosts = get_hosts()

# ============================================================
# TARJETAS DE MÉTRICAS
# ============================================================
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="🖥️ Hosts Activos",
        value=st.session_state.stats.get("total_hosts", 0),
        delta=None
    )

with col2:
    critical_vulns = st.session_state.stats.get("vulnerabilities", {}).get("critical", 0)
    st.metric(
        label="🔴 Vulnerabilidades Críticas",
        value=critical_vulns,
        delta="↑" if critical_vulns > 0 else None
    )

with col3:
    high_vulns = st.session_state.stats.get("vulnerabilities", {}).get("high", 0)
    st.metric(
        label="🟠 Vulnerabilidades Altas",
        value=high_vulns,
        delta="↑" if high_vulns > 0 else None
    )

with col4:
    st.metric(
        label="💀 Exploits Exitosos",
        value=st.session_state.stats.get("total_exploits", 0),
        delta=None
    )

st.markdown("---")

# ============================================================
# GRAFICOS
# ============================================================
col1, col2 = st.columns(2)

with col1:
    st.subheader("📊 Vulnerabilidades por Severidad")
    vulns_by_severity = st.session_state.stats.get("vulnerabilities", {})
    df_severity = pd.DataFrame({
        "Severidad": list(vulns_by_severity.keys()),
        "Cantidad": list(vulns_by_severity.values())
    })
    if not df_severity.empty:
        fig = px.bar(
            df_severity,
            x="Severidad",
            y="Cantidad",
            color="Severidad",
            color_discrete_map={
                "critical": "#ef4444",
                "high": "#f97316",
                "medium": "#eab308",
                "low": "#22c55e"
            }
        )
        fig.update_layout(
            showlegend=False,
            xaxis_title="Severidad",
            yaxis_title="Cantidad",
            plot_bgcolor="#1e293b",
            paper_bgcolor="#0e1117",
            font_color="#fafafa"
        )
        st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("🎯 Top 10 Hosts Prioritarios")
    df_priorities = pd.DataFrame(st.session_state.priorities)
    if not df_priorities.empty:
        fig = px.bar(
            df_priorities,
            x="ip",
            y="cvss",
            color="cvss",
            color_continuous_scale="Reds",
            hover_data=["vulns"]
        )
        fig.update_layout(
            xaxis_title="IP",
            yaxis_title="CVSS Score",
            plot_bgcolor="#1e293b",
            paper_bgcolor="#0e1117",
            font_color="#fafafa"
        )
        st.plotly_chart(fig, use_container_width=True)

# ============================================================
# TABLAS
# ============================================================
tab1, tab2, tab3, tab4 = st.tabs(["🎯 Prioridades", "💀 Exploits", "🔍 Vulnerabilidades", "🖥️ Hosts"])

with tab1:
    st.subheader("Top Hosts por CVSS")
    df_priorities = pd.DataFrame(st.session_state.priorities)
    if not df_priorities.empty:
        st.dataframe(
            df_priorities.style.background_gradient(subset=["cvss"], cmap="Reds"),
            use_container_width=True,
            height=400
        )

with tab2:
    st.subheader("Últimos Exploits Exitosos")
    df_exploits = pd.DataFrame(st.session_state.exploits)
    if not df_exploits.empty:
        # Aplicar colores según CVSS
        def color_cvss(val):
            if val >= 9:
                return "background-color: #ef4444"
            elif val >= 7:
                return "background-color: #f97316"
            elif val >= 4:
                return "background-color: #eab308"
            else:
                return "background-color: #22c55e"

        st.dataframe(
            df_exploits.style.applymap(color_cvss, subset=["cvss"]),
            use_container_width=True,
            height=400
        )

with tab3:
    st.subheader("Últimas Vulnerabilidades Detectadas")
    df_vulns = pd.DataFrame(st.session_state.vulns)
    if not df_vulns.empty:
        st.dataframe(
            df_vulns.style.background_gradient(subset=["cvss"], cmap="Reds"),
            use_container_width=True,
            height=400
        )

with tab4:
    st.subheader("Todos los Hosts")
    df_hosts = pd.DataFrame(st.session_state.hosts)
    if not df_hosts.empty:
        st.dataframe(
            df_hosts,
            use_container_width=True,
            height=400
        )

# ============================================================
# ACCIONES
# ============================================================
st.markdown("---")
st.subheader("⚡ Acciones Rápidas")

col1, col2, col3 = st.columns(3)

with col1:
    with st.form(key="scan_form"):
        target = st.text_input("🎯 Nuevo Escaneo", placeholder="192.168.1.0/24")
        submit_scan = st.form_submit_button("Iniciar Escaneo")
        if submit_scan:
            try:
                # Enviar solicitud a la API para iniciar escaneo
                response = requests.post(
                    f"http://{settings.API_HOST}:{settings.API_PORT}/api/scan",
                    json={"target": target},
                    auth=(settings.API_USERNAME, settings.API_PASSWORD)
                )
                if response.status_code == 200:
                    st.success(f"✅ Escaneo iniciado para: {target}")
                else:
                    st.error(f"❌ Error: {response.json().get('detail', 'Desconocido')}")
            except Exception as e:
                st.error(f"❌ Error al conectar con la API: {e}")

with col2:
    with st.form(key="block_form"):
        ip_to_block = st.text_input("🚫 Bloquear IP", placeholder="192.168.1.100")
        submit_block = st.form_submit_button("Bloquear IP")
        if submit_block:
            try:
                response = requests.post(
                    f"http://{settings.API_HOST}:{settings.API_PORT}/api/block-ip",
                    json={"ip": ip_to_block},
                    auth=(settings.API_USERNAME, settings.API_PASSWORD)
                )
                if response.status_code == 200:
                    st.success(f"✅ IP bloqueada: {ip_to_block}")
                else:
                    st.error(f"❌ Error: {response.json().get('detail', 'Desconocido')}")
            except Exception as e:
                st.error(f"❌ Error al conectar con la API: {e}")

with col3:
    st.markdown("**📊 Exportar Datos**")
    if st.button("📄 Exportar a CSV"):
        df = pd.DataFrame(st.session_state.hosts)
        csv = df.to_csv(index=False)
        st.download_button(
            label="Descargar CSV",
            data=csv,
            file_name="kraken_hosts.csv",
            mime="text/csv"
        )

# ============================================================
# PIE DE PÁGINA
# ============================================================
st.markdown("---")
st.markdown("""
    <div style="text-align: center; color: #64748b;">
        <p>KRAKEN v3.0 - Motor de Explotación Autónomo | © 2024 Sealclient</p>
        <p>Última actualización: {}</p>
    </div>
""".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")), unsafe_allow_html=True)
