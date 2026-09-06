"""Native and bounded fallback workspace-folder selection helpers."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys


def choose_workspace_folder():
    """Ask the server's local desktop for one existing folder; never connect or ingest."""
    if sys.platform == "darwin":
        command = ["/usr/bin/osascript", "-e", '''activate
try
    return POSIX path of (choose folder with prompt "연결할 위키 폴더를 선택하세요 (AGENTS.md와 wiki 폴더)")
on error number -128
    return ""
end try''']
    elif sys.platform == "win32":
        executable = shutil.which("powershell.exe")
        if not executable:
            raise ValueError("폴더 선택 창을 열 수 없습니다. 아래에 폴더 경로를 직접 입력하세요.")
        command = [executable, "-NoProfile", "-NonInteractive", "-STA", "-Command", '''
Add-Type -AssemblyName System.Windows.Forms
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = '연결할 위키 폴더를 선택하세요 (AGENTS.md와 wiki 폴더)'
$dialog.ShowNewFolderButton = $false
try {
    if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
        [Console]::Write($dialog.SelectedPath)
    }
} finally { $dialog.Dispose() }
''']
    else:
        raise ValueError("이 환경에서는 폴더 선택 창을 지원하지 않습니다. 아래에 폴더 경로를 직접 입력하세요.")
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=120, check=False)
    except subprocess.TimeoutExpired:
        raise ValueError("폴더 선택 시간이 지났습니다. 다시 선택하거나 경로를 직접 입력하세요.") from None
    except (OSError, UnicodeError):
        raise ValueError("폴더 선택 창을 열 수 없습니다. 데스크톱 환경을 확인하거나 경로를 직접 입력하세요.") from None
    if result.returncode:
        raise ValueError("현재 서버 실행 환경에서 폴더 선택 창을 열지 못했습니다. 일반 데스크톱 터미널에서 서버를 실행하거나 경로를 직접 입력하세요.")
    selected = result.stdout.rstrip("\r\n")
    if not selected:
        return {"cancelled": True}
    try:
        folder = Path(selected)
        if not folder.is_absolute() or not folder.is_dir():
            raise ValueError("선택한 폴더를 찾을 수 없습니다. 다시 선택하세요.")
        return {"cancelled": False, "root": str(folder.resolve())}
    except OSError:
        raise ValueError("선택한 폴더를 읽을 수 없습니다. 다시 선택하세요.") from None


def browse_folders(body: dict, connected_root: Path | None) -> dict:
    """List one local directory for the browser fallback without changing app state."""
    raw_path = body.get("path")
    if raw_path is not None:
        if not isinstance(raw_path, str) or len(raw_path) > 4096 or "\x00" in raw_path:
            raise ValueError("폴더 경로 형식이 올바르지 않습니다.")
        requested = Path(raw_path)
        if not requested.is_absolute():
            raise ValueError("절대 경로로 폴더를 선택하세요.")
    else:
        requested = connected_root.parent if connected_root is not None else Path.home()
    try:
        folder = requested.resolve(strict=True)
        if not folder.is_dir():
            raise ValueError
    except (OSError, RuntimeError, ValueError):
        raise ValueError("폴더를 찾을 수 없거나 읽을 수 없습니다.") from None

    directories = []
    truncated = False
    try:
        with os.scandir(folder) as entries:
            for scanned, entry in enumerate(entries, start=1):
                try:
                    if not entry.name.startswith(".") and not entry.is_symlink() and entry.is_dir(follow_symlinks=False):
                        directories.append({"name": entry.name, "path": str(Path(entry.path).resolve())})
                except (OSError, RuntimeError):
                    pass
                if scanned >= 5000:
                    truncated = True
                    break
    except (OSError, PermissionError):
        raise ValueError("폴더를 읽을 권한이 없습니다.") from None
    directories.sort(key=lambda item: item["name"].casefold())
    if len(directories) > 200:
        truncated = True
    directories = directories[:200]

    shortcuts = [("Home", Path.home())]
    if connected_root is not None:
        shortcuts.append(("Current wiki", connected_root))
    filesystem_root = Path(folder.anchor)
    shortcuts.append(("Filesystem root", filesystem_root))
    volumes = Path("/Volumes")
    if sys.platform == "darwin" and volumes.is_dir():
        shortcuts.append(("Volumes", volumes))
    unique_shortcuts = []
    seen = set()
    for name, path in shortcuts:
        try:
            resolved = path.resolve(strict=True)
            if not resolved.is_dir():
                continue
        except (OSError, RuntimeError):
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        unique_shortcuts.append({"name": name, "path": str(resolved)})
    parent = folder.parent if folder.parent != folder else None
    return {"path": str(folder), "parent": str(parent) if parent is not None else None,
            "directories": directories, "shortcuts": unique_shortcuts, "truncated": truncated}
