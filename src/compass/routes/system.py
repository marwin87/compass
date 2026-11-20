from fastapi import APIRouter, HTTPException

from compass import about as about_info
from compass import (
    notes,
    settings,
)

settings_router = APIRouter(prefix="/api/settings")
about_router = APIRouter(prefix="/api/about")
data_router = APIRouter(prefix="/api/data")


@settings_router.get("")
def read_settings() -> dict[str, object]:
    return settings.current()


@settings_router.put("")
def write_settings(patch: dict[str, object]) -> dict[str, object]:
    """Partial update of known settings; one invalid key rejects the whole request."""
    try:
        return settings.update(patch)
    except settings.SettingError as problem:
        raise HTTPException(
            status_code=422, detail={"code": "invalid_setting", "key": problem.key}
        ) from None


@about_router.get("")
def read_about() -> dict[str, object]:
    return about_info.about()


@data_router.delete("", status_code=204)
def clear_data() -> None:
    """Remove every note, tag and category (the default one stays); settings are kept."""
    notes.replace_all([], [])
