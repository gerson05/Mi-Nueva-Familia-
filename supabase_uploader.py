"""
supabase_uploader.py
--------------------
Sube PDFs de recibos a Supabase Storage y registra los aportes en la tabla `aportes`.

Estructura Storage:
  bucket: recibos
  path:   {zona}/{patrocinador}/{filename}

Tabla `aportes` (crear en Supabase SQL Editor):
  create table aportes (
    id uuid default gen_random_uuid() primary key,
    created_at timestamptz default now(),
    zona text not null,
    patrocinador text not null,
    cedula text,
    mes text,
    año text,
    valor text,
    metodo text,
    comprobante text,
    banco text,
    fecha_aporte text,
    filename text,
    storage_path text,
    public_url text
  );
"""

import os

SUPABASE_URL = "https://xhigifzmylcaxkxzqzom.supabase.co"
BUCKET = "recibos"


def _client(secret_key: str):
    from supabase import create_client
    return create_client(SUPABASE_URL, secret_key)


def upload_receipt(
    pdf_path: str,
    zona: str,
    patrocinador: str,
    cedula: str,
    mes: str,
    año: str,
    valor: str,
    metodo: str,
    comprobante: str,
    banco: str,
    fecha_aporte: str,
    secret_key: str,
) -> dict:
    """
    Sube PDF a Storage y registra en tabla aportes.
    Retorna {"success": bool, "url": str, "error": str}
    """
    try:
        sb = _client(secret_key)
        filename = os.path.basename(pdf_path)

        # Ruta dentro del bucket: zona/patrocinador/archivo.pdf
        zona_clean = zona.strip().upper()
        pat_clean = patrocinador.strip().upper()
        storage_path = f"{zona_clean}/{pat_clean}/{filename}"

        # Subir PDF
        with open(pdf_path, "rb") as f:
            sb.storage.from_(BUCKET).upload(
                path=storage_path,
                file=f,
                file_options={"content-type": "application/pdf", "upsert": "true"},
            )

        # URL pública
        public_url = sb.storage.from_(BUCKET).get_public_url(storage_path)

        # Registrar en tabla aportes
        sb.table("aportes").insert({
            "zona": zona_clean,
            "patrocinador": pat_clean,
            "cedula": cedula,
            "mes": mes.strip().upper() if mes else "",
            "año": año,
            "valor": valor,
            "metodo": metodo,
            "comprobante": comprobante,
            "banco": banco,
            "fecha_aporte": fecha_aporte,
            "filename": filename,
            "storage_path": storage_path,
            "public_url": public_url,
        }).execute()

        return {"success": True, "url": public_url}

    except Exception as e:
        return {"success": False, "error": str(e)}


def upload_antecedente(
    pdf_path: str,
    zona: str,
    patrocinador: str,
    cedula: str,
    fuente: str,
    fecha_consulta: str,
    secret_key: str,
) -> dict:
    """
    Sube PDF de antecedente a Storage y registra en tabla antecedentes.
    fuente: policia | procuraduria | contraloria | ofac
    fecha_consulta: string YYYY-MM-DD
    Retorna {"success": bool, "url": str, "error": str}
    """
    try:
        from datetime import date, timedelta
        sb = _client(secret_key)
        filename = os.path.basename(pdf_path)
        zona_clean = zona.strip().upper()
        pat_clean = patrocinador.strip().upper()

        storage_path = f"{zona_clean}/{pat_clean}-{cedula}/antecedentes/{fuente}/{filename}"

        with open(pdf_path, "rb") as f:
            sb.storage.from_(BUCKET).upload(
                path=storage_path,
                file=f,
                file_options={"content-type": "application/pdf", "upsert": "true"},
            )

        public_url = sb.storage.from_(BUCKET).get_public_url(storage_path)

        # Calcular vencimiento: 90 días desde consulta
        fecha_dt = date.fromisoformat(fecha_consulta)
        fecha_vencimiento = (fecha_dt + timedelta(days=90)).isoformat()

        sb.table("antecedentes").insert({
            "zona": zona_clean,
            "patrocinador": pat_clean,
            "cedula": cedula,
            "fuente": fuente.lower(),
            "fecha_consulta": fecha_consulta,
            "fecha_vencimiento": fecha_vencimiento,
            "storage_path": storage_path,
            "public_url": public_url,
        }).execute()

        return {"success": True, "url": public_url}

    except Exception as e:
        return {"success": False, "error": str(e)}


def load_antecedentes_patrocinador(cedula: str, secret_key: str) -> list:
    """Retorna antecedentes de un patrocinador ordenados por fecha desc."""
    try:
        sb = _client(secret_key)
        res = (
            sb.table("antecedentes")
            .select("*")
            .eq("cedula", cedula)
            .order("fecha_consulta", desc=True)
            .execute()
        )
        return res.data or []
    except Exception:
        return []


def load_zone_receipts(zona: str, secret_key: str) -> list:
    """
    Retorna lista de aportes de una zona desde la tabla aportes.
    """
    try:
        sb = _client(secret_key)
        res = (
            sb.table("aportes")
            .select("*")
            .eq("zona", zona.strip().upper())
            .order("created_at", desc=True)
            .execute()
        )
        return res.data or []
    except Exception:
        return []
