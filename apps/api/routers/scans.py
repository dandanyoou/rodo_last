import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from apps.api.core.config import settings
from apps.api.core.database import get_db
from apps.api.models import ScanSession
from apps.api.schemas import ScanSessionDetail, ScanSessionRead

router = APIRouter(prefix="/scan", tags=["scans"])

ALLOWED_VIDEO_EXT = {"mp4", "mov", "webm", "m4v"}


def _now():
    return datetime.now(timezone.utc)


def _execute_scan(scan_id: int, video_path: str):
    from apps.api.core.database import SessionLocal
    from apps.api.services.scan_reconstruct import ReconstructionError, generate_mesh, reconstruct

    db = SessionLocal()
    try:
        scan = db.get(ScanSession, scan_id)
        if scan is None:
            return
        scan.status = "running"
        db.commit()

        cloud, camera_count = reconstruct(Path(video_path))
        scan.point_count = len(cloud)
        scan.camera_count = camera_count
        scan.pointcloud_json = json.dumps(cloud.tolist())

        verts, faces, method = generate_mesh(cloud)
        if verts is not None:
            scan.mesh_vertices_json = json.dumps(verts.tolist())
            scan.mesh_faces_json = json.dumps(faces.tolist())
            scan.mesh_method = method

        scan.status = "done"
        scan.finished_at = _now()
        db.commit()
    except (ReconstructionError, Exception) as e:
        scan = db.get(ScanSession, scan_id)
        if scan:
            scan.status = "failed"
            scan.error = str(e)
            scan.finished_at = _now()
            db.commit()
    finally:
        db.close()


@router.post("/upload", response_model=ScanSessionRead, status_code=201)
async def upload_scan(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    name: str = Form("이름 없는 스캔"),
    db: Session = Depends(get_db),
):
    ext = video.filename.rsplit(".", 1)[-1].lower() if video.filename and "." in video.filename else "webm"
    if ext not in ALLOWED_VIDEO_EXT:
        ext = "webm"

    scan_dir = Path(settings.UPLOAD_DIR) / "scan_videos"
    scan_dir.mkdir(parents=True, exist_ok=True)
    video_filename = f"{uuid.uuid4().hex}.{ext}"
    video_path = scan_dir / video_filename
    video_path.write_bytes(await video.read())

    scan = ScanSession(name=name.strip() or "이름 없는 스캔", video_filename=video_filename, status="pending")
    db.add(scan)
    db.commit()
    db.refresh(scan)

    background_tasks.add_task(_execute_scan, scan.id, str(video_path))
    return scan


@router.get("/{scan_id}", response_model=ScanSessionDetail)
def get_scan(scan_id: int, db: Session = Depends(get_db)):
    scan = db.get(ScanSession, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="ScanSession not found")

    data = ScanSessionDetail.model_validate(scan)
    if scan.status == "done" and scan.pointcloud_json:
        data.points = json.loads(scan.pointcloud_json)
        data.has_mesh = bool(scan.mesh_vertices_json)
        if scan.mesh_vertices_json:
            data.mesh_vertices = json.loads(scan.mesh_vertices_json)
            data.mesh_faces = json.loads(scan.mesh_faces_json)
            data.mesh_method = scan.mesh_method
    return data
