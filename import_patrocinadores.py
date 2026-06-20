"""
Script de importación masiva de patrocinadores desde la carpeta TRONCAL.
Extrae nombre, período de patrocinio, sube el FP a Supabase y registra en BD.
Uso: python import_patrocinadores.py
"""

import os
import re
import json
import sys
from datetime import date
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────────
BASE_TRONCAL = Path(r"C:\Users\gdjhb.GERSON\Downloads\proyecto mnf\TRONCAL-MI NUEVA FAMILIA")
ZONA = "CALI - TRONCAL"
SUPABASE_URL = "https://xhigifzmylcaxkxzqzom.supabase.co"
BUCKET = "recibos"

CONFIG_PATH = Path(__file__).parent / "config.json"
try:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        _cfg = json.load(f)
    SUPABASE_KEY = _cfg.get("supabase_key", "").strip()
except Exception:
    SUPABASE_KEY = ""

if not SUPABASE_KEY:
    print("ERROR: supabase_key no encontrado en config.json")
    sys.exit(1)

try:
    from supabase import create_client
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
except ImportError:
    print("ERROR: pip install supabase")
    sys.exit(1)

# ── Mapeo de meses ───────────────────────────────────────────────────────────
MES_MAP = {
    "ENE": 1, "ENERO": 1,
    "FEB": 2, "FEBRERO": 2,
    "MAR": 3, "MARZO": 3,
    "ABR": 4, "ABRIL": 4,
    "MAY": 5, "MAYO": 5,
    "JUN": 6, "JUNIO": 6,
    "JUL": 7, "JULIO": 7,
    "AGO": 8, "AGOSTO": 8,
    "SEP": 9, "SEPT": 9, "SEPTIEMBRE": 9,
    "OCT": 10, "OCTUBRE": 10,
    "NOV": 11, "N0V": 11, "NOVIEMBRE": 11,  # N0V con cero
    "DIC": 12, "DIC.": 12, "DICIEMBRE": 12,
}

def parse_mes_año(texto):
    """Extrae (mes:int, año:int) de un fragmento de texto como 'SEP 2025' o 'NOVIEMBRE - 2024'."""
    texto = texto.strip().upper().replace("-", " ").replace(".", "")
    tokens = texto.split()
    mes, año = None, None
    for t in tokens:
        t_clean = t.strip()
        if t_clean in MES_MAP:
            mes = MES_MAP[t_clean]
        elif t_clean.isdigit() and len(t_clean) == 4:
            año = int(t_clean)
    return mes, año

def parse_periodo(nombre_carpeta):
    """
    Extrae (fecha_inicio, fecha_fin) de nombres como:
      PATROCINIO SEP 2025 - AGO 2026
      PATROCINIO N0V 2025- OCT 2026
      JUNIO 2025- MAYO 2026
      DIC 2024 - NOV 2025
    Retorna (None, None) si no se puede parsear.
    """
    nombre = nombre_carpeta.upper()
    # quitar prefijo PATROCINIO / PATRCINIO
    nombre = re.sub(r"PATR[A-Z]*\s*", "", nombre).strip()

    # separar por " - " o por "-" (con posibles espacios)
    partes = re.split(r"\s*-\s*", nombre, maxsplit=1)
    if len(partes) < 2:
        return None, None

    m1, a1 = parse_mes_año(partes[0])
    m2, a2 = parse_mes_año(partes[1])

    if None in (m1, a1, m2, a2):
        return None, None

    return date(a1, m1, 1), date(a2, m2, 1)

def es_carpeta_patrocinio(nombre):
    n = nombre.upper()
    return any(k in n for k in ["PATROCINIO", "PATRCINIO", "PATROCIO"]) or \
           re.search(r"(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC|ENERO|FEBRERO|MARZO|ABRIL|MAYO|JUNIO|JULIO|AGOSTO|SEPTIEMBRE|OCTUBRE|NOVIEMBRE|DICIEMBRE)\s+\d{4}", n, re.I)

def carpeta_mas_reciente(ruta_docs):
    """Retorna la subcarpeta más reciente (por fecha_fin) dentro de DOCUMENTOS."""
    candidatos = []
    if not ruta_docs.exists():
        return None, None, None
    for item in ruta_docs.iterdir():
        if item.is_dir() and es_carpeta_patrocinio(item.name):
            inicio, fin = parse_periodo(item.name)
            if fin:
                candidatos.append((fin, inicio, item))
    if not candidatos:
        return None, None, None
    candidatos.sort(key=lambda x: x[0], reverse=True)
    fin, inicio, carpeta = candidatos[0]
    return inicio, fin, carpeta

