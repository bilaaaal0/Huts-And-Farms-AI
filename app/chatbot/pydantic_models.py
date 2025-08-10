from pydantic import BaseModel, Field, UrlConstraints
from typing import List, Dict, Optional
from datetime import date
from uuid import UUID
# Base response models
class BaseResponse(BaseModel):
    success: bool
    message: str

# Property ID lookup models
class PropertyIdResponse(BaseResponse):
    property_id: Optional[UUID] = None
    name: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None

# Property listing models
class PropertyResult(BaseModel):
    property_id: UUID
    name: str
    city: str
    shift_type: str
    price: float

class PropertyListResponse(BaseModel):
    message: str
    # results: List[PropertyResult] = []
    # count: int = 0
    error: Optional[str] = None

# Property details models
class PropertyInfo(BaseModel):
    name: str
    description: str
    city: str
    country: str
    max_occupancy: int
    address: str
    day_price: float
    night_price: float
    full_price: float

class PropertyDetailsResponse(BaseResponse):
    property_id: Optional[UUID] = None
    details: Optional[str] = None
    property_info: Optional[PropertyInfo] = None
    error: Optional[str] = None

# Property images models
class PropertyImagesResponse(BaseResponse):
    property_id: Optional[UUID] = None
    images: List[str] = []
    images_count: int = 0

# Property videos models
class PropertyVideosResponse(BaseResponse):
    property_id: Optional[UUID] = None
    videos: List[str] = []
    videos_count: int = 0

# Availability check models
class AvailabilityResponse(BaseModel):
    availability: Dict[str, str] = Field(
        description="Dictionary mapping dates (YYYY-MM-DD) to availability status"
    )