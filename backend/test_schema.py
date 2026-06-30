from pydantic import BaseModel
from typing import Optional
from datetime import date

class T(BaseModel):
    d: Optional[date] = None

t = T.model_validate({"d": "2026-06-26"})
print("OK:", t.d)
