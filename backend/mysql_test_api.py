from getpass import getpass
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import SQLAlchemyError


password = getpass("MySQL parolini kiriting: ")

database_url = URL.create(
    drivername="mysql+pymysql",
    username="anime_app",
    password=password,
    host="127.0.0.1",
    port=3306,
    database="anime_metadata",
)

engine = create_engine(
    database_url,
    pool_pre_ping=True,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    engine.dispose()


app = FastAPI(
    title="MySQL Test API",
    lifespan=lifespan,
)


class MessageCreate(BaseModel):
    massage: str


@app.get("/health")
def health():
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text("SELECT DATABASE(), VERSION()")
            )
            database, version = result.fetchone()

        return {
            "status": "ok",
            "database": database,
            "mysql_version": version,
        }

    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=503,
            detail=f"Database unavailable: {type(error).__name__}",
        ) from error


@app.post("/messages")
def create_message(data: MessageCreate):
    try:
        with engine.begin() as connection:
            result = connection.execute(
                text("""
                    INSERT INTO connection_test (massage)
                    VALUES (:massage)
                """),
                {"massage": data.massage},
            )

            return {
                "id": result.lastrowid,
                "massage": data.massage,
            }

    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {type(error).__name__}",
        ) from error


@app.get("/messages")
def list_messages():
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text("""
                    SELECT id, massage, created_at
                    FROM connection_test
                    ORDER BY id DESC
                """)
            )

            return [dict(row) for row in result.mappings().all()]

    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {type(error).__name__}",
        ) from error

@app.put("/messages/{message_id}")
def update_message(message_id: int, data: MessageCreate):
    try:
        with engine.begin() as connection:
            result = connection.execute(
                text("""
                    UPDATE connection_test
                    SET massage = :massage
                    WHERE id = :id
                """),
                {
                    "massage": data.massage,
                    "id": message_id,
                },
            )

            if result.rowcount == 0:
                raise HTTPException(
                    status_code=404,
                    detail="Message not found",
                )

        return {
            "id": message_id,
            "massage": data.massage,
            "status": "updated",
        }

    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {type(error).__name__}",
        ) from error


@app.delete("/messages/{message_id}")
def delete_message(message_id: int):
    try:
        with engine.begin() as connection:
            result = connection.execute(
                text("""
                    DELETE FROM connection_test
                    WHERE id = :id
                """),
                {"id": message_id},
            )

            if result.rowcount == 0:
                raise HTTPException(
                    status_code=404,
                    detail="Message not found",
                )

        return {
            "id": message_id,
            "status": "deleted",
        }

    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {type(error).__name__}",
        ) from error