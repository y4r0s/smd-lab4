"""CRUD проектов сравнения (ФТ-1, ФТ-10).

Инварианты агрегата Project (ЛР № 2, таблица 11): уникальность имени (409),
проект с активными сравнениями не удаляется (409).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=schemas.ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(payload: schemas.ProjectCreate, db: Session = Depends(get_db)) -> models.Project:
    project = models.Project(name=payload.name, description=payload.description)
    db.add(project)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"проект с именем {payload.name!r} уже существует",
        ) from exc
    db.refresh(project)
    return project


@router.get("", response_model=list[schemas.ProjectOut])
def list_projects(db: Session = Depends(get_db)) -> list[models.Project]:
    return list(db.query(models.Project).order_by(models.Project.id).all())


@router.get("/{project_id}", response_model=schemas.ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db)) -> models.Project:
    project = db.get(models.Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="проект не найден")
    return project


@router.put("/{project_id}", response_model=schemas.ProjectOut)
def update_project(
    project_id: int, payload: schemas.ProjectUpdate, db: Session = Depends(get_db)
) -> models.Project:
    project = db.get(models.Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="проект не найден")
    data = payload.model_dump(exclude_unset=True)
    if "name" in data:
        project.name = data["name"]
    if "description" in data:
        project.description = data["description"]
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"проект с именем {data.get('name')!r} уже существует",
        ) from exc
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, db: Session = Depends(get_db)) -> None:
    project = db.get(models.Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="проект не найден")
    if project.comparisons:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="проект содержит сравнения и не может быть удалён (инвариант ЛР № 2)",
        )
    db.delete(project)
    db.commit()
