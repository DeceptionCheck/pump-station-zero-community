# Start the local practice station on 127.0.0.1 (default port 8180). Stop with Ctrl+C.
param([int]$Port = 8180)
Set-Location (Join-Path $PSScriptRoot '..')
python -m community.server --port $Port
