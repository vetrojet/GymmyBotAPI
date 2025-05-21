from fastapi import FastAPI, HTTPException, Depends, status
from pydantic import BaseModel
from typing import List, Optional
from datetime import date
from sqlalchemy import create_engine, Column, Integer, String, Float, Date, ForeignKey
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from fastapi.security import OAuth2PasswordBearer

app = FastAPI()

# Конфигурация БД
DATABASE_URL = "sqlite:///./workouts.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# Модели БД
class UserDB(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True)
    full_name = Column(String)
    username = Column(String)


class ExerciseDB(Base):
    __tablename__ = "exercises"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    name = Column(String, nullable=False)
    description = Column(String)


class SetDB(Base):
    __tablename__ = "sets"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    exercise_id = Column(Integer, ForeignKey("exercises.id"), index=True)
    weight = Column(Float, nullable=False)
    reps = Column(Integer, nullable=False)
    set_number = Column(Integer, nullable=False)
    date = Column(Date, nullable=False)


Base.metadata.create_all(bind=engine)


# Pydantic схемы
class UserBase(BaseModel):
    telegram_id: int
    full_name: Optional[str] = None
    username: Optional[str] = None


class UserCreate(UserBase):
    pass


class ExerciseBase(BaseModel):
    name: str
    description: Optional[str] = None


class ExerciseCreate(ExerciseBase):
    pass


class Exercise(ExerciseBase):
    id: int
    user_id: int

    class Config:
        from_attributes = True


class SetBase(BaseModel):
    exercise_id: int
    weight: float
    reps: int
    set_number: int
    date: date


class SetCreate(SetBase):
    pass


class Set(SetBase):
    id: int
    user_id: int

    class Config:
        from_attributes = True


# Зависимости
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# Вспомогательные функции
async def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    # Здесь должна быть реальная логика аутентификации
    # Для примера считаем, что token = telegram_id
    user = db.query(UserDB).filter(UserDB.telegram_id == int(token)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


# Эндпоинты пользователей
@app.post("/users/", response_model=UserBase)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(UserDB).filter(UserDB.telegram_id == user.telegram_id).first()
    if db_user:
        raise HTTPException(status_code=400, detail="User already exists")

    new_user = UserDB(**user.model_dump())
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


# Эндпоинты упражнений
@app.post("/exercises/", response_model=Exercise)
def create_exercise(
        exercise: ExerciseCreate,
        current_user: UserDB = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    db_exercise = ExerciseDB(**exercise.model_dump(), user_id=current_user.id)
    db.add(db_exercise)
    db.commit()
    db.refresh(db_exercise)
    return db_exercise


@app.get("/exercises/", response_model=List[Exercise])
def get_exercises(
        current_user: UserDB = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    return db.query(ExerciseDB).filter(ExerciseDB.user_id == current_user.id).all()


@app.get("/exercises/{exercise_id}", response_model=Exercise)
def get_exercise(
        exercise_id: int,
        current_user: UserDB = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    exercise = db.query(ExerciseDB).filter(
        ExerciseDB.id == exercise_id,
        ExerciseDB.user_id == current_user.id
    ).first()
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return exercise


# Эндпоинты подходов
@app.post("/sets/", response_model=Set)
def create_set(
        set_data: SetCreate,
        current_user: UserDB = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    # Проверяем существование упражнения
    exercise = db.query(ExerciseDB).filter(
        ExerciseDB.id == set_data.exercise_id,
        ExerciseDB.user_id == current_user.id
    ).first()
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")

    db_set = SetDB(**set_data.model_dump(), user_id=current_user.id)
    db.add(db_set)
    db.commit()
    db.refresh(db_set)
    return db_set


@app.get("/sets/", response_model=List[Set])
def get_sets(
        exercise_id: Optional[int] = None,
        current_user: UserDB = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    query = db.query(SetDB).filter(SetDB.user_id == current_user.id)

    if exercise_id:
        query = query.filter(SetDB.exercise_id == exercise_id)

    return query.order_by(SetDB.date.desc()).all()


@app.delete("/sets/{set_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_set(
        set_id: int,
        current_user: UserDB = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    set_to_delete = db.query(SetDB).filter(
        SetDB.id == set_id,
        SetDB.user_id == current_user.id
    ).first()

    if not set_to_delete:
        raise HTTPException(status_code=404, detail="Set not found")

    db.delete(set_to_delete)
    db.commit()