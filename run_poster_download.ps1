$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = "C:\Users\vetri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Log = Join-Path $Root "poster-download.log"

Set-Location $Root
& $Python download_posters.py --source tmdb --delay 1.2 *> $Log
