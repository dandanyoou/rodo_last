import json
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.api.core.database import get_db
from apps.api.models import Layout, SimResult, SimRun
from apps.api.schemas import SimRunCreate, SimRunDetail, SimRunRead
from apps.api.services.simulation import run_simulation

router = APIRouter(tags=["simruns"])


def _now():
    return datetime.now(timezone.utc)


def _layout_geometry(layout):
    return {
        "venue_width": layout.venue.width,
        "venue_height": layout.venue.height,
        "entrance": {"x": layout.entrance_x, "y": layout.entrance_y},
        "exit": {"x": layout.exit_x, "y": layout.exit_y},
        "booths": [{"id": b.id, "name": b.name, "x": b.x, "y": b.y, "w": b.w, "h": b.h} for b in layout.booths],
        "floor_image_filename": layout.floor_image_filename,
    }


def _execute_simrun(simrun_id: int):
    from apps.api.core.database import SessionLocal
    db = SessionLocal()
    try:
        simrun = db.get(SimRun, simrun_id)
        if simrun is None:
            return
        simrun.status = "running"
        simrun.started_at = _now()
        db.commit()

        layout = simrun.layout
        result = run_simulation(layout.venue, layout, layout.booths, simrun.visitor_count, seed=42)

        db.add(SimResult(
            simrun_id=simrun.id,
            booth_stats_json=json.dumps(result["booth_stats"], ensure_ascii=False),
            bottleneck_ranking_json=json.dumps(result["bottleneck_ranking"], ensure_ascii=False),
            overall_congestion_score=result["overall_congestion_score"],
            heatmap_cells_json=json.dumps(result["heatmap_cells"], ensure_ascii=False),
            cell_size=result["cell_size"],
        ))
        simrun.status = "done"
        simrun.finished_at = _now()
        db.commit()
    except Exception as e:
        simrun = db.get(SimRun, simrun_id)
        if simrun:
            simrun.status = "failed"
            simrun.error = str(e)
            simrun.finished_at = _now()
            db.commit()
    finally:
        db.close()


@router.post("/layouts/{layout_id}/simruns", response_model=SimRunRead, status_code=201)
def create_simrun(
    layout_id: int,
    body: SimRunCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    layout = db.get(Layout, layout_id)
    if not layout:
        raise HTTPException(status_code=404, detail="Layout not found")

    visitor_count = max(10, min(body.visitor_count, 5000))
    simrun = SimRun(layout_id=layout.id, visitor_count=visitor_count, status="pending")
    db.add(simrun)
    db.commit()
    db.refresh(simrun)

    background_tasks.add_task(_execute_simrun, simrun.id)
    return simrun


@router.get("/simruns/{simrun_id}", response_model=SimRunDetail)
def get_simrun(simrun_id: int, db: Session = Depends(get_db)):
    simrun = db.get(SimRun, simrun_id)
    if not simrun:
        raise HTTPException(status_code=404, detail="SimRun not found")

    data = SimRunDetail.model_validate(simrun)
    data.layout_geometry = _layout_geometry(simrun.layout)
    if simrun.result:
        data.booth_stats = json.loads(simrun.result.booth_stats_json)
        data.bottleneck_ranking = json.loads(simrun.result.bottleneck_ranking_json)
        data.overall_congestion_score = simrun.result.overall_congestion_score
        data.heatmap_cells = json.loads(simrun.result.heatmap_cells_json)
        data.cell_size = simrun.result.cell_size
    return data


@router.get("/simruns/compare")
def compare_simruns(a: int, b: int, db: Session = Depends(get_db)):
    sa = db.get(SimRun, a)
    sb = db.get(SimRun, b)
    if not sa or not sb:
        raise HTTPException(status_code=404, detail="SimRun not found")
    if sa.status != "done" or sb.status != "done":
        raise HTTPException(status_code=400, detail="두 시뮬레이션이 모두 완료되어야 비교할 수 있습니다.")

    def _payload(simrun):
        return {
            "id": simrun.id,
            "layout_id": simrun.layout_id,
            "visitor_count": simrun.visitor_count,
            "overall_congestion_score": simrun.result.overall_congestion_score,
            "bottleneck_ranking": json.loads(simrun.result.bottleneck_ranking_json),
            "heatmap_cells": json.loads(simrun.result.heatmap_cells_json),
            "cell_size": simrun.result.cell_size,
            "layout_geometry": _layout_geometry(simrun.layout),
        }

    score_a = sa.result.overall_congestion_score
    score_b = sb.result.overall_congestion_score
    more_congested = "A" if score_a > score_b else ("B" if score_b > score_a else "동일")

    return {"a": _payload(sa), "b": _payload(sb), "more_congested": more_congested}
