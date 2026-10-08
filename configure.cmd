@echo off
setlocal
"%~dp0runtime\python.exe" -B -m app configure %*
if not errorlevel 1 exit /b 0
echo If Python could not start, install the Microsoft Visual C++ x64 runtime:
echo https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist
exit /b 1
