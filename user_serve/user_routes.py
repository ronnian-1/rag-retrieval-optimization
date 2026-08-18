from fastapi import APIRouter, Body
from db_server.user_repository import login_user
from pydantic import BaseModel


user_router = APIRouter(
    prefix="/user",
    tags=["user"]
)

class LoginRequest(BaseModel):
    username: str

@user_router.post("/login")
async def login(data: LoginRequest):

    return login_user(data.username)