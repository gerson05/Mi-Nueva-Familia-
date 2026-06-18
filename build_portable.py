"""
build_portable.py
-----------------
Empaqueta "Mi Nueva Familia" en una versión portable para Windows.
Estructura generada:
  MiNuevaFamilia-Portable/
    INICIAR.bat
    REPARAR_32BIT.bat
    python/           ← Python 3.10 embeddable + dependencias
    app/              ← código fuente (.py, .json de logs)
    datos/            ← Excel de transacciones + plantilla Word
    config.json       ← configuración (rutas, API key)
    hf_config.json
"""

import os
import sys
import shutil
import urllib.request
import zipfile
import subprocess
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORTABLE_DIR = os.path.join(BASE_DIR, "MiNuevaFamilia-Portable")
PYTHON_DIR = os.path.join(PORTABLE_DIR, "python")
APP_DIR = os.path.join(PORTABLE_DIR, "app")
DATOS_DIR = os.path.join(PORTABLE_DIR, "datos")

PYTHON_ARCH = "amd64"
PYTHON_ZIP_URL = f"https://www.python.org/ftp/python/3.10.11/python-3.10.11-embed-{PYTHON_ARCH}.zip"
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"

REQUIREMENTS = [
    "typing_extensions",
    "packaging",
    "streamlit",
    "python-docx",
    "python-calamine",
    "Pillow",
    "google-generativeai",
    "docx2pdf",
    "selenium",
    "webdriver-manager",
    "gradio_client",
    "openpyxl",
    "gspread",
    "google-auth",
    "google-api-python-client",
]

def print_step(msg):
    print("\n" + "=" * 60)
    print(f" >>> {msg}")
    print("=" * 60 + "\n")

