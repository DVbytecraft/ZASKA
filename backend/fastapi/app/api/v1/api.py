from fastapi import APIRouter

from app.api.v1.routers import (
    addresses,
    admin,
    auth,
    cards,
    chat,
    feature_flags,
    kyc,
    payments,
    statement,
    system,
    tasks,
    users,
    wallet,
)

api_router = APIRouter()
api_router.include_router(system.router)   # /system/* en premier — pas de JWT requis
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(tasks.router)
api_router.include_router(payments.router)
api_router.include_router(chat.router)
api_router.include_router(feature_flags.router)
api_router.include_router(kyc.router)
api_router.include_router(wallet.router)
api_router.include_router(admin.router)
api_router.include_router(addresses.router)
api_router.include_router(cards.router)
api_router.include_router(statement.router)
