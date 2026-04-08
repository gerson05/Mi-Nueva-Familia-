import streamlit as st
import pandas as pd
import os
import shutil
import unicodedata
import json
from datetime import datetime

import pythoncom
pythoncom.CoInitialize()

try:
    from docx2pdf import convert
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
from io import BytesIO
from gemini_extractor import extract_receipt_data
from doc_generator import generate_receipt

# Configuración de página
st.set_page_config(page_title="Generador de Recibos - Mi Nueva Familia", page_icon="📄", layout="centered")

MESES = {
    1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL", 5: "MAYO", 6: "JUNIO",
    7: "JULIO", 8: "AGOSTO", 9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE", 12: "DICIEMBRE"
}
MESES_ABREV = {
    1: "ENE", 2: "FEB", 3: "MAR", 4: "ABR", 5: "MAY", 6: "JUN",
    7: "JUL", 8: "AGO", 9: "SEP", 10: "OCT", 11: "NOV", 12: "DIC"
}

def normalize(text):
    if not text:
        return ""
    return "".join(c for c in unicodedata.normalize('NFD', str(text)) if unicodedata.category(c) != 'Mn').lower().strip()

CONFIG_FILE = "config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_config(config_data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config_data, f, ensure_ascii=False, indent=4)

def find_sponsor_folder(sponsor_name, base_path):
    """Busca la carpeta del patrocinador en Troncal e Inactivos."""
    if not base_path or not os.path.exists(base_path):
        return None

    search_name = normalize(sponsor_name)

    # 1. Buscar en la raíz de Troncal
    for item in os.listdir(base_path):
        item_path = os.path.join(base_path, item)
        if os.path.isdir(item_path) and search_name in normalize(item):
            return item_path

    # 2. Buscar en 1. INACTIVOS
    inactivos_path = os.path.join(base_path, "1. INACTIVOS")
    if os.path.exists(inactivos_path):
        for item in os.listdir(inactivos_path):
            item_path = os.path.join(inactivos_path, item)
            if os.path.isdir(item_path) and search_name in normalize(item):
                return item_path

    return None

def find_existing_sponsorship_year(sponsor_name, base_path):
    """Busca la subcarpeta PATROCINIO más reciente en CONSIGNACIONES y retorna el rango."""
    sponsor_folder = find_sponsor_folder(sponsor_name, base_path)
    if sponsor_folder:
        consig_path = os.path.join(sponsor_folder, "CONSIGNACIONES")
        if os.path.exists(consig_path):
            try:
                folders = [f for f in os.listdir(consig_path) if os.path.isdir(os.path.join(consig_path, f)) and f.upper().startswith("PATROCINIO")]
                if folders:
                    import re
                    
                    def sort_key(folder_name):
                        # Extraer años mencionados en la carpeta
                        years = [int(y) for y in re.findall(r'\b20\d{2}\b', folder_name)]
                        max_year = max(years) if years else 0
                        # También considerar fecha de modificación como desempate
                        try:
                            mtime = os.path.getmtime(os.path.join(consig_path, folder_name))
                        except Exception:
                            mtime = 0
                        return (max_year, mtime)

                    # Ordenar priorizando el año más alto y luego la más reciente modificación
                    folders.sort(key=sort_key, reverse=True)
                    
                    match = re.match(r"(?i)PATROCINIO\s*(.*)", folders[0])
                    if match:
                        return match.group(1).strip()
            except Exception:
                pass
    return None

def parse_date_from_excel(val):
    """Convierte cualquier formato de fecha del Excel a objeto datetime."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        val = val.strip()
        for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%y", "%d/%m/%y"):
            try:
                return datetime.strptime(val, fmt)
            except ValueError:
                continue
    # Puede ser un número serial de Excel (días desde 1900)
    try:
        import numbers
        if isinstance(val, numbers.Number):
            from datetime import timedelta
            return datetime(1899, 12, 30) + timedelta(days=int(val))
    except Exception:
        pass
    return None

def default_sponsorship_year(row, base_path):
    """Genera el rango de patrocinio basado en la carpeta existente o en las fechas de Excel."""
    # 1. Intentar obtener el nombre de la carpeta PATROCINIO ya existente
    existing_year = find_existing_sponsorship_year(str(row.get('Patrocinador', '')), base_path)
    if existing_year:
        return existing_year

    # 2. Si no, calcular desde el Excel
    ini = parse_date_from_excel(row.get('Fecha de inicio (D-M-A)'))
    fin = parse_date_from_excel(row.get('Fecha de finalización (D-M-A)'))
    if ini and fin:
        mes_ini = MESES.get(ini.month, "")
        mes_fin = MESES.get(fin.month, "")
        return f"{mes_ini} {ini.year} - {mes_fin} {fin.year}"
    
    # 3. Default fallback
    return "MARZO 2026 - FEBRERO 2027"

# CSS
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main-header {
        color: #1e293b;
        font-weight: 700;
        text-align: center;
        padding-bottom: 20px;
    }
    .stButton>button {
        background-color: #3b82f6;
        color: white;
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s;
    }
    .stButton>button:hover {
        background-color: #2563eb;
        transform: translateY(-2px);
    }
    .stButton>button[kind="primary"] {
        background-color: #16a34a;
    }
    .stButton>button[kind="primary"]:hover {
        background-color: #15803d;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-header">📄 Generador Automático de Recibos</h1>', unsafe_allow_html=True)

# API Key (preconfigurada)
api_key = "AIzaSyAn6_EZ15kl1Li0ikb9MtlX5qWaWIJbNSk"

# -----------------------------------------------------
# CONFIGURACIÓN DE RUTAS Y SEDES
# -----------------------------------------------------
config = load_config()

with st.expander("⚙️ Configuración del Sistema", expanded=not (bool(config.get("excel_path")) and bool(config.get("base_folder")))):
    st.markdown("Por favor verifica las rutas en tu computador local antes de generar recibos. Estas se guardarán automáticamente para la próxima vez.")
    
    if "tmp_excel" not in st.session_state: st.session_state.tmp_excel = config.get("excel_path", "TRANSACCIONES MI NUEVA FAMILIA VALLE 2026 .xlsx")
    if "tmp_base" not in st.session_state: st.session_state.tmp_base = config.get("base_folder", "")
    if "tmp_template" not in st.session_state: st.session_state.tmp_template = config.get("template_path", "118673 - VILMA BEJARANO_FEB 2026.docx")

    c1, c2 = st.columns([5,1])
    with c1:
        st.session_state.tmp_excel = st.text_input("Ruta al archivo Excel (Base de datos):", value=st.session_state.tmp_excel)
    with c2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("📂 Buscar", key="btn_ex"):
            import subprocess, sys
            script = "import tkinter as tk, tkinter.filedialog as fd; root=tk.Tk(); root.withdraw(); root.wm_attributes('-topmost', 1); print(fd.askopenfilename(filetypes=[('Excel', '*.xlsx *.xls')]))"
            res = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True).stdout.strip()
            if res and res != "None":
                st.session_state.tmp_excel = res
                st.rerun()

    c1, c2 = st.columns([5,1])
    with c1:
        st.session_state.tmp_base = st.text_input("Carpeta Principal de su Zona (ej: TRONCAL-MI NUEVA FAMILIA):", value=st.session_state.tmp_base)
    with c2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("📂 Buscar", key="btn_base"):
            import subprocess, sys
            script = "import tkinter as tk, tkinter.filedialog as fd; root=tk.Tk(); root.withdraw(); root.wm_attributes('-topmost', 1); print(fd.askdirectory())"
            res = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True).stdout.strip()
            if res and res != "None":
                st.session_state.tmp_base = res
                st.rerun()

    c1, c2 = st.columns([5,1])
    with c1:
        st.session_state.tmp_template = st.text_input("Ruta de la Plantilla de Formato Word:", value=st.session_state.tmp_template)
    with c2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("📂 Buscar", key="btn_temp"):
            import subprocess, sys
            script = "import tkinter as tk, tkinter.filedialog as fd; root=tk.Tk(); root.withdraw(); root.wm_attributes('-topmost', 1); print(fd.askopenfilename(filetypes=[('Word', '*.docx')]))"
            res = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True).stdout.strip()
            if res and res != "None":
                st.session_state.tmp_template = res
                st.rerun()

    if st.button("Guardar Configuración Local"):
        new_excel = st.session_state.tmp_excel
        new_base_folder = st.session_state.tmp_base
        new_template = st.session_state.tmp_template
        if not os.path.exists(new_excel):
            st.error("El archivo Excel no existe en la ruta proporcionada.")
        elif not os.path.exists(new_base_folder):
            st.error("La carpeta base proporcionada no existe.")
        elif not os.path.exists(new_template):
            st.error("El archivo de plantilla Word no existe.")
        else:
            save_config({
                "excel_path": new_excel,
                "base_folder": new_base_folder,
                "template_path": new_template
            })
            st.success("Configuración actualizada correctamente.")
            st.rerun()

if not config.get("excel_path") or not os.path.exists(config.get("excel_path")) or not os.path.exists(config.get("base_folder")):
    st.warning("Debes configurar primero rutas válidas en el panel superior (⚙️ Configuración del Sistema) para poder continuar.")
    st.stop()

# Leer zonas únicas desde la base de datos maestra
excel_path = config["excel_path"]
try:
    # Se extrae de la pestaña maestra "Copia de BD PATROCINADORES CONF"
    df_preview = pd.read_excel(excel_path, sheet_name="Copia de BD PATROCINADORES CONF", header=1)
    df_preview.columns = df_preview.columns.str.strip().str.replace('\n', ' ')
    
    col_municipio = 'MUNICIPIO/ FORO' if 'MUNICIPIO/ FORO' in df_preview.columns else ('MUNICIPIO/FORO' if 'MUNICIPIO/FORO' in df_preview.columns else None)
    
    if col_municipio:
        # Extraer zonas únicas ordenadas, omitiendo vacíos o 'nan'
        available_zones = sorted([z for z in df_preview[col_municipio].dropna().unique() if str(z).strip() and str(z).lower() != 'nan'])
    else:
        available_zones = ["CALI - TRONCAL", "CALI - CAMBULOS", "CALI - PACARÁ"] # Fallback
except Exception as e:
    st.error(f"Error al analizar el archivo Excel configurado: {e}")
    st.stop()

selected_zone = st.selectbox("Selecciona la Sede / Zona a administrar:", available_zones)

# -----------------------------------------------------
# CARGA DE DATOS EXCEL
# -----------------------------------------------------
@st.cache_data(show_spinner="Cargando base de datos de patrocinadores...")
def load_data(path, zone_filter):
    df = pd.read_excel(path, sheet_name="Copia de BD PATROCINADORES CONF", header=1)
    df.columns = df.columns.str.strip().str.replace('\n', ' ')
    
    col_municipio = 'MUNICIPIO/ FORO' if 'MUNICIPIO/ FORO' in df.columns else ('MUNICIPIO/FORO' if 'MUNICIPIO/FORO' in df.columns else None)
    
    if col_municipio:
        df_filtered = df[df[col_municipio].astype(str).str.contains(zone_filter, case=False, na=False)].copy()
    else:
        df_filtered = df.copy()

    if 'Patrocinador' not in df_filtered.columns or 'Cédula / NIT' not in df_filtered.columns:
        raise ValueError("Faltan columnas de 'Patrocinador' o 'Cédula / NIT' en la hoja maestra.")
    df_filtered['Dropdown_Label'] = df_filtered['Patrocinador'].astype(str) + " - CC: " + df_filtered['Cédula / NIT'].astype(str)
    return df_filtered

try:
    df_sponsors = load_data(excel_path, selected_zone)
except Exception as e:
    st.error(f"Error al cargar la zona '{selected_zone}': {e}")
    st.stop()

# -----------------------------------------------------
# INICIALIZACIÓN SESSION STATE
# -----------------------------------------------------
for key in ['ai_results', 'doc_bytes', 'output_filename', 'mes_final', 'output_path',
            'sponsor_name', 'ano_patrocinio']:
    if key not in st.session_state:
        st.session_state[key] = None

# -----------------------------------------------------
# SELECCIÓN DEL PATROCINADOR
# -----------------------------------------------------
with st.container(border=True):
    st.subheader("1. Selección del Patrocinador")

    if df_sponsors.empty:
        st.warning("No se encontraron patrocinadores con el filtro 'CALI - TRONCAL'.")
        st.stop()

    sponsor_lists = [x for x in df_sponsors['Dropdown_Label'].tolist() if str(x) != 'nan - CC: nan']
    selected_sponsor = st.selectbox("Busca y selecciona un patrocinador:", sponsor_lists)

    if selected_sponsor:
        sponsor_data = df_sponsors[df_sponsors['Dropdown_Label'] == selected_sponsor].iloc[0]

        col1, col2 = st.columns(2)
        with col1:
            st.info(f"**Nombre:** {str(sponsor_data.get('Patrocinador', ''))}")
            st.info(f"**Cédula/NIT:** {str(sponsor_data.get('Cédula / NIT', ''))}")
        with col2:
            st.info(f"**Teléfono:** {str(sponsor_data.get('Teléfono', ''))}")
            st.info(f"**Correo:** {str(sponsor_data.get('Correo Electronico', 'No registrado'))}")

        st.markdown("### Configuración adicional para el recibo")

        default_ano = default_sponsorship_year(sponsor_data, config.get("base_folder"))

        c1, c2 = st.columns(2)
        with c1:
            default_ninos = str(sponsor_data.get('NÚMERO DE PATROCINIOS', '1'))
            try:
                if pd.isna(sponsor_data.get('NÚMERO DE PATROCINIOS')):
                    default_ninos = "1"
            except Exception:
                pass
            ninos = st.text_input("Niños patrocinados:", value=default_ninos)
        with c2:
            ano_patrocinio = st.text_input("Año de patrocinio:", value=default_ano)

# -----------------------------------------------------
# COMPROBANTE DE PAGO
# -----------------------------------------------------
with st.container(border=True):
    st.subheader("2. Comprobante de Pago")
    uploaded_file = st.file_uploader("Sube la imagen del comprobante de transferencia", type=['png', 'jpg', 'jpeg'])

if uploaded_file is not None and selected_sponsor:
    img_col1, img_col2, img_col3 = st.columns([1.5, 2, 1.5])
    with img_col2:
        st.image(uploaded_file, caption="Comprobante cargado", use_container_width=True)

    # PASO A: ANALIZAR CON IA
    if st.button("Analizar Comprobante con IA", use_container_width=True):
        with st.spinner("Analizando comprobante..."):
            try:
                temp_img_path = "temp_receipt.jpg"
                with open(temp_img_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                st.session_state.ai_results = extract_receipt_data(api_key, temp_img_path)
                st.success("Análisis completado. Revisa y ajusta los datos abajo.")
            except Exception as e:
                st.error(f"Error en el análisis: {str(e)}")

    # PASO B: EDITAR Y GENERAR
    if st.session_state.ai_results:
        st.markdown("---")
        st.subheader("3. Revisión de Datos Extraídos")

        col_ai1, col_ai2 = st.columns(2)
        with col_ai1:
            val_base = st.text_input("Valor de consignación (Base):", value=st.session_state.ai_results.get('valor_consignacion', ''))
            val_obs = st.text_input("Observación del valor (Opcional):", placeholder="ej: 10.000 saldo a favor")
            fecha_final = st.text_input("Fecha de consignación:", value=st.session_state.ai_results.get('fecha_consignacion', ''))
        with col_ai2:
            comprobante_final = st.text_input("Número de comprobante:", value=st.session_state.ai_results.get('numero_comprobante', ''))
            mes_final = st.text_input("Mes del Aporte:", value=st.session_state.ai_results.get('mes_aporte', ''))

        valor_final = val_base
        if val_obs:
            valor_final = f"{val_base} ({val_obs})"

        # PASO C: GENERAR DOCUMENTO
        if st.button("Generar Recibo Word", type="primary", use_container_width=True):
            with st.spinner("Creando archivo Word..."):
                try:
                    template_path = config.get("template_path", "118673 - VILMA BEJARANO_FEB 2026.docx")
                    temp_img_path = "temp_receipt.jpg"

                    name_parts = str(sponsor_data.get('Patrocinador', '')).strip().split()
                    short_name = " ".join(name_parts[:2]).upper() if len(name_parts) >= 2 else (" ".join(name_parts).upper() if name_parts else "PATROCINADOR")
                    month_abbr = str(mes_final)[:3].upper() if mes_final else "XXX"
                    output_filename = f"{short_name}-{month_abbr}.docx"
                    output_path = f"temp_{output_filename}"

                    foro_name = selected_zone.split("-")[-1].strip() if "-" in selected_zone else selected_zone

                    context = {
                        "foro": foro_name,
                        "nombre": str(sponsor_data.get('Patrocinador', '')),
                        "identificacion": str(sponsor_data.get('Cédula / NIT', '')),
                        "telefono": str(sponsor_data.get('Teléfono', '')),
                        "correo": str(sponsor_data.get('Correo Electronico', '')),
                        "valor": valor_final,
                        "fecha": fecha_final,
                        "comprobante": comprobante_final,
                        "mes": str(mes_final).upper(),
                        "ninos": str(ninos),
                        "ano_patrocinio": str(ano_patrocinio)
                    }

                    generate_receipt(template_path, output_path, context, image_path=temp_img_path)

                    with open(output_path, "rb") as f:
                        doc_bytes = f.read()

                    # Guardar en session_state para uso posterior
                    st.session_state.doc_bytes = doc_bytes
                    st.session_state.output_filename = output_filename
                    st.session_state.output_path = output_path
                    st.session_state.mes_final = mes_final
                    st.session_state.sponsor_name = str(sponsor_data.get('Patrocinador', ''))
                    st.session_state.ano_patrocinio = ano_patrocinio

                    st.success("Recibo generado correctamente.")
                except Exception as e:
                    st.error(f"Error generando el recibo: {str(e)}")

# -----------------------------------------------------
# PASO D: DESCARGA Y GUARDADO (siempre visible si hay documento)
# -----------------------------------------------------
if st.session_state.doc_bytes:
    st.markdown("---")
    st.subheader("4. Descargar y Guardar")

    act_col1, act_col2 = st.columns(2)

    with act_col1:
        st.download_button(
            label="Descargar Word",
            data=st.session_state.doc_bytes,
            file_name=st.session_state.output_filename,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True
        )

    with act_col2:
        if st.button(f"Guardar en Carpeta ({selected_zone})", use_container_width=True):
            sponsor_folder = find_sponsor_folder(st.session_state.sponsor_name, config.get("base_folder"))
            if not sponsor_folder:
                st.error(f"No se encontró la carpeta de **{st.session_state.sponsor_name}** en la ruta base proporcionada ni en Inactivos.")
            else:
                try:
                    # Estructura: CONSIGNACIONES / PATROCINIO [RANGO] / [MES]
                    consignaciones_dir = os.path.join(sponsor_folder, "CONSIGNACIONES")
                    os.makedirs(consignaciones_dir, exist_ok=True)

                    periodo_dir = os.path.join(consignaciones_dir, f"PATROCINIO {st.session_state.ano_patrocinio}")
                    os.makedirs(periodo_dir, exist_ok=True)

                    mes_dir_name = str(st.session_state.mes_final).strip().upper()
                    final_dir = os.path.join(periodo_dir, mes_dir_name)
                    os.makedirs(final_dir, exist_ok=True)

                    # Guardar Word
                    word_save_path = os.path.join(final_dir, st.session_state.output_filename)
                    with open(word_save_path, "wb") as f:
                        f.write(st.session_state.doc_bytes)

                    st.info(f"Word guardado exitosamente en:\n`{word_save_path}`")

                    # Convertir y guardar PDF
                    pdf_filename = st.session_state.output_filename.replace(".docx", ".pdf")
                    pdf_save_path = os.path.join(final_dir, pdf_filename)

                    if PDF_SUPPORT:
                        with st.spinner("Convirtiendo a PDF (requiere Microsoft Word)..."):
                            try:
                                convert(word_save_path, pdf_save_path)
                                st.success(f"PDF generado y guardado exitosamente en:\n`{pdf_save_path}`")
                            except Exception as pdf_err:
                                st.warning(f"El archivo Word fue guardado exitosamente, pero la conversión a PDF falló. Detalles adicionales: {pdf_err}")
                    else:
                        st.warning("El archivo Word fue guardado. La conversión automática a PDF no está disponible ('docx2pdf' no instalada) pero el proceso ha terminado.")

                    st.success(f"Proceso concluido exitosamente.\n\nCarpeta destino: `{final_dir}`")

                except Exception as save_err:
                    st.error(f"Error al guardar: {str(save_err)}")
