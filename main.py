import uuid

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import date
from sqlalchemy import create_engine, Column, String, Date, ForeignKey, Float, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session

# Инициализация SQLAlchemy
SQLALCHEMY_DATABASE_URL = "sqlite:///./workouts.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Модель упражнения
class ExerciseDB(Base):
    __tablename__ = "exercises"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    description = Column(String)

    sets = relationship("SetDB", back_populates="exercise", cascade="all, delete")


# Модель подхода
class SetDB(Base):
    __tablename__ = "sets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    exercise_id = Column(String, ForeignKey("exercises.id"))
    weight = Column(Float, nullable=False)
    reps = Column(Integer, nullable=False)
    set_number = Column(Integer, nullable=False)
    date = Column(Date, nullable=False)  # Дата выполнения подхода

    exercise = relationship("ExerciseDB", back_populates="sets")

# Создаем таблицы
Base.metadata.create_all(bind=engine)

# Pydantic модели (схемы)
class SetBase(BaseModel):
    weight: float
    reps: int
    set_number: int
    date: date  # Формат: "YYYY-MM-DD"

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat()  # Для корректной сериализации в JSON
        }


class SetCreate(SetBase):
    exercise_id: int


class Set(SetBase):
    id: int

    class Config:
        orm_mode = True
        json_encoders = {
            date: lambda v: v.isoformat()
        }


class ExerciseBase(BaseModel):
    name: str
    description: Optional[str] = None


class ExerciseCreate(ExerciseBase):
    pass

class Exercise(ExerciseBase):
    id: int
    sets: List[Set] = []

    class Config:
        orm_mode = True
        json_encoders = {
            date: lambda v: v.isoformat()
        }

app = FastAPI()

# Dependency для получения сессии БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Роуты
# Роуты для упражнений
@app.post("/exercises/", response_model=Exercise, status_code=201)
def create_exercise(exercise: ExerciseCreate, db: Session = Depends(get_db)):
    db_exercise = ExerciseDB(**exercise.model_dump())
    db.add(db_exercise)
    db.commit()
    db.refresh(db_exercise)
    return db_exercise


@app.get("/exercises/", response_model=List[Exercise])
def get_exercises(db: Session = Depends(get_db)):
    return db.query(ExerciseDB).all()


@app.get("/exercises/{exercise_id}", response_model=Exercise)
def get_exercise(exercise_id: str, db: Session = Depends(get_db)):
    exercise = db.query(ExerciseDB).filter(ExerciseDB.id == exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return exercise

# Роуты для подходов
@app.post("/sets/", response_model=Set, status_code=201)
def create_set(set_data: SetCreate, db: Session = Depends(get_db)):
    # Проверяем существование упражнения
    if not db.query(ExerciseDB).filter(ExerciseDB.id == set_data.exercise_id).first():
        raise HTTPException(status_code=404, detail="Exercise not found")

    db_set = SetDB(**set_data.model_dump())
    db.add(db_set)
    db.commit()
    db.refresh(db_set)
    return db_set


@app.get("/exercises/{exercise_id}/sets", response_model=List[Set])
def get_exercise_sets(exercise_id: str, db: Session = Depends(get_db)):
    exercise = db.query(ExerciseDB).filter(ExerciseDB.id == exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return exercise.sets


@app.get("/sets/recent", response_model=List[Set])
def get_recent_sets(limit: int = 10, db: Session = Depends(get_db)):
    return db.query(SetDB).order_by(SetDB.date.desc()).limit(limit).all()
