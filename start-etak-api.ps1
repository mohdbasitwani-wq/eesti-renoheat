param(
  [string]$CsvPath = "$env:USERPROFILE\Downloads\etak_buildings_index.csv",
  [string]$HostName = "127.0.0.1",
  [int]$Port = 8765
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ServerScript = Join-Path $ProjectRoot "backend\etak_search_server_v2.py"

if (-not (Test-Path $CsvPath)) {
  Write-Host "Missing ETAK CSV: $CsvPath" -ForegroundColor Red
  Write-Host "Create it first from ETAK_Eesti_pohikaart_2024_SHP.zip."
  exit 1
}

Write-Host "Starting ETAK API with $CsvPath"
py -3 $ServerScript --csv $CsvPath --host $HostName --port $Port
