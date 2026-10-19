# Mobalytics no-focus patch

A small, reversible Windows patch that stops Mobalytics' League game-event handlers from automatically raising its desktop windows.

**No installation required. Uses Windows PowerShell 5.1, included with Windows 10/11.** Supports only the inspected Windows build **1.956.363** and the exact file hashes in `supported.json`.

## Use

1. Download this repository as a ZIP and extract it to a writable folder.
2. Close any active match, double-click **Do.cmd**, and confirm the signature-change warning.
3. To reverse the patch, double-click **Undo.cmd**.

Keep the extracted folder: Do stores both verified originals in its local `.backups` directory. No administrator access is needed for the standard per-user installation. Each change closes and restarts Mobalytics. Running Do twice or Undo twice does nothing on the second run.

Unknown files and app updates are refused. A newer release needs fresh inspection; these scripts intentionally support only this one. Undo also refuses unknown versions, so old backups cannot overwrite a new install.

## Review the change

All logic lives in [Patch-Mobalytics.ps1](Patch-Mobalytics.ps1). The two CMD files only launch it; [supported.json](supported.json) pins the original file hashes.

The script replaces exactly **13** calls to `restore`, `showWindowBehind`, or `bringToFront` within the League window controller's automatic window-update and game-state methods with same-length no-op statements. It updates the modified archive entry hashes and the expected archive-header hash embedded in `Mobalytics.exe`.

Manual opening handlers and overlay code are not edited. Startup and read-only file validation were observed on the inspected build. **In-match focus behavior, overlays and game integration remain unverified.**

## Limitations

- The executable modification **invalidates its publisher signature**. Mobalytics logs an unsigned-app warning; some integration features may reject it. Undo restores both original files.
- The archive integrity check remains consistent. No Windows security, anti-cheat or system signature-enforcement settings are changed.
- The launcher uses a process-scoped execution-policy bypass to run the downloaded local script; it does not change the machine's execution policy.
- The startup check proves only that a process remains running. On failure, the script attempts rollback to the starting state. If recovery fails, transaction copies remain in `.backups` for manual recovery.
- No downloads, external modules, game files, account settings or update settings are involved.
- No proprietary binaries, backups, extracted application source or personal logs are included in this repository.

## Read-only check / custom paths

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Patch-Mobalytics.ps1 -Action Check
```

Check requires existing backups. Use `-BackupDir "C:\path\to\backups"` or `-InstallDir "C:\path\to\mobalytics-desktop"` for custom locations. Do accepts `-AcceptSignatureChange` after reviewing this document.

This is an unofficial project, unaffiliated with Mobalytics or Overwolf. The MIT license covers only the code in this repository.
