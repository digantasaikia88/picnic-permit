from pydantic import BaseModel, ConfigDict, Field


class _FromOrm(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# Public dropdown items: only what the application form needs.
class PublicDistrict(_FromOrm):
    id: int
    name: str


class PublicPoliceStation(_FromOrm):
    id: int
    name: str
    district_id: int


class DistrictOut(_FromOrm):
    id: int
    code: int
    name: str
    short_name: str
    is_active: bool


class DistrictCreate(BaseModel):
    code: int
    name: str = Field(min_length=1, max_length=100)
    short_name: str = Field(min_length=1, max_length=30)


class DistrictUpdate(BaseModel):
    code: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    short_name: str | None = Field(default=None, min_length=1, max_length=30)
    is_active: bool | None = None


class PoliceStationOut(_FromOrm):
    id: int
    name: str
    district_id: int
    is_active: bool


class PoliceStationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    district_id: int


class PoliceStationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    district_id: int | None = None
    is_active: bool | None = None


class DtoOfficeOut(_FromOrm):
    id: int
    code: str
    name: str
    district_id: int
    is_active: bool


class DtoOfficeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=150)
    district_id: int


class DtoOfficeUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=30)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    district_id: int | None = None
    is_active: bool | None = None


class BulkImportResult(BaseModel):
    added: int
    skipped: int
