from typing import Optional
from pydantic import BaseModel

class LocationDTO(BaseModel):
    lat: float
    lon: float
    address: Optional[str] = None

    class Config:
        from_attributes = True
