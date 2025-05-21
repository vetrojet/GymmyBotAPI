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

# Модели базы данных
class WorkoutDB(Base):
    __tablename__ = "workouts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    date = Column(Date, nullable=False)
    comments = Column(String)

    exercises = relationship("ExerciseDB", back_populates="workout", cascade="all, delete")

class ExerciseDB(Base):
    __tablename__ = "exercises"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workout_id = Column(String, ForeignKey("workouts.id"))
    name = Column(String, nullable=False)
    notes = Column(String)

    workout = relationship("WorkoutDB", back_populates="exercises")
    sets = relationship("SetDB", back_populates="exercise", cascade="all, delete")


class SetDB(Base):
    __tablename__ = "sets"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    exercise_id = Column(String, ForeignKey("exercises.id"))
    weight = Column(Float, nullable=False)
    reps = Column(Integer, nullable=False)
    set_number = Column(Integer, nullable=False)

    exercise = relationship("ExerciseDB", back_populates="sets")

# Создаем таблицы
Base.metadata.create_all(bind=engine)


# Pydantic модели (схемы)
class SetBase(BaseModel):
    weight: float
    reps: int
    set_number: int


class SetCreate(SetBase):
    pass


class Set(SetBase):
    id: str

    class Config:
        orm_mode = True


class ExerciseBase(BaseModel):
    name: str
    notes: Optional[str] = None


class ExerciseCreate(ExerciseBase):
    pass


class Exercise(ExerciseBase):
    id: str
    sets: List[Set] = []

    class Config:
        orm_mode = True


class WorkoutBase(BaseModel):
    date: date
    comments: Optional[str] = None


class WorkoutCreate(WorkoutBase):
    pass


class Workout(WorkoutBase):
    id: str
    exercises: List[Exercise] = []

    class Config:
        orm_mode = True

app = FastAPI()

# Dependency для получения сессии БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Роуты
@app.post("/workouts/", response_model=Workout, status_code=201)
def create_workout(workout: WorkoutCreate, db: Session = Depends(get_db)):
    db_workout = WorkoutDB(**workout.dict())
    db.add(db_workout)
    db.commit()
    db.refresh(db_workout)
    return db_workout


@app.get("/workouts/", response_model=List[Workout])
def get_workouts(db: Session = Depends(get_db)):
    workouts = db.query(WorkoutDB).all()
    return workouts


@app.post("/workouts/{workout_id}/exercises/", response_model=Exercise, status_code=201)
def create_exercise(workout_id: str, exercise: ExerciseCreate, db: Session = Depends(get_db)):
    db_workout = db.query(WorkoutDB).filter(WorkoutDB.id == workout_id).first()
    if not db_workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    db_exercise = ExerciseDB(**exercise.dict(), workout_id=workout_id)
    db.add(db_exercise)
    db.commit()
    db.refresh(db_exercise)
    return db_exercise


@app.post("/exercises/{exercise_id}/sets/", response_model=Set, status_code=201)
def create_set(exercise_id: str, set_data: SetCreate, db: Session = Depends(get_db)):
    db_exercise = db.query(ExerciseDB).filter(ExerciseDB.id == exercise_id).first()
    if not db_exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")

    db_set = SetDB(**set_data.dict(), exercise_id=exercise_id)
    db.add(db_set)
    db.commit()
    db.refresh(db_set)
    return db_set


@app.get("/exercises/{exercise_id}/sets/", response_model=List[Set])
def get_exercise_sets(exercise_id: str, db: Session = Depends(get_db)):
    db_exercise = db.query(ExerciseDB).filter(ExerciseDB.id == exercise_id).first()
    if not db_exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")

    return db_exercise.sets
