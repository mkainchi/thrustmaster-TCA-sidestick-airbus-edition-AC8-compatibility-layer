@echo off
setlocal
"%~dp0runtime\python.exe" -B -m app configure --mode xbox %*
exit /b %errorlevel%
