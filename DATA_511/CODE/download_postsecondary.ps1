# Downloads Integrated Postsecondary Education Data System complete data files
# (fall 2018 through fall 2023) plus their data dictionaries into DATA_511\DATA\RAW,
# then unzips each one into its own folder. Safe to rerun: existing zips are skipped.
#
# Files per fall year Y:
#   HD{Y}          Institution directory (control, level, Carnegie class)
#   ADM{Y}         Admissions: applicants, admits, enrolled (yield)
#   IC{Y}_AY       Tuition and fees for the academic year starting in fall Y
#   SFA{yy}{yy+1}  Student financial aid and net price for the fall Y cohort
#   F{yy}{yy+1}_F2 Finance, private nonprofit form, fiscal year ending in Y+1

$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$base = 'https://nces.ed.gov/ipeds/datacenter/data'
$raw  = Join-Path $PSScriptRoot '..\DATA\RAW'
New-Item -ItemType Directory -Force -Path $raw | Out-Null

$files = foreach ($y in 2018..2022) {
    $aidYear = '{0:D2}{1:D2}' -f ($y % 100), (($y + 1) % 100)
    "HD$y", "ADM$y", "IC${y}_AY", "SFA$aidYear", "F${aidYear}_F2"
}

$failed = @()

foreach ($f in $files) {
    foreach ($name in @($f, "${f}_Dict")) {
        $zip = Join-Path $raw "$name.zip"
        try {
            if (-not (Test-Path $zip)) {
                Write-Host "Downloading $name"
                Invoke-WebRequest -Uri "$base/$name.zip" -OutFile $zip -ErrorAction Stop
            }
            Expand-Archive -Path $zip -DestinationPath (Join-Path $raw $f) -Force -ErrorAction Stop
        }
        catch {
            if (Test-Path $zip) { Remove-Item $zip }
            $failed += $name
        }
    }
}

Write-Host ""
if ($failed.Count -eq 0) {
    Write-Host "All $($files.Count) files and dictionaries downloaded."
} else {
    Write-Host "These failed:" -ForegroundColor Yellow
    $failed | ForEach-Object { Write-Host "  $_" }
}