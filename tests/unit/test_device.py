from types import SimpleNamespace

from custom_components.home_activity_manager import device as device_module
from custom_components.home_activity_manager.const import DOMAIN


def test_get_device_by_identifier_uses_async_get_devices():
    device = SimpleNamespace(
        identifiers={(DOMAIN, "appliance")}, config_entry_id="entry"
    )
    calls = []

    def get_devices(**kwargs):
        calls.append(kwargs)
        return [device]

    registry = SimpleNamespace(async_get_devices=get_devices)

    assert (
        device_module._get_device_by_identifier(
            registry, (DOMAIN, "appliance"), "entry"
        )
        is device
    )
    assert calls == [
        {"identifiers": {(DOMAIN, "appliance")}, "config_entry_id": "entry"}
    ]


def test_appliance_device_info_uses_class_name_when_name_is_missing():
    entry = SimpleNamespace(entry_id="entry", title="Openings")
    config = {"appliance_type": "opening", "appliance_class": "window"}

    device_info = device_module.appliance_device_info(entry, config)

    assert device_info["name"] == "Window"


def test_get_device_by_identifier_uses_legacy_registry_view():
    device = SimpleNamespace(
        identifiers={(DOMAIN, "appliance")}, config_entries={"entry"}
    )
    registry = SimpleNamespace(devices={"device-id": device})

    assert (
        device_module._get_device_by_identifier(
            registry, (DOMAIN, "appliance"), "entry"
        )
        is device
    )
    assert (
        device_module._get_device_by_identifier(
            registry, (DOMAIN, "appliance"), "other-entry"
        )
        is None
    )


def test_remove_appliance_group_devices_uses_public_device_collection(
    monkeypatch, hass
):
    category_device = SimpleNamespace(
        id="category", identifiers={(DOMAIN, "category:laundry")}
    )
    appliance_device = SimpleNamespace(
        id="appliance", identifiers={(DOMAIN, "washer")}
    )
    removed = []
    registry = SimpleNamespace(
        async_get_devices=lambda: [],
        devices=(category_device, appliance_device),
        async_remove_device=removed.append,
    )
    monkeypatch.setattr(device_module.dr, "async_get", lambda _: registry)

    device_module.remove_appliance_group_devices(hass)

    assert removed == ["category"]


def test_remove_appliance_group_devices_supports_legacy_registry(monkeypatch, hass):
    profile_device = SimpleNamespace(
        id="profile", identifiers={(DOMAIN, "profile:washer")}
    )
    removed = []
    registry = SimpleNamespace(
        devices={"profile": profile_device}, async_remove_device=removed.append
    )
    monkeypatch.setattr(device_module.dr, "async_get", lambda _: registry)

    device_module.remove_appliance_group_devices(hass)

    assert removed == ["profile"]
