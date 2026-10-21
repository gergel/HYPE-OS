from pydantic import BaseModel


class MyDashboardConfig(BaseModel):
    visible_widgets: list[str] | None


class DashboardConfigUpdate(BaseModel):
    visible_widgets: list[str] | None
