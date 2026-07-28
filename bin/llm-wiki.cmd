@echo off
setlocal
REM Prefer the Windows Python launcher, then fall back to python on PATH.
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 "%~dp0..\scripts\llm_wiki.py" %*
  exit /b %ERRORLEVEL%
)
python "%~dp0..\scripts\llm_wiki.py" %*
exit /b %ERRORLEVEL%
