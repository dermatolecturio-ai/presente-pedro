@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Presente do Victor Prudencio para O Pedro

REM Este .bat mora em packaging\windows — sobe 2 niveis ate a raiz do projeto
cd /d "%~dp0..\.."
set "ROOT=%CD%"
set "RUNTIME=%ROOT%\runtime"
set "VENV=%RUNTIME%\venv"
set "FFMPEG_DIR=%ROOT%\packaging\windows\ffmpeg\bin"

echo.
echo === Presente do Victor Prudencio para O Pedro ===
echo Pasta: %ROOT%
echo.

if not exist "%RUNTIME%" mkdir "%RUNTIME%"

REM ---- Preferir venv ja criado ----
if exist "%VENV%\Scripts\python.exe" goto :have_venv

REM ---- Criar venv com py launcher ou python do PATH ----
where py >nul 2>&1
if not errorlevel 1 (
  echo [1/4] Criando ambiente com py -3.12 ...
  py -3.12 -m venv "%VENV%" 2>nul
  if exist "%VENV%\Scripts\python.exe" goto :have_venv
  echo Tentando py -3 ...
  py -3 -m venv "%VENV%" 2>nul
  if exist "%VENV%\Scripts\python.exe" goto :have_venv
)

where python >nul 2>&1
if not errorlevel 1 (
  echo [1/4] Criando ambiente com python ...
  python -m venv "%VENV%"
  if exist "%VENV%\Scripts\python.exe" goto :have_venv
)

echo [ERRO] Python 3.12+ nao encontrado no PATH.
echo Baixe em https://www.python.org/downloads/
echo Na instalacao, marque: "Add python.exe to PATH"
echo Depois rode este arquivo de novo.
pause
exit /b 1

:have_venv
set "PY=%VENV%\Scripts\python.exe"
echo [1/4] Python: %PY%

if exist "%RUNTIME%\.deps-ok" goto :deps_ok
echo [2/4] Instalando dependencias ^(primeira vez demora; precisa internet^)...
"%PY%" -m pip install --upgrade pip wheel setuptools
if errorlevel 1 goto :fail
"%PY%" -m pip install torch
if errorlevel 1 goto :fail
"%PY%" -m pip install -r "%ROOT%\requirements.txt"
if errorlevel 1 goto :fail
echo ok>"%RUNTIME%\.deps-ok"
goto :ffmpeg

:deps_ok
echo [2/4] Dependencias ja instaladas.

:ffmpeg
if exist "%FFMPEG_DIR%\ffmpeg.exe" (
  echo [3/4] ffmpeg ok.
) else (
  echo [3/4] Baixando ffmpeg...
  "%PY%" "%ROOT%\packaging\windows\fetch_ffmpeg.py"
)

echo [4/4] Abrindo o presente...
set "PRESENT_PEDRO_ROOT=%ROOT%"
set "PATH=%FFMPEG_DIR%;%PATH%"
"%PY%" "%ROOT%\packaging\windows\launcher.py"
set "EC=%ERRORLEVEL%"
echo.
if not "%EC%"=="0" (
  echo Encerrou com codigo %EC%.
  pause
)
exit /b %EC%

:fail
echo Falha na instalacao.
pause
exit /b 1
