@echo off
chcp 65001 >nul 2>&1
title Generador de Versión Portable
color 0E

echo =======================================================
echo    MI NUEVA FAMILIA - GENERADOR DE PORTABLE
echo =======================================================
echo.
echo Este script creará un paquete ZIP independiente con todo
echo lo necesario para ejecutar la aplicación sin instalar Python.
echo.
pause

python build_portable.py

echo.
pause
