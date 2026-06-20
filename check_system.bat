@echo off
chcp 65001 >nul
setlocal

echo.
echo =================================================
echo   TranscriptionAI — Verification systeme
echo =================================================
echo.

:: Vérification de l'environnement virtuel
if not exist .venv\Scripts\activate (
    echo [INFO] Environnement virtuel .venv absent.
    echo        Lancement avec Python systeme...
    echo.
    python check_system.py
) else (
    call .venv\Scripts\activate
    python check_system.py
)

echo.
pause
