from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class Article:
    id: str          # hash(url) или guid
    title: str
    summary: str
    source: str      # например, 'TASS'
    url: str
    published: Optional[datetime] 