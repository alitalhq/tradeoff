from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class Bar(BaseModel):
    asset_id: int
    timeframe: str
    bar_start: datetime
    bar_end: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


class NewsItem(BaseModel):
    id: int
    source: str
    headline: str
    summary: str
    url: str
    published_at: datetime
