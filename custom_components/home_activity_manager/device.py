"""Device registry helpers for appliance profile groups."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from .appliance_types import get_appliance_model
from .const import CONF_APPLIANCE_TYPE, DOMAIN


def _profile_device_identifier(config: dict[str, Any]) -> tuple[str, str] | None:
    appliance_type = config.get(CONF_APPLIANCE_TYPE)
    if appliance_type is None:
        return None
    return (DOMAIN, f"profile:{appliance_type}")


def register_appliance_profile_device(
    hass: HomeAssistant, entry: ConfigEntry, config: dict[str, Any]
) -> None:
    """Register the shared, entity-free device for an appliance profile."""
    identifier = _profile_device_identifier(config)
    model = get_appliance_model(config.get(CONF_APPLIANCE_TYPE))
    if identifier is None or model is None:
        return

    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={identifier},
        name=model,
        model=model,
        manufacturer="Home Activity Manager",
    )


def appliance_device_info(entry: ConfigEntry, config: dict[str, Any]) -> DeviceInfo:
    """Return device info that nests this appliance under its profile device."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=config.get("name", entry.title),
        model=get_appliance_model(config.get(CONF_APPLIANCE_TYPE)),
        via_device=_profile_device_identifier(config),
    )