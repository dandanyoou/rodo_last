import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from apps.api.core.config import settings
from apps.api.core.database import get_db
from apps.api.models import Booth, Layout, SimRun, Venue
from apps.api.schemas import LayoutRead
from apps.api.services.tiled_import import LayoutImportError, parse_layout_json

router = APIRouter(prefix="/layouts", tags=["layouts"])

ALLOWED_IMAGE_EXT = {"png", "jpg", "jpeg", "webp"}


@router.post("/upload", response_model=LayoutRead, status_code=201)
async def upload_layout(
    venue_name: str = Form(...),
    layout_name: str = Form(...),
    layout_file: UploadFile = File(...),
    floor_image: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    content = await layout_file.read()
    try:
        data = json.loads(content)
        (width, height), (ex, ey), (xx, xy), booths = parse_layout_json(data)
    except (LayoutImportError, ValueError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=422, detail=f"배치도를 읽지 못했습니다: {e}")

    floor_image_filename = None
    if floor_image and floor_image.filename:
        ext = floor_image.filename.rsplit(".", 1)[-1].lower() if "." in floor_image.filename else ""
        if ext not in ALLOWED_IMAGE_EXT:
            raise HTTPException(status_code=422, detail="평면도 이미지는 png/jpg/jpeg/webp만 지원합니다.")
        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)
        floor_image_filename = f"{uuid.uuid4().hex}_{floor_image.filename}"
        img_bytes = await floor_image.read()
        (upload_dir / floor_image_filename).write_bytes(img_bytes)

    venue = Venue(name=venue_name, width=width, height=height)
    db.add(venue)
    db.flush()

    layout = Layout(
        venue_id=venue.id,
        name=layout_name,
        entrance_x=ex,
        entrance_y=ey,
        exit_x=xx,
        exit_y=xy,
        floor_image_filename=floor_image_filename,
    )
    db.add(layout)
    db.flush()

    for b in booths:
        db.add(Booth(
            layout_id=layout.id,
            name=b["name"],
            x=b["x"], y=b["y"], w=b["w"], h=b["h"],
            stay_type=b["stay_type"],
        ))

    db.commit()
    db.refresh(layout)
    return layout


@router.get("/{layout_id}", response_model=LayoutRead)
def get_layout(layout_id: int, db: Session = Depends(get_db)):
    layout = db.get(Layout, layout_id)
    if not layout:
        raise HTTPException(status_code=404, detail="Layout not found")
    return layout


@router.get("/{layout_id}/simruns")
def list_simruns(layout_id: int, db: Session = Depends(get_db)):
    layout = db.get(Layout, layout_id)
    if not layout:
        raise HTTPException(status_code=404, detail="Layout not found")
    runs = db.query(SimRun).filter_by(layout_id=layout_id).order_by(SimRun.created_at.desc()).all()
    return [{"id": r.id, "status": r.status, "visitor_count": r.visitor_count, "created_at": r.created_at} for r in runs]


@router.delete("/{layout_id}", status_code=204)
def delete_layout(layout_id: int, db: Session = Depends(get_db)):
    layout = db.get(Layout, layout_id)
    if not layout:
        raise HTTPException(status_code=404, detail="Layout not found")
    db.delete(layout)
    db.commit()
