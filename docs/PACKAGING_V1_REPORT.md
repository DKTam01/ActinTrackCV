# Plain-language packaging report (v1.0.0)

**Date:** 2026-09-15  
**Audience:** anyone who just wants to know “how do people get the app?”

---

## The short version

We want lab users to **download a zip and double-click**, without installing Python.

| Computer | What they download | What they click |
|---|---|---|
| Mac (Apple Silicon) | `ActinTrackCV-1.0.0-macos-arm64.zip` | `ActinTrackCV.app` |
| Windows (64-bit) | `ActinTrackCV-1.0.0-windows-x64-onefolder.zip` | `ActinTrackCV.exe` inside the unzipped folder |

Both live on the same GitHub page:  
https://github.com/Sapkota-Lab/ActinTrackCV/releases/tag/v1.0.0

The Mac zip was built on a Mac. The Windows zip **cannot** be built on a Mac — Windows programs need to be assembled on Windows. So we use **GitHub Actions**: a free Windows computer in the cloud that GitHub turns on for us, builds the zip, and attaches it to the release.

---

## Why not Whisky / Wine on your Mac?

Whisky lets a Mac *try* to run Windows programs. Building ActinTrackCV for Windows is different: it needs real Windows libraries for PyQt6, OpenCV, and video decoding. That is fragile under Whisky and easy to get wrong for a lab release.

**Rule of thumb:** Mac builds on Mac. Windows builds on Windows (or on GitHub’s Windows machines).

---

## What was already done for Mac (v1.0.0)

1. Version set to **1.0.0** (the earlier “0.3.0” label was corrected).
2. Built `ActinTrackCV.app` with the project’s macOS packaging script.
3. Zipped it and published it on GitHub Releases as **v1.0.0**.
4. Opened pull request #7 so this work can land on `main` when you want.

Mac users: unzip → open the app → if Gatekeeper blocks it, right-click → Open (or Privacy & Security → Open Anyway).

---

## What this Windows work adds

1. **A GitHub Actions workflow** (`.github/workflows/package-windows.yml`) that:
   - Checks out the repo on a real Windows runner
   - Installs Python + packaging dependencies
   - Runs the existing script `packaging/windows/build_windows.ps1`
   - Zips the whole `ActinTrackCV` folder (`.exe` + `_internal` + helpers)
   - Optionally uploads that zip onto an existing release tag (e.g. `v1.0.0`)

2. **README / packaging docs** updated so Windows download instructions match v1.0.0.

3. **Triggering a build from your Mac:**  
   GitHub → **Actions** → **Package Windows** → **Run workflow** → set `release_tag` to `v1.0.0` if you want it on the release page automatically.

You do **not** need a Windows laptop for day-to-day packaging once this workflow is on the branch GitHub can see.

---

## What Windows users do (same spirit as Mac)

1. Go to the v1.0.0 release page.
2. Download `ActinTrackCV-1.0.0-windows-x64-onefolder.zip`.
3. Unzip.
4. Open the `ActinTrackCV` folder.
5. Double-click `ActinTrackCV.exe`.
6. Keep the whole folder together (do not move only the `.exe`).
7. If SmartScreen warns (unsigned build): **More info → Run anyway**.

Workspaces still live outside the app (user Documents), just like Mac.

---

## What this is *not*

- Not a fancy Windows installer wizard (`.msi` / Setup.exe) yet — zip is intentional for now.
- Not code-signed — SmartScreen will warn, same idea as unsigned Mac Gatekeeper.
- Not built inside Whisky.
- Does not replace older releases (`v0.2.2`, etc.); v1.0.0 is the current scientific Workbench cut.

---

## How to check it worked

1. Release page shows **two** assets: Mac zip and Windows zip.
2. On a Windows PC: unzip → double-click → About shows **ActinTrackCV 1.0.0**.
3. Import an AVI/MP4, confirm Cell Boundary, set Measurement Cutoff, Run Metrics.

---

## If something fails

- **Workflow red on GitHub:** open the failed job log under Actions → Package Windows.
- **Zip missing on the release:** re-run the workflow with `release_tag = v1.0.0` (the release must already exist).
- **App won’t start on Windows:** keep `_internal` next to the `.exe`; try SmartScreen “Run anyway”; ask for a console debug build (`build_windows.ps1 -Console`) if needed.
