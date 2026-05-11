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


def abrir_navegador():
    """Espera a que el servidor esté listo y abre el navegador."""
    time.sleep(3)
    webbrowser.open(URL)


def main():
    print("=" * 60)
    print("  MI NUEVA FAMILIA - Sistema de Gestión")
    print("=" * 60)
    print(f"\n  Iniciando servidor en {URL} ...")
    print("  (No cierres esta ventana mientras uses la aplicación)\n")

    # Abrir navegador en un hilo separado
    threading.Thread(target=abrir_navegador, daemon=True).start()

    # Iniciar Streamlit
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", APP_FILE,
            "--server.port", str(PORT),
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
            "--theme.primaryColor", "#1e293b",
            "--theme.backgroundColor", "#0e1117",
            "--theme.secondaryBackgroundColor", "#1e293b",
            "--theme.textColor", "#fafafa",
        ], cwd=BASE_DIR)
    except KeyboardInterrupt:
        print("\n  Aplicación cerrada.")
    except Exception as e:
        print(f"\n  Error: {e}")
        print("  Asegúrate de haber ejecutado INSTALAR.bat primero.")
        input("\n  Presiona Enter para cerrar...")


if __name__ == "__main__":
    main()
