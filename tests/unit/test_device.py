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


def test_move_device_to_config_entry_uses_new_api_when_available():
    calls = []

    class ModernRegistry:
        def async_update_device(self, device_id, *, new_config_entry_id):
            calls.append((device_id, new_config_entry_id))

    device_module.move_device_to_config_entry(
        ModernRegistry(), "device", "old-entry", "new-entry"
    )

    assert calls == [("device", "new-entry")]


def test_move_device_to_config_entry_falls_back_to_legacy_api():
    calls = []

    class LegacyRegistry:
        def async_update_device(
            self, device_id, *, add_config_entry_id, remove_config_entry_id
        ):
            calls.append(
                (device_id, add_config_entry_id, remove_config_entry_id)
            )

    device_module.move_device_to_config_entry(
        LegacyRegistry(), "device", "old-entry", "new-entry"
    )

    assert calls == [("device", "new-entry", "old-entry")]


def test_remove_appliance_group_devices_uses_public_registry_api(monkeypatch, hass):
    category_device = SimpleNamespace(
        id="category", identifiers={(DOMAIN, "category:laundry")}
    )
    appliance_device = SimpleNamespace(
        id="appliance", identifiers={(DOMAIN, "washer")}
    )
    removed = []
    registry = SimpleNamespace(
        async_get_devices=lambda: [category_device, appliance_device],
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
