from fastapi import APIRouter

from app.features.assomi.router import router as assomi_router
from app.features.email.router import router as email_router
from app.features.nat.router import router as nat_intake_router
from app.features.nat.spin_router import router as spin_router

api_router = APIRouter()
api_router.include_router(nat_intake_router)
api_router.include_router(spin_router)
api_router.include_router(assomi_router)
api_router.include_router(email_router)
