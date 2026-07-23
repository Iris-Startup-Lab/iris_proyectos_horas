<#
.SYNOPSIS
    Script de ejecución del Pipeline Iris Proyectos Horas para Windows (PowerShell).
.DESCRIPTION
    Ejecuta el pipeline en el entorno de Conda 'data_engineering' reenviando cualquier argumento o flag.
.EXAMPLE
    .\run_pipeline.ps1 --weeks 2
    .\run_pipeline.ps1 --test
    .\run_pipeline.ps1 --full-reload
#>

Param(
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$PipelineArgs
)

$ErrorActionPreference = "Stop"

# Buscar ejecutable de Python en el entorno Conda data_engineering
$CondaPythonCandidates = @(
    "E:\Users\1167486\AppData\Local\anaconda3\envs\data_engineering\python.exe",
    "$env:USERPROFILE\AppData\Local\anaconda3\envs\data_engineering\python.exe",
    "$env:USERPROFILE\anaconda3\envs\data_engineering\python.exe",
    "C:\ProgramData\anaconda3\envs\data_engineering\python.exe"
)

$PythonExe = $null
foreach ($path in $CondaPythonCandidates) {
    if (Test-Path $path) {
        $PythonExe = $path
        break
    }
}

if (-not $PythonExe) {
    $PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
}

if (-not $PythonExe) {
    Write-Error "No se encontró el ejecutable de Python para el entorno 'data_engineering'."
    exit 1
}

Write-Host "=== Ejecutando Pipeline Iris Proyectos Horas ($PythonExe) ===" -ForegroundColor Green
& $PythonExe -m src.pipeline_actividades_trello @PipelineArgs
