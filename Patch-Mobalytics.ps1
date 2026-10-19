# Built-in Windows PowerShell 5.1 only. No downloads or external modules.
[CmdletBinding()]
param(
    [ValidateSet('Do','Undo','Check')][string]$Action = 'Check',
    [string]$InstallDir = "$env:LOCALAPPDATA\Programs\mobalytics-desktop",
    [string]$BackupDir = "$PSScriptRoot\.backups",
    [switch]$AcceptSignatureChange
)
$ErrorActionPreference = 'Stop'
$originalHeaderHash = 'fd3bfb6457d5b0a44bcbe1086511e1c9d14cc5e90dd6b858a39e7f489ebd80ac'
$patchedHeaderHash = 'ad90428901fc8d74a064dd1104601465e9686ef1295c01d51ca55110f6099915'
$supported = Get-Content -LiteralPath "$PSScriptRoot\supported.json" -Raw | ConvertFrom-Json
$exe = Join-Path $InstallDir 'Mobalytics.exe'
$asar = Join-Path $InstallDir 'resources\app.asar'
$savedExe = Join-Path $BackupDir 'Mobalytics.exe.original'
$savedAsar = Join-Path $BackupDir 'app.asar.original'

function Get-ByteHash([byte[]]$Bytes) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($Bytes))).Replace('-','').ToLowerInvariant() }
    finally { $sha.Dispose() }
}
function Get-FileDigest([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}
function Read-Archive([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    try {
        $reader = [IO.BinaryReader]::new($stream)
        $null = $reader.ReadUInt32()
        $headerSize = $reader.ReadUInt32()
        $null = $reader.ReadUInt32()
        $jsonSize = $reader.ReadUInt32()
        if ($jsonSize -gt 16777216 -or $jsonSize -lt 2) { throw 'Invalid archive header size.' }
        $raw = $reader.ReadBytes($jsonSize)
        $headerText = [Text.Encoding]::UTF8.GetString($raw)
        $header = $headerText | ConvertFrom-Json
        $entry = $header.files.build.files.'src_lol_bootstrap_ts.js'
        if (!$entry -or $entry.size -gt 15000000) { throw 'Unsupported archive entry.' }
        $offset = 8 + [long]$headerSize + [long]$entry.offset
        $stream.Position = $offset
        $content = $reader.ReadBytes($entry.size)
        if ($content.Length -ne $entry.size -or (Get-ByteHash $content) -ne $entry.integrity.hash) {
            throw 'Archive entry integrity check failed.'
        }
        return @{ Raw=$raw; Text=$headerText; Entry=$entry; Offset=$offset; Content=$content }
    } finally { $stream.Dispose() }
}
function Stop-Mobalytics {
    Get-Process Mobalytics -ErrorAction SilentlyContinue | ForEach-Object {
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        if (!$_.WaitForExit(5000)) { throw 'Mobalytics did not stop. Close it and retry.' }
    }
    Start-Sleep -Seconds 1
}
function Start-Mobalytics {
    Start-Process -FilePath $exe -WorkingDirectory $InstallDir -WindowStyle Hidden
    Start-Sleep -Seconds 6
    if (!(Get-Process Mobalytics -ErrorAction SilentlyContinue)) { throw 'Mobalytics failed to start.' }
}

try {
    if ($Action -eq 'Do' -and !$AcceptSignatureChange) {
        throw 'Read README.md, then use Do.cmd or add -AcceptSignatureChange.'
    }
    $hasExe = Test-Path -LiteralPath $savedExe
    $hasAsar = Test-Path -LiteralPath $savedAsar
    if ($hasExe -ne $hasAsar) { throw 'Incomplete backups. Preserve the folder and investigate.' }
    if (!$hasExe) {
        if ($Action -ne 'Do') { throw 'No backups. Do creates backups from the supported original install.' }
        if ((Get-FileDigest $exe) -ne $supported.original_exe_sha256 -or
            (Get-FileDigest $asar) -ne $supported.original_asar_sha256) {
            throw 'Unknown or modified version. Nothing changed. Updates need a new review.'
        }
        $null = New-Item -ItemType Directory -Path $BackupDir -Force
        # File.Copy refuses to overwrite any existing backup.
        [IO.File]::Copy($exe,$savedExe,$false)
        [IO.File]::Copy($asar,$savedAsar,$false)
    }
    if ((Get-FileDigest $savedExe) -ne $supported.original_exe_sha256 -or
        (Get-FileDigest $savedAsar) -ne $supported.original_asar_sha256) { throw 'Backups do not match the reviewed build.' }
    $original = Read-Archive $savedAsar
    if ((Get-ByteHash $original.Raw) -ne $originalHeaderHash) { throw 'Unexpected original header.' }
    $source = [Text.Encoding]::UTF8.GetString($original.Content)
    $first = $source.IndexOf('    async updateLCWindow(placeBehindGame = true) {',[StringComparison]::Ordinal)
    if ($first -lt 0) { throw 'Expected controller not found.' }
    $last = $source.IndexOf('    async reset() {',$first,[StringComparison]::Ordinal)
    if ($last -le $first) { throw 'Expected controller boundary not found.' }
    $section = $source.Substring($first,$last-$first)
    $pattern = 'this\.windowsManagerService\.(?:bringToFront|restore|showWindowBehind)\([^;\r\n]*\);'
    if ([regex]::Matches($section,$pattern).Count -ne 13) { throw 'Unexpected activation call count.' }
    $fixed = [regex]::Replace($section,$pattern,{param($m) 'void 0;'.PadRight($m.Length)})
    $newContent = [Text.Encoding]::UTF8.GetBytes($source.Substring(0,$first)+$fixed+$source.Substring($last))
    if ($newContent.Length -ne $original.Content.Length -or $original.Entry.integrity.blocks.Count -ne 1) {
        throw 'Unsupported archive layout.'
    }
    $newHeader = [Text.Encoding]::UTF8.GetBytes($original.Text.Replace($original.Entry.integrity.hash,(Get-ByteHash $newContent)))
    if ($newHeader.Length -ne $original.Raw.Length -or (Get-ByteHash $newHeader) -ne $patchedHeaderHash) {
        throw 'Patch result differs from the reviewed patch.'
    }
    $newExe = [IO.File]::ReadAllBytes($savedExe)
    $exeText = [Text.Encoding]::ASCII.GetString($newExe)
    $hashOffset = $exeText.IndexOf($originalHeaderHash,[StringComparison]::Ordinal)
    if ($hashOffset -lt 0 -or $exeText.IndexOf($originalHeaderHash,$hashOffset+1,[StringComparison]::Ordinal) -ge 0) {
        throw 'Expected executable hash is missing or ambiguous.'
    }
    [Array]::Copy([Text.Encoding]::ASCII.GetBytes($patchedHeaderHash),0,$newExe,$hashOffset,64)
    $patchedExeHash = Get-ByteHash $newExe
    $current = Read-Archive $asar
    $state = Get-ByteHash $current.Raw
    $exeHash = Get-FileDigest $exe
    $isOriginal = $state -eq $originalHeaderHash -and $exeHash -eq $supported.original_exe_sha256
    $isPatched = $state -eq $patchedHeaderHash -and $exeHash -eq $patchedExeHash
    if (!$isOriginal -and !$isPatched) { throw 'Installed files changed. Nothing modified. Do not restore old files over an update.' }
    Write-Host ('Current state: ' + $(if ($isPatched) {'PATCHED'} else {'ORIGINAL'}))
    if ($Action -eq 'Check') { Write-Host 'Files, archive integrity and backups validated.'; exit 0 }
    if (($Action -eq 'Do' -and $isPatched) -or ($Action -eq 'Undo' -and $isOriginal)) {
        Write-Host 'Already in the requested state. Nothing changed.'; exit 0
    }
    $tempExe = Join-Path $BackupDir 'transaction-Mobalytics.exe'
    $tempAsar = Join-Path $BackupDir 'transaction-app.asar'
    if ((Test-Path $tempExe) -or (Test-Path $tempAsar)) { throw 'Recovery copies exist. Preserve them and investigate.' }
    Stop-Mobalytics
    [IO.File]::Copy($exe,$tempExe,$false)
    [IO.File]::Copy($asar,$tempAsar,$false)
    $completed = $false
    try {
        if ($Action -eq 'Do') {
            $stream = [IO.File]::Open($asar,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
            try {
                $stream.Position=16; $stream.Write($newHeader,0,$newHeader.Length)
                $stream.Position=$original.Offset; $stream.Write($newContent,0,$newContent.Length)
                $stream.Flush()
            } finally { $stream.Dispose() }
            [IO.File]::WriteAllBytes($exe,$newExe)
            $targetHeader=$patchedHeaderHash; $targetExe=$patchedExeHash
        } else {
            [IO.File]::Copy($savedAsar,$asar,$true)
            [IO.File]::Copy($savedExe,$exe,$true)
            $targetHeader=$originalHeaderHash; $targetExe=$supported.original_exe_sha256
        }
        $verified = Read-Archive $asar
        if ((Get-ByteHash $verified.Raw) -ne $targetHeader -or (Get-FileDigest $exe) -ne $targetExe) {
            throw 'Post-write verification failed.'
        }
        Start-Mobalytics
        $completed=$true
        Write-Host 'Done. Startup passed; in-game behavior still needs verification.'
    } catch {
        $failure=$_
        Stop-Mobalytics
        [IO.File]::Copy($tempAsar,$asar,$true)
        [IO.File]::Copy($tempExe,$exe,$true)
        Start-Mobalytics
        $completed=$true
        throw $failure
    } finally {
        if ($completed) {
            Remove-Item -LiteralPath $tempExe,$tempAsar
        }
    }
} catch { Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red; exit 1 }
