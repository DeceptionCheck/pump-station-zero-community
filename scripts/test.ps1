# Run the test suite. No network or packages needed.
Set-Location (Join-Path $PSScriptRoot '..')
python -m unittest discover -s tests -v
