"""
build_portable.py
-----------------
Script para empaquetar la aplicación "Mi Nueva Familia" en una versión portable para Windows.
Descarga e instala Python Embeddable, instala pip y las dependencias, copia los archivos necesarios
y comprime todo en un archivo ZIP listo para compartir.
"""

import os
import sys
import shutil
import urllib.request
import zipfile
import subprocess
import json

# Rutas
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORTABLE_DIR = os.path.join(BASE_DIR, "MiNuevaFamilia-Portable")
PYTHON_DIR = os.path.join(PORTABLE_DIR, "python")

# URLs de descarga
PYTHON_ZIP_URL = "https://www.python.org/ftp/python/3.10.11/python-3.10.11-embed-amd64.zip"
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"

# Librerías a instalar
REQUIREMENTS = [
    "streamlit",
    "python-docx",
    "python-calamine",
    "Pillow",
    "google-generativeai",
    "docx2pdf",
    "selenium",
    "webdriver-manager",
    "gradio_client",
    "openpyxl"
]

def print_step(msg):
    print("\n" + "=" * 60)
    print(f" >>> {msg}")
    print("=" * 60 + "\n")

def main():
    # 1. Limpiar directorio portable anterior
    if os.path.exists(PORTABLE_DIR):
        print_step("Limpiando compilaciones anteriores...")
        shutil.rmtree(PORTABLE_DIR)
    os.makedirs(PORTABLE_DIR, exist_ok=True)
    os.makedirs(PYTHON_DIR, exist_ok=True)

    # 2. Descargar Python Embeddable
    python_zip_path = os.path.join(BASE_DIR, "python_embed.zip")
    if not os.path.exists(python_zip_path):
        print_step("Descargando Python 3.10.11 Embeddable (AMD64)...")
        try:
            urllib.request.urlretrieve(PYTHON_ZIP_URL, python_zip_path)
            print("Python descargado correctamente.")
        except Exception as e:
            print(f"Error al descargar Python: {e}")
            sys.exit(1)
    else:
        print("Se encontró el archivo python_embed.zip localmente.")

    # 3. Extraer Python Embeddable
    print_step("Extrayendo Python Portable...")
    try:
        with zipfile.ZipFile(python_zip_path, 'r') as zip_ref:
            zip_ref.extractall(PYTHON_DIR)
        print("Python extraído en:", PYTHON_DIR)
    except Exception as e:
        print(f"Error al extraer Python: {e}")
        sys.exit(1)

    # 4. Configurar python310._pth para habilitar site-packages
    print_step("Configurando rutas de Python portable...")
    pth_file = os.path.join(PYTHON_DIR, "python310._pth")
    if os.path.exists(pth_file):
        try:
            with open(pth_file, "r") as f:
                content = f.read()
            
            # Descomentar 'import site' si está comentado
            if "#import site" in content:
                content = content.replace("#import site", "import site")
            elif "import site" not in content:
                content += "\nimport site\n"
            
            with open(pth_file, "w") as f:
                f.write(content)
            print("Archivo python310._pth configurado correctamente.")
        except Exception as e:
            print(f"Error al configurar python310._pth: {e}")
            sys.exit(1)
    else:
        print("ERROR: No se encontró python310._pth")
        sys.exit(1)

    # 5. Descargar get-pip.py
    get_pip_path = os.path.join(BASE_DIR, "get-pip.py")
    if not os.path.exists(get_pip_path):
        print_step("Descargando script de instalación de pip...")
        try:
            urllib.request.urlretrieve(GET_PIP_URL, get_pip_path)
            print("get-pip.py descargado correctamente.")
        except Exception as e:
            print(f"Error al descargar get-pip.py: {e}")
            sys.exit(1)
    else:
        print("Se encontró get-pip.py localmente.")

    # 6. Instalar pip en el entorno portable
    print_step("Instalando pip en Python Portable...")
    portable_python_exe = os.path.join(PYTHON_DIR, "python.exe")
    try:
        # Ejecutar get-pip.py usando el python portable
        res = subprocess.run([portable_python_exe, get_pip_path], capture_output=True, text=True)
        if res.returncode != 0:
            print("Error al instalar pip:")
            print(res.stderr)
            sys.exit(1)
        print("pip instalado correctamente en el entorno portable.")
    except Exception as e:
        print(f"Error ejecutando get-pip.py: {e}")
        sys.exit(1)

    # 7. Instalar dependencias
    print_step("Instalando librerías requeridas (puede tardar un momento)...")
    try:
        # Ejecutar pip install usando el python portable
        cmd = [portable_python_exe, "-m", "pip", "install"] + REQUIREMENTS
        print("Ejecutando:", " ".join(cmd))
        
        # Mostrar salida en tiempo real
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print("  " + output.strip())
        
        rc = process.poll()
        if rc != 0:
            print(f"Error instalando dependencias. Código de salida: {rc}")
            sys.exit(1)
        print("Librerías instaladas con éxito.")
    except Exception as e:
        print(f"Error al instalar dependencias: {e}")
        sys.exit(1)

    # 8. Copiar archivos de la aplicación
    print_step("Copiando archivos del código fuente...")
    app_files = [
        "app.py",
        "launcher.py",
        "doc_generator.py",
        "gemini_extractor.py",
        "image_upscaler.py",
        "antecedentes_checker.py",
        "antecedentes_log.json"
    ]
    for file_name in app_files:
        src = os.path.join(BASE_DIR, file_name)
        dst = os.path.join(PORTABLE_DIR, file_name)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            print(f"  Copiado: {file_name}")
        else:
            print(f"  Advertencia: No se encontró {file_name}")

    # 9. Copiar Excel y archivos Word/PDF de la raíz
    print_step("Copiando base de datos Excel y archivos Word/PDF de la raíz...")
    for file_name in os.listdir(BASE_DIR):
        file_path = os.path.join(BASE_DIR, file_name)
        if os.path.isdir(file_path):
            continue  # Omitir directorios (incluyendo patrocinadores)

        ext = os.path.splitext(file_name)[1].lower()
        
        # Validar si es el Excel de transacciones o un archivo docx/pdf
        is_excel = file_name.startswith("TRANSACCIONES") and ext == ".xlsx"
        is_doc_or_pdf = ext in [".docx", ".pdf"]
        
        # Excluir instaladores y este script
        is_script = file_name in [
            "build_portable.py", "python_embed.zip", "get-pip.py", 
            "INSTALAR.bat", "INICIAR.bat", "CREAR_PORTABLE.bat", "INICIAR_PORTABLE.bat"
        ]

        if (is_excel or is_doc_or_pdf) and not is_script:
            dst = os.path.join(PORTABLE_DIR, file_name)
            shutil.copy2(file_path, dst)
            print(f"  Copiado: {file_name}")

    # 10. Crear archivos de configuración con rutas relativas
    print_step("Configurando archivos config.json y hf_config.json...")
    
    # Intentar preservar la clave API del config.json del desarrollador, pero cambiar rutas a relativas
    dev_config_path = os.path.join(BASE_DIR, "config.json")
    api_key = ""
    default_excel = ""
    default_base = ""
    default_template = ""
    
    if os.path.exists(dev_config_path):
        try:
            with open(dev_config_path, "r", encoding="utf-8") as f:
                dev_config = json.load(f)
                api_key = dev_config.get("api_key", "")
                
                # Obtener el nombre del excel de transacciones de la ruta original
                orig_excel = dev_config.get("excel_path", "")
                if orig_excel:
                    default_excel = os.path.basename(orig_excel)
                
                # Obtener el nombre de la carpeta base (patrocinadores) si existía
                orig_base = dev_config.get("base_folder", "")
                if orig_base:
                    default_base = os.path.basename(orig_base)
                
                # Obtener el nombre del template
                orig_temp = dev_config.get("template_path", "")
                if orig_temp:
                    default_template = os.path.basename(orig_temp)
        except Exception as e:
            print("  No se pudo leer el config.json original, usando valores por defecto:", e)

    # Si no se pudieron resolver nombres por defecto, buscar en los archivos copiados
    if not default_excel:
        for f in os.listdir(PORTABLE_DIR):
            if f.startswith("TRANSACCIONES") and f.endswith(".xlsx"):
                default_excel = f
                break
    if not default_template:
        for f in os.listdir(PORTABLE_DIR):
            if f.endswith(".docx") and not f.startswith("temp_") and not f.startswith("test_"):
                default_template = f
                break

    # Escribir config.json portable
    config_portable = {
        "excel_path": default_excel,
        "base_folder": default_base, # Vacío o el nombre relativo (el receptor deberá configurarlo o crear la carpeta)
        "template_path": default_template,
        "api_key": api_key
    }
    
    with open(os.path.join(PORTABLE_DIR, "config.json"), "w", encoding="utf-8") as f:
        json.dump(config_portable, f, ensure_ascii=False, indent=4)
    print("  config.json creado con rutas relativas.")

    # Escribir hf_config.json portable (preservando el token si existía)
    hf_token = ""
    dev_hf_path = os.path.join(BASE_DIR, "hf_config.json")
    if os.path.exists(dev_hf_path):
        try:
            with open(dev_hf_path, "r", encoding="utf-8") as f:
                dev_hf = json.load(f)
                hf_token = dev_hf.get("hf_token", "")
        except Exception:
            pass

    hf_portable = {
        "hf_token": hf_token
    }
    with open(os.path.join(PORTABLE_DIR, "hf_config.json"), "w", encoding="utf-8") as f:
        json.dump(hf_portable, f, ensure_ascii=False, indent=4)
    print("  hf_config.json configurado.")

    # 11. Escribir el script de arranque INICIAR.bat en el portable
    print_step("Escribiendo script INICIAR.bat...")
    iniciar_bat_content = """@echo off
chcp 65001 >nul 2>&1
title Mi Nueva Familia - Portable
color 0B

echo.
echo ╔══════════════════════════════════════════════════════╗
echo ║   MI NUEVA FAMILIA - Versión Portable              ║
echo ║   Iniciando aplicación local...                  ║
echo ╚══════════════════════════════════════════════════════╝
echo.
echo   La aplicación se abrirá en tu navegador automáticamente.
echo   NO cierres esta ventana mientras uses el sistema.
echo.

cd /d "%~dp0"
python\\python.exe launcher.py

if %errorlevel% neq 0 (
    echo.
    echo  ❌ Hubo un error al iniciar la aplicación portable.
    echo.
    pause
)
"""
    with open(os.path.join(PORTABLE_DIR, "INICIAR.bat"), "w", encoding="utf-8") as f:
        f.write(iniciar_bat_content)
    print("  INICIAR.bat creado en el directorio portable.")

    # 12. Comprimir en un archivo ZIP
    print_step("Comprimiendo todo en MiNuevaFamilia-Portable.zip...")
    zip_output_name = os.path.join(BASE_DIR, "MiNuevaFamilia-Portable")
    try:
        # Comprimir usando shutil (generará MiNuevaFamilia-Portable.zip)
        shutil.make_archive(zip_output_name, 'zip', PORTABLE_DIR)
        print("  ¡Archivo comprimido creado con éxito!")
        print(f"  Ubicación: {zip_output_name}.zip")
    except Exception as e:
        print(f"  Error al crear el archivo comprimido ZIP: {e}")
        sys.exit(1)

    print_step("PROCESO DE EMPAQUETADO COMPLETADO CON ÉXITO")
    print("Ahora puedes compartir el archivo 'MiNuevaFamilia-Portable.zip' con tus compañeros.")
    print("Ellos solo tendrán que:")
    print("  1. Descomprimir el archivo ZIP.")
    print("  2. Hacer doble clic en 'INICIAR.bat' para usar la aplicación.")
    print("=" * 60)

if __name__ == "__main__":
    main()
