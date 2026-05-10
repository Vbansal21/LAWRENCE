from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def _windows_path(path: Path) -> str:
    if shutil.which("wslpath") is None:
        raise RuntimeError("wslpath is required from WSL.")
    return subprocess.check_output(["wslpath", "-w", str(path)], text=True).strip()


def take_screenshot(out_path: Path) -> Path:
    if shutil.which("powershell.exe") is None:
        raise RuntimeError("powershell.exe is required for screenshot capture from WSL.")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    target = _windows_path(out_path)
    ps_script = (
        "Add-Type -AssemblyName System.Windows.Forms;"
        "Add-Type -AssemblyName System.Drawing;"
        "$b=[System.Windows.Forms.SystemInformation]::VirtualScreen;"
        "$bmp=New-Object System.Drawing.Bitmap $b.Width,$b.Height;"
        "$g=[System.Drawing.Graphics]::FromImage($bmp);"
        "$g.CopyFromScreen($b.Left,$b.Top,0,0,$b.Size);"
        f"$bmp.Save('{target}',[System.Drawing.Imaging.ImageFormat]::Png);"
        "$g.Dispose();$bmp.Dispose();"
    )
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    if not out_path.exists():
        raise RuntimeError(f"screenshot was not written: {out_path}")
    return out_path


def clipboard_image(out_path: Path) -> Path:
    if shutil.which("powershell.exe") is None:
        raise RuntimeError("powershell.exe is required for clipboard image capture from WSL.")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    target = _windows_path(out_path)
    ps_script = (
        "Add-Type -AssemblyName System.Windows.Forms;"
        "Add-Type -AssemblyName System.Drawing;"
        "$img=[System.Windows.Forms.Clipboard]::GetImage();"
        "if ($null -eq $img) { exit 2 };"
        f"$img.Save('{target}',[System.Drawing.Imaging.ImageFormat]::Png);"
        "$img.Dispose();"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode == 2:
        raise RuntimeError("clipboard does not currently contain an image.")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "clipboard capture failed.")
    if not out_path.exists():
        raise RuntimeError(f"clipboard image was not written: {out_path}")
    return out_path


def newest_image(directory: Path) -> Path:
    if not directory.exists():
        raise RuntimeError(f"directory does not exist: {directory}")
    candidates = [
        path
        for pattern in ("*.png", "*.jpg", "*.jpeg", "*.webp")
        for path in directory.glob(pattern)
        if path.is_file()
    ]
    if not candidates:
        raise RuntimeError(f"no recent image found in: {directory}")
    return max(candidates, key=lambda path: path.stat().st_mtime)

