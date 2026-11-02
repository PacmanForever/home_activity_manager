"""Device registry helpers for appliance category groups."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from .appliance_types import get_appliance_model
from .const import CONF_APPLIANCE_TYPE, DOMAIN


def _get_device_by_identifier(
    registry: Any, identifier: tuple[str, str], config_entry_id: str
) -> Any:
    get_by_identifier = getattr(registry, "async_get_device_by_identifier", None)
    if get_by_identifier is not None:
        return get_by_identifier(identifier, config_entry_id)
    return registry.async_get_device(identifiers={identifier})


def remove_appliance_group_devices(hass: HomeAssistant) -> None:
    """Remove empty category/profile parents and detach their appliance devices."""
    registry = dr.async_get(hass)
    for device in tuple(registry.devices.values()):
        if any(
            domain == DOMAIN
            and identifier.startswith(("category:", "profile:"))
            for domain, identifier in device.identifiers
        ):
            registry.async_remove_device(device.id)


def appliance_device_info(entry: ConfigEntry, config: dict[str, Any]) -> DeviceInfo:
    """Return device info for a standalone configured appliance."""
    appliance_type = config.get(CONF_APPLIANCE_TYPE)
    appliance_id = config.get("_appliance_id", entry.entry_id)
    return DeviceInfo(
        identifiers={(DOMAIN, appliance_id)},
        name=config.get("name", entry.title),
        model=get_appliance_model(appliance_type),
        via_device=None,
    )