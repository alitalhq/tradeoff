from datetime import datetime
from pydantic import BaseModel

from app.types import Money


class Bar(BaseModel):
    asset_id: int
    timeframe: str
    bar_start: datetime
    bar_end: datetime
    open: Money
    high: Money
    low: Money
    close: Money
    volume: int


class NewsItem(BaseModel):
    id: int
    source: str
    headline: str
    summary: str
    url: str
    published_at: datetime
