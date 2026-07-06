from app.api.crud_router import build_crud_router
from app.models.campaign import Campaign
from app.schemas.campaign import CampaignCreate, CampaignRead, CampaignUpdate

router = build_crud_router(
    model=Campaign,
    create_schema=CampaignCreate,
    update_schema=CampaignUpdate,
    read_schema=CampaignRead,
    prefix="/campaigns",
    tags=["campaigns"],
    page="/kampanyok",
)
