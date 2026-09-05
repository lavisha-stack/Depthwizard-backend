"""HTTP routes shared by the frontend and 3D viewer."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from file_manager import (
    UploadTooLargeError,
    create_job,
    get_job_dir,
    read_status,
    safe_result_file,
    save_upload,
    save_support_file,
    update_status,
)
from pipeline_runner import PipelineStageError, run_pipeline

router = APIRouter(prefix="/api")
logger = logging.getLogger("depthwizard")


def _run_pipeline_background(
    input_path: Path,
    job_dir: Path,
    job_id: str,
    srtm_path: Path | None,
    gcp_path: Path | None,
) -> None:
    """Run a job after the upload response; run_pipeline persists all failures."""
    try:
        run_pipeline(input_path, job_dir, job_id, srtm_path, gcp_path)
    except PipelineStageError:
        # The job's status.json already contains the safe message and private
        # stdout/stderr. Avoid turning a handled pipeline failure into an
        # unhandled ASGI background-task exception.
        logger.info("[DepthWizard] Job %s ended with a recorded pipeline failure", job_id)


def _load_metadata(job_dir: Path) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for path in (
        job_dir / "person1" / "metadata.json",
        job_dir / "person2" / "depth_metadata.json",
        job_dir / "person3" / "calibration_report.json",
        job_dir / "person3" / "metadata.json",
    ):
        if path.is_file():
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(value, dict):
                    merged.update(value)
            except (OSError, json.JSONDecodeError):
                logger.warning("Could not read metadata file %s", path)
    return merged


def _find(job_dir: Path, names: tuple[str, ...], prefixes: tuple[str, ...] = ()) -> Path | None:
    for folder in ("results", "person3", "person2", "person1"):
        for name in names:
            path = job_dir / folder / name
            if path.is_file():
                return path
        for path in folder_path_files(job_dir / folder):
            if any(path.name.startswith(prefix) for prefix in prefixes):
                return path
    return None


def folder_path_files(path: Path) -> list[Path]:
    return list(path.iterdir()) if path.is_dir() else []


def _url(request: Request, job_id: str, path: Path | None) -> str | None:
    return str(request.url_for("get_result_file", job_id=job_id, filename=path.name)) if path else None


@router.post("/process")
async def process_image(
    request: Request,
    background_tasks: BackgroundTasks,
    image: UploadFile = File(..., description="TIFF, PNG, or JPEG image"),
    srtm: UploadFile | None = File(None, description="Optional SRTM TIFF/HGT"),
    gcp: UploadFile | None = File(None, description="Optional GCP CSV/JSON"),
) -> dict[str, Any]:
    job_id, job_dir = create_job()
    logger.info("[DepthWizard] New job: %s", job_id)
    try:
        input_path = await save_upload(image, job_dir)
        srtm_path = await save_support_file(srtm, job_dir, "srtm", {".tif", ".tiff", ".hgt"}) if srtm else None
        gcp_path = await save_support_file(gcp, job_dir, "gcps", {".csv", ".json"}) if gcp else None
        update_status(job_dir, status="queued", progress=5)
        background_tasks.add_task(
            _run_pipeline_background,
            input_path,
            job_dir,
            job_id,
            srtm_path,
            gcp_path,
        )
    except UploadTooLargeError as exc:
        update_status(job_dir, status="failed", progress=0, stage="upload", message=str(exc))
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except ValueError as exc:
        update_status(job_dir, status="failed", progress=0, stage="upload", message=str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"job_id": job_id, "status": "queued", "progress": 5}


@router.get("/status/{job_id}")
def job_status(job_id: str) -> dict[str, Any]:
    try:
        return read_status(get_job_dir(job_id))
    except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=404, detail="Job not found.") from exc


def build_results(request: Request, job_id: str, job_dir: Path) -> dict[str, Any]:
    status = read_status(job_dir)
    if status.get("status") != "completed":
        raise HTTPException(status_code=409, detail="Results are not available because the job is not complete.")
    depth_preview = _find(job_dir, ("relative_depth_preview.png", "relative_depth_preview.jpg", "relative_depth_preview.jpeg", "relative_depth_preview.tif", "relative_depth_preview.tiff"), ("relative_depth_preview",))
    dsm_preview = _find(job_dir, ("dsm_preview.png", "preview_dsm.png", "dsm_preview.jpg", "dsm_preview.jpeg", "dsm_preview.tif", "dsm_preview.tiff"), ("dsm_preview", "preview_dsm"))
    dsm = _find(job_dir, ("absolute_dsm.tif", "absolute_dsm.tiff", "fused_dsm.tif", "fused_dsm.tiff", "absolute_dsm.npy", "fused_dsm.npy"))
    # The Three.js client consumes the browser-safe JSON contract. Raw NPY/TIFF
    # arrays remain available through dsm_download_url, but must never be sent
    # as heightmap_url because response.json() cannot decode those formats.
    heightmap = _find(job_dir, ("heightmap.json",))
    # Person 1 bounds rgb_model.png to the configured model grid (normally no
    # more than 3072 px), which is comfortably within modern WebGL limits and
    # retains much more oblique-view detail than the small UI preview.
    texture = _find(job_dir, ("rgb_model.png", "rgb_model.jpg", "rgb_model.jpeg", "preview.png", "rgb_model.tif", "rgb_model.tiff"), ("rgb_model",))
    metadata_file = _find(job_dir, ("metadata.json", "calibration_report.json"))
    result: dict[str, Any] = {"job_id": job_id, "status": "completed"}
    result.update(_load_metadata(job_dir))
    result.update({
        "depth_preview_url": _url(request, job_id, depth_preview),
        "dsm_preview_url": _url(request, job_id, dsm_preview),
        "dsm_download_url": _url(request, job_id, dsm),
        "three_d_data_url": _url(request, job_id, heightmap),
        "heightmap_url": _url(request, job_id, heightmap),
        "texture_url": _url(request, job_id, texture),
        "metadata_url": _url(request, job_id, metadata_file),
    })
    return result


@router.get("/results/{job_id}")
def job_results(request: Request, job_id: str) -> dict[str, Any]:
    try:
        return build_results(request, job_id, get_job_dir(job_id))
    except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=404, detail="Job not found.") from exc


@router.get("/files/{job_id}/{filename}", name="get_result_file")
def get_result_file(job_id: str, filename: str) -> FileResponse:
    try:
        path = safe_result_file(get_job_dir(job_id), filename)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="File not found.") from exc
    return FileResponse(path, filename=path.name)
