from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.database import get_session
from app.models.user import ApiKey, User
from app.security.auth import authenticate_user, create_user
from app.security.vault import vault

router = APIRouter(prefix="/users", tags=["users"])


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class ApiKeyCreate(BaseModel):
    exchange: str
    api_key: str
    api_secret: str
    is_paper: bool = True


@router.post("/register")
async def register(body: UserCreate, session: AsyncSession = Depends(get_session)) -> dict:
    existing = await session.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Username already taken")

    user = await create_user(session, body.username, body.email, body.password)
    return {"user": user.to_dict()}


@router.post("/login")
async def login(body: UserLogin, session: AsyncSession = Depends(get_session)) -> dict:
    user = await authenticate_user(session, body.username, body.password)
    if not user:
        raise HTTPException(401, "Invalid credentials")
    return {"user": user.to_dict()}


@router.get("/{user_id}")
async def get_user(user_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    return {"user": user.to_dict()}


@router.post("/{user_id}/keys")
async def add_api_key(
    user_id: str, body: ApiKeyCreate, session: AsyncSession = Depends(get_session)
) -> dict:
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")

    api_key = ApiKey(
        user_id=user_id,
        exchange=body.exchange,
        api_key_enc=vault.encrypt(body.api_key),
        api_secret_enc=vault.encrypt(body.api_secret),
        is_paper=body.is_paper,
    )
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)
    return {"key": api_key.to_dict()}


@router.get("/{user_id}/keys")
async def list_api_keys(user_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    result = await session.execute(
        select(ApiKey).where(ApiKey.user_id == user_id)
    )
    keys = result.scalars().all()
    return {"keys": [k.to_dict() for k in keys]}


@router.delete("/{user_id}/keys/{key_id}")
async def delete_api_key(
    user_id: str, key_id: str, session: AsyncSession = Depends(get_session)
) -> dict:
    key = await session.get(ApiKey, key_id)
    if not key or key.user_id != user_id:
        raise HTTPException(404, "API key not found")
    await session.delete(key)
    await session.commit()
    return {"deleted": key_id}
