from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from app.market.models import Bar, NewsItem
from app.types import Money


SessionStatus = Literal["created", "running", "paused", "awaiting_limits", "finished"]


class _Message(BaseModel):
    # Serialized messages always carry their `type`, so the schema marks it required.
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class ClockMessage(_Message):
    type: Literal["clock"] = "clock"
    sim_time: datetime
    status: SessionStatus


class BarMessage(_Message):
    type: Literal["bar"] = "bar"
    asset_id: int
    bar: Bar


class NewsMessage(_Message):
    type: Literal["news"] = "news"
    item: NewsItem


class FillMessage(_Message):
    type: Literal["fill"] = "fill"
    order_id: int
    status: Literal["filled", "rejected"]
    price: Money | None
    reason: str | None


class PeriodMessage(_Message):
    type: Literal["period"] = "period"
    period_no: int
    starts_at: datetime
    ends_at: datetime
    awaiting_limits: bool


class AdjustmentMessage(_Message):
    type: Literal["adjustment"] = "adjustment"
    portfolio_id: int
    asset_id: int
    action_type: Literal["split", "dividend"]
    qty_delta: Money
    cash_delta: Money


ServerMessage = Annotated[
    Union[ClockMessage, BarMessage, NewsMessage, FillMessage, PeriodMessage, AdjustmentMessage],
    Field(discriminator="type"),
]
server_message_adapter: TypeAdapter = TypeAdapter(ServerMessage)
