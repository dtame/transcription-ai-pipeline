@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo.
echo =================================================
echo   TranscriptionAI — Installation Windows
echo =================================================
echo.

:: Vérification de Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python n'est pas installe ou introuvable dans le PATH.
    echo.
    echo Installez Python 3.11 depuis https://www.python.org/downloads/
    echo Cochez bien "Add Python to PATH" lors de l'installation.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PYTHON_VER=%%v
echo [OK] %PYTHON_VER% detecte.
echo.

:: Création de l'environnement virtuel
if exist .venv (
    echo [INFO] Environnement virtuel .venv deja present. Suppression pour reinstallation propre...
    rmdir /s /q .venv
)

echo [1/4] Creation de l'environnement virtuel .venv ...
python -m venv .venv
if errorlevel 1 (
    echo [ERREUR] Impossible de creer l'environnement virtuel.
    pause
    exit /b 1
)
echo [OK] Environnement virtuel cree.
echo.

:: Activation
echo [2/4] Activation de l'environnement virtuel ...
call .venv\Scripts\activate
if errorlevel 1 (
    echo [ERREUR] Impossible d'activer l'environnement virtuel.
    pause
    exit /b 1
)
echo [OK] Environnement virtuel actif.
echo.

:: Mise à jour de pip
echo [3/4] Mise a jour de pip ...
python -m pip install --upgrade pip --quiet
echo [OK] pip mis a jour.
echo.

:: Installation des dépendances
echo [4/4] Installation des dependances (requirements.txt) ...
echo       Cela peut prendre plusieurs minutes selon votre connexion.
echo.
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERREUR] L'installation des dependances a echoue.
    echo Verifiez votre connexion internet et relancez install_windows.bat.
    pause
    exit /b 1
)
echo.
echo [OK] Dependances installees.
echo.

:: Création des dossiers nécessaires
echo Verification et creation des dossiers ...
for %%d in (depot sortie logs temp rejets archives) do (
    if not exist %%d (
        mkdir %%d
        echo   [CREE] %%d\
    ) else (
        echo   [OK]   %%d\ existe deja
    )
)
echo.

:: Résumé final
echo =================================================
echo   Installation terminee avec succes !
echo =================================================
echo.
echo Prochaines etapes :
echo.
echo   1. Verifier le systeme :
echo         check_system.bat
echo.
echo   2. Demarrer l'interface :
echo         start_ui.bat
echo.
echo   3. Ou lancer la console :
echo         start_console.bat
echo.
pause
