@echo off
setlocal
REM Resolve plugin root when CLAUDE_PLUGIN_ROOT is set (marketplace), else this bin/ parent.
if defined CLAUDE_PLUGIN_ROOT (
  set "ROOT=%CLAUDE_PLUGIN_ROOT%"
) else (
  set "ROOT=%~dp0.."
)
REM Prefer the Windows Python launcher, then fall back to python on PATH.
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 "%ROOT%\scripts\llm_wiki.py" %*
  exit /b %ERRORLEVEL%
)
python "%ROOT%\scripts\llm_wiki.py" %*
exit /b %ERRORLEVEL%
