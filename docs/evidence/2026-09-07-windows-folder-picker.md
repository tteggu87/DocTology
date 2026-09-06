---
title: Windows cross-drive folder selection verification
type: evidence
evidence_id: EVIDENCE-2026-09-07-WINDOWS-FOLDERS
date: 2026-09-07
subject: Windows native folder selection and in-app drive navigation
source_of_truth: false
target_fingerprint: sha256:5e930b8a9dca122ec099c22a80999f2cc3848e1fdb3d1a01a578409c7600e49d
---

# Windows cross-drive folder selection

The in-app fallback previously offered Home, the connected wiki, and the current
filesystem root only. Reaching C:\ could not reveal sibling drives. The native
Windows dialog existed, but had no explicit This PC starting point.

## Change

- The Windows FolderBrowserDialog starts at MyComputer (This PC), enables visual
  styles, and requests AutoUpgradeEnabled only where that property exists.
- The fallback appends every assigned Windows drive letter using GetLogicalDrives.
  It does not resolve or probe each drive while listing the current folder, so
  empty removable media and unavailable mapped drives do not stall discovery.
  Access is checked when the user selects a drive. Manual absolute paths remain.
- The button explicitly says 기본 폴더 선택 창; the input example includes D:.
  Choosing a folder still does not connect automatically or weaken validation.

GetLogicalDrives returns assigned drive-letter bits, not a guarantee that media
is readable: [Microsoft API documentation](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getlogicaldrives).
The native dialog properties are defined in the
[WinForms documentation](https://learn.microsoft.com/en-us/dotnet/api/system.windows.forms.folderbrowserdialog).
Older PowerShell/WinForms may retain the classic folder dialog appearance.

## Verification

- Focused Python folder tests: 18 pass. Windows API and native dialog are mocked
  on macOS; coverage includes C/D/E/Z mask decoding, API failure, and drive shortcuts.
- JavaScript UI suite: 111 pass, including navigation C → D → a Korean-named folder,
  preservation of backslashes, and selection without an automatic connect request.
- Full Python suite with TMPDIR set to a resolved local state directory: 405 pass.
- Default macOS temporary-directory run: four failures and five errors involving
  /var versus /private/var aliases in existing document catalog, chat receipt,
  and source-entry tests. The same nine failures/errors reproduced on unchanged
  HEAD a32a099 in a temporary Git archive across those three test modules.
  Canonicalizing only the test temporary directory resolves them; unrelated
  application/test behavior was not changed for this folder fix.
- Skill inventory and whitespace checks pass. Repo Docs final gate is run after
  this record and its links are written.

Actual Windows native-dialog interaction, removable-drive selection, and mapped
network drive access still require a Windows host. No Windows execution is
claimed. Model calls, global skill installation, commit, and push were not part
of this change.

The fingerprint hashes each path + NUL + file bytes + NUL in this order:
`runtime/wiki_dashboard_folders.py`, `dashboard/app.js`, `dashboard/index.html`,
`tests/test_wiki_dashboard_folder_picker.py`, `tests/dashboard/dashboard_ui.test.cjs`.
