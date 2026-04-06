import sqlite3
import pandas as pd
import streamlit as st
import io

# =========================
# 🔌 CONEXION SQLITE
# =========================
conn = sqlite3.connect("inventario.db")

# =========================
# 🔐 LOGIN
# =========================
USUARIOS = {"admin": "1234", "rey": "admin"}

if "login" not in st.session_state:
    st.session_state.login = False

if not st.session_state.login:
    st.title("🔐 Login")

    user = st.text_input("Usuario")
    pwd = st.text_input("Contraseña", type="password")

    if st.button("Ingresar"):
        if user in USUARIOS and USUARIOS[user] == pwd:
            st.session_state.login = True
            st.rerun()
        else:
            st.error("Credenciales incorrectas")

    st.stop()

# =========================
# 📊 APP
# =========================
st.title("📊 Sistema de Inventario")

# =========================
# 🔄 CARGA DESDE SQLITE
# =========================
try:
    activos = pd.read_sql("SELECT * FROM inventario", conn)
    st.success("📂 Datos cargados desde base")
except:
    activos = None

# =========================
# 📥 SI NO HAY DATA → SUBIR
# =========================
if activos is None or activos.empty:

    archivo = st.file_uploader("Sube tu archivo Excel", type=["xlsx"])

    if archivo:
        df = pd.read_excel(archivo, header=None)

        # 🔍 Detectar encabezado
        for i, row in df.iterrows():
            if row.astype(str).str.contains("DNI").any():
                df.columns = df.iloc[i]
                df = df[i+1:]
                break

        df.columns = df.columns.map(lambda x: str(x).strip().upper())
        df = df.loc[:, ~df.columns.duplicated()]

        # 🔍 Detectar columnas dinámicas
        col_dni = [c for c in df.columns if "DNI" in str(c)][0]
        col_activo = [c for c in df.columns if "ACTIVO" in str(c)][0]
        col_estado = [c for c in df.columns if "ESTADO" in str(c)][0]
        col_equipo = [c for c in df.columns if "EQUIPO" in str(c)][0]
        col_planilla = [c for c in df.columns if "PLANILLA" in str(c)][0]
        col_fecha = [c for c in df.columns if "FECHA" in str(c)][0]

        # opcionales
        col_cargo = next((c for c in df.columns if "CARGO" in str(c)), None)
        col_anexo = next((c for c in df.columns if "CODIGO" in str(c)), None)

        # 🔥 FILTROS
        df = df[df[col_planilla].astype(str).str.contains("PLANILLA", case=False)]
        df = df[df[col_equipo].astype(str).str.contains("PC|LAPTOP", case=False)]
        df = df.dropna(subset=[col_dni, col_activo, col_estado])

        df[col_fecha] = pd.to_datetime(df[col_fecha], errors="coerce")
        df = df.sort_values(by=col_fecha)

        # 🔥 MANTENER TODAS LAS COLUMNAS
        ultimo = df.drop_duplicates(subset=[col_activo], keep="last")

        activos = ultimo[
            ~ultimo[col_estado].astype(str).str.contains("DEVOLUCION", case=False)
        ]

        # 🔥 GUARDAR EN SQLITE
        activos.to_sql("inventario", conn, if_exists="replace", index=False)

        st.success("✅ Datos guardados correctamente")
        st.rerun()

    st.stop()

# =========================
# 🔎 BUSQUEDA MULTIPLE
# =========================
st.subheader("🔎 Búsqueda inteligente")

busqueda = st.text_input("Buscar (DNI, nombre, activo, etc. separado por comas)")

if busqueda:
    valores = [v.strip() for v in busqueda.split(",") if v.strip()]
    filtro_total = pd.Series(False, index=activos.index)

    for valor in valores:
        filtro = activos.astype(str).apply(
            lambda row: row.str.contains(valor, case=False).any(),
            axis=1
        )
        filtro_total = filtro_total | filtro

    resultado = activos[filtro_total].drop_duplicates()

    st.write(f"🔍 Resultados: {len(resultado)}")
    st.dataframe(resultado)

# =========================
# 📊 DASHBOARD
# =========================

# 🔹 POR AREA
if "CARGO" in activos.columns:
    st.subheader("📊 Equipos por Área")

    pivot = activos.groupby("CARGO")["ACTIVO"].count().reset_index()
    pivot.columns = ["AREA", "CANTIDAD"]

    st.dataframe(pivot)

# 🔹 TIPO USUARIO
col_anexo = next((c for c in activos.columns if "CODIGO" in str(c)), None)

if col_anexo:
    activos["TIPO_USUARIO"] = activos[col_anexo].astype(str).apply(
        lambda x: "AGENTE" if str(x).startswith("S00100") else "ADMINISTRATIVO"
    )

    st.subheader("📊 Equipos por tipo de usuario")

    resumen = activos.groupby("TIPO_USUARIO")["ACTIVO"].count().reset_index()
    resumen.columns = ["TIPO", "CANTIDAD"]

    st.dataframe(resumen)
    st.bar_chart(resumen.set_index("TIPO"))

# =========================
# 📥 DESCARGA
# =========================
buffer = io.BytesIO()
activos.to_excel(buffer, index=False)

st.download_button(
    "📥 Descargar Inventario",
    data=buffer.getvalue(),
    file_name="inventario.xlsx"
)