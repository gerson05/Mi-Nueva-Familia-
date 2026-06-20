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
from image_upscaler import upscale_image, check_upscaler_available
from antecedentes_checker import (
    consultar_todos, cargar_log, obtener_vigencia,
    _extraer_nombre_ofac, _output_dir_para_patrocinador, DOWNLOADS_DIR
)

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
PATROCINADORES_LOCALES_FILE = "patrocinadores_locales.json"

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

def load_local_sponsors(zone: str) -> pd.DataFrame:
    cols = ["Patrocinador", "Cédula / NIT", "MUNICIPIO/FORO", "Teléfono", "Correo Electronico", "NÚMERO DE PATROCINIOS"]
    if not os.path.exists(PATROCINADORES_LOCALES_FILE):
        return pd.DataFrame(columns=cols)
    try:
        with open(PATROCINADORES_LOCALES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        sponsors = data.get(zone, [])
        if not sponsors:
            return pd.DataFrame(columns=cols)
        df = pd.DataFrame(sponsors)
        for col in cols:
            if col not in df.columns:
                df[col] = ""
        return df[cols]
    except Exception:
        return pd.DataFrame(columns=cols)

def save_local_sponsor(zone: str, sponsor: dict):
    data = {}
    if os.path.exists(PATROCINADORES_LOCALES_FILE):
        try:
            with open(PATROCINADORES_LOCALES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    if zone not in data:
        data[zone] = []
    cedula = str(sponsor.get("Cédula / NIT", "")).strip()
    data[zone] = [s for s in data[zone] if str(s.get("Cédula / NIT", "")).strip() != cedula]
    data[zone].append(sponsor)
    with open(PATROCINADORES_LOCALES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def delete_local_sponsor(zone: str, cedula: str):
    if not os.path.exists(PATROCINADORES_LOCALES_FILE):
        return
    try:
        with open(PATROCINADORES_LOCALES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if zone in data:
            data[zone] = [s for s in data[zone] if str(s.get("Cédula / NIT", "")).strip() != cedula.strip()]
        with open(PATROCINADORES_LOCALES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def is_match(search_name, folder_name):
    # Verifica si al menos 2 palabras del nombre están en el nombre de la carpeta,
    # o si el search_name completo es parte del folder.
    s_norm = normalize(search_name)
    f_norm = normalize(folder_name)
    if s_norm in f_norm:
        return True
    parts = s_norm.split()
    hits = sum(1 for part in parts if part in f_norm)
    return hits >= 2

def find_sponsor_folder(sponsor_name, base_path):
    """Busca la carpeta del patrocinador en la base asignada e Inactivos."""
    if not base_path or not os.path.exists(base_path):
        return None

    # 1. Buscar en la raíz de la sede
    for item in os.listdir(base_path):
        item_path = os.path.join(base_path, item)
        if os.path.isdir(item_path) and is_match(sponsor_name, item):
            return item_path

    # 2. Buscar en 1. INACTIVOS
    inactivos_path = os.path.join(base_path, "1. INACTIVOS")
    if os.path.exists(inactivos_path):
        for item in os.listdir(inactivos_path):
            item_path = os.path.join(inactivos_path, item)
            if os.path.isdir(item_path) and is_match(sponsor_name, item):
                return item_path

    return None

def find_existing_sponsorship_year(sponsor_name, base_path):
    """Busca la subcarpeta PATROCINIO más reciente en CONSIGNACIONES y retorna el rango."""
    sponsor_folder = find_sponsor_folder(sponsor_name, base_path)
    if sponsor_folder:
        consig_path = os.path.join(sponsor_folder, "CONSIGNACIONES")
        if os.path.exists(consig_path):
            try:
                folders = [f for f in os.listdir(consig_path) if os.path.isdir(os.path.join(consig_path, f)) and "PATROCINIO" in f.upper()]
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
                    
                    match = re.search(r"(?i)PATROCINIO\s*(.*)", folders[0])
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

# -----------------------------------------------------
# CONFIGURACIÓN DE RUTAS Y SEDES
# -----------------------------------------------------
config = load_config()

# API Key
api_key = config.get("api_key", "")

with st.expander("⚙️ Configuración del Sistema", expanded=not (bool(config.get("excel_path")) and bool(config.get("base_folder")) and bool(config.get("api_key")))):
    st.markdown("Por favor verifica las rutas en tu computador local antes de generar recibos. Estas se guardarán automáticamente para la próxima vez.")
    
    if "tmp_excel" not in st.session_state: st.session_state.tmp_excel = config.get("excel_path", "TRANSACCIONES MI NUEVA FAMILIA VALLE 2026 .xlsx")
    if "tmp_base" not in st.session_state: st.session_state.tmp_base = config.get("base_folder", "")
    if "tmp_template" not in st.session_state: st.session_state.tmp_template = config.get("template_path", "118673 - VILMA BEJARANO_FEB 2026.docx")
    if "tmp_api_key" not in st.session_state: st.session_state.tmp_api_key = config.get("api_key", "")
    if "tmp_apps_script_url" not in st.session_state: st.session_state.tmp_apps_script_url = config.get("apps_script_url", "")
    if "tmp_supabase_key" not in st.session_state: st.session_state.tmp_supabase_key = config.get("supabase_key", "")

    c1, c2 = st.columns([5,1])
    with c1:
        st.session_state.tmp_excel = st.text_input("Ruta al archivo Excel (Base de datos):", value=st.session_state.tmp_excel)
    with c2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("📂 Buscar", key="btn_ex"):
            import subprocess
            _ps = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "$f = New-Object System.Windows.Forms.OpenFileDialog; "
                "$f.Filter = 'Excel|*.xlsx;*.xls'; "
                "$f.TopMost = $true; "
                "[void]$f.ShowDialog(); "
                "$f.FileName"
            )
            _r = subprocess.run(["powershell", "-NoProfile", "-Command", _ps], capture_output=True, text=True)
            res = _r.stdout.strip()
            if res and os.path.exists(res):
                st.session_state.tmp_excel = res
                st.rerun()
            elif _r.returncode != 0:
                st.error("No se pudo abrir el selector. Escribe la ruta manualmente.")

    c1, c2 = st.columns([5,1])
    with c1:
        st.session_state.tmp_base = st.text_input("Carpeta Principal de su Zona (ej: TRONCAL-MI NUEVA FAMILIA):", value=st.session_state.tmp_base)
    with c2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("📂 Buscar", key="btn_base"):
            import subprocess
            _ps = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "$f = New-Object System.Windows.Forms.FolderBrowserDialog; "
                "$f.RootFolder = 'MyComputer'; "
                "[void]$f.ShowDialog(); "
                "$f.SelectedPath"
            )
            _r = subprocess.run(["powershell", "-NoProfile", "-Command", _ps], capture_output=True, text=True)
            res = _r.stdout.strip()
            if res and os.path.exists(res):
                st.session_state.tmp_base = res
                st.rerun()
            elif _r.returncode != 0:
                st.error("No se pudo abrir el selector. Escribe la ruta manualmente.")

    c1, c2 = st.columns([5,1])
    with c1:
        st.session_state.tmp_template = st.text_input("Ruta de la Plantilla de Formato Word:", value=st.session_state.tmp_template)
    with c2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("📂 Buscar", key="btn_temp"):
            import subprocess
            _ps = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "$f = New-Object System.Windows.Forms.OpenFileDialog; "
                "$f.Filter = 'Word|*.docx'; "
                "$f.TopMost = $true; "
                "[void]$f.ShowDialog(); "
                "$f.FileName"
            )
            _r = subprocess.run(["powershell", "-NoProfile", "-Command", _ps], capture_output=True, text=True)
            res = _r.stdout.strip()
            if res and os.path.exists(res):
                st.session_state.tmp_template = res
                st.rerun()
            elif _r.returncode != 0:
                st.error("No se pudo abrir el selector. Escribe la ruta manualmente.")

    st.session_state.tmp_api_key = st.text_input("Clave de API de Gemini (API Key):", value=st.session_state.tmp_api_key, type="password")
    st.session_state.tmp_supabase_key = st.text_input(
        "Clave Supabase (Secret Key):",
        value=st.session_state.tmp_supabase_key,
        type="password",
        help="Secret key de Supabase para subir recibos al repositorio centralizado."
    )

    if st.button("Guardar Configuración Local"):
        new_excel = st.session_state.tmp_excel
        new_base_folder = st.session_state.tmp_base
        new_template = st.session_state.tmp_template
        new_api_key = st.session_state.tmp_api_key
        new_apps_script_url = st.session_state.tmp_apps_script_url.strip()
        new_supabase_key = st.session_state.tmp_supabase_key.strip()
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
                "template_path": new_template,
                "api_key": new_api_key,
                "apps_script_url": new_apps_script_url,
                "supabase_key": new_supabase_key,
            })
            st.success("Configuración actualizada correctamente.")
            st.rerun()

if not config.get("excel_path") or not os.path.exists(config.get("excel_path")) or not os.path.exists(config.get("base_folder")) or not config.get("api_key"):
    st.warning("Debes configurar primero rutas válidas y tu Clave de API de Gemini en el panel superior (⚙️ Configuración del Sistema) para poder continuar.")
    st.stop()

# Leer zonas disponibles directamente de los nombres de hoja del Excel
excel_path = config["excel_path"]

# Hojas a ignorar (no son zonas de patrocinadores)
SHEETS_IGNORADAS = {
    "", "corte trimestral", "zona cali", "zona sur", "zona centro",
    "copia de bd patrocinadores conf"
}

# Cache persistente de estructura de hojas (evita re-detectar encabezados en cada carga)
SHEET_CACHE_FILE = "sheet_cache.json"

def load_sheet_cache() -> dict:
    if os.path.exists(SHEET_CACHE_FILE):
        try:
            with open(SHEET_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_sheet_cache(cache: dict):
    try:
        with open(SHEET_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# Usar session_state para no re-abrir el Excel en cada interaccion de Streamlit
if "_xl_sheet_names" not in st.session_state or st.session_state.get("_xl_path") != excel_path:
    try:
        _xl = pd.ExcelFile(excel_path, engine="openpyxl")
        st.session_state["_xl_sheet_names"] = _xl.sheet_names
        st.session_state["_xl_path"] = excel_path
    except PermissionError:
        # Archivo bloqueado (Excel abierto, OneDrive/GDrive sincronizando, antivirus)
        # Intentar leer en memoria con acceso compartido de Windows
        try:
            import io, tempfile, ctypes, ctypes.wintypes
            # CreateFile con FILE_SHARE_READ|WRITE|DELETE — bypasea locks de otros procesos
            _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            _GENERIC_READ = 0x80000000
            _FILE_SHARE_ALL = 0x00000001 | 0x00000002 | 0x00000004
            _OPEN_EXISTING = 3
            _FILE_ATTR_NORMAL = 0x80
            _handle = _kernel32.CreateFileW(
                excel_path, _GENERIC_READ, _FILE_SHARE_ALL,
                None, _OPEN_EXISTING, _FILE_ATTR_NORMAL, None
            )
            _INVALID = ctypes.wintypes.HANDLE(-1).value
            if _handle == _INVALID:
                raise OSError(f"CreateFile falló: error {ctypes.get_last_error()}")
            _size = ctypes.wintypes.DWORD(0)
            _file_size = _kernel32.GetFileSize(_handle, ctypes.byref(_size))
            _buf = ctypes.create_string_buffer(_file_size)
            _read = ctypes.wintypes.DWORD(0)
            _kernel32.ReadFile(_handle, _buf, _file_size, ctypes.byref(_read), None)
            _kernel32.CloseHandle(_handle)
            _data = bytes(_buf)
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as _tmp:
                _tmp.write(_data)
                _tmp_path = _tmp.name
            _xl = pd.ExcelFile(_tmp_path, engine="openpyxl")
            st.session_state["_xl_sheet_names"] = _xl.sheet_names
            st.session_state["_xl_path"] = excel_path
            st.session_state["_xl_tmp_path"] = _tmp_path
            st.info("ℹ️ El archivo Excel está en uso por otro proceso. Se leyó en modo compartido.")
        except Exception as e2:
            st.error(
                "No se puede abrir el archivo Excel. Posibles causas:\n\n"
                "1. **OneDrive o Google Drive** sincronizando — pausa y recarga.\n"
                "2. **Excel** abierto — ciérralo y recarga.\n"
                "3. **Antivirus** escaneando — espera unos segundos y recarga.\n"
                "4. **Permisos de Windows** — intenta mover el Excel a otra carpeta (ej: Escritorio).\n\n"
                f"Detalle técnico: {e2}"
            )
            st.stop()
    except Exception as e:
        st.error(f"Error al abrir el archivo Excel: {e}")
        st.stop()

try:
    available_zones = sorted([
        s.strip() for s in st.session_state["_xl_sheet_names"]
        if s.strip() and s.strip().lower() not in SHEETS_IGNORADAS
    ])
    if not available_zones:
        raise ValueError("No se encontraron hojas de zona en el archivo Excel.")
except Exception as e:
    st.error(f"Error al analizar el archivo Excel configurado: {e}")
    st.stop()

selected_zone = st.selectbox("Selecciona la Sede / Zona a administrar:", available_zones)

def get_dynamic_base_folder(zone_str, configured_base):
    if not configured_base or not os.path.exists(configured_base):
        return configured_base
    parent_dir = os.path.dirname(configured_base)
    zone_keyword = normalize(zone_str.split("-")[-1].strip())
    for item in os.listdir(parent_dir):
        item_path = os.path.join(parent_dir, item)
        if os.path.isdir(item_path) and zone_keyword in normalize(item):
            return item_path
    return configured_base

dynamic_base_folder = get_dynamic_base_folder(selected_zone, config.get("base_folder"))

# -----------------------------------------------------
# CARGA DE DATOS EXCEL
# -----------------------------------------------------

# Nombre de la hoja de Base de Datos de Patrocinadores (hoja protegida con correos, dirección, etc.)
BD_SHEET_NAME = ","

@st.cache_data(show_spinner="Cargando datos adicionales de patrocinadores...")
def load_bd_emails(path: str) -> pd.DataFrame:
    """Carga correos electrónicos y datos adicionales desde la hoja BD protegida.

    La hoja ',' contiene la Base de Datos maestra con columnas como:
      Col 5: Cédula / NIT
      Col 8: Correo Electronico
      Col 16: Número de niños patrocinados
    Los encabezados están en la fila 1, datos desde la fila 2+.
    """
    try:
        # Leer solo las columnas necesarias: cédula (5), correo (8), num patrocinios (16)
        read_kw = dict(
            sheet_name=BD_SHEET_NAME, header=None,
            skiprows=2,  # datos empiezan en fila 2 (0-indexed), saltamos filas 0 y 1
            usecols=[5, 8, 16], dtype=str,
        )
        try:
            df_bd = pd.read_excel(path, engine="calamine", **read_kw)
        except Exception:
            df_bd = pd.read_excel(path, engine="openpyxl", **read_kw)

        df_bd.columns = ["_bd_cedula", "Correo Electronico", "NÚMERO DE PATROCINIOS"]
        df_bd["_bd_cedula"] = df_bd["_bd_cedula"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
        df_bd = df_bd[df_bd["_bd_cedula"].notna() & ~df_bd["_bd_cedula"].isin(["", "nan", "None"])]
        return df_bd
    except Exception:
        return pd.DataFrame(columns=["_bd_cedula", "Correo Electronico", "NÚMERO DE PATROCINIOS"])

@st.cache_data(show_spinner="Cargando base de datos de patrocinadores...")
def load_data(path: str, zone_filter: str) -> pd.DataFrame:
    """Carga patrocinadores de la hoja de zona.

    Estructura del Excel (2 filas de encabezado):
      - Fila N  : PATROCINADOR, MUNICIPIO/FORO
      - Fila N+1: CEDULA O NIT, TELEFONO  (sub-encabezado)
      - Fila N+2+: datos reales

    Optimizaciones aplicadas:
    - Estructura cacheada en disco (sheet_cache.json): solo se detecta 1 vez.
    - Motor calamine (Rust): lectura de datos ~3-5x mas rapida que openpyxl.
    - usecols: solo 4 columnas de 385+ se leen del archivo.
    - st.cache_data: resultado cacheado por Streamlit entre recargas.
    """
    # -- 1. Encontrar hoja exacta (usando session_state para no re-abrir el archivo) --
    sheet_names = st.session_state.get("_xl_sheet_names", [])
    sheet_name = next(
        (s for s in sheet_names if s.strip().lower() == zone_filter.strip().lower()),
        None,
    )
    if sheet_name is None:
        raise ValueError(f"No se encontro la hoja '{zone_filter}' en el Excel.")

    # -- 2. Obtener estructura de encabezado (cache persistente en disco) ----------
    _sheet_cache = load_sheet_cache()
    cache_key = f"{path}::{sheet_name}"

    if cache_key not in _sheet_cache:
        # Primera vez: detectar leyendo solo 6 filas
        df_probe = pd.read_excel(
            path, sheet_name=sheet_name, header=None, nrows=6, engine="openpyxl"
        )
        header_row = name_col = cedula_col = mun_col = tel_col = cedula_row = None

        for row_i, row in df_probe.iterrows():
            for col_i, val in enumerate(row):
                cell = str(val).strip().upper() if pd.notna(val) else ""
                if cell == "PATROCINADOR":
                    header_row = row_i
                    name_col = col_i
                if "MUNICIPIO" in cell and mun_col is None:
                    mun_col = col_i

        if header_row is None:
            raise ValueError(
                f"No se encontro la columna 'PATROCINADOR' en '{sheet_name}'."
            )
        for col_i, val in enumerate(df_probe.iloc[header_row]):
            cell = str(val).strip().upper() if pd.notna(val) else ""
            if "MUNICIPIO" in cell:
                mun_col = col_i

        for search_row in [header_row + 1, header_row]:
            if search_row >= len(df_probe):
                continue
            for col_i, val in enumerate(df_probe.iloc[search_row]):
                cell = str(val).strip().upper() if pd.notna(val) else ""
                if ("DULA" in cell or "NIT" in cell) and cedula_col is None:
                    cedula_col = col_i
                    cedula_row = search_row
                if "TEL" in cell and tel_col is None:
                    tel_col = col_i
            if cedula_col is not None:
                break

        if cedula_col is None:
            raise ValueError(
                f"No se encontro la columna 'CEDULA O NIT' en '{sheet_name}'."
            )

        struct = {
            "header_row": header_row,
            "cedula_row": cedula_row,
            "name_col": name_col,
            "cedula_col": cedula_col,
            "mun_col": mun_col,
            "tel_col": tel_col,
            "data_start": (cedula_row if cedula_row is not None else header_row) + 1,
        }
        _sheet_cache[cache_key] = struct
        save_sheet_cache(_sheet_cache)
    else:
        struct = _sheet_cache[cache_key]

    name_col   = struct["name_col"]
    cedula_col = struct["cedula_col"]
    mun_col    = struct["mun_col"]
    tel_col    = struct["tel_col"]
    data_start = struct["data_start"]

    # -- 3. Leer solo columnas necesarias con calamine (motor Rust) ---------------
    cols_needed = sorted(set(filter(
        lambda x: x is not None, [name_col, cedula_col, mun_col, tel_col]
    )))
    read_kw = dict(
        sheet_name=sheet_name, header=None,
        skiprows=data_start, usecols=cols_needed, dtype=str,
    )
    try:
        df = pd.read_excel(path, engine="calamine", **read_kw)
    except Exception:
        df = pd.read_excel(path, engine="openpyxl", **read_kw)

    # -- 4. Renombrar a nombres internos estandar ---------------------------------
    col_map = {}
    if name_col   in df.columns: col_map[name_col]   = "Patrocinador"
    if cedula_col in df.columns: col_map[cedula_col] = "Cedula / NIT"
    if mun_col    in df.columns: col_map[mun_col]    = "MUNICIPIO/FORO"
    if tel_col    in df.columns: col_map[tel_col]    = "Telefono"
    df.rename(columns=col_map, inplace=True)
    if "Cedula / NIT" in df.columns:
        df.rename(columns={"Cedula / NIT": "Cedula / NIT"}, inplace=True)
    # Alias con acentos para compatibilidad
    df.rename(columns={"Cedula / NIT": "Cédula / NIT", "Telefono": "Teléfono"}, inplace=True)

    if "Patrocinador" not in df.columns or "Cédula / NIT" not in df.columns:
        raise ValueError(
            f"No se pudieron mapear las columnas esenciales en '{sheet_name}'."
        )

    # -- 5. Limpiar filas vacias --------------------------------------------------
    df = df[df["Patrocinador"].notna()].copy()
    df = df[~df["Patrocinador"].str.strip().isin(["", "nan", "None"])].copy()
    df["Cédula / NIT"] = (
        df["Cédula / NIT"].str.replace(r"\.0$", "", regex=True).str.strip()
    )

    # -- 6. Cruzar con hoja BD para obtener correo y numero de patrocinios --------
    df_bd = load_bd_emails(path)
    if not df_bd.empty:
        df = df.merge(
            df_bd, left_on="Cédula / NIT", right_on="_bd_cedula", how="left"
        ).drop(columns=["_bd_cedula"], errors="ignore")

    # Asegurar que la columna exista aunque la BD no haya cargado
    if "Correo Electronico" not in df.columns:
        df["Correo Electronico"] = ""
    if "NÚMERO DE PATROCINIOS" not in df.columns:
        df["NÚMERO DE PATROCINIOS"] = ""

    df["Dropdown_Label"] = df["Patrocinador"].str.strip() + " - CC: " + df["Cédula / NIT"]
    return df

_excel_read_path = st.session_state.get("_xl_tmp_path", excel_path)
try:
    df_sponsors = load_data(_excel_read_path, selected_zone)
except Exception as e:
    st.error(f"Error al cargar la zona '{selected_zone}': {e}")
    st.stop()

# Fusionar con patrocinadores registrados localmente (no están en el Excel)
_df_locales = load_local_sponsors(selected_zone)
if not _df_locales.empty:
    df_sponsors = pd.concat([df_sponsors, _df_locales], ignore_index=True)
    df_sponsors["Dropdown_Label"] = (
        df_sponsors["Patrocinador"].str.strip() + " - CC: " + df_sponsors["Cédula / NIT"]
    )

# -----------------------------------------------------
# INICIALIZACIÓN SESSION STATE
# -----------------------------------------------------
for key in ['ai_results', 'doc_bytes', 'output_filename', 'mes_final', 'output_path',
            'sponsor_name', 'ano_patrocinio', 'current_sponsor']:
    if key not in st.session_state:
        st.session_state[key] = None

# -----------------------------------------------------

# === PESTANAS PRINCIPALES ====================================================
tab_recibos, tab_revision, tab_antecedentes, tab_importar = st.tabs([
    "📄 Generador de Recibos", "🔍 Revisión Zonal", "🔎 Antecedentes", "📥 Importar Patrocinador"
])

with tab_recibos:
    # SELECCIÓN DEL PATROCINADOR
    # -----------------------------------------------------
    with st.container(border=True):
        st.subheader("1. Selección del Patrocinador")

        if df_sponsors.empty:
            st.warning("No se encontraron patrocinadores con el filtro seleccionado.")
            st.stop()

        sponsor_lists = sorted([
            s for s in (str(x) for x in df_sponsors['Dropdown_Label'])
            if s and s not in ('nan - CC: nan', 'nan', 'None', '')
        ])
        selected_sponsor = st.selectbox("Busca y selecciona un patrocinador (puedes escribir para buscar):", sponsor_lists)

        if selected_sponsor:
            if st.session_state.current_sponsor != selected_sponsor:
                # Limpiar el estado anterior para asegurar que no quede un comprobante de un patrocinador viejo
                st.session_state.current_sponsor = selected_sponsor
                st.session_state.ai_results = None
                st.session_state.doc_bytes = None
                st.session_state.upscaled_img_path = None
                st.session_state.use_upscaled = False
                st.session_state.upscale_error = None

            sponsor_data = df_sponsors[df_sponsors['Dropdown_Label'] == selected_sponsor].iloc[0]

            col1, col2 = st.columns(2)
            with col1:
                st.info(f"**Nombre:** {str(sponsor_data.get('Patrocinador', ''))}")
                st.info(f"**Cédula/NIT:** {str(sponsor_data.get('Cédula / NIT', ''))}")
            with col2:
                st.info(f"**Teléfono:** {str(sponsor_data.get('Teléfono', ''))}")
                correo_val = sponsor_data.get('Correo Electronico', None)
                st.info(f"**Correo:** {str(correo_val) if correo_val and str(correo_val).lower() not in ['nan','none',''] else 'No registrado'}")

            st.markdown("### Configuración adicional para el recibo")

            default_ano = default_sponsorship_year(sponsor_data, dynamic_base_folder)

            c1, c2 = st.columns(2)
            with c1:
                _ninos_raw = sponsor_data.get('NÚMERO DE PATROCINIOS', None)
                try:
                    default_ninos = "1" if _ninos_raw is None or pd.isna(_ninos_raw) else str(int(float(str(_ninos_raw))))
                except Exception:
                    default_ninos = "1"
                ninos = st.text_input("Niños patrocinados:", value=default_ninos)
            with c2:
                ano_patrocinio = st.text_input("Año de patrocinio:", value=default_ano)

            image_alignment = st.radio("Alineación del comprobante en el documento:", ["Izquierda", "Central"], horizontal=True)

    # -----------------------------------------------------
    # COMPROBANTE DE PAGO
    # -----------------------------------------------------

    # Inicializar estado para la imagen mejorada
    if 'upscaled_img_path' not in st.session_state:
        st.session_state.upscaled_img_path = None
    if 'use_upscaled' not in st.session_state:
        st.session_state.use_upscaled = False
    if 'upscale_error' not in st.session_state:
        st.session_state.upscale_error = None

    with st.container(border=True):
        st.subheader("2. Comprobante de Pago")
        # Al concatenar el nombre del patrocinador al key, el componente se reinicia si el patrocinador cambia
        upload_key = f"uploader_{st.session_state.current_sponsor}" if st.session_state.current_sponsor else "uploader"
        uploaded_file = st.file_uploader("Sube la imagen del comprobante de transferencia", type=['png', 'jpg', 'jpeg'], key=upload_key)

    if uploaded_file is not None and selected_sponsor:

        # Siempre guardar la imagen original en disco para poder usarla
        temp_img_path_original = "temp_receipt_original.jpg"
        uploaded_file.seek(0)
        with open(temp_img_path_original, "wb") as f:
            f.write(uploaded_file.read())

        # ---- SECCIÓN DE MEJORA DE IMAGEN ----
        with st.container(border=True):
            st.markdown("### Mejora de Calidad de Imagen")
            st.caption("Opcional — usa este paso si el comprobante esta borroso o de baja resolucion. Tarda ~30-60 segundos.")

            upscale_col1, upscale_col2 = st.columns([1, 1])

            with upscale_col1:
                st.image(temp_img_path_original, caption="Original", use_container_width=True)

            with upscale_col2:
                if st.session_state.upscaled_img_path and os.path.exists(st.session_state.upscaled_img_path):
                    st.image(st.session_state.upscaled_img_path, caption="Mejorada", use_container_width=True)
                else:
                    st.markdown(
                        """
                        <div style='
                            border: 2px dashed #94a3b8;
                            border-radius: 12px;
                            height: 200px;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            color: #94a3b8;
                            font-size: 14px;
                            text-align: center;
                            padding: 20px;
                        '>
                            La imagen mejorada aparecera aqui
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

            with st.expander("⚙️ Ajustes de nivel de aumento"):
                ui_upscale_mode = st.radio(
                    "Modo de mejora",
                    ["Local (rapido, offline)", "IA - HuggingFace (mejor calidad, requiere internet)"],
                    index=0, horizontal=True,
                    help="Local usa Pillow (instantaneo). IA usa Flux.1-dev-Controlnet-Upscaler para resultados superiores."
                )
                use_ai_mode = "HuggingFace" in ui_upscale_mode

                if use_ai_mode:
                    st.caption("El modo IA puede tardar 30-60 segundos. Requiere internet y el paquete `gradio_client`.")

                ui_upscale_factor = st.radio(
                    "Nivel de Aumento",
                    [2, 4, 8], index=0, horizontal=True,
                    help="Aumento de resolución. 2x suele ser suficiente para mejorar legibilidad."
                )

            if st.session_state.upscale_error:
                st.error(st.session_state.upscale_error)

            btn_col1, btn_col2 = st.columns([1, 1])
            with btn_col1:
                btn_label = "Mejorar con IA" if use_ai_mode else "Mejorar Calidad de Imagen"
                if st.button(btn_label, use_container_width=True, key="btn_upscale"):
                    st.session_state.upscale_error = None
                    spinner_msg = "Procesando imagen con IA de HuggingFace... puede tardar hasta 60s." if use_ai_mode else "Procesando imagen localmente..."
                    with st.spinner(spinner_msg):
                        try:
                            upscaled_path = "temp_receipt_upscaled.jpg"
                            upscale_image(
                                input_path=temp_img_path_original,
                                output_path=upscaled_path,
                                upscale_factor=ui_upscale_factor,
                                use_ai=use_ai_mode,
                            )
                            st.session_state.upscaled_img_path = upscaled_path
                            st.session_state.use_upscaled = True
                            st.success("Imagen mejorada correctamente. Se usara la version mejorada para el analisis.")
                            st.rerun()
                        except Exception as e:
                            st.session_state.upscale_error = (
                                f"No se pudo mejorar la imagen: {str(e)}. "
                                f"Puedes continuar con la imagen original."
                            )

            with btn_col2:
                if st.session_state.upscaled_img_path and os.path.exists(st.session_state.upscaled_img_path):
                    toggle_label = "Usar imagen original" if st.session_state.use_upscaled else "Usar imagen mejorada"
                    if st.button(toggle_label, use_container_width=True, key="btn_toggle_img"):
                        st.session_state.use_upscaled = not st.session_state.use_upscaled
                        st.rerun()

            # Indicador de cuál imagen se está usando
            if st.session_state.upscaled_img_path and os.path.exists(st.session_state.upscaled_img_path):
                if st.session_state.use_upscaled:
                    st.success("Se usara la imagen mejorada para el analisis IA y el documento Word.")
                else:
                    st.info("Se usara la imagen original para el analisis IA y el documento Word.")

        # Determinar qué imagen se usará en los pasos siguientes
        if st.session_state.use_upscaled and st.session_state.upscaled_img_path and os.path.exists(st.session_state.upscaled_img_path):
            temp_img_path = st.session_state.upscaled_img_path
        else:
            temp_img_path = temp_img_path_original

        # PASO A: ANALIZAR CON IA
        if st.button("Analizar Comprobante con IA", use_container_width=True):
            with st.spinner("Analizando comprobante..."):
                try:
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

            st.markdown("#### Datos adicionales para copiar a Excel")
            col_ex1, col_ex2, col_ex3 = st.columns(3)
            with col_ex1:
                ai_metodo = st.session_state.ai_results.get('metodo', 'TRANSFERENCIA').strip().upper()
                default_index = 0
                if ai_metodo == "CONSIGNACION":
                    default_index = 1
                metodo_excel = st.selectbox("Método:", ["TRANSFERENCIA", "CONSIGNACION"], index=default_index)
            with col_ex2:
                cuenta_excel = st.text_input("Cuenta / Referencia Excel:", value=comprobante_final)
            with col_ex3:
                ai_banco = st.session_state.ai_results.get('banco', 'BANCOLOMBIA').strip().upper()
                lugar_excel = st.text_input("Lugar (Entidad):", value=ai_banco)

            valor_final = val_base
            if val_obs:
                valor_final = f"{val_base} ({val_obs})"

            # PASO C: GENERAR DOCUMENTO
            if st.button("Generar Recibo Word", type="primary", use_container_width=True):
                with st.spinner("Creando archivo Word..."):
                    try:
                        template_path = config.get("template_path", "118673 - VILMA BEJARANO_FEB 2026.docx")
                        # Usar la imagen mejorada si el usuario la seleccionó
                        if st.session_state.use_upscaled and st.session_state.upscaled_img_path and os.path.exists(st.session_state.upscaled_img_path):
                            temp_img_path = st.session_state.upscaled_img_path
                        else:
                            temp_img_path = temp_img_path_original

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
                            "correo": "" if str(sponsor_data.get('Correo Electronico', '')).lower() in ('nan', 'none', '') else str(sponsor_data.get('Correo Electronico', '')),
                            "valor": valor_final,
                            "fecha": fecha_final,
                            "comprobante": comprobante_final,
                            "mes": str(mes_final).upper(),
                            "ninos": str(ninos),
                            "ano_patrocinio": str(ano_patrocinio),
                            "alineacion": image_alignment
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
                        # Datos para registro en Google Sheets
                        # Extraer año de la fecha del comprobante (formato DD/MM/AAAA)
                        _año = ""
                        try:
                            _año = str(fecha_final).strip().split("/")[-1].split("-")[-1][:4]
                        except Exception:
                            pass
                        st.session_state.sheets_payload = {
                            "zona": selected_zone,
                            "cedula": str(sponsor_data.get('Cédula / NIT', '')).replace('.0', '').strip(),
                            "mes": str(mes_final).strip().upper(),
                            "año": _año,
                            "valor": val_base,
                            "metodo": metodo_excel,
                            "comprobante": comprobante_final,
                            "banco": lugar_excel,
                            "fecha": fecha_final,
                        }
                        st.session_state.sheets_registrado = False

                        st.success("Recibo generado correctamente.")

                        # Copiar al portapapeles
                        # Formato: valor  metodo  cuenta/referencia  lugar  fecha  ano_patrocinio  comprobante
                        excel_text = f"{val_base}\t{metodo_excel}\t{cuenta_excel}\t{lugar_excel}\t{fecha_final}\t{ano_patrocinio}\t{comprobante_final}"
                        try:
                            import subprocess
                            # Usar el comando clip de powershell/cmd en Windows en utf-16
                            process = subprocess.Popen(['clip'], stdin=subprocess.PIPE, shell=True)
                            process.communicate(excel_text.encode('utf-16'))
                            st.info(f"📋 ¡Fila copiada al portapapeles de Excel exitosamente!\nDatos: `{excel_text}`")
                        except Exception as e:
                            st.warning(f"No se pudo copiar automáticamente al portapapeles. Selecciónalo y copia manualmente:\n\n{excel_text}")

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
                sponsor_folder = find_sponsor_folder(st.session_state.sponsor_name, dynamic_base_folder)
                if not sponsor_folder:
                    st.error(f"No se encontró la carpeta de **{st.session_state.sponsor_name}** en la ruta base proporcionada ni en Inactivos.")
                else:
                    try:
                        # Estructura: CONSIGNACIONES / PATROCINIO [RANGO] / [MES]
                        consignaciones_dir = os.path.join(sponsor_folder, "CONSIGNACIONES")
                        os.makedirs(consignaciones_dir, exist_ok=True)

                        # Buscar carpeta existente para evitar duplicar por culpa de prefijos numéricos ("2.PATROCINIO...")
                        periodo_dir = None
                        target_year = str(st.session_state.ano_patrocinio).strip().upper()

                        for f in os.listdir(consignaciones_dir):
                            path_f = os.path.join(consignaciones_dir, f)
                            if os.path.isdir(path_f) and "PATROCINIO" in f.upper() and target_year in f.upper():
                                periodo_dir = path_f
                                break

                        # Si no la encuentra, la crea limpia
                        if not periodo_dir:
                            periodo_dir = os.path.join(consignaciones_dir, f"PATROCINIO {target_year}")

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
                                    st.success(f"PDF generado y guardado en:\n`{pdf_save_path}`")

                                    # ── Subida automática a Supabase ──
                                    _sb_key = config.get("supabase_key", "").strip()
                                    if _sb_key:
                                        with st.spinner(f"Subiendo recibo a Supabase · zona {selected_zone}..."):
                                            try:
                                                from supabase_uploader import upload_receipt as _sb_upload
                                                _año_sb = ""
                                                try:
                                                    _año_sb = str(fecha_final).strip().split("/")[-1].split("-")[-1][:4]
                                                except Exception:
                                                    pass
                                                _sb_r = _sb_upload(
                                                    pdf_path=pdf_save_path,
                                                    zona=selected_zone,
                                                    patrocinador=str(st.session_state.sponsor_name),
                                                    cedula=str(sponsor_data.get("Cédula / NIT", "")).replace(".0", "").strip(),
                                                    mes=str(st.session_state.mes_final).strip().upper(),
                                                    año=_año_sb,
                                                    valor=val_base,
                                                    metodo=metodo_excel,
                                                    comprobante=comprobante_final,
                                                    banco=lugar_excel,
                                                    fecha_aporte=fecha_final,
                                                    secret_key=_sb_key,
                                                )
                                                if _sb_r["success"]:
                                                    st.success(f"Recibo subido al repositorio central. [Ver PDF]({_sb_r['url']})")
                                                else:
                                                    st.warning(f"Guardado local OK, pero no se pudo subir a Supabase: {_sb_r.get('error', '')}")
                                            except ImportError:
                                                st.info("Instala `supabase` para subida automática al repositorio central.")
                                    else:
                                        st.info("Configura la Clave Supabase para subir al repositorio central.")
                                except Exception as pdf_err:
                                    st.warning(f"Word guardado. Conversión a PDF falló: {pdf_err}")
                        else:
                            st.warning("El archivo Word fue guardado. La conversión automática a PDF no está disponible ('docx2pdf' no instalada) pero el proceso ha terminado.")

                        st.success(f"Proceso concluido exitosamente.\n\nCarpeta destino: `{final_dir}`")

                    except Exception as save_err:
                        st.error(f"Error al guardar: {str(save_err)}")

        # ── Registrar en Google Sheets ────────────────────────────────────────
        _SHEET_ID = "1wLzWVFWMtfI3vmHbg6vywYdvj3wCpGysqs4hG1C55Js"
        _SA_FILE = os.path.join(os.path.dirname(__file__), "service_account.json")
        if os.path.exists(_SA_FILE) and st.session_state.get("sheets_payload"):
            st.markdown("---")
            _payload = st.session_state.sheets_payload
            if st.session_state.get("sheets_registrado"):
                st.success(
                    f"✅ Ya registrado en Google Sheets — "
                    f"{_payload.get('mes')} · {_payload.get('valor')} · {_payload.get('comprobante')}"
                )
            else:
                st.markdown(
                    f"**Registrar en Google Sheets:** `{_payload.get('zona')}` · "
                    f"`{_payload.get('mes')}` · valor `{_payload.get('valor')}`"
                )
                if st.button("📊 Registrar en Google Sheets", use_container_width=True, key="btn_sheets"):
                    try:
                        import gspread
                        from google.oauth2.service_account import Credentials
                        _scopes = [
                            "https://www.googleapis.com/auth/spreadsheets",
                            "https://www.googleapis.com/auth/drive",
                        ]
                        _creds = Credentials.from_service_account_file(_SA_FILE, scopes=_scopes)
                        _gc = gspread.authorize(_creds)
                        _sh = _gc.open_by_key(_SHEET_ID)
                        _zona = _payload.get("zona", "").lower().replace(" ", "-")
                        try:
                            _ws = _sh.worksheet(_zona)
                        except gspread.WorksheetNotFound:
                            _ws = _sh.sheet1
                        _fila = [
                            _payload.get("fecha", ""),
                            _payload.get("cedula", ""),
                            _payload.get("zona", ""),
                            _payload.get("mes", ""),
                            _payload.get("año", ""),
                            _payload.get("valor", ""),
                            _payload.get("metodo", ""),
                            _payload.get("banco", ""),
                            _payload.get("comprobante", ""),
                        ]
                        _ws.append_row(_fila, value_input_option="USER_ENTERED")
                        st.session_state.sheets_registrado = True
                        st.success("✅ Registrado en Google Sheets correctamente.")
                        st.rerun()
                    except Exception as _se:
                        st.error(f"No se pudo registrar en Google Sheets: {_se}")


with tab_antecedentes:
    # -----------------------------------------------------
    # SECCIÓN 5: CONSULTA DE ANTECEDENTES
    # -----------------------------------------------------
    st.markdown("---")
    st.markdown('<h2 style="text-align:center; color:#1e293b;">Consulta de Antecedentes</h2>', unsafe_allow_html=True)

    with st.container(border=True):
        st.subheader("5. Consulta de Antecedentes de Patrocinadores")
        st.caption(
            "Consulta automatizada de antecedentes judiciales, OFAC, fiscales y disciplinarios. "
            "Los PDFs se guardan en la carpeta de Descargas con el nombre del patrocinador. "
            "Vigencia: 3 meses."
        )

        # ---- PANEL DE ALERTAS DE VIGENCIA ----
        import re as _re_alerts
        log_antecedentes = cargar_log()
        fuentes_check = {"policia": "Policia", "ofac": "OFAC", "contraloria": "Contraloria", "procuraduria": "Procuraduria"}

        vencidos = []      # ya vencidos
        por_vencer = []    # vencen en 15 dias o menos
        sin_registro = 0   # nunca consultados

        for _, row in df_sponsors.iterrows():
            ced_raw = str(row.get('Cédula / NIT', '')).replace('.0', '').strip()
            ced_clean = _re_alerts.sub(r'[^0-9]', '', ced_raw)
            nombre_pat = str(row.get('Patrocinador', ''))

            if not ced_clean or ced_clean == 'nan':
                continue

            # Buscar en el log con la cédula (puede estar con o sin limpiar)
            log_entry = log_antecedentes.get(ced_clean) or log_antecedentes.get(ced_raw)

            if not log_entry:
                sin_registro += 1
                continue

            consultas = log_entry.get("consultas", {})
            for fuente_key, fuente_label in fuentes_check.items():
                vigente, fecha_consulta, dias = obtener_vigencia(ced_clean, fuente_key)
                if vigente is None:
                    # Intentar con cédula sin limpiar
                    vigente, fecha_consulta, dias = obtener_vigencia(ced_raw, fuente_key)

                if vigente is not None:
                    if not vigente:
                        vencidos.append((nombre_pat, ced_clean, fuente_label, fecha_consulta, dias))
                    elif dias is not None and dias <= 15:
                        por_vencer.append((nombre_pat, ced_clean, fuente_label, fecha_consulta, dias))

        # Mostrar alertas
        if vencidos or por_vencer:
            st.markdown("#### Alertas de Vigencia")

            if vencidos:
                with st.expander(f"🔴 {len(vencidos)} antecedente(s) VENCIDO(S)", expanded=True):
                    for nombre_v, ced_v, fuente_v, fecha_v, dias_v in vencidos:
                        st.error(f"**{nombre_v}** (CC: {ced_v}) — {fuente_v}: vencido hace {abs(dias_v)} dias (consultado: {fecha_v})")

            if por_vencer:
                with st.expander(f"🟡 {len(por_vencer)} antecedente(s) por vencer en los proximos 15 dias", expanded=True):
                    for nombre_p, ced_p, fuente_p, fecha_p, dias_p in por_vencer:
                        st.warning(f"**{nombre_p}** (CC: {ced_p}) — {fuente_p}: vence en {dias_p} dias (consultado: {fecha_p})")

            st.markdown("---")
        elif log_antecedentes:
            st.success("Todos los antecedentes registrados estan vigentes.")

        if sin_registro > 0 and not log_antecedentes:
            st.info(f"Aun no hay antecedentes registrados. Selecciona patrocinadores abajo para consultar.")

        # Multiselect de patrocinadores
        if not df_sponsors.empty:
            opciones_ant = sorted([
                s for s in (str(x) for x in df_sponsors['Dropdown_Label'])
                if s and s not in ('nan - CC: nan', 'nan', 'None', '')
            ])
            seleccionados_ant = st.multiselect(
                "Selecciona los patrocinadores a consultar:",
                opciones_ant,
                help="Puedes seleccionar multiples patrocinadores"
            )

            # Fuentes a consultar
            st.markdown("**Fuentes a consultar:**")
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                chk_policia = st.checkbox("Policia Nacional (Antecedentes Judiciales)", value=True)
                chk_ofac = st.checkbox("OFAC (Lista Clinton)", value=True)
            with col_f2:
                chk_contraloria = st.checkbox("Contraloria (Antecedentes Fiscales)", value=True)
                chk_procuraduria = st.checkbox("Procuraduria (Antecedentes Disciplinarios)", value=True)

            # Mostrar vigencia de los seleccionados
            if seleccionados_ant:
                st.markdown("#### Estado de vigencia")
                fuentes_nombres = {
                    "policia": "Policia",
                    "ofac": "OFAC",
                    "contraloria": "Contraloria",
                    "procuraduria": "Procuraduria"
                }
                for sel_label in seleccionados_ant:
                    sel_row = df_sponsors[df_sponsors['Dropdown_Label'] == sel_label].iloc[0]
                    sel_cedula = str(sel_row.get('Cédula / NIT', '')).replace('.0', '').strip()
                    sel_nombre = str(sel_row.get('Patrocinador', ''))

                    with st.expander(f"{sel_nombre} - CC: {sel_cedula}"):
                        for fuente_key, fuente_label in fuentes_nombres.items():
                            vigente, fecha, dias = obtener_vigencia(sel_cedula, fuente_key)
                            if vigente is None:
                                st.markdown(f"- {fuente_label}: Sin registro")
                            elif vigente:
                                st.markdown(f"- {fuente_label}: Vigente hasta {dias} dias (consultado: {fecha})")
                            else:
                                st.markdown(f"- {fuente_label}: **VENCIDO** (consultado: {fecha})")

            # Botón de consulta
            if seleccionados_ant:
                fuentes_sel = []
                if chk_policia:
                    fuentes_sel.append("policia")
                if chk_ofac:
                    fuentes_sel.append("ofac")
                if chk_contraloria:
                    fuentes_sel.append("contraloria")
                if chk_procuraduria:
                    fuentes_sel.append("procuraduria")

                if not fuentes_sel:
                    st.warning("Selecciona al menos una fuente de antecedentes.")
                else:
                    tiene_contraloria = "contraloria" in fuentes_sel
                    if tiene_contraloria:
                        st.info(
                            "La Contraloria requiere resolver un reCAPTCHA manualmente. "
                            "Se abrira una ventana de Chrome donde deberas hacer click en "
                            "'No soy un robot' y luego en 'Buscar'. El sistema esperara hasta que completes el proceso."
                        )

                    if st.button("Consultar Antecedentes Seleccionados", use_container_width=True, type="primary"):
                        # Preparar lista de patrocinadores
                        lista_pat = []
                        for sel_label in seleccionados_ant:
                            sel_row = df_sponsors[df_sponsors['Dropdown_Label'] == sel_label].iloc[0]
                            lista_pat.append({
                                "nombre": str(sel_row.get('Patrocinador', '')),
                                "cedula": str(sel_row.get('Cédula / NIT', '')).replace('.0', '').strip()
                            })

                        # Ejecutar consultas con progreso
                        progress_bar = st.progress(0)
                        status_area = st.empty()
                        log_area = st.container()
                        mensajes = []

                        def callback_progreso(mensaje, progreso=None):
                            mensajes.append(mensaje)
                            status_area.info(mensaje)
                            if progreso is not None:
                                progress_bar.progress(min(progreso, 1.0))

                        resultados = consultar_todos(lista_pat, fuentes_sel, callback_progreso)
                        progress_bar.progress(1.0)
                        status_area.empty()

                        # Mostrar resultados
                        st.markdown("### Resultados")
                        for ced, info in resultados.items():
                            nombre_r = info["nombre"]
                            carpeta = _output_dir_para_patrocinador(nombre_r)
                            with st.expander(f"{nombre_r} - CC: {ced}", expanded=True):
                                for fuente, res in info["resultados"].items():
                                    if res["exito"]:
                                        st.success(f"{fuente.title()}: {res['detalle']}")
                                    else:
                                        st.error(f"{fuente.title()}: Error - {res['detalle']}")
                                st.info(f"Carpeta: `{carpeta}`")

                        st.success("Proceso de consulta de antecedentes finalizado.")

with tab_revision:
    from revision_aportes import render_revision_tab
    render_revision_tab(config, dynamic_base_folder, df_sponsors, excel_path, selected_zone)

with tab_importar:
    st.markdown("### 📥 Importar Patrocinador Nuevo")
    st.caption(
        "Importa la carpeta descargada de Google Drive y registra los datos del patrocinador "
        "para que quede disponible en el generador de recibos."
    )

    with st.container(border=True):
        st.markdown(f"**Zona destino:** `{selected_zone}`")
        st.markdown(f"**Carpeta local:** `{dynamic_base_folder}`")
        if not os.path.exists(dynamic_base_folder):
            st.error("La carpeta de zona no existe. Verifica la configuración del sistema.")

    # ── PASO 1: Importar carpeta ──────────────────────────────────────────────
    with st.container(border=True):
        st.subheader("Paso 1 — Importar carpeta desde Drive")

        if "import_src" not in st.session_state:
            st.session_state.import_src = ""
        if "import_folder_done" not in st.session_state:
            st.session_state.import_folder_done = False

        ci1, ci2 = st.columns([5, 1])
        with ci1:
            import_src_val = st.text_input(
                "Ruta de la carpeta del patrocinador (descargada de Drive):",
                value=st.session_state.import_src,
                placeholder="Ej: C:/Users/TuUsuario/Downloads/NOMBRE PATROCINADOR",
                key="import_src_input"
            )
            st.session_state.import_src = import_src_val
        with ci2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("📂 Buscar", key="btn_import_browse"):
                import subprocess as _sp
                _ps = (
                    "Add-Type -AssemblyName System.Windows.Forms; "
                    "$f = New-Object System.Windows.Forms.FolderBrowserDialog; "
                    "$f.RootFolder = 'MyComputer'; "
                    "[void]$f.ShowDialog(); "
                    "$f.SelectedPath"
                )
                _r2 = _sp.run(["powershell", "-NoProfile", "-Command", _ps], capture_output=True, text=True)
                _res = _r2.stdout.strip()
                if _res and os.path.exists(_res):
                    st.session_state.import_src = _res
                    st.session_state.import_folder_done = False
                    st.rerun()
                elif _r2.returncode != 0:
                    st.error("No se pudo abrir el selector. Escribe la ruta manualmente.")

        src = st.session_state.import_src.strip()

        if src and os.path.isdir(src):
            folder_name = os.path.basename(src)
            dest = os.path.join(dynamic_base_folder, folder_name)

            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("**Carpeta a importar:**")
                st.code(folder_name)
            with col_b:
                st.markdown("**Se copiará a:**")
                st.code(dest)

            try:
                items = sorted(os.listdir(src))
                with st.expander(f"Contenido de la carpeta ({len(items)} elemento(s))"):
                    for item in items:
                        icon = "📁" if os.path.isdir(os.path.join(src, item)) else "📄"
                        st.markdown(f"{icon}&nbsp;&nbsp;{item}")
            except Exception:
                pass

            if os.path.exists(dest):
                st.warning(
                    f"⚠️ Ya existe una carpeta **{folder_name}** en esta zona. "
                    "Los archivos nuevos se agregarán sin sobreescribir los existentes."
                )

            if st.session_state.import_folder_done:
                st.success(f"✅ Carpeta **{folder_name}** ya importada.")
            else:
                if st.button("📥 Importar carpeta", type="primary", use_container_width=True, key="btn_do_import"):
                    with st.spinner("Copiando carpeta..."):
                        try:
                            shutil.copytree(src, dest, dirs_exist_ok=True)
                            st.session_state.import_folder_done = True
                            # Pre-rellenar nombre sugerido para el formulario
                            st.session_state.import_nombre_sugerido = folder_name.title()
                            st.rerun()
                        except Exception as imp_err:
                            st.error(f"Error al importar: {imp_err}")

        elif src and not os.path.isdir(src):
            st.error("La ruta indicada no existe o no es una carpeta válida.")

    # ── PASO 2: Registrar datos ───────────────────────────────────────────────
    with st.container(border=True):
        st.subheader("Paso 2 — Registrar datos del patrocinador")
        st.caption(
            "Completa los datos para que el patrocinador aparezca en el generador de recibos. "
            "Solo Nombre y Cédula son obligatorios."
        )

        nombre_sug = st.session_state.get("import_nombre_sugerido", "")

        with st.form("form_nuevo_patrocinador"):
            fc1, fc2 = st.columns(2)
            with fc1:
                fn_nombre = st.text_input("Nombre completo *", value=nombre_sug, placeholder="VALENTINA MUÑOZ GARCIA")
                fn_cedula = st.text_input("Cédula / NIT *", placeholder="12345678")
                fn_municipio = st.text_input("Municipio / Foro", placeholder="CALI")
            with fc2:
                fn_telefono = st.text_input("Teléfono", placeholder="3001234567")
                fn_correo = st.text_input("Correo electrónico", placeholder="correo@ejemplo.com")
                fn_ninos = st.text_input("N° de niños patrocinados", value="1")

            submitted = st.form_submit_button("💾 Registrar patrocinador", type="primary", use_container_width=True)

        if submitted:
            if not fn_nombre.strip() or not fn_cedula.strip():
                st.error("Nombre y Cédula son obligatorios.")
            else:
                save_local_sponsor(selected_zone, {
                    "Patrocinador": fn_nombre.strip().upper(),
                    "Cédula / NIT": fn_cedula.strip().replace(".0", ""),
                    "MUNICIPIO/FORO": fn_municipio.strip().upper(),
                    "Teléfono": fn_telefono.strip(),
                    "Correo Electronico": fn_correo.strip(),
                    "NÚMERO DE PATROCINIOS": fn_ninos.strip(),
                })
                st.success(
                    f"✅ **{fn_nombre.strip().upper()}** registrado correctamente en la zona **{selected_zone}**. "
                    "Ya aparece en el generador de recibos."
                )
                st.session_state.import_src = ""
                st.session_state.import_folder_done = False
                st.session_state.import_nombre_sugerido = ""
                st.cache_data.clear()
                st.rerun()

    # ── Patrocinadores registrados localmente ─────────────────────────────────
    _locales = load_local_sponsors(selected_zone)
    if not _locales.empty:
        with st.container(border=True):
            st.subheader("Patrocinadores registrados localmente en esta zona")
            st.caption("Estos patrocinadores fueron añadidos manualmente y no están en el Excel.")
            for _, lr in _locales.iterrows():
                lc1, lc2 = st.columns([5, 1])
                with lc1:
                    st.markdown(
                        f"**{lr['Patrocinador']}** — CC: {lr['Cédula / NIT']} "
                        f"| Tel: {lr.get('Teléfono','') or '—'} "
                        f"| {lr.get('MUNICIPIO/FORO','') or '—'}"
                    )
                with lc2:
                    if st.button("🗑️ Eliminar", key=f"del_local_{lr['Cédula / NIT']}"):
                        delete_local_sponsor(selected_zone, lr["Cédula / NIT"])
                        st.cache_data.clear()
                        st.rerun()
