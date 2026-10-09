@echo off
setlocal
"%~dp0runtime\python.exe" -B -m app configure --mode target-xbox %*
exit /b %errorlevel%
