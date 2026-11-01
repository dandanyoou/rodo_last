from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


# --- Venue ---

class VenueCreate(BaseModel):
    name: str
    width: float
    height: float


class VenueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    width: float
    height: float
    created_at: datetime


# --- Booth ---

class BoothRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    x: float
    y: float
    w: float
    h: float
    stay_type: str


# --- Layout ---

class LayoutRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    venue_id: int
    name: str
    version: int
    entrance_x: float
    entrance_y: float
    exit_x: float
    exit_y: float
    floor_image_filename: Optional[str]
    created_at: datetime
    booths: list[BoothRead] = []


# --- SimRun ---

class SimRunCreate(BaseModel):
    visitor_count: int = 500


class SimRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    layout_id: int
    visitor_count: int
    status: str
    error: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]


class SimRunDetail(SimRunRead):
    booth_stats: Optional[dict] = None
    bottleneck_ranking: Optional[list] = None
    overall_congestion_score: Optional[float] = None
    heatmap_cells: Optional[list] = None
    cell_size: Optional[float] = None
    layout_geometry: Optional[dict] = None


# --- ScanSession ---

class ScanSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    status: str
    error: Optional[str]
    point_count: Optional[int]
    camera_count: Optional[int]
    created_at: datetime
    finished_at: Optional[datetime]


class ScanSessionDetail(ScanSessionRead):
    points: Optional[list] = None
    has_mesh: bool = False
    mesh_vertices: Optional[list] = None
    mesh_faces: Optional[list] = None
    mesh_method: Optional[str] = None
