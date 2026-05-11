@echo off
chcp 65001 >nul 2>&1
title Mi Nueva Familia - Aplicacion
color 0B

echo.
echo ╔══════════════════════════════════════════════════════╗
echo ║   MI NUEVA FAMILIA - Sistema de Gestion             ║
echo ║   Iniciando aplicacion...                            ║
echo ╚══════════════════════════════════════════════════════╝
echo.
echo   La aplicacion se abrira en tu navegador automaticamente.
echo   NO cierres esta ventana mientras uses la aplicacion.
echo.
echo   Para cerrar la aplicacion, cierra esta ventana o presiona Ctrl+C.
echo.
echo ─────────────────────────────────────────────────────────

cd /d "%~dp0"
python launcher.py

if %errorlevel% neq 0 (
    echo.
    echo  ❌ Error al iniciar la aplicacion.
    echo  Ejecuta INSTALAR.bat primero para configurar todo.
    echo.
    pause
)
