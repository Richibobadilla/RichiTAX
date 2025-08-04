# RichiTAX (versión sin cv2 ni pyzbar, compatible con Streamlit Cloud)
import streamlit as st
import fitz  # PyMuPDF
import pandas as pd
import chromedriver_autoinstaller
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import unicodedata
import re

# --- CONTROL DE ACCESO ---
def check_password():
    def password_entered():
        if (
            st.session_state["username"] in st.secrets["passwords"] and
            st.session_state["password"] == st.secrets["passwords"][st.session_state["username"]]
        ):
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Usuario", on_change=password_entered, key="username")
        st.text_input("Contraseña", type="password", on_change=password_entered, key="password")
        st.stop()
    elif not st.session_state["password_correct"]:
        st.text_input("Usuario", on_change=password_entered, key="username")
        st.text_input("Contraseña", type="password", on_change=password_entered, key="password")
        st.error("Usuario o contraseña incorrectos")
        st.stop()

check_password()

# --- CONFIGURACION INICIAL ---
st.set_page_config(page_title="RichiTAX", page_icon="📄", layout="wide")
st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(to right, #fff0e5, #eafafc);
    }
    .main .block-container {
        background-color: white;
        padding: 2rem;
        border-radius: 20px;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.15);
    }
    .stDownloadButton>button {
        background: linear-gradient(to right, #6c63ff, #5145cd);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 10px 20px;
        font-weight: bold;
        transition: 0.3s;
    }
    .stDownloadButton>button:hover {
        background: linear-gradient(to right, #5145cd, #6c63ff);
        transform: scale(1.03);
        cursor: pointer;
    }
    </style>
""", unsafe_allow_html=True)

# --- FUNCIONES ---
def es_match(label, target):
    try:
        l1 = unicodedata.normalize('NFKD', label).encode('ASCII', 'ignore').decode().upper().strip()
        l2 = unicodedata.normalize('NFKD', target).encode('ASCII', 'ignore').decode().upper().strip()
        return l2 in l1
    except:
        return False

def procesar_pdf(pdf_file):
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    for page in doc:
        text = page.get_text()
        match = re.search(r'https://verificacfdi\.facturaelectronica\.sat\.gob\.mx.*?re=[^&\s]+&fe=[^&\s]+', text)
        if match:
            return match.group(0)
    return None

def extraer_datos_desde_pagina(url):
    chromedriver_autoinstaller.install()
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--window-size=1200x1400")
    driver = webdriver.Chrome(options=options)
    driver.get(url)
    wait = WebDriverWait(driver, 10)

    nombre_razon = rfc_detectado = "No detectado"
    datos_extra = {
        "Entidad Federativa": "No detectado",
        "Municipio": "No detectado",
        "Colonia": "No detectado",
        "Nombre de la vialidad": "No detectado",
        "Número exterior": "No detectado",
        "Número interior": "No detectado",
        "CP": "No detectado",
        "Régimen Fiscal": "No detectado",
        "Fecha de alta": "No detectado"
    }

    try:
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "li")))
        texto = driver.find_element(By.CSS_SELECTOR, "li.ui-li-static.ui-body-c.ui-corner-top.ui-corner-bottom").text
        match = re.search(r"RFC[:\s]+([A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3})", texto.upper())
        if match:
            rfc_detectado = match.group(1)

        filas = driver.find_elements(By.XPATH, "//table[@role='grid']//tr")
        nombre = paterno = materno = ""
        for fila in filas:
            celdas = fila.find_elements(By.TAG_NAME, "td")
            if len(celdas) >= 2:
                label = celdas[0].text.strip().upper()
                valor = celdas[1].text.strip()
                if es_match(label, "Denominación o Razón Social"):
                    nombre_razon = valor
                elif es_match(label, "Nombre:"):
                    nombre = valor
                elif es_match(label, "Apellido Paterno:"):
                    paterno = valor
                elif es_match(label, "Apellido Materno:"):
                    materno = valor
                elif "ENTIDAD FEDERATIVA" in label:
                    datos_extra["Entidad Federativa"] = valor
                elif "MUNICIPIO" in label:
                    datos_extra["Municipio"] = valor
                elif "COLONIA" in label:
                    datos_extra["Colonia"] = valor
                elif "NOMBRE DE LA VIALIDAD" in label:
                    datos_extra["Nombre de la vialidad"] = valor
                elif "NÚMERO EXTERIOR" in label:
                    datos_extra["Número exterior"] = valor
                elif "NÚMERO INTERIOR" in label:
                    datos_extra["Número interior"] = valor
                elif "CP" in label:
                    datos_extra["CP"] = valor
                elif "RÉGIMEN" in label:
                    datos_extra["Régimen Fiscal"] = valor
                elif "FECHA DE ALTA" in label:
                    datos_extra["Fecha de alta"] = valor

        if nombre and paterno:
            nombre_razon = f"{nombre} {paterno} {materno}"

    except Exception as e:
        print("Error:", e)

    driver.quit()
    return nombre_razon, rfc_detectado, datos_extra

# --- UI ---
st.title("📄 RichiTAX (con QR)")
st.markdown("Sube tus constancias fiscales en PDF y te daremos un Excel con los datos directamente del portal SAT.")

archivos = st.file_uploader("Selecciona archivos PDF", type="pdf", accept_multiple_files=True)

if archivos:
    resultados = []
    with st.spinner("🔍 Procesando archivos..."):
        for archivo in archivos:
            qr_data = procesar_pdf(archivo)
            if qr_data and qr_data.startswith("http"):
                nombre_razon, rfc_extraido, datos_extra = extraer_datos_desde_pagina(qr_data)
            else:
                nombre_razon = "QR no detectado"
                rfc_extraido = "No detectado"
                datos_extra = {campo: "No detectado" for campo in [
                    "Entidad Federativa", "Municipio", "Colonia", "Nombre de la vialidad", "Número exterior",
                    "Número interior", "CP", "Régimen Fiscal", "Fecha de alta"]}

            fila = {"Archivo": archivo.name, "Nombre/Razón Social": nombre_razon, "RFC": rfc_extraido}
            fila.update(datos_extra)
            resultados.append(fila)

    df_resultado = pd.DataFrame(resultados)
    st.success("✅ Procesamiento completo.")
    st.dataframe(df_resultado)

    nombre_archivo = "resultado_constancias.xlsx"
    df_resultado.to_excel(nombre_archivo, index=False)
    with open(nombre_archivo, "rb") as f:
        st.download_button("📅 Descargar Excel", f, file_name=nombre_archivo)

st.markdown("<div style='text-align:center; margin-top:40px; color:#aaa;'>Hecho con 🐼 por Ricarbo Bobadilla – 2025</div>", unsafe_allow_html=True)

#C:\py\LECTOR> python -m streamlit run lectorqr.py