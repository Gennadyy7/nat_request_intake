from pydantic import BaseModel, ConfigDict, Field


class NatWebApiFile(BaseModel):
    model_config = ConfigDict(extra='ignore')

    id: int
    file: str
    file_size: str | None = None
    type: str | None = None


class NatSendResponse(BaseModel):
    model_config = ConfigDict(extra='ignore')

    id: int
    status: int


class NatStatusResponse(BaseModel):
    model_config = ConfigDict(extra='ignore')

    id: int
    status: int
    progress: str | None = None
    count_of_lines: str | None = None
    files: list[NatWebApiFile] = Field(default_factory=list)
