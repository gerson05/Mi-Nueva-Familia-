@echo off
chcp 65001 >nul 2>&1
title Mi Nueva Familia - Instalador
color 0A

echo.
echo ╔══════════════════════════════════════════════════════╗
echo ║   MI NUEVA FAMILIA - Instalador Automatico         ║
echo ║   Sistema de Gestion de Patrocinadores              ║
echo ╚══════════════════════════════════════════════════════╝
echo.

:: 1. Verificar si Python está instalado
echo [1/4] Verificando Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  ❌ Python NO esta instalado.
    echo.
    echo  Para instalar Python:
    echo  1. Ve a https://www.python.org/downloads/
    echo  2. Descarga Python 3.10 o superior
    echo  3. IMPORTANTE: Marca la casilla "Add Python to PATH" durante la instalacion
    echo  4. Ejecuta este instalador de nuevo despues de instalar Python
    echo.
    echo  ¿Deseas abrir la pagina de descarga de Python ahora? (S/N)
    set /p OPEN_PYTHON="> "
    if /i "%OPEN_PYTHON%"=="S" (
        start https://www.python.org/downloads/
    )
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYTHON_VER=%%v
echo  ✅ Python %PYTHON_VER% encontrado.
echo.

:: 2. Instalar dependencias
echo [2/4] Instalando dependencias (puede tardar unos minutos)...
echo.
pip install --quiet streamlit python-docx python-calamine Pillow google-generativeai docx2pdf selenium webdriver-manager gradio_client
if %errorlevel% neq 0 (
    echo.
    echo  ⚠️  Hubo un problema instalando algunas dependencias.
    echo  Intentando de nuevo con permisos elevados...
    pip install --user streamlit python-docx python-calamine Pillow google-generativeai docx2pdf selenium webdriver-manager gradio_client
)
echo.
echo  ✅ Dependencias instaladas.
echo.

:: 3. Crear archivo de configuracion inicial si no existe
echo [3/4] Configurando la aplicacion...
if not exist "config.json" (
    echo { > config.json
    echo   "excel_path": "", >> config.json
    echo   "base_folder": "" >> config.json
    echo } >> config.json
    echo  📝 Archivo de configuracion creado. Se configurara al abrir la app.
) else (
    echo  ✅ Configuracion existente encontrada.
)

if not exist "hf_config.json" (
    echo { > hf_config.json
    echo   "hf_token": "" >> hf_config.json
    echo } >> hf_config.json
    echo  📝 Para usar la mejora con IA, edita hf_config.json y agrega tu token de HuggingFace.
)
echo.

:: 4. Crear acceso directo en el escritorio
echo [4/4] Creando acceso directo en el Escritorio...
set SCRIPT_DIR=%~dp0
set SHORTCUT_NAME=Mi Nueva Familia.lnk
set DESKTOP=%USERPROFILE%\Desktop

:: Crear un VBScript temporal para crear el acceso directo
echo Set oWS = WScript.CreateObject("WScript.Shell") > "%TEMP%\crear_acceso.vbs"
echo sLinkFile = "%DESKTOP%\%SHORTCUT_NAME%" >> "%TEMP%\crear_acceso.vbs"
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> "%TEMP%\crear_acceso.vbs"
echo oLink.TargetPath = "%SCRIPT_DIR%INICIAR.bat" >> "%TEMP%\crear_acceso.vbs"
echo oLink.WorkingDirectory = "%SCRIPT_DIR%" >> "%TEMP%\crear_acceso.vbs"
echo oLink.Description = "Mi Nueva Familia - Sistema de Gestion" >> "%TEMP%\crear_acceso.vbs"
echo oLink.WindowStyle = 1 >> "%TEMP%\crear_acceso.vbs"
echo oLink.Save >> "%TEMP%\crear_acceso.vbs"
cscript /nologo "%TEMP%\crear_acceso.vbs"
del "%TEMP%\crear_acceso.vbs"
echo  ✅ Acceso directo creado en el Escritorio.
echo.

:: Finalizado
echo ╔══════════════════════════════════════════════════════╗
echo ║   ✅ INSTALACION COMPLETADA                         ║
echo ║                                                      ║
echo ║   Para iniciar la aplicacion:                        ║
echo ║   - Doble click en "Mi Nueva Familia" en el         ║
echo ║     Escritorio, o ejecuta INICIAR.bat                ║
echo ╚══════════════════════════════════════════════════════╝
echo.
echo ¿Deseas iniciar la aplicacion ahora? (S/N)
set /p START_APP="> "
if /i "%START_APP%"=="S" (
    call "%SCRIPT_DIR%INICIAR.bat"
)
pause
