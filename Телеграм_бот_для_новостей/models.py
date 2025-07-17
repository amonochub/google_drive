from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class Article:
    id: str
    title: str
    summary: str
    url: str
    source: str
    published: Optional[datetime] 