@echo off
chcp 65001 >nul
setlocal
rem 双击打开离线演示页（demo\demo.html），打开后自动开始讲解。不联网、不运行任何程序，只调用浏览器。
set "PAGE=%~dp0demo\demo.html"
if not exist "%PAGE%" (
  echo 找不到 demo\demo.html。请先运行：.venv\Scripts\python demo\build_demo.py
  pause
  exit /b 1
)
set "EDGE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if not exist "%EDGE%" set "EDGE=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
if exist "%EDGE%" (
  start "" "%EDGE%" --new-window "%PAGE%"
) else (
  start "" "%PAGE%"
)
echo 演示页已在浏览器中打开：按 F 全屏，空格暂停/继续，左右方向键切换步骤。
timeout /t 4 >nul
