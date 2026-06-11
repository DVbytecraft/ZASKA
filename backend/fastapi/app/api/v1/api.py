from fastapi import APIRouter

from app.api.v1.routers import (
    aml,
    addresses,
    admin,
    auth,
    b2b,
    calls,
    cards,
    chat,
    disputes,
    feature_flags,
    food,
    fx,
    geo,
    kyc,
    moderation,
    notifications,
    payments,
    public_demo,
    referrals,
    shop,
    statement,
    subscriptions,
    system,
    tasks,
    trust,
    users,
    vtc,
    wallet,
)

api_router = APIRouter()
api_router.include_router(system.router)   # /system/* en premier — pas de JWT requis
api_router.include_router(public_demo.router)  # /v1/* — endpoints publics, CORS *, pas de JWT/cle API
api_router.include_router(aml.router)
api_router.include_router(auth.router)
api_router.include_router(b2b.router)
api_router.include_router(users.router)
api_router.include_router(tasks.router)
api_router.include_router(food.router)
api_router.include_router(payments.router)
api_router.include_router(chat.router)
api_router.include_router(calls.router)
api_router.include_router(feature_flags.router)
api_router.include_router(geo.router)
api_router.include_router(kyc.router)
api_router.include_router(shop.router)
api_router.include_router(wallet.router)
api_router.include_router(admin.router)
api_router.include_router(addresses.router)
api_router.include_router(cards.router)
api_router.include_router(statement.router)
api_router.include_router(notifications.router)
api_router.include_router(fx.router)
api_router.include_router(trust.router)
api_router.include_router(subscriptions.router)
api_router.include_router(referrals.router)
api_router.include_router(disputes.router)
api_router.include_router(moderation.router)
api_router.include_router(vtc.router)
