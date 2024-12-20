param (
    [string]$ProcessingPath,
    [string]$OutputPath
)

Write-Host "Processing images in directory: $ProcessingPath"
Write-Host "Output directory: $OutputPath"

if (-Not (Test-Path $ProcessingPath)) {
    Write-Host "Error: Processing directory does not exist."
    exit 1
}

if (-Not (Test-Path $OutputPath)) {
    Write-Host "Creating output directory: $OutputPath"
    New-Item -ItemType Directory -Force -Path $OutputPath
}

$pythonScriptPath = "data/zzz_360_TOOLS/PixelateImages.py"
if (-Not (Test-Path $pythonScriptPath)) {
    Write-Host "Error: Python script does not exist."
    exit 1
}

Write-Host "Calling Python script for pixelation..."
$process = python $pythonScriptPath $ProcessingPath $OutputPath
if ($LASTEXITCODE -ne 0) {
    Write-Host "Python script failed."
    exit 1
}

Write-Host "Processing completed successfully."
