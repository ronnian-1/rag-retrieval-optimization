from fastapi import APIRouter, Body, Depends
from db_server.user_repository import login_user
from db_server.base import get_db
from pydantic import BaseModel
from sqlalchemy.orm import Session


user_router = APIRouter(
    prefix="/user",
    tags=["user"]
)

class LoginRequest(BaseModel):
    username: str

@user_router.post("/login")
async def login(data: LoginRequest, db: Session = Depends(get_db)):

    return login_user(data.username, db)
