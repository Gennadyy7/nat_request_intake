from fastapi import APIRouter

from app.features.nat.router import router as nat_intake_router

api_router = APIRouter()
api_router.include_router(nat_intake_router)
