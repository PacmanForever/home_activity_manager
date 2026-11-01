"""Device registry helpers for appliance profile groups."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from .appliance_types import APPLIANCE_TYPES, get_appliance_model
from .const import CONF_APPLIANCE_TYPE, DOMAIN


def _profile_device_identifier(appliance_type: str) -> tuple[str, str]:
    return (DOMAIN, f"profile:{appliance_type}")


def register_appliance_profile_devices(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Register every profile group while this integration has an entry."""
    registry = dr.async_get(hass)
    for appliance_type in APPLIANCE_TYPES:
        model = get_appliance_model(appliance_type)
        if model is None:
            continue
        registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={_profile_device_identifier(appliance_type)},
            name=model,
            model=model,
            manufacturer="Home Activity Manager",
        )


def appliance_device_info(entry: ConfigEntry, config: dict[str, Any]) -> DeviceInfo:
    """Return device info for an appliance nested under its profile group."""
    appliance_type = config.get(CONF_APPLIANCE_TYPE)
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=config.get("name", entry.title),
        model=get_appliance_model(appliance_type),
        via_device=(
            _profile_device_identifier(appliance_type)
            if appliance_type is not None
            else None
        ),
    )