@echo off
chcp 65001 >nul
setlocal

echo.
echo =================================================
echo   TranscriptionAI — Console
echo =================================================
echo.

:: Vérification de l'environnement virtuel
if not exist .venv\Scripts\activate (
    echo [ERREUR] Environnement virtuel .venv introuvable.
    echo Lancez d'abord install_windows.bat
    echo.
    pause
    exit /b 1
)

:: Activation
call .venv\Scripts\activate

echo [OK] Environnement virtuel actif.
echo [OK] Lancement de TranscriptionAI en mode console...
echo.

python main.py

echo.
pause
