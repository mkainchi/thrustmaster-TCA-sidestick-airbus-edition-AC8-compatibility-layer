@echo off
setlocal
"%~dp0runtime\python.exe" -B "%~dp0tools\privacy_check.py" %*
set "TCA_CHECK_RESULT=%ERRORLEVEL%"
exit /b %TCA_CHECK_RESULT%
