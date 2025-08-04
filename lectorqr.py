
import streamlit as st 
import fitz  # PyMuPDF
import pandas as pd
import re
import chromedriver_autoinstaller
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="RichiTAX QR", layout="wide")

st.markdown("## 📄 RichiTAX QR Scanner (Streamlit Cloud Compatible)")
st.markdown("Sube tus constancias fiscales en PDF. Extraeremos el link del SAT y los datos directamente del portal.")

# --- FUNCIONES ---
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

    resultado = {"Nombre o Razón Social": "No detectado", "RFC": "No detectado"}
    campos = [
        "Entidad Federativa", "Municipio", "Colonia", "Nombre de la vialidad", 
        "Número exterior", "Número interior", "CP", "Régimen Fiscal", "Fecha de alta"
    ]
    for campo in campos:
        resultado[campo] = "No detectado"

    try:
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "li")))
        li_rfc = driver.find_element(By.CSS_SELECTOR, "li.ui-li-static.ui-body-c.ui-corner-top.ui-corner-bottom")
        texto = li_rfc.get_attribute("innerText").strip().upper()
        rfc_match = re.search(r"RFC[:\s]+([A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3})", texto)
        if rfc_match:
            resultado["RFC"] = rfc_match.group(1)

        tabla = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "ui-datatable-data")))
        filas = tabla.find_elements(By.TAG_NAME, "tr")

        nombre = paterno = materno = ""
        for fila in filas:
            celdas = fila.find_elements(By.TAG_NAME, "td")
            if len(celdas) >= 2:
                label = celdas[0].text.strip().upper()
                valor = celdas[1].text.strip().upper()
                if "DENOMINACIÓN" in label or "RAZÓN SOCIAL" in label:
                    resultado["Nombre o Razón Social"] = valor
                elif "NOMBRE" in label and not paterno:
                    nombre = valor
                elif "PATERNO" in label:
                    paterno = valor
                elif "MATERNO" in label:
                    materno = valor
        if nombre and paterno:
            resultado["Nombre o Razón Social"] = f"{nombre} {paterno} {materno}"

        tablas_info = driver.find_elements(By.XPATH, "//table[@role='grid']")
        for tabla in tablas_info:
            filas = tabla.find_elements(By.TAG_NAME, "tr")
            for fila in filas:
                celdas = fila.find_elements(By.TAG_NAME, "td")
                if len(celdas) >= 2:
                    label = celdas[0].text.strip().upper()
                    valor = celdas[1].text.strip()
                    for campo in campos:
                        if campo.upper() in label:
                            resultado[campo] = valor
    except Exception as e:
        print("Error:", e)
    driver.quit()
    return resultado

# --- APP ---
archivos = st.file_uploader("Selecciona archivos PDF", type="pdf", accept_multiple_files=True)

if archivos:
    resultados = []
    with st.spinner("Procesando archivos..."):
        for archivo in archivos:
            qr_data = procesar_pdf(archivo)
            if qr_data and qr_data.startswith("http"):
                datos = extraer_datos_desde_pagina(qr_data)
            else:
                datos = {
                    "Nombre o Razón Social": "No se encontró link en el PDF",
                    "RFC": "No detectado",
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
            datos["Archivo"] = archivo.name
            resultados.append(datos)

    df = pd.DataFrame(resultados)
    st.success("✅ ¡Listo!")
    st.dataframe(df)

    nombre_excel = "resultado_constancias.xlsx"
    df.to_excel(nombre_excel, index=False)
    with open(nombre_excel, "rb") as f:
        st.download_button("📥 Descargar Excel", f, file_name=nombre_excel)
