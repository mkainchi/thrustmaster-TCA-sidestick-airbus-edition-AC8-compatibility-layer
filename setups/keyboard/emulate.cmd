@echo off
setlocal
"%~dp0runtime\python.exe" -B -m app emulate --mode keyboard %*
exit /b %errorlevel%