def buscar_fp(carpeta):
    """Busca el archivo FP (Formato de Postulación) en la carpeta."""
    if not carpeta or not carpeta.exists():
        return None
    # Primero: archivo que empiece con FP
    for f in carpeta.iterdir():
        if f.is_file() and f.name.upper().startswith("FP") and f.suffix.lower() == ".pdf":
            return f
    # Segundo: *_compressed.pdf
    for f in carpeta.iterdir():
        if f.is_file() and "compressed" in f.name.lower() and f.suffix.lower() == ".pdf":
            return f
    return None

def upload_fp(nombre_pat, fp_path):
    """Sube el FP a Supabase Storage y retorna (storage_path, public_url)."""
    nombre_safe = re.sub(r"[^a-zA-Z0-9._-]", "_", nombre_pat)
    filename = fp_path.name
    storage_path = f"{ZONA}/patrocinadores/{nombre_safe}/FP_{nombre_safe}.pdf"
    with open(fp_path, "rb") as f:
        data = f.read()
    try:
        sb.storage.from_(BUCKET).upload(storage_path, data, {"upsert": "true", "content-type": "application/pdf"})
    except Exception as e:
        if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
            pass  # ya existe, seguimos
        else:
            print(f"  ⚠ Storage error: {e}")
            return None, None
    public_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{storage_path}"
    return storage_path, public_url

def ya_existe(nombre):
    """Verifica si el patrocinador ya está en la BD."""
    res = sb.table("patrocinadores").select("id").ilike("nombre", nombre.strip()).execute()
    return len(res.data) > 0

def procesar_carpeta(carpeta_pat, estado="activo"):
    nombre = carpeta_pat.name.strip()
    # Ignorar carpetas especiales
    if nombre.startswith("1.") or nombre.startswith("Formato"):
        return

    print(f"\n{'activo' if estado == 'activo' else 'INACTIVO'} → {nombre}")

    if ya_existe(nombre):
        print("  → Ya existe en BD, omitiendo")
        return

    ruta_docs = carpeta_pat / "DOCUMENTOS"
    inicio, fin, carpeta_periodo = carpeta_mas_reciente(ruta_docs)

    if inicio and fin:
        print(f"  Período: {inicio.strftime('%b %Y')} → {fin.strftime('%b %Y')}")
    else:
        print("  ⚠ No se pudo detectar período de patrocinio")

    fp_path = buscar_fp(carpeta_periodo)
    storage_path, public_url = None, None

    if fp_path:
        print(f"  FP: {fp_path.name}")
        storage_path, public_url = upload_fp(nombre, fp_path)
        if storage_path:
            print(f"  ✓ FP subido")
    else:
        print("  ⚠ No se encontró archivo FP")

    registro = {
        "nombre": nombre,
        "zona": ZONA,
        "estado": estado,
        "fecha_inicio_patrocinio": inicio.isoformat() if inicio else None,
        "fecha_fin_patrocinio": fin.isoformat() if fin else None,
        "fp_storage_path": storage_path,
        "fp_public_url": public_url,
    }

    try:
        sb.table("patrocinadores").insert(registro).execute()
        print(f"  ✓ Registrado en BD")
    except Exception as e:
        print(f"  ✗ Error BD: {e}")

# ── Ejecución ────────────────────────────────────────────────────────────────
print("=" * 60)
print("IMPORTANDO PATROCINADORES TRONCAL")
print("=" * 60)

# Activos
for carpeta in sorted(BASE_TRONCAL.iterdir()):
    if carpeta.is_dir() and carpeta.name != "1. INACTIVOS":
        procesar_carpeta(carpeta, estado="activo")

# Inactivos
inactivos_path = BASE_TRONCAL / "1. INACTIVOS"
if inactivos_path.exists():
    print("\n--- INACTIVOS ---")
    for carpeta in sorted(inactivos_path.iterdir()):
        if carpeta.is_dir():
            procesar_carpeta(carpeta, estado="inactivo")

print("\n" + "=" * 60)
print("IMPORTACION COMPLETADA")
print("=" * 60)
