"""Device registry helpers for appliance category groups."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from .appliance_types import (
    APPLIANCE_CATEGORIES,
    APPLIANCE_CATEGORY_NAMES,
    get_appliance_category,
    get_appliance_model,
)
from .const import CONF_APPLIANCE_TYPE, DOMAIN


def _category_device_identifier(category: str) -> tuple[str, str]:
    return (DOMAIN, f"category:{category}")


def register_appliance_category_devices(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Register every general category group while this integration has an entry."""
    registry = dr.async_get(hass)
    for category in APPLIANCE_CATEGORIES:
        name = APPLIANCE_CATEGORY_NAMES[category]
        registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={_category_device_identifier(category)},
            name=name,
            model=name,
            manufacturer="Home Activity Manager",
        )


def remove_legacy_profile_devices(
    hass: HomeAssistant, entry: ConfigEntry, config: dict[str, Any]
) -> None:
    """Move existing appliance devices to category parents and drop profile parents."""
    registry = dr.async_get(hass)
    appliance_type = config.get(CONF_APPLIANCE_TYPE)
    category = get_appliance_category(appliance_type)
    category_device = (
        registry.async_get_device(identifiers={_category_device_identifier(category)})
        if category is not None
        else None
    )

    for device in registry.devices.get_devices_for_config_entry_id(entry.entry_id):
        if (
            category_device is not None
            and device.identifiers.intersection({(DOMAIN, entry.entry_id)})
            and device.via_device_id is not None
            and (parent := registry.async_get(device.via_device_id)) is not None
            and any(
                domain == DOMAIN and identifier.startswith("profile:")
                for domain, identifier in parent.identifiers
            )
        ):
            registry.async_update_device(
                device.id, via_device_id=category_device.id
            )

    for device in registry.devices.get_devices_for_config_entry_id(entry.entry_id):
        if any(
            domain == DOMAIN and identifier.startswith("profile:")
            for domain, identifier in device.identifiers
        ):
            registry.async_update_device(
                device.id, remove_config_entry_id=entry.entry_id
            )


def appliance_device_info(entry: ConfigEntry, config: dict[str, Any]) -> DeviceInfo:
    """Return device info for an appliance nested under its general category."""
    appliance_type = config.get(CONF_APPLIANCE_TYPE)
    category = get_appliance_category(appliance_type)
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=config.get("name", entry.title),
        model=get_appliance_model(appliance_type),
        via_device=(
            _category_device_identifier(category)
            if category is not None
            else None
        ),
    )