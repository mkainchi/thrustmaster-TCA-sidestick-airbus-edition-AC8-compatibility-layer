@echo off
setlocal
"%~dp0runtime\python.exe" -B -m app configure --mode keyboard %*
exit /b %errorlevel%
