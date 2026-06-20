"""
launcher.py
-----------
Lanzador de la aplicación Mi Nueva Familia.
Inicia el servidor Streamlit y abre el navegador automáticamente.
"""
import sys
import os
import time
import webbrowser
import subprocess
import threading

# Configurar la ruta base
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_FILE = os.path.join(BASE_DIR, "app.py")
PORT = 8501
URL = f"http://localhost:{PORT}"

# Paquetes que deben estar disponibles antes de lanzar Streamlit
PAQUETES_REQUERIDOS = [
    "typing_extensions",
    "packaging",
    "streamlit",
    "docx",
    "PIL",
    "openpyxl",
    "supabase",
]


def get_site_packages():
    """Devuelve la ruta al site-packages del Python portable (si existe)."""
    candidates = [
        os.path.join(BASE_DIR, "python", "Lib", "site-packages"),
        os.path.join(BASE_DIR, "python", "lib", "site-packages"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def build_env():
    """Crea un entorno de ejecución con PYTHONPATH apuntando al site-packages portable."""
    env = os.environ.copy()
    site_pkg = get_site_packages()
    if site_pkg:
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = site_pkg + (os.pathsep + existing if existing else "")
    return env


def instalar_dependencias_faltantes():
    """Detecta e instala automáticamente paquetes faltantes."""
    faltantes = []
    for paquete in PAQUETES_REQUERIDOS:
        try:
            __import__(paquete)
        except ImportError:
            faltantes.append(paquete)

    if not faltantes:
        return

    # Mapear nombres de importación a nombres de pip
    mapa_pip = {
        "docx": "python-docx",
        "PIL": "Pillow",
    }

    print("\n  Detectando dependencias faltantes, instalando...")
    for pkg in faltantes:
        pip_name = mapa_pip.get(pkg, pkg)
        print(f"  ⚙  Instalando {pip_name}...")
        resultado = subprocess.run(
            [sys.executable, "-m", "pip", "install", pip_name, "--quiet", "--no-user"],
            capture_output=True,
            text=True,
        )
        if resultado.returncode == 0:
            print(f"  ✅ {pip_name} instalado correctamente.")
        else:
            print(f"  ⚠️  No se pudo instalar {pip_name}:")
            print("     " + resultado.stderr.strip()[:200])


def abrir_navegador():
    """Espera a que el servidor esté listo y abre el navegador."""
    time.sleep(3)
    webbrowser.open(URL)


def main():
    print("=" * 60)
    print("  MI NUEVA FAMILIA - Sistema de Gestión")
    print("=" * 60)

    # Auto-reparar dependencias faltantes antes de lanzar Streamlit
    instalar_dependencias_faltantes()

    print(f"\n  Iniciando servidor en {URL} ...")
    print("  (No cierres esta ventana mientras uses la aplicación)\n")

    # Abrir navegador en un hilo separado
    threading.Thread(target=abrir_navegador, daemon=True).start()

    # Iniciar Streamlit con PYTHONPATH explícito para la portable
    try:
        res = subprocess.run([
            sys.executable, "-m", "streamlit", "run", APP_FILE,
            "--server.port", str(PORT),
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
            "--theme.primaryColor", "#1e293b",
            "--theme.backgroundColor", "#0e1117",
            "--theme.secondaryBackgroundColor", "#1e293b",
            "--theme.textColor", "#fafafa",
        ], cwd=BASE_DIR, env=build_env())
        
        if res.returncode != 0:
            print(f"\n  ❌ El servidor de Streamlit se detuvo con el código de error: {res.returncode}")
            input("\n  Presiona Enter para salir...")
            sys.exit(res.returncode)
            
    except KeyboardInterrupt:
        print("\n  Aplicación cerrada.")
    except Exception as e:
        print(f"\n  Error: {e}")
        print("  Asegúrate de haber ejecutado INSTALAR.bat primero.")
        input("\n  Presiona Enter para cerrar...")
        sys.exit(1)


if __name__ == "__main__":
    main()
