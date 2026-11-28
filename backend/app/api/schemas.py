from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field, model_validator

from app.types import Money

Timeframe = Literal["1m", "1h", "1d"]

MAX_REPLAY_DAYS = 366 * 12
MAX_PERIODS = 1000
MAX_SESSION_ASSETS = 200
MIN_SPEED, MAX_SPEED = Decimal("0.1"), Decimal("20")


class SessionCreate(BaseModel):
    mode: Literal["live", "replay"]
    bar_timeframe: Timeframe
    start_at: AwareDatetime
    end_at: AwareDatetime | None = None
    initial_cash: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    period_length_days: int | None = Field(default=None, gt=0)
    speed: Decimal = Field(default=Decimal("1"), ge=MIN_SPEED, le=MAX_SPEED, decimal_places=2)
    # Assets the session trades; omitted or empty means every asset.
    asset_ids: list[int] | None = Field(default=None, max_length=MAX_SESSION_ASSETS)

    @model_validator(mode="after")
    def check_range(self):
        if self.mode == "replay" and (self.end_at is None or self.end_at <= self.start_at):
            raise ValueError("replay sessions need end_at after start_at")
        if self.end_at is not None:
            span_days = (self.end_at - self.start_at).total_seconds() / 86400
            if span_days > MAX_REPLAY_DAYS:
                raise ValueError(f"sessions can span at most {MAX_REPLAY_DAYS} days")
            if self.period_length_days and span_days / self.period_length_days > MAX_PERIODS:
                raise ValueError(f"a session can have at most {MAX_PERIODS} trading periods")
        return self


class PeriodOut(BaseModel):
    period_no: int
    starts_at: datetime
    ends_at: datetime


class SessionOut(BaseModel):
    id: int
    mode: str
    bar_timeframe: Timeframe
    start_at: datetime
    end_at: datetime | None
    sim_time: datetime
    speed: Money
    status: str
    initial_cash: Money
    period_length_days: int | None
    portfolio_id: int
    periods: list[PeriodOut]
    asset_ids: list[int]


class SpeedIn(BaseModel):
    """Replay steps per real second."""
    speed: Decimal = Field(ge=MIN_SPEED, le=MAX_SPEED, decimal_places=2)


class PositionOut(BaseModel):
    asset_id: int
    symbol: str
    net_qty: Money
    avg_cost: Money
    last_price: Money | None


class PortfolioOut(BaseModel):
    cash: Money
    positions: list[PositionOut]


class OrderCreate(BaseModel):
    asset_id: int
    side: Literal["buy", "sell"]
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=4)
    order_type: Literal["market", "limit"] = "market"
    limit_price: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=4)

    @model_validator(mode="after")
    def check_limit_price(self):
        if (self.order_type == "limit") != (self.limit_price is not None):
            raise ValueError("limit_price is required for limit orders and only for them")
        return self


class OrderOut(BaseModel):
    id: int
    asset_id: int
    side: str
    order_type: str
    quantity: Money
    limit_price: Money | None
    placed_at_sim: datetime
    status: str
    reject_reason: str | None


class PeriodLimitIn(BaseModel):
    max_buy_amount: Decimal | None = Field(default=None, ge=0)
    max_sell_amount: Decimal | None = Field(default=None, ge=0)
    max_orders: int | None = Field(default=None, ge=0)


class AssetOut(BaseModel):
    id: int
    symbol: str
    name: str
    sector: str
