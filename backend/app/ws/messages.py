from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter

from app.market.models import Bar, NewsItem
from app.types import Money


class ClockMessage(BaseModel):
    type: Literal["clock"] = "clock"
    sim_time: datetime
    status: Literal["created", "running", "paused", "finished"]


class BarMessage(BaseModel):
    type: Literal["bar"] = "bar"
    asset_id: int
    bar: Bar


class NewsMessage(BaseModel):
    type: Literal["news"] = "news"
    item: NewsItem


class FillMessage(BaseModel):
    type: Literal["fill"] = "fill"
    order_id: int
    status: Literal["filled", "rejected"]
    price: Money | None
    reason: str | None


class PeriodMessage(BaseModel):
    type: Literal["period"] = "period"
    period_no: int
    starts_at: datetime
    ends_at: datetime
    awaiting_limits: bool


ServerMessage = Annotated[
    Union[ClockMessage, BarMessage, NewsMessage, FillMessage, PeriodMessage],
    Field(discriminator="type"),
]
server_message_adapter: TypeAdapter = TypeAdapter(ServerMessage)
