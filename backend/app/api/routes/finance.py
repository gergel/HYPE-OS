from app.api.crud_router import build_crud_router
from app.models.finance import Expense, KpForgalom, Revenue
from app.schemas.finance import (
    ExpenseCreate,
    ExpenseRead,
    ExpenseUpdate,
    KpForgalomCreate,
    KpForgalomRead,
    KpForgalomUpdate,
    RevenueCreate,
    RevenueRead,
    RevenueUpdate,
)

expenses_router = build_crud_router(
    model=Expense,
    create_schema=ExpenseCreate,
    update_schema=ExpenseUpdate,
    read_schema=ExpenseRead,
    prefix="/expenses",
    tags=["finance"],
)

revenues_router = build_crud_router(
    model=Revenue,
    create_schema=RevenueCreate,
    update_schema=RevenueUpdate,
    read_schema=RevenueRead,
    prefix="/revenues",
    tags=["finance"],
)

kp_forgalom_router = build_crud_router(
    model=KpForgalom,
    create_schema=KpForgalomCreate,
    update_schema=KpForgalomUpdate,
    read_schema=KpForgalomRead,
    prefix="/kp-forgalom",
    tags=["finance"],
)