def main():
    # 1. Limpiar compilaciones anteriores
    if os.path.exists(PORTABLE_DIR):
        print_step("Limpiando compilaciones anteriores...")
        shutil.rmtree(PORTABLE_DIR)
    os.makedirs(PORTABLE_DIR, exist_ok=True)
    os.makedirs(PYTHON_DIR, exist_ok=True)
    os.makedirs(APP_DIR, exist_ok=True)
    os.makedirs(DATOS_DIR, exist_ok=True)

    # 2. Descargar Python Embeddable
    python_zip_path = os.path.join(BASE_DIR, f"python_embed_{PYTHON_ARCH}.zip")
    if not os.path.exists(python_zip_path):
        print_step(f"Descargando Python 3.10.11 Embeddable ({PYTHON_ARCH})...")
        try:
            urllib.request.urlretrieve(PYTHON_ZIP_URL, python_zip_path)
            print("Python descargado correctamente.")
        except Exception as e:
            print(f"Error al descargar Python: {e}")
            sys.exit(1)
    else:
        print(f"Se encontró {os.path.basename(python_zip_path)} localmente.")

    # 3. Extraer Python Embeddable
    print_step("Extrayendo Python Portable...")
    with zipfile.ZipFile(python_zip_path, 'r') as zip_ref:
        zip_ref.extractall(PYTHON_DIR)
    print("Python extraído en:", PYTHON_DIR)

    # 4. Configurar python310._pth para habilitar site-packages
    print_step("Configurando rutas de Python portable...")
    pth_file = os.path.join(PYTHON_DIR, "python310._pth")
    if not os.path.exists(pth_file):
        print("ERROR: No se encontró python310._pth")
        sys.exit(1)
    with open(pth_file, "r") as f:
        content = f.read()
    if "#import site" in content:
        content = content.replace("#import site", "import site")
    elif "import site" not in content:
        content += "\nimport site\n"
    if "Lib/site-packages" not in content and "Lib\\site-packages" not in content:
        content = content.rstrip("\n") + "\n./Lib/site-packages\n"
    # Agregar carpeta app/ al path para que los imports entre módulos funcionen
    if "./app" not in content and ".\\app" not in content:
        content = content.rstrip("\n") + "\n../app\n"
    with open(pth_file, "w") as f:
        f.write(content)
    print("python310._pth configurado correctamente.")

    # 5. Descargar get-pip.py
    get_pip_path = os.path.join(BASE_DIR, "get-pip.py")
    if not os.path.exists(get_pip_path):
        print_step("Descargando get-pip.py...")
        urllib.request.urlretrieve(GET_PIP_URL, get_pip_path)
    else:
        print("Se encontró get-pip.py localmente.")

    # 6. Instalar pip
    print_step("Instalando pip en Python Portable...")
    portable_python = os.path.join(PYTHON_DIR, "python.exe")
    res = subprocess.run([portable_python, get_pip_path], capture_output=True, text=True)
    if res.returncode != 0:
        print("Error al instalar pip:")
        print(res.stderr)
        sys.exit(1)
    print("pip instalado correctamente.")

    # 7. Instalar dependencias
    print_step("Instalando librerías requeridas (puede tardar varios minutos)...")
    cmd = [portable_python, "-m", "pip", "install", "--no-user", "--prefer-binary", "--no-warn-script-location"] + REQUIREMENTS
    print("Ejecutando:", " ".join(cmd))
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in process.stdout:
        if line.strip():
            print("  " + line.strip())
    rc = process.wait()
    if rc != 0:
        print(f"Error instalando dependencias. Código: {rc}")
        sys.exit(1)
    print("Librerías instaladas.")

    # 8. Copiar código fuente a app/
    print_step("Copiando código fuente a carpeta app/...")
    app_files = [
        "app.py",
        "launcher.py",
        "doc_generator.py",
        "gemini_extractor.py",
        "image_upscaler.py",
        "antecedentes_checker.py",
        "revision_aportes.py",
        "drive_uploader.py",
    ]
    for file_name in app_files:
        src = os.path.join(BASE_DIR, file_name)
        dst = os.path.join(APP_DIR, file_name)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            print(f"  Copiado: app/{file_name}")
        else:
            print(f"  Advertencia: No se encontró {file_name}")

    # Archivos de log/estado van también en app/
    log_files = ["antecedentes_log.json", "revision_log.json", "service_account.json"]
    for file_name in log_files:
        src = os.path.join(BASE_DIR, file_name)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(APP_DIR, file_name))
            print(f"  Copiado: app/{file_name}")

    # 9. Copiar Excel y plantilla Word a datos/
    print_step("Copiando base de datos y plantilla a carpeta datos/...")
    EXCLUIR_PREFIJOS = ("temp_", "test_", "~$")
    default_excel = ""
    default_template = ""

    for file_name in os.listdir(BASE_DIR):
        file_path = os.path.join(BASE_DIR, file_name)
        if os.path.isdir(file_path):
            continue
        # Saltar temporales y archivos de bloqueo de Office
        if any(file_name.startswith(p) for p in EXCLUIR_PREFIJOS):
            continue
        ext = os.path.splitext(file_name)[1].lower()
        is_excel = file_name.upper().startswith("TRANSACCIONES") and ext == ".xlsx"
        is_template = ext == ".docx"
        if is_excel:
            shutil.copy2(file_path, os.path.join(DATOS_DIR, file_name))
            default_excel = f"datos/{file_name}"
            print(f"  Copiado: datos/{file_name}")
        elif is_template:
            shutil.copy2(file_path, os.path.join(DATOS_DIR, file_name))
            if not default_template:
                default_template = f"datos/{file_name}"
            print(f"  Copiado: datos/{file_name}")

    # 10. Leer config del desarrollador para preservar API key
    print_step("Configurando config.json...")
    api_key = ""
    apps_script_url = ""
    dev_config_path = os.path.join(BASE_DIR, "config.json")
    if os.path.exists(dev_config_path):
        try:
            with open(dev_config_path, "r", encoding="utf-8") as f:
                dev_config = json.load(f)
            api_key = dev_config.get("api_key", "")
            apps_script_url = dev_config.get("apps_script_url", "")
        except Exception as e:
            print(f"  No se pudo leer config.json del desarrollador: {e}")

    # Si no encontró excel/template por nombre, buscar en datos/
    if not default_excel:
        for f in os.listdir(DATOS_DIR):
            if f.upper().startswith("TRANSACCIONES") and f.endswith(".xlsx"):
                default_excel = f"datos/{f}"
                break
    if not default_template:
        for f in os.listdir(DATOS_DIR):
            if f.endswith(".docx"):
                default_template = f"datos/{f}"
                break

    config_portable = {
        "excel_path": default_excel,
        "base_folder": "",
        "template_path": default_template,
        "api_key": api_key,
        "apps_script_url": apps_script_url,
    }
    with open(os.path.join(PORTABLE_DIR, "config.json"), "w", encoding="utf-8") as f:
        json.dump(config_portable, f, ensure_ascii=False, indent=4)
    print("  config.json creado.")

    hf_token = ""
    dev_hf_path = os.path.join(BASE_DIR, "hf_config.json")
    if os.path.exists(dev_hf_path):
        try:
            with open(dev_hf_path, "r", encoding="utf-8") as f:
                hf_token = json.load(f).get("hf_token", "")
        except Exception:
            pass
    with open(os.path.join(PORTABLE_DIR, "hf_config.json"), "w", encoding="utf-8") as f:
        json.dump({"hf_token": hf_token}, f, ensure_ascii=False, indent=4)
    print("  hf_config.json creado.")

    # 11. Escribir INICIAR.bat
    print_step("Escribiendo INICIAR.bat...")
    iniciar_bat = r"""@echo off
chcp 65001 >nul 2>&1
title Mi Nueva Familia - Portable
color 0B

echo.
echo ========================================================
echo    MI NUEVA FAMILIA - Version Portable
echo    Iniciando aplicacion local...
echo ========================================================
echo.
echo   La aplicacion se abrira en tu navegador automaticamente.
echo   NO cierres esta ventana mientras usas el sistema.
echo.

cd /d "%~dp0"

if not exist "python\python.exe" (
    echo.
    echo ERROR: No se encontro python\python.exe
    echo Asegurate de haber descomprimido la carpeta completa.
    echo.
    pause
    exit /b 1
)

python\python.exe --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ERROR DE COMPATIBILIDAD: El Python incluido no es compatible.
    echo Ejecuta REPARAR_32BIT.bat para solucionarlo.
    echo.
    pause
    exit /b 1
)

set PYTHONPATH=%~dp0python\Lib\site-packages;%~dp0app;%PYTHONPATH%

python\python.exe -c "import typing_extensions" >nul 2>&1
if %errorlevel% neq 0 (
    echo Reparando dependencias faltantes...
    python\python.exe -m pip install typing_extensions packaging --quiet --no-user --no-warn-script-location
)

python\python.exe app\launcher.py

if %errorlevel% neq 0 (
    echo.
    echo Error al iniciar. Intenta ejecutar como administrador.
    echo.
    pause
)
"""
    with open(os.path.join(PORTABLE_DIR, "INICIAR.bat"), "w", encoding="utf-8") as f:
        f.write(iniciar_bat)
    print("  INICIAR.bat creado.")

    # Copiar REPARAR_32BIT.bat a la raíz del portable
    rep_src = os.path.join(BASE_DIR, "REPARAR_32BIT.bat")
    if os.path.exists(rep_src):
        shutil.copy2(rep_src, os.path.join(PORTABLE_DIR, "REPARAR_32BIT.bat"))
        print("  REPARAR_32BIT.bat copiado.")

    # 12. Comprimir en ZIP
    print_step("Comprimiendo en MiNuevaFamilia-Portable.zip...")
    zip_output = os.path.join(BASE_DIR, "MiNuevaFamilia-Portable")
    shutil.make_archive(zip_output, 'zip', BASE_DIR, "MiNuevaFamilia-Portable")
    print(f"  ZIP creado: {zip_output}.zip")

    print_step("EMPAQUETADO COMPLETADO")
    print("Estructura del portable:")
    print("  INICIAR.bat          (doble clic para abrir)")
    print("  REPARAR_32BIT.bat    (solo si hay error de bits)")
    print("  config.json          (configuracion guardada)")
    print("  python/              (Python embebido + librerias)")
    print("  app/                 (codigo de la aplicacion)")
    print("  datos/               (Excel y plantilla Word)")
    print()
    print("Comparte: MiNuevaFamilia-Portable.zip")

if __name__ == "__main__":
    main()
