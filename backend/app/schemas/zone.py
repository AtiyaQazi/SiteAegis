from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ZoneBase(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )

    description: str | None = None

    location: str | None = Field(
        default=None,
        max_length=255,
    )

    risk_level: str = Field(
        default="low",
        max_length=20,
    )

    polygon: list[list[float]] | None = None

    @field_validator("polygon")
    @classmethod
    def validate_polygon(
        cls,
        value: list[list[float]] | None,
    ):
        if value is None:
            return value

        if len(value) < 3:
            raise ValueError(
                "Polygon must contain at least 3 points"
            )

        for point in value:
            if len(point) != 2:
                raise ValueError(
                    "Each polygon point must contain exactly [x, y]"
                )

            x, y = point

            if not 0.0 <= x <= 1.0:
                raise ValueError(
                    "Polygon x coordinates must be between 0 and 1"
                )

            if not 0.0 <= y <= 1.0:
                raise ValueError(
                    "Polygon y coordinates must be between 0 and 1"
                )

        return value


class ZoneCreate(ZoneBase):
    pass


class ZoneUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )

    description: str | None = None

    location: str | None = Field(
        default=None,
        max_length=255,
    )

    risk_level: str | None = Field(
        default=None,
        max_length=20,
    )

    polygon: list[list[float]] | None = None

    @field_validator("polygon")
    @classmethod
    def validate_polygon(
        cls,
        value: list[list[float]] | None,
    ):
        if value is None:
            return value

        if len(value) < 3:
            raise ValueError(
                "Polygon must contain at least 3 points"
            )

        for point in value:
            if len(point) != 2:
                raise ValueError(
                    "Each polygon point must contain exactly [x, y]"
                )

            x, y = point

            if not 0.0 <= x <= 1.0:
                raise ValueError(
                    "Polygon x coordinates must be between 0 and 1"
                )

            if not 0.0 <= y <= 1.0:
                raise ValueError(
                    "Polygon y coordinates must be between 0 and 1"
                )

        return value


class ZoneResponse(ZoneBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )