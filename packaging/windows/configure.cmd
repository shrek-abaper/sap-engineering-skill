@echo off
rem Interactive configuration entry for the installed sap-adt runtime.
rem STATUS: IMPLEMENTED, NOT VERIFIED (no Windows build host in workspace).
rem Uses the absolute path of this very install (no PATH dependency) and
rem never takes a password on the command line.
setlocal
set "SAP_ADT_EXE=%~dp0sap-adt.exe"

if not exist "%SAP_ADT_EXE%" (
  echo [ERROR] %SAP_ADT_EXE% not found. Re-run the installer.
  exit /b 1
)

echo sap-adt version:
"%SAP_ADT_EXE%" --version || exit /b 1
echo.
echo Starting interactive configuration (the password prompt is hidden and
echo stored in the OS keystore, never in this script or on the command line):
echo.
"%SAP_ADT_EXE%" configure
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo [FAILED] configure exited with %RC%. Re-run "%~f0" to try again.
  exit /b %RC%
)
echo.
echo Keystore backend diagnostics (no secrets shown):
"%SAP_ADT_EXE%" credentials doctor
endlocal
