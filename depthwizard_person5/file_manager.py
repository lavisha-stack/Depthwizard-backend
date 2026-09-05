"""Safe job directories, uploads, status files, and result discovery."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from config import MAX_UPLOAD_SIZE_MB, RUNTIME_DIR

ALLOWED_EXTENSIONS = {".tif", ".tiff", ".png", ".jpg", ".jpeg"}
JOB_ID_PATTERN = re.compile(r"^job_[0-9a-f]{12}$")
SIGNATURES = {
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".tif": (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"),
    ".tiff": (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"),
}


class UploadTooLargeError(ValueError):
    pass


def create_job() -> tuple[str, Path]:
    (RUNTIME_DIR / "uploads").mkdir(parents=True, exist_ok=True)
    (RUNTIME_DIR / "jobs").mkdir(parents=True, exist_ok=True)
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    job_dir = RUNTIME_DIR / "jobs" / job_id
    for name in ("input", "person1", "person2", "person3", "results"):
        (job_dir / name).mkdir(parents=True, exist_ok=False)
    update_status(job_dir, job_id=job_id, status="uploaded", progress=0)
    return job_id, job_dir


def get_job_dir(job_id: str) -> Path:
    if not JOB_ID_PATTERN.fullmatch(job_id):
        raise FileNotFoundError(job_id)
    path = (RUNTIME_DIR / "jobs" / job_id).resolve()
    jobs_root = (RUNTIME_DIR / "jobs").resolve()
    if path.parent != jobs_root or not path.is_dir():
        raise FileNotFoundError(job_id)
    return path


async def save_upload(upload: UploadFile, job_dir: Path) -> Path:
    original = Path(upload.filename or "upload").name
    suffix = Path(original).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported image format. Use TIFF, PNG, or JPEG.")
    destination = job_dir / "input" / f"scene{suffix}"
    maximum = MAX_UPLOAD_SIZE_MB * 1024 * 1024
    size = 0
    header = b""
    try:
        with destination.open("wb") as output:
            while chunk := await upload.read(1024 * 1024):
                if not header:
                    header = chunk[:8]
                size += len(chunk)
                if size > maximum:
                    raise UploadTooLargeError(f"Upload exceeds the {MAX_UPLOAD_SIZE_MB} MB limit.")
                output.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()
    if size == 0 or not any(header.startswith(sig) for sig in SIGNATURES[suffix]):
        destination.unlink(missing_ok=True)
        raise ValueError("The uploaded file does not appear to match its image extension.")
    return destination


async def save_support_file(upload: UploadFile, job_dir: Path, stem: str, allowed: set[str]) -> Path:
    """Save SRTM/GCP inputs under fixed names, with traversal and size protection."""
    original = Path(upload.filename or "").name
    suffix = Path(original).suffix.lower()
    if suffix not in allowed:
        raise ValueError(f"Unsupported {stem} format. Allowed: {', '.join(sorted(allowed))}.")
    if suffix == ".hgt":
        # GDAL derives an HGT tile's coordinates from names such as N28E077.hgt;
        # renaming every upload to srtm.hgt destroys that georeferencing.
        if not re.fullmatch(r"[NS]\d{2}[EW]\d{3}\.hgt", original, re.IGNORECASE):
            raise ValueError("SRTM HGT files must keep a tile name such as N28E077.hgt.")
        destination = job_dir / "input" / original.upper().replace(".HGT", ".hgt")
    else:
        destination = job_dir / "input" / f"{stem}{suffix}"
    maximum = MAX_UPLOAD_SIZE_MB * 1024 * 1024
    size = 0
    try:
        with destination.open("wb") as output:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > maximum:
                    raise UploadTooLargeError(f"{stem.upper()} upload exceeds the {MAX_UPLOAD_SIZE_MB} MB limit.")
                output.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()
    if not size:
        destination.unlink(missing_ok=True)
        raise ValueError(f"The uploaded {stem} file is empty.")
    return destination


def update_status(job_dir: Path, **values: Any) -> dict[str, Any]:
    path = job_dir / "status.json"
    current: dict[str, Any] = {}
    if path.exists():
        current = json.loads(path.read_text(encoding="utf-8"))
    current.update(values)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(current, indent=2), encoding="utf-8")
    temporary.replace(path)
    return current


def read_status(job_dir: Path) -> dict[str, Any]:
    status = json.loads((job_dir / "status.json").read_text(encoding="utf-8"))
    # Subprocess output is retained on disk for teammates debugging integration,
    # but is not sent to browsers where it can be noisy or reveal local paths.
    for private_key in ("stdout", "stderr"):
        status.pop(private_key, None)
    return status


def safe_result_file(job_dir: Path, filename: str) -> Path:
    # Only a plain filename is accepted; callers cannot select directories.
    if not filename or Path(filename).name != filename or filename in {".", ".."}:
        raise FileNotFoundError(filename)
    for folder in ("results", "person3", "person2", "person1", "input"):
        candidate = (job_dir / folder / filename).resolve()
        if candidate.parent == (job_dir / folder).resolve() and candidate.is_file():
            return candidate
    raise FileNotFoundError(filename)
