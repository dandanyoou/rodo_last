from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, ForeignKey
)
from sqlalchemy.orm import DeclarativeBase, relationship


def _now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class ScanSession(Base):
    __tablename__ = "scan_session"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    video_filename = Column(String(300), nullable=False)
    status = Column(String(20), default="pending")  # pending/running/done/failed
    error = Column(Text, nullable=True)
    point_count = Column(Integer, nullable=True)
    camera_count = Column(Integer, nullable=True)
    pointcloud_json = Column(Text, nullable=True)
    mesh_vertices_json = Column(Text, nullable=True)
    mesh_faces_json = Column(Text, nullable=True)
    mesh_method = Column(String(30), nullable=True)
    created_at = Column(DateTime, default=_now)
    finished_at = Column(DateTime, nullable=True)


class Venue(Base):
    __tablename__ = "venue"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    width = Column(Float, nullable=False)
    height = Column(Float, nullable=False)
    created_at = Column(DateTime, default=_now)

    layouts = relationship("Layout", back_populates="venue", cascade="all, delete-orphan")
    field_logs = relationship("FieldLog", back_populates="venue", cascade="all, delete-orphan")


class Layout(Base):
    __tablename__ = "layout"

    id = Column(Integer, primary_key=True)
    venue_id = Column(Integer, ForeignKey("venue.id"), nullable=False)
    name = Column(String(200), nullable=False)
    version = Column(Integer, default=1)
    entrance_x = Column(Float, nullable=False)
    entrance_y = Column(Float, nullable=False)
    exit_x = Column(Float, nullable=False)
    exit_y = Column(Float, nullable=False)
    floor_image_filename = Column(String(300), nullable=True)
    created_at = Column(DateTime, default=_now)

    venue = relationship("Venue", back_populates="layouts")
    booths = relationship("Booth", back_populates="layout", cascade="all, delete-orphan")
    simruns = relationship("SimRun", back_populates="layout", cascade="all, delete-orphan")


class Booth(Base):
    __tablename__ = "booth"

    id = Column(Integer, primary_key=True)
    layout_id = Column(Integer, ForeignKey("layout.id"), nullable=False)
    name = Column(String(200), nullable=False)
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    w = Column(Float, nullable=False)
    h = Column(Float, nullable=False)
    stay_type = Column(String(20), default="관람형")

    layout = relationship("Layout", back_populates="booths")


class SimRun(Base):
    __tablename__ = "sim_run"

    id = Column(Integer, primary_key=True)
    layout_id = Column(Integer, ForeignKey("layout.id"), nullable=False)
    visitor_count = Column(Integer, nullable=False)
    repeats = Column(Integer, default=1)
    status = Column(String(20), default="pending")  # pending/running/done/failed
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_now)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    layout = relationship("Layout", back_populates="simruns")
    result = relationship("SimResult", back_populates="simrun", uselist=False, cascade="all, delete-orphan")


class SimResult(Base):
    __tablename__ = "sim_result"

    id = Column(Integer, primary_key=True)
    simrun_id = Column(Integer, ForeignKey("sim_run.id"), nullable=False)
    booth_stats_json = Column(Text, nullable=False)
    bottleneck_ranking_json = Column(Text, nullable=False)
    overall_congestion_score = Column(Float, nullable=False)
    heatmap_cells_json = Column(Text, nullable=False, default="[]")
    cell_size = Column(Float, nullable=False, default=1.0)

    simrun = relationship("SimRun", back_populates="result")


# FieldLog / Accuracy / SegmentWeight: schema only — manual ingestion until PoC round 1
class FieldLog(Base):
    __tablename__ = "field_log"

    id = Column(Integer, primary_key=True)
    venue_id = Column(Integer, ForeignKey("venue.id"), nullable=False)
    measured_at = Column(DateTime, nullable=False)
    zone = Column(String(200), nullable=False)
    headcount = Column(Integer, nullable=False)

    venue = relationship("Venue", back_populates="field_logs")


class Accuracy(Base):
    __tablename__ = "accuracy"

    id = Column(Integer, primary_key=True)
    simrun_id = Column(Integer, ForeignKey("sim_run.id"), nullable=False)
    fieldlog_id = Column(Integer, ForeignKey("field_log.id"), nullable=False)
    metric = Column(String(50), nullable=False)
    predicted = Column(Float, nullable=False)
    actual = Column(Float, nullable=False)
    error_pct = Column(Float, nullable=False)


class SegmentWeight(Base):
    __tablename__ = "segment_weight"

    id = Column(Integer, primary_key=True)
    segment = Column(String(100), nullable=False)
    booth_stay_type = Column(String(20), nullable=False)
    stay_multiplier = Column(Float, default=1.0)
    evidence_log_count = Column(Integer, default=0)
