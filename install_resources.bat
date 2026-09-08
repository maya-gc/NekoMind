@echo off
rem ------------------------------------------------------------
rem install_resources.bat - Instala recursos necessários para o NekoMind
rem ------------------------------------------------------------
rem Este script automatiza a instalação de:
rem   * ESP-IDF e toolchains (local ao repositório)
rem   * Ambientes virtuais Python para backend e frontend
rem   * Dependências Python (FastAPI, Streamlit, etc.)
rem   * (Opcional) Configurações de ambiente
rem ------------------------------------------------------------

rem Verifica se o diretório do script está correto
set "REPO_ROOT=%~dp0"

rem ---------- ESP-IDF ----------
echo Instalando ESP-IDF e toolchains ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%REPO_ROOT%scripts\setup_espidf_portable.ps1"
if errorlevel 1 (
    echo ERRO: Falha ao instalar ESP-IDF.
    exit /b 1
)

rem ---------- Backend ----------
echo Configurando ambiente Python do backend ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%REPO_ROOT%scripts\setup_backend.ps1"
if errorlevel 1 (
    echo ERRO: Falha ao configurar o backend.
    exit /b 1
)

rem ---------- Frontend ----------
echo Configurando ambiente Python do frontend ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%REPO_ROOT%scripts\setup_frontend.ps1"
if errorlevel 1 (
    echo ERRO: Falha ao configurar o frontend.
    exit /b 1
)

rem ---------- Conclusao ----------
echo.
echo Instalacao concluida com sucesso.
echo.
echo Use "bash scripts/run_all.sh" (ou .ps1) para iniciar o backend e o frontend.
echo.
pause