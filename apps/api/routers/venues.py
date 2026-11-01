from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.api.core.database import get_db
from apps.api.models import Venue
from apps.api.schemas import VenueCreate, VenueRead

router = APIRouter(prefix="/venues", tags=["venues"])


@router.get("", response_model=list[VenueRead])
def list_venues(db: Session = Depends(get_db)):
    return db.query(Venue).order_by(Venue.created_at.desc()).all()


@router.post("", response_model=VenueRead, status_code=201)
def create_venue(body: VenueCreate, db: Session = Depends(get_db)):
    venue = Venue(**body.model_dump())
    db.add(venue)
    db.commit()
    db.refresh(venue)
    return venue


@router.get("/{venue_id}", response_model=VenueRead)
def get_venue(venue_id: int, db: Session = Depends(get_db)):
    venue = db.get(Venue, venue_id)
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
    return venue


@router.delete("/{venue_id}", status_code=204)
def delete_venue(venue_id: int, db: Session = Depends(get_db)):
    venue = db.get(Venue, venue_id)
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
    db.delete(venue)
    db.commit()
