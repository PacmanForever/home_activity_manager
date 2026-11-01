"""Device registry helpers for appliance category groups."""

from __future__ import annotations

import inspect
from typing import Any, cast

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

_VIA_DEVICE_KEY = (
    "via_device_id"
    if "via_device_id"
    in inspect.signature(dr.DeviceRegistry.async_get_or_create).parameters
    else "via_device"
)


def _category_device_identifier(category: str) -> tuple[str, str]:
    return (DOMAIN, f"category:{category}")


def _get_device_by_identifier(
    registry: dr.DeviceRegistry,
    identifier: tuple[str, str],
    config_entry_id: str,
) -> Any:
    """Look up a device with the API available in this Home Assistant version."""
    get_by_identifier = getattr(registry, "async_get_device_by_identifier", None)
    if get_by_identifier is not None:
        return get_by_identifier(identifier, config_entry_id)
    return registry.async_get_device(identifiers={identifier})


def register_appliance_category_devices(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Register the single category group owned by this config entry."""
    registry = dr.async_get(hass)
    category = entry.data.get("category")
    if category not in APPLIANCE_CATEGORIES:
        category = get_appliance_category(entry.data.get(CONF_APPLIANCE_TYPE))
    if category is None:
        return
    name = APPLIANCE_CATEGORY_NAMES[category]
    registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={_category_device_identifier(category)},
        name=name,
        model=name,
        manufacturer="Home Activity Manager",
    )


def remove_legacy_profile_devices(
    hass: HomeAssistant, entry: ConfigEntry, config: dict[str, Any] | None = None
) -> None:
    """Move existing appliance devices to category parents and drop profile parents."""
    registry = dr.async_get(hass)
    configurations = (
        [(entry.entry_id, config)]
        if config is not None
        else [
            (record.get("id", entry.entry_id), {
                **record.get("data", {}),
                **record.get("options", {}),
            })
            for record in entry.data.get("appliances", [])
            if isinstance(record, dict)
        ]
    )
    if not configurations:
        configurations = [(entry.entry_id, {**entry.data, **entry.options})]
    category = entry.data.get("category")
    if category not in APPLIANCE_CATEGORIES:
        category = get_appliance_category(
            configurations[0][1].get(CONF_APPLIANCE_TYPE)
        )
    category_device = (
        _get_device_by_identifier(
            registry,
            _category_device_identifier(category),
            entry.entry_id,
        )
        if category is not None
        else None
    )

    appliance_ids = {appliance_id for appliance_id, _ in configurations}
    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        if category_device is not None and any(
            (DOMAIN, appliance_id) in device.identifiers
            for appliance_id in appliance_ids
        ):
            parent = registry.async_get(device.via_device_id)
            if parent is not None and any(
                domain == DOMAIN and identifier.startswith("profile:")
                for domain, identifier in parent.identifiers
            ):
                registry.async_update_device(device.id, via_device_id=category_device.id)

    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        if any(
            domain == DOMAIN and identifier.startswith("profile:")
            for domain, identifier in device.identifiers
        ):
            registry.async_update_device(
                device.id, remove_config_entry_id=entry.entry_id
            )


def appliance_device_info(
    hass: HomeAssistant | None, entry: ConfigEntry, config: dict[str, Any]
) -> DeviceInfo:
    """Return device info for an appliance nested under its general category."""
    appliance_type = config.get(CONF_APPLIANCE_TYPE)
    category = get_appliance_category(appliance_type)
    appliance_id = config.get("_appliance_id", entry.entry_id)
    info: dict[str, Any] = {
        "identifiers": {(DOMAIN, appliance_id)},
        "name": config.get("name", entry.title),
        "model": get_appliance_model(appliance_type),
    }
    if category is not None:
        category_identifier = _category_device_identifier(category)
        if _VIA_DEVICE_KEY == "via_device_id" and hass is not None:
            parent = _get_device_by_identifier(
                dr.async_get(hass), category_identifier, entry.entry_id
            )
            if parent is not None:
                info[_VIA_DEVICE_KEY] = parent.id
        elif _VIA_DEVICE_KEY == "via_device":
            info[_VIA_DEVICE_KEY] = category_identifier
    return cast(DeviceInfo, info)