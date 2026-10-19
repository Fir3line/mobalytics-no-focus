# Mobalytics no-focus patch

A small, reversible Windows patch that stops Mobalytics' League game-event handlers from automatically raising its desktop windows.

**Unofficial. Supports only the inspected Windows build `1.956.363` and the exact file hashes in [`supported.json`](supported.json).** An update requires a new code review and supported hashes. This does not automatically patch arbitrary future releases.

## Use

1. Install Python 3.10 or newer, available as `py` or `python`.
2. Download this repository and extract it to a writable folder. Keep that folder for Undo.
3. Close any active match, then double-click **Do.cmd** and confirm.
4. To reverse the change, double-click **Undo.cmd**.

Do saves and verifies both originals in the local `.backups` folder before modifying anything. Each change closes and restarts Mobalytics. Neither script needs administrator access for the standard per-user installation.

The scripts stop if installed files or backups do not match the reviewed build. Undo also refuses unknown versions: do not copy old backups over a newer release.

## What changes

All patch logic is in [`patch_mobalytics.py`](patch_mobalytics.py), using only Python's standard library:

1. Locate `build/src_lol_bootstrap_ts.js` inside the installed `resources/app.asar`.
2. Within the League window controller's automatic window-update/game-state methods, replace exactly **13** calls to `restore`, `showWindowBehind`, or `bringToFront` with same-length no-op statements.
3. Recompute that entry's archive integrity hashes and update the matching expected archive-header hash embedded in `Mobalytics.exe`.

Manual opening handlers and overlay code are not edited. Startup with the patch was observed on the inspected build. **In-match focus behavior, overlay and game integration have not been verified.**

## Important limitations

- Modifying the executable **invalidates its publisher signature**. Mobalytics logs an unsigned-application warning; some integration features may reject it. Undo restores the original executable and archive.
- This keeps the archive hash check consistent; it does not disable system security, anti-cheat, or Windows signature enforcement.
- Updates may overwrite the patch. Reapplying to a new release needs inspection, not just replacement hashes.
- A process-existence startup check cannot prove all app features work. If startup fails, the script attempts to restore the state from before that run. If recovery fails, transaction copies remain in `.backups` for manual recovery.
- No game files, account settings, network requests or update settings are modified. No proprietary binaries or extracted application source are included in this repository.

## CLI and verification

```powershell
py -3 patch_mobalytics.py do --accept-signature-change
py -3 patch_mobalytics.py check
py -3 patch_mobalytics.py undo
py -3 -m unittest discover -s tests -v
```

Optional `--install-dir` and `--backup-dir` arguments accept custom paths. `check` is read-only and requires existing backups. Backups contain Mobalytics' own proprietary files; keep them local.

This project is not affiliated with Mobalytics or Overwolf. The MIT license covers this repository's code only.
