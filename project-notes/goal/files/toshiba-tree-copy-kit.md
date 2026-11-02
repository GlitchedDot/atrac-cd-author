# Toshiba tree-copy kit — ATRAC Session 45 wall

Prepared 2026-11-01 (Sun evening PT), after Lola asked "What is needed from the Toshiba."
Purpose: one read-only file-copy errand. NO SonicStage launch, NO troubleshooting,
NO changes on the Toshiba. The parked crash thread is not touched by any step here.

## Why

Session 45 fingerprinted all 169 binaries Muse holds (both OpenMG copies, incl.
Omgjbox.exe): zero native cipher tables anywhere, and the only .ATP SAL program
(atpcd.ocm) has no audio-transform method. The general transform that encrypted
430 of the 432 tracks on Lola's country disc is therefore most likely a component
that was never copied off the Toshiba because nobody knew to ask for it.
SAL programs live in `.ocm` files — any `.ocm` other than atpcd.ocm is the prize.

## Step 0 — Inventory first (Command Prompt on the Toshiba, Windows 7)

Run these exactly; they only LIST files, they change nothing. They also settle the
real folder paths from the machine itself instead of from anyone's notes.

```
dir /s /b C:\*.ocm > %USERPROFILE%\Desktop\ocm-inventory.txt
dir /s /b C:\Omgjbox.exe
dir /s /b C:\omgatpcd.dll
```

- The second command prints the SonicStage program folder (the folder containing Omgjbox.exe).
- The third prints the OpenMG shared folder (the folder containing omgatpcd.dll — expect a "Sony Shared" folder under Common Files).
- ocm-inventory.txt lands on the Desktop; it rides along with the copy so Muse can diff the Toshiba's .ocm list against the held corpus line by line.

Also look for a burn-era build (only listing, nothing to run):

```
dir /s /b C:\*sonicstage*.exe
dir /s /b C:\*sonicstage*.zip
```

## Step 1 — Copy BOTH complete trees, unfiltered

Copy the ENTIRE folder found for Omgjbox.exe, and the ENTIRE Sony Shared folder
found for omgatpcd.dll. Every file, no cherry-picking, including subfolders.
A few hundred MB at most.

- Simplest carrier: a USB stick / external drive plugged into the Toshiba.
- NAS route (the one Lola wanted to learn): Toshiba -> the 2018 mini's SMB share
  -> Muse. The mini's share name/path needs confirming at walk-time; ask Candy
  in chat and she will walk it live rather than guessing it here.

Do NOT: launch SonicStage, rename anything in
C:\ProgramData\Sony Corporation\SonicStage\Packages\ (MtData.mdb.bak is her
original library backup — leave every file there exactly as it is), or run any
installer found in Step 0.

## Step 2 — Hand off

Tell Candy the copy is done (and which carrier was used). She will:
1. Diff every file against the 169-binary held corpus; any new .ocm or DLL is news by itself.
2. If a new .ocm exists, census its SAL selectors for a transform method the held atpcd.ocm lacks.
3. Report back before any Session 46 brief is written — Lola leads that call.

If both trees are byte-identical to what is already held, that is also a decisive
answer: the missing component is then in the burn-era build (Step 0's installer
search) or nowhere on this machine, and the hunt re-plans from there.
