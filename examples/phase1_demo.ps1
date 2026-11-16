# Phase 1 demonstration, as a PowerShell session. Same scenario as phase1_demo.py.
#
#   powershell -File examples/phase1_demo.ps1 OUTPUT_DIR
#
# Needs `bbim` on the PATH (for example inside `uv run`, or an activated environment).
param([Parameter(Mandatory = $true)][string]$Out)
$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force $Out | Out-Null
$f = Join-Path $Out "casa.bbim"

# A function name is case-insensitive in PowerShell, so it must not be called "bbim".
function Invoke-Bbim { & bbim @args; if ($LASTEXITCODE -ne 0) { throw "bbim $args failed" } }

Invoke-Bbim new $f --name Casa --force
Invoke-Bbim level add $f "Piano terra" 0
Invoke-Bbim level add $f "Primo piano" "3,00"

# Four 30 cm walls, ground floor to first floor; shared end points give mitred corners.
# Decimal commas are quoted: unquoted, PowerShell reads 3,00 as an array.
$base = @("--thickness", "0,30", "--base", "Piano terra", "--top", "Primo piano")
$south = Invoke-Bbim wall add $f --start 0 0 --end 6 0 @base --quiet
Invoke-Bbim wall add $f --start 6 0 --end 6 4 @base --quiet | Out-Null
$north = Invoke-Bbim wall add $f --start 6 4 --end 0 4 @base --quiet
Invoke-Bbim wall add $f --start 0 4 --end 0 0 @base --quiet | Out-Null

Invoke-Bbim door add $f $south --position "1,50" --width "0,90" --height "2,10" --swing left --hinge start
Invoke-Bbim window add $f $north --position 3 --width "1,20" --height "1,40" --sill "0,90"
Invoke-Bbim wall joins $f

Invoke-Bbim ifc export $f (Join-Path $Out "casa-before.ifc") --validate
Invoke-Bbim plan $f "Piano terra" (Join-Path $Out "casa-before.svg") --scale 1:50 --paper A4

Invoke-Bbim level move $f "Primo piano" "3,20"
Invoke-Bbim wall list $f

Invoke-Bbim ifc export $f (Join-Path $Out "casa-after.ifc") --validate
Invoke-Bbim plan $f "Piano terra" (Join-Path $Out "casa-after.svg") --scale 1:50 --paper A4
