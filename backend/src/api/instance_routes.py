"""
File: instance_routes.py

Purpose:
Defines API endpoints for instance operations.

Used by:
- FastAPI app
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..services.instance_service import InstanceService
from ..schemas.instance import InstanceCreate, InstanceUpdate, InstanceResponse

router = APIRouter(prefix="/instances", tags=["Instances"])


@router.post("/", response_model=InstanceResponse)
def create_instance(data: InstanceCreate, db: Session = Depends(get_db)):
    service = InstanceService(db)
    return service.create_instance(data)


@router.get("/", response_model=list[InstanceResponse])
def get_instances(db: Session = Depends(get_db)):
    service = InstanceService(db)
    return service.get_all_instances()


@router.get("/{instance_id}", response_model=InstanceResponse)
def get_instance(instance_id: int, db: Session = Depends(get_db)):
    service = InstanceService(db)
    instance = service.get_instance(instance_id)
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")
    return instance


@router.put("/{instance_id}", response_model=InstanceResponse)
def update_instance(instance_id: int, data: InstanceUpdate, db: Session = Depends(get_db)):
    service = InstanceService(db)
    instance = service.update_instance(instance_id, data)
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")
    return instance


@router.delete("/{instance_id}")
def delete_instance(instance_id: int, db: Session = Depends(get_db)):
    service = InstanceService(db)
    success = service.delete_instance(instance_id)
    if not success:
        raise HTTPException(status_code=404, detail="Instance not found")
    return {"message": "Instance deleted successfully"}
