@echo off
chcp 65001 >nul
setlocal

echo.
echo =================================================
echo   TranscriptionAI — Interface Streamlit
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
echo [OK] Lancement de l'interface Streamlit...
echo.
echo      Ouvrez votre navigateur sur : http://localhost:8501
echo      Appuyez sur Ctrl+C pour arreter.
echo.

streamlit run streamlit_app.py
