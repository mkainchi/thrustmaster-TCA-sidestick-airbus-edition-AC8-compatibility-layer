@echo off
setlocal
"%~dp0runtime\python.exe" -B -m app emulate --mode target-xbox %*
exit /b %errorlevel%
