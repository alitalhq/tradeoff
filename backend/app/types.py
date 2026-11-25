from decimal import Decimal
from typing import Annotated

from pydantic import PlainSerializer

# Money and quantities travel as strings in JSON so no client ever rounds them through a float.
Money = Annotated[Decimal, PlainSerializer(lambda v: str(v), return_type=str, when_used="json")]
