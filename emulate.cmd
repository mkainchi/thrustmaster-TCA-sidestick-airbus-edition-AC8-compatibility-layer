@echo off
setlocal
"%~dp0runtime\python.exe" -B -m app emulate %*
exit /b %errorlevel%
