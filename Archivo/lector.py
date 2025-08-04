import os
import fitz
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import pandas as pd
import re
from datetime import datetime

# Configuración de Tesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
os.environ["TESSDATA_PREFIX"] = r"C:\Program Files\Tesseract-OCR\tessdata"

def tiene_texto(pdf_path):
    with fitz.open(pdf_path) as doc:
        for page in doc:
            if page.get_text().strip():
                return True
    return False

def leer_texto_directo(pdf_path):
    texto = ""
    with fitz.open(pdf_path) as doc:
        for page in doc:
            texto += page.get_text()
    return texto

def leer_texto_ocr(pdf_path):
    texto = ""
    paginas = convert_from_path(pdf_path, dpi=300)
    for imagen in paginas:
        texto += pytesseract.image_to_string(imagen, lang='spa')
    return texto

def leer_pdf(pdf_path):
    if tiene_texto(pdf_path):
        print(f"✅ Texto directo detectado en: {os.path.basename(pdf_path)}")
        return leer_texto_directo(pdf_path)
    else:
        print(f"🟡 Texto no detectable, usando OCR en: {os.path.basename(pdf_path)}")
        return leer_texto_ocr(pdf_path)

def extraer_datos(texto):
    def buscar_patron(label, limpiar_con=None, cortadores_extras=None):
        match = re.search(rf'{label}[:\s]*([\w\sÁÉÍÓÚÑñ.,\-\/&]+)', texto, re.IGNORECASE)
        if match:
            resultado = match.group(1).strip()
            # Limpieza por palabra conocida
            if limpiar_con and limpiar_con.lower() in resultado.lower():
                resultado = resultado.split(limpiar_con, 1)[0].strip()
            # Limpieza por cortadores extra si están pegados
            if cortadores_extras:
                for cortador in cortadores_extras:
                    if cortador.lower() in resultado.lower():
                        resultado = resultado.split(cortador, 1)[0].strip()
            return resultado
        return "No encontrado"

    rfc_match = re.search(r'\b([A-ZÑ&]{3,4}\d{6}[A-Z0-9]{2,3})\b', texto)
    rfc = rfc_match.group(1) if rfc_match else "No encontrado"

    razon = "No encontrada"

    match_directa = re.search(r'Denominación/Razón Social[:\s]*([\w\sÁÉÍÓÚÑñ.,\-\/&]+)', texto, re.IGNORECASE)
    if match_directa:
        razon = match_directa.group(1).strip()
        razon = re.sub(r'\bR[ÉE]GIMEN.*$', '', razon, flags=re.IGNORECASE).strip()
    else:
        lineas = texto.splitlines()
        prohibidas = [
            "CÉDULA DE IDENTIFICACIÓN FISCAL",
            "SERVICIO DE ADMINISTRACIÓN TRIBUTARIA",
            "REGISTRO FEDERAL DE CONTRIBUYENTES",
            "CONSTANCIA DE SITUACIÓN FISCAL"
        ]
        for i, linea in enumerate(lineas):
            l_clean = linea.lower().replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
            if "denominacion" in l_clean or "razon social" in l_clean:
                if ":" in linea:
                    razon_candidata = linea.split(":")[-1].strip()
                    if razon_candidata.isupper() and razon_candidata not in prohibidas and len(razon_candidata) > 3:
                        razon = razon_candidata
                        break
                elif i + 1 < len(lineas):
                    siguiente = lineas[i + 1].strip()
                    if siguiente.isupper() and siguiente not in prohibidas and len(siguiente) > 3:
                        razon = siguiente
                        break

        if razon == "No encontrada":
            nombre_match = re.search(r'Nombre \(s\):\s*([A-ZÑÁÉÍÓÚ ]+)', texto, re.IGNORECASE)
            apellido1_match = re.search(r'Primer Apellido:\s*([A-ZÑÁÉÍÓÚ ]+)', texto, re.IGNORECASE)
            apellido2_match = re.search(r'Segundo Apellido:\s*([A-ZÑÁÉÍÓÚ ]+)', texto, re.IGNORECASE)

            if nombre_match and apellido1_match and apellido2_match:
                nombre = nombre_match.group(1).strip()
                apellido1 = apellido1_match.group(1).strip()
                apellido2 = apellido2_match.group(1).strip()
                razon = f"{nombre} {apellido1} {apellido2}"

    # Campos con limpieza adicional
    cp = buscar_patron("Código Postal", limpiar_con="Tipo de Vialidad")
    vialidad = buscar_patron("Nombre de Vialidad", limpiar_con="Número Exterior")
    no_ext = buscar_patron("Número Exterior", limpiar_con="Número Interior")
    no_int = buscar_patron("Número Interior", limpiar_con="Nombre de la Colonia")
    colonia = buscar_patron(
        "Nombre de la Colonia",
        limpiar_con="Nombre de la Localidad",
        cortadores_extras=["Nombre de la Localidad", "Nombre del Municipio", "Nombre de la Entidad"]
    )
    localidad = buscar_patron(
        "Nombre de la Localidad",
        limpiar_con="Nombre del Municipio o Demarcación Territorial",
        cortadores_extras=["Nombre del Municipio", "Nombre de la Entidad", "Nombre del Municipio o Demarcación Territorial"]
    )
    municipio = buscar_patron(
        "Nombre del Municipio o Demarcación Territorial",
        limpiar_con="Nombre de la Entidad Federativa",
        cortadores_extras=["Nombre de la Entidad Federativa", "Entidad Federativa"]
    )
    estado = buscar_patron("Nombre de la Entidad Federativa", limpiar_con="Tipo de Vialidad")
    regimen = buscar_patron("Régimen")

    return {
        "RFC": rfc,
        "Razón Social": razon,
        "Código Postal": cp,
        "Vialidad": vialidad,
        "Número Exterior": no_ext,
        "Número Interior": no_int,
        "Colonia": colonia,
        "Localidad": localidad,
        "Municipio/Demarcación": municipio,
        "Estado": estado,
        "Régimen": regimen
    }

def main():
    carpeta = "docs"
    archivos = [f for f in os.listdir(carpeta) if f.lower().endswith(".pdf")]
    resultados = []

    for archivo in archivos:
        ruta = os.path.join(carpeta, archivo)
        texto = leer_pdf(ruta)
        datos = extraer_datos(texto)

        datos_ordenado = {"Archivo": archivo}
        datos_ordenado.update(datos)
        resultados.append(datos_ordenado)

    df = pd.DataFrame(resultados)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    nombre_archivo = f"Lector_{timestamp}.xlsx"

    df.to_excel(nombre_archivo, index=False)
    print(f"\n✅ Archivo '{nombre_archivo}' guardado con éxito.")

if __name__ == "__main__":
    main()
