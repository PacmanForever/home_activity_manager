"""Home Assistant-managed config-flow component tests."""

import asyncio

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    selector,
)
from homeassistant.helpers.storage import Store
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.plugins import enable_custom_integrations

from custom_components.home_activity_manager import async_migrate_entry
from custom_components.home_activity_manager.appliance_types import (
    APPLIANCE_GROUPS,
    APPLIANCE_PROFILES,
    get_appliance_group_name,
)
from custom_components.home_activity_manager.config_flow import (
    _validate_climate_entity,
)
from custom_components.home_activity_manager import device as device_module
from custom_components.home_activity_manager.const import (
    CONF_ALARM_REPEAT_COUNT,
    CONF_ALARM_REPEAT_INTERVAL_SECONDS,
    CONF_APPLIANCE_CLASS,
    CONF_APPLIANCE_GROUP,
    CONF_APPLIANCE_TYPE,
    CONF_CLIMATE_ENTITY,
    CONF_MEDIA_PLAYER_ENTITY,
    CONF_COVER_ENTITY,
    CONF_ENERGY_ENTITY,
    CONF_COMPRESSOR_INACTIVE_ACTIONS,
    CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS,
    CONF_DOOR_ENTITY,
    CONF_DOOR_OPEN_ACTIONS,
    CONF_DOOR_OPEN_DELAY_SECONDS,
    CONF_EMPTIED_ACTIONS,
    CONF_FINISH_ACTIONS,
    CONF_GROUP_ACTIONS,
    CONF_MAIL_ARRIVAL_ACTIONS,
    CONF_MAIL_MOTION_ENTITY,
    CONF_MAIL_SLOT_ENTITY,
    CONF_LOCK_ENTITY,
    CONF_LOCK_LOCKED_ACTIONS,
    CONF_LOCK_UNLOCKED_ACTIONS,
    CONF_PENDING_ACTIONS,
    CONF_PENDING_DELAY_SECONDS,
    CONF_PENDING_INTERVAL_SECONDS,
    CONF_PENDING_REPEATS,
    CONF_POWER_ENTITY,
    CONF_PLUG_ENTITY,
    CONF_PLUG_OFF_ACTIONS,
    CONF_PLUG_OFF_REPEAT_COUNT,
    CONF_PLUG_OFF_REPEAT_INTERVAL_SECONDS,
    CONF_RUNNING_ENTITY,
    CONF_SHUTTER_CONTACT_ENTITY,
    CONF_SHUTTER_COVER_ENTITY,
    CONF_SHUTTER_OPEN_ACTIONS,
    CONF_SHUTTER_CLOSE_ACTIONS,
    CONF_START_ACTIONS,
    CONF_MAX_RUNTIME_ACTIONS,
    CONF_MAX_RUNTIME_SECONDS,
    DOMAIN,
)


def _device_config_entry_ids(device):
    config_entry_id = getattr(device, "config_entry_id", None)
    return (
        {config_entry_id}
        if config_entry_id is not None
        else device.config_entries
    )


def _group_class_mode_for_profile(profile_name: str) -> tuple[str, str, str]:
    return next(
        (group, appliance_class, mode)
        for group, classes in APPLIANCE_GROUPS.items()
        for appliance_class, modes in classes.items()
        for mode, candidate in modes.items()
        if candidate == profile_name
    )


async def _select_profile_for_setup(hass, flow_id: str, name: str, profile_name: str):
    group, appliance_class, mode = _group_class_mode_for_profile(profile_name)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"name": name, CONF_APPLIANCE_GROUP: group}
    )
    if result["step_id"] == "appliance_class":
        result = await hass.config_entries.flow.async_configure(
            flow_id, {CONF_APPLIANCE_CLASS: appliance_class}
        )
    return await hass.config_entries.flow.async_configure(
        flow_id, {"activity_mode": mode}
    )


@pytest.mark.asyncio
async def test_add_appliance_through_four_config_flow_steps(
    hass, enable_custom_integrations
):
    hass.config.language = "ca"
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert CONF_POWER_ENTITY not in {
        marker.schema for marker in result["data_schema"].schema
    }
    flow_id = result["flow_id"]

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            "name": "Washer",
            CONF_APPLIANCE_GROUP: "large_appliances",
        },
    )
    assert result["step_id"] == "appliance_class"
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_APPLIANCE_CLASS: "washer"}
    )
    assert result["step_id"] == "activity_mode_large_appliances"
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"activity_mode": "power"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sensors_laundry"
    power_selector = next(
        value
        for marker, value in result["data_schema"].schema.items()
        if marker.schema == "laundry_power_entity"
    )
    assert isinstance(power_selector, selector.EntitySelector)
    assert power_selector.config["filter"] == [
        {"domain": ["sensor"], "device_class": ["power"]}
    ]

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {"laundry_power_entity": "sensor.washer_power"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "parameters_laundry"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            "start_power_w": 1,
            "start_duration_seconds": 15,
            "finish_power_w": 1,
            "finish_duration_seconds": 60,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "parameters_laundry"
    assert result["errors"] == {"base": "invalid_thresholds"}

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            "start_power_w": 4,
            "start_duration_seconds": 15,
            "finish_power_w": 1,
            "finish_duration_seconds": 60,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "actions_laundry"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            CONF_START_ACTIONS: [],
            CONF_FINISH_ACTIONS: [],
            "max_runtime_actions": [],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Grans electrodomèstics"
    assert result["data"]["category"] == "large_appliances"
    appliance = result["data"]["appliances"][0]
    assert appliance["data"][CONF_POWER_ENTITY] == "sensor.washer_power"
    assert appliance["data"][CONF_APPLIANCE_TYPE] == "laundry"
    assert appliance["data"][CONF_APPLIANCE_CLASS] == "washer"
    assert CONF_DOOR_ENTITY not in appliance["data"]
    assert "start_duration_seconds" not in appliance["data"]
    assert appliance["options"]["start_power_w"] == 4
    assert appliance["options"][CONF_START_ACTIONS] == []
    assert appliance["options"][CONF_FINISH_ACTIONS] == []


    entry = result["result"]
    options_result = await hass.config_entries.options.async_init(entry.entry_id)
    options_flow_id = options_result["flow_id"]
    actions = next(
        value
        for marker, value in options_result["data_schema"].schema.items()
        if marker.schema == "appliance_action"
    )
    assert actions.config["options"] == ["add", "group_actions", "edit", "remove"]


@pytest.mark.asyncio
async def test_initial_flow_assigns_selected_area_to_new_appliance(
    hass, enable_custom_integrations
):
    area = ar.async_get(hass).async_create("Kitchen")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]
    area_selector = next(
        field
        for marker, field in result["data_schema"].schema.items()
        if marker.schema == "area_id"
    )
    assert isinstance(area_selector, selector.AreaSelector)

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            "name": "Kitchen mailbox",
            "area_id": area.id,
            CONF_APPLIANCE_GROUP: "deliveries",
        },
    )
    if result["step_id"] == "appliance_class":
        result = await hass.config_entries.flow.async_configure(
            flow_id, {CONF_APPLIANCE_CLASS: "mailbox"}
        )
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"activity_mode": "mail_motion"}
    )
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {"mailbox_motion_arrival_entity": "binary_sensor.kitchen_mail_motion"},
    )
    assert result["step_id"] == "actions_mailbox_motion"
    result = await hass.config_entries.flow.async_configure(flow_id, {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    appliance = result["data"]["appliances"][0]
    assert appliance["area_id"] == area.id
    device = device_module._get_device_by_identifier(
        dr.async_get(hass), (DOMAIN, appliance["id"]), result["result"].entry_id
    )
    assert device is not None
    assert device.area_id == area.id


@pytest.mark.asyncio
async def test_add_access_with_primary_cover_mode(hass, enable_custom_integrations):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {"name": "Garage door", CONF_APPLIANCE_GROUP: "openings"},
    )
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_APPLIANCE_CLASS: "access"}
    )
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"activity_mode": "cover"}
    )
    assert result["step_id"] == "sensors_opening_cover"
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"opening_cover_entity": "cover.garage_door"}
    )
    assert result["step_id"] == "actions_opening_cover"
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_START_ACTIONS: [], CONF_FINISH_ACTIONS: []}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    appliance = result["data"]["appliances"][0]
    assert appliance["data"][CONF_APPLIANCE_TYPE] == "opening_cover"
    assert appliance["data"][CONF_APPLIANCE_CLASS] == "access"
    assert appliance["data"][CONF_COVER_ENTITY] == "cover.garage_door"


@pytest.mark.asyncio
async def test_initial_opening_flow_clears_deselected_shutter_source(
    hass, enable_custom_integrations
):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]
    result = await _select_profile_for_setup(
        hass, flow_id, "Kitchen window", "opening"
    )
    assert result["step_id"] == "sensors_opening"
    selections = {
        "opening_sensor": "binary_sensor.kitchen_window",
        "opening_shutter_contact_entity": "binary_sensor.kitchen_shutter_contact",
        "opening_shutter_cover_entity": "cover.kitchen_shutter",
    }

    result = await hass.config_entries.flow.async_configure(flow_id, selections)
    assert result["step_id"] == "sensors_opening"
    assert result["errors"]["base"] == "invalid_shutter_sources"
    assert "clear_associated_shutter" not in {
        marker.schema for marker in result["data_schema"].schema
    }

    corrected_selections = dict(selections)
    corrected_selections.pop("opening_shutter_cover_entity")
    result = await hass.config_entries.flow.async_configure(
        flow_id, corrected_selections
    )
    assert result["step_id"] == "actions_opening"
    action_values = {
        marker.schema: [] for marker in result["data_schema"].schema
    }
    result = await hass.config_entries.flow.async_configure(flow_id, action_values)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    appliance = result["data"]["appliances"][0]["data"]
    assert appliance[CONF_SHUTTER_CONTACT_ENTITY] == selections[
        "opening_shutter_contact_entity"
    ]
    assert appliance[CONF_SHUTTER_COVER_ENTITY] is None


@pytest.mark.asyncio
async def test_add_access_with_contact_and_optional_lock(hass, enable_custom_integrations):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {"name": "Garage access", CONF_APPLIANCE_GROUP: "openings"},
    )
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_APPLIANCE_CLASS: "access"}
    )
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"activity_mode": "running_sensor"}
    )
    assert result["step_id"] == "sensors_access_contact"
    sensor_keys = {marker.schema for marker in result["data_schema"].schema}
    assert "access_contact_sensor" in sensor_keys
    assert "access_lock_entity" in sensor_keys
    assert CONF_SHUTTER_CONTACT_ENTITY not in sensor_keys
    assert CONF_SHUTTER_COVER_ENTITY not in sensor_keys
    assert CONF_COVER_ENTITY not in sensor_keys

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            "access_contact_sensor": "binary_sensor.garage_access",
            "access_lock_entity": "lock.garage_access",
        },
    )
    assert result["step_id"] == "actions_access_contact"
    action_keys = {marker.schema for marker in result["data_schema"].schema}
    assert CONF_LOCK_LOCKED_ACTIONS in action_keys
    assert CONF_LOCK_UNLOCKED_ACTIONS in action_keys
    assert CONF_SHUTTER_OPEN_ACTIONS not in action_keys
    assert CONF_SHUTTER_CLOSE_ACTIONS not in action_keys
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_START_ACTIONS: [], CONF_FINISH_ACTIONS: []}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    appliance = result["data"]["appliances"][0]
    assert appliance["data"][CONF_APPLIANCE_TYPE] == "access_contact"
    assert appliance["data"][CONF_APPLIANCE_CLASS] == "access"
    assert appliance["data"][CONF_RUNNING_ENTITY] == "binary_sensor.garage_access"
    assert appliance["data"][CONF_LOCK_ENTITY] == "lock.garage_access"
    assert CONF_SHUTTER_CONTACT_ENTITY not in appliance["data"]
    assert CONF_SHUTTER_COVER_ENTITY not in appliance["data"]


@pytest.mark.asyncio
async def test_edit_access_with_primary_cover_mode(hass, enable_custom_integrations):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "category": "openings",
            "name": "Garage door",
            CONF_APPLIANCE_TYPE: "opening_cover",
            CONF_APPLIANCE_CLASS: "access",
            CONF_COVER_ENTITY: "cover.garage_door",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"name": "Garage door"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sensors_opening_cover"


@pytest.mark.asyncio
async def test_setup_adds_appliance_to_existing_group(
    hass, enable_custom_integrations
):
    hass.states.async_set(
        "sensor.existing_washer_power", "0", {"unit_of_measurement": "W"}
    )
    hass.states.async_set(
        "sensor.another_washer_power", "0", {"unit_of_measurement": "W"}
    )
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Large appliances",
        data={
            "category": "large_appliances",
            "appliances": [
                {
                    "id": "existing-washer",
                    "data": {
                        "name": "Existing washer",
                        CONF_APPLIANCE_TYPE: "laundry",
                        CONF_APPLIANCE_CLASS: "washer",
                        CONF_POWER_ENTITY: "sensor.existing_washer_power",
                    },
                    "options": {},
                }
            ],
        },
    )
    existing_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(existing_entry.entry_id)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"name": "Another washer", CONF_APPLIANCE_GROUP: "large_appliances"},
    )
    assert result["step_id"] == "appliance_class"
    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_APPLIANCE_CLASS: "washer"}
    )
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"activity_mode": "power"}
    )
    assert result["step_id"] == "sensors_laundry"
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"laundry_power_entity": "sensor.another_washer_power"}
    )
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            "start_power_w": 4,
            "start_duration_seconds": 15,
            "finish_power_w": 1,
            "finish_duration_seconds": 60,
        },
    )
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            CONF_START_ACTIONS: [],
            CONF_FINISH_ACTIONS: [],
            "max_runtime_actions": [],
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "appliance_added"
    await hass.async_block_till_done()
    assert len(existing_entry.data["appliances"]) == 2
    assert existing_entry.data["appliances"][1]["data"][CONF_POWER_ENTITY] == (
        "sensor.another_washer_power"
    )
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    updated_entry = hass.config_entries.async_get_entry(existing_entry.entry_id)
    assert updated_entry is not None
    assert len(updated_entry.runtime_data) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("category", "appliance_class", "activity_mode", "profile_name"),
    (
        (
            category,
            appliance_class,
            activity_mode,
            profile_name,
        )
        for category, classes in APPLIANCE_GROUPS.items()
        for appliance_class, modes in [next(iter(classes.items()))]
        for activity_mode, profile_name in [next(iter(modes.items()))]
    ),
)
async def test_options_flow_adds_appliance_with_registered_mode_step(
    hass,
    enable_custom_integrations,
    category,
    appliance_class,
    activity_mode,
    profile_name,
):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=category,
        data={"category": category, "appliances": []},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    flow_id = result["flow_id"]
    result = await hass.config_entries.options.async_configure(
        flow_id, {"appliance_action": "add"}
    )
    result = await hass.config_entries.options.async_configure(
        flow_id, {"name": f"New {appliance_class}"}
    )
    if len(APPLIANCE_GROUPS[category]) > 1:
        assert result["step_id"] == "appliance_class"
        result = await hass.config_entries.options.async_configure(
            flow_id, {CONF_APPLIANCE_CLASS: appliance_class}
        )

    assert result["step_id"] == f"activity_mode_{category}"

    result = await hass.config_entries.options.async_configure(
        flow_id, {"activity_mode": activity_mode}
    )
    assert result["step_id"] == f"sensors_{profile_name}"


@pytest.mark.asyncio
async def test_options_flow_sorts_add_appliance_choices_in_active_language(
    hass, enable_custom_integrations
):
    hass.config.language = "ca"
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Climate",
        data={"category": "climate", "appliances": []},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    flow_id = result["flow_id"]
    result = await hass.config_entries.options.async_configure(
        flow_id, {"appliance_action": "add"}
    )
    result = await hass.config_entries.options.async_configure(
        flow_id, {"name": "New appliance"}
    )
    fields = {
        marker.schema: field
        for marker, field in result["data_schema"].schema.items()
    }
    assert fields[CONF_APPLIANCE_CLASS].config["options"] == [
        "air_conditioner",
        "thermostat",
        "fan",
    ]

    result = await hass.config_entries.options.async_configure(
        flow_id, {CONF_APPLIANCE_CLASS: "fan"}
    )
    mode_field = next(
        field
        for marker, field in result["data_schema"].schema.items()
        if marker.schema == "activity_mode"
    )
    assert mode_field.config["options"] == ["fan", "smart_plug", "power"]


@pytest.mark.asyncio
@pytest.mark.parametrize("assign_area", [True, False])
async def test_options_flow_adds_mailbox_to_loaded_group_device_registry(
    hass, enable_custom_integrations, assign_area
):
    existing_id = "existing-mailbox"
    existing_arrival = "binary_sensor.existing_mail_arrival"
    existing_door = "binary_sensor.existing_mail_door"
    hass.states.async_set(existing_arrival, "off")
    hass.states.async_set(existing_door, "off")
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Deliveries",
        data={
            "category": "deliveries",
            "appliances": [
                {
                    "id": existing_id,
                    "data": {
                        "name": "Existing mailbox",
                        CONF_APPLIANCE_TYPE: "mailbox_motion",
                        CONF_APPLIANCE_CLASS: "mailbox",
                        "mail_motion_entity": existing_arrival,
                        CONF_DOOR_ENTITY: existing_door,
                    },
                    "options": {},
                }
            ],
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    area_registry = ar.async_get(hass)
    existing_area = area_registry.async_create("Existing area")
    device_registry = dr.async_get(hass)
    existing_device = device_module._get_device_by_identifier(
        device_registry, (DOMAIN, existing_id), entry.entry_id
    )
    assert existing_device is not None
    device_registry.async_update_device(existing_device.id, area_id=existing_area.id)
    new_area = area_registry.async_create("New area") if assign_area else None

    result = await hass.config_entries.options.async_init(entry.entry_id)
    flow_id = result["flow_id"]
    result = await hass.config_entries.options.async_configure(
        flow_id, {"appliance_action": "add"}
    )
    add_appliance_input = {"name": "New mailbox"}
    if new_area is not None:
        add_appliance_input["area_id"] = new_area.id
    result = await hass.config_entries.options.async_configure(
        flow_id, add_appliance_input
    )
    assert result["step_id"] == "activity_mode_deliveries"
    result = await hass.config_entries.options.async_configure(
        flow_id, {"activity_mode": "mail_motion"}
    )
    result = await hass.config_entries.options.async_configure(
        flow_id,
        {
            "mailbox_motion_arrival_entity": "binary_sensor.new_mail_arrival",
            "mailbox_motion_door_entity": "binary_sensor.new_mail_door",
        },
    )
    assert result["step_id"] == "parameters_mailbox_motion"
    result = await hass.config_entries.options.async_configure(
        flow_id,
        {
            "pending_delay_seconds": 900,
            "pending_interval_seconds": 900,
            "pending_repeats": 3,
        },
    )
    assert result["step_id"] == "actions_mailbox_motion"
    result = await hass.config_entries.options.async_configure(
        flow_id,
        {
            "start_actions": [],
            "finish_actions": [],
            "pending_actions": [],
            "emptied_actions": [],
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    new_appliance_id = entry.data["appliances"][1]["id"]
    entity_registry = er.async_get(hass)
    pending_entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{new_appliance_id}_pending_unload"
    )
    device = device_module._get_device_by_identifier(
        device_registry, (DOMAIN, new_appliance_id), entry.entry_id
    )

    assert len(entry.runtime_data) == 2
    assert pending_entity_id is not None
    assert device is not None
    assert entity_registry.async_get(pending_entity_id).device_id == device.id
    assert device.area_id == (new_area.id if new_area is not None else None)
    assert device_registry.async_get(existing_device.id).area_id == existing_area.id
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_activity_modes_follow_the_selected_category(
    hass, enable_custom_integrations
):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"name": "Air conditioner", CONF_APPLIANCE_GROUP: "climate"}
    )
    assert result["step_id"] == "appliance_class"
    assert set(next(iter(result["data_schema"].schema.values())).config["options"]) == {
        "air_conditioner", "fan", "thermostat"
    }
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_APPLIANCE_CLASS: "air_conditioner"}
    )
    assert result["step_id"] == "activity_mode_climate"
    mode_selector = next(iter(result["data_schema"].schema.values()))
    assert set(mode_selector.config["options"]) == {"running_sensor", "power", "climate"}
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"activity_mode": "running_sensor"}
    )
    assert result["step_id"] == "sensors_air_conditioner_contact"
    assert "air_conditioner_contact_running_entity" in result["data_schema"].schema


@pytest.mark.asyncio
async def test_fan_activity_modes_offer_power_smart_switch_and_fan_entity(
    hass, enable_custom_integrations
):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"name": "Fan", CONF_APPLIANCE_GROUP: "climate"}
    )
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_APPLIANCE_CLASS: "fan"}
    )

    assert result["step_id"] == "activity_mode_climate"
    mode_selector = next(iter(result["data_schema"].schema.values()))
    assert set(mode_selector.config["options"]) == {"fan", "power", "smart_plug"}
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"activity_mode": "smart_plug"}
    )
    assert result["step_id"] == "sensors_fan_switch"
    assert "fan_switch_plug_entity" in result["data_schema"].schema


@pytest.mark.asyncio
async def test_air_conditioner_climate_mode_requires_climate_entity(
    hass, enable_custom_integrations
):
    climate_entry = MockConfigEntry(domain="climate_source")
    climate_entry.add_to_hass(hass)
    climate_entity = er.async_get(hass).async_get_or_create(
        "climate",
        climate_entry.domain,
        "air_conditioner",
        config_entry=climate_entry,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {"name": "Air conditioner", CONF_APPLIANCE_GROUP: "climate"},
    )
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_APPLIANCE_CLASS: "air_conditioner"}
    )
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"activity_mode": "climate"}
    )

    assert result["step_id"] == "sensors_air_conditioner_climate"
    schema_keys = {marker.schema for marker in result["data_schema"].schema}
    assert "air_conditioner_climate_climate_entity" in schema_keys
    assert "air_conditioner_climate_power_entity" in schema_keys
    assert "air_conditioner_climate_running_entity" not in schema_keys

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {"air_conditioner_climate_climate_entity": climate_entity.entity_id},
    )
    assert result["step_id"] == "actions_air_conditioner_climate"
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_START_ACTIONS: [], CONF_FINISH_ACTIONS: []}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["appliances"][0]["data"][CONF_CLIMATE_ENTITY] == (
        climate_entity.entity_id
    )


@pytest.mark.asyncio
async def test_add_air_conditioner_with_opening_sensor(hass, enable_custom_integrations):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]
    result = await _select_profile_for_setup(
        hass, flow_id, "Air conditioner", "air_conditioner_contact"
    )
    assert result["step_id"] == "sensors_air_conditioner_contact"
    schema_keys = {marker.schema for marker in result["data_schema"].schema}
    assert "air_conditioner_contact_running_entity" in schema_keys
    assert "air_conditioner_contact_power_entity" in schema_keys
    assert CONF_DOOR_ENTITY not in schema_keys

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {"air_conditioner_contact_running_entity": "binary_sensor.ac_vane"},
    )
    assert result["step_id"] == "actions_air_conditioner_contact"
    assert CONF_PENDING_ACTIONS not in {
        marker.schema for marker in result["data_schema"].schema
    }

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_START_ACTIONS: [], CONF_FINISH_ACTIONS: []},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    appliance = result["data"]["appliances"][0]
    assert appliance["data"][CONF_RUNNING_ENTITY] == "binary_sensor.ac_vane"
    assert CONF_POWER_ENTITY not in appliance["data"]


@pytest.mark.asyncio
async def test_thermostat_climate_accepts_parented_entity(
    hass, enable_custom_integrations
):
    climate_entry = MockConfigEntry(domain="climate_source")
    climate_entry.add_to_hass(hass)
    entity_registry = er.async_get(hass)
    parentless_entity = entity_registry.async_get_or_create(
        "climate", climate_entry.domain, "parentless", config_entry=climate_entry
    )
    climate_device = dr.async_get(hass).async_get_or_create(
        config_entry_id=climate_entry.entry_id,
        identifiers={(climate_entry.domain, "device")},
        name="Existing climate device",
    )
    parented_entity = entity_registry.async_get_or_create(
        "climate",
        climate_entry.domain,
        "parented",
        config_entry=climate_entry,
        device_id=climate_device.id,
    )
    assert _validate_climate_entity(hass, parented_entity.entity_id)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]
    sensor_step = await _select_profile_for_setup(
        hass, flow_id, "Thermostat", "thermostat_climate"
    )
    climate_selector = next(
        value
        for marker, value in sensor_step["data_schema"].schema.items()
        if marker.schema == "thermostat_climate_climate_entity"
    )
    sensor_form = await hass.config_entries.flow.async_configure(
        flow_id, {"thermostat_climate_climate_entity": parented_entity.entity_id}
    )
    assert sensor_form["step_id"] == "actions_thermostat_climate"
    assert isinstance(climate_selector, selector.EntitySelector)
    assert climate_selector.config["domain"] == ["climate"]
    assert "exclude_entities" not in climate_selector.config
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_START_ACTIONS: [], CONF_FINISH_ACTIONS: []}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["appliances"][0]["data"][CONF_CLIMATE_ENTITY] == (
        parented_entity.entity_id
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {"name": "Thermostat 2", CONF_APPLIANCE_GROUP: "climate"},
    )
    assert result["step_id"] == "appliance_class"


@pytest.mark.asyncio
async def test_climate_entity_must_be_replaced_in_options(
    hass, enable_custom_integrations
):
    climate_entry = MockConfigEntry(domain="climate_source")
    climate_entry.add_to_hass(hass)
    climate_entity = er.async_get(hass).async_get_or_create(
        "climate", climate_entry.domain, "air_conditioner", config_entry=climate_entry
    )
    replacement = er.async_get(hass).async_get_or_create(
        "climate", climate_entry.domain, "replacement", config_entry=climate_entry
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Climate AC",
        data={
            "name": "Climate AC",
            CONF_APPLIANCE_TYPE: "thermostat_climate",
            CONF_CLIMATE_ENTITY: climate_entity.entity_id,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    flow_id = result["flow_id"]
    result = await hass.config_entries.options.async_configure(
        flow_id, {"name": "Climate AC"}
    )
    assert result["step_id"] == "sensors_thermostat_climate"
    climate_selector = next(
        value
        for marker, value in result["data_schema"].schema.items()
        if marker.schema == "thermostat_climate_climate_entity"
    )
    assert isinstance(climate_selector, selector.EntitySelector)

    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(
            flow_id, {"thermostat_climate_climate_entity": None}
        )
    result = await hass.config_entries.options.async_configure(
        flow_id, {"thermostat_climate_climate_entity": replacement.entity_id}
    )
    assert result["step_id"] == "actions_thermostat_climate"
    result = await hass.config_entries.options.async_configure(
        flow_id, {CONF_START_ACTIONS: [], CONF_FINISH_ACTIONS: []}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data.get(CONF_CLIMATE_ENTITY) == replacement.entity_id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("arrival_key", "arrival_config_key", "profile"),
    [
        (
            "mailbox_motion_arrival_entity",
            CONF_MAIL_MOTION_ENTITY,
            "mailbox_motion",
        ),
        (
            "mailbox_slot_arrival_entity",
            CONF_MAIL_SLOT_ENTITY,
            "mailbox_slot",
        ),
    ],
)
async def test_mailbox_can_be_configured_without_main_door_sensor(
    hass, enable_custom_integrations, arrival_key, arrival_config_key, profile
):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]
    await _select_profile_for_setup(
        hass, flow_id, "Mailbox", profile
    )

    result = await hass.config_entries.flow.async_configure(
        flow_id, {arrival_key: "binary_sensor.mail_arrival"}
    )
    assert result["step_id"] == f"actions_{profile}"
    result = await hass.config_entries.flow.async_configure(flow_id, {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    appliance = result["data"]["appliances"][0]
    assert appliance["data"][arrival_config_key] == "binary_sensor.mail_arrival"
    assert CONF_DOOR_ENTITY not in appliance["data"]


@pytest.mark.asyncio
async def test_mailbox_slot_requires_a_separate_main_door_sensor(
    hass, enable_custom_integrations
):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]
    await _select_profile_for_setup(
        hass, flow_id, "Mailbox", "mailbox_slot"
    )

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            "mailbox_slot_arrival_entity": "binary_sensor.mailbox_contact",
            "mailbox_slot_door_entity": "binary_sensor.mailbox_contact",
        },
    )
    assert result["step_id"] == "sensors_mailbox_slot"
    assert result["errors"] == {"base": "mailbox_sensors_must_be_distinct"}

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            "mailbox_slot_arrival_entity": "binary_sensor.mail_slot",
            "mailbox_slot_door_entity": "binary_sensor.mailbox_door",
        },
    )
    assert result["step_id"] == "parameters_mailbox_slot"


@pytest.mark.asyncio
async def test_options_flow_updates_entry_and_clears_removed_door_configuration(
    hass, enable_custom_integrations
):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Washer",
        data={
            "name": "Washer",
            "appliance_type": "washer",
            CONF_POWER_ENTITY: "sensor.washer_power",
            CONF_DOOR_ENTITY: "binary_sensor.washer_door",
        },
        options={
            "start_power_w": 4,
            "start_duration_seconds": 15,
            "finish_power_w": 1,
            "finish_duration_seconds": 60,
            CONF_PENDING_ACTIONS: [{"action": "notify.send_message"}],
            CONF_PENDING_DELAY_SECONDS: 120,
            CONF_PENDING_INTERVAL_SECONDS: 300,
            CONF_PENDING_REPEATS: 5,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert CONF_APPLIANCE_GROUP in result["data_schema"].schema
    assert CONF_APPLIANCE_CLASS in result["data_schema"].schema
    assert "activity_mode" in result["data_schema"].schema
    flow_id = result["flow_id"]

    result = await hass.config_entries.options.async_configure(
        flow_id,
        {
            "name": "Washer 2",
        },
    )
    assert result["step_id"] == "sensors_washer"
    result = await hass.config_entries.options.async_configure(
        flow_id,
        {
            "washer_power_entity": "sensor.new_power",
            "washer_door_entity": None,
        },
    )
    assert result["step_id"] == "parameters_washer"
    result = await hass.config_entries.options.async_configure(
        flow_id,
        {
            "start_power_w": 5,
            "start_duration_seconds": 30,
            "finish_power_w": 1,
            "finish_duration_seconds": 60,
        },
    )
    assert result["step_id"] == "actions_washer"
    result = await hass.config_entries.options.async_configure(
        flow_id,
        {
            CONF_START_ACTIONS: [],
            CONF_FINISH_ACTIONS: [],
            "max_runtime_actions": [],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.title == "Washer 2"
    assert entry.data[CONF_APPLIANCE_TYPE] == "washer"
    assert entry.data[CONF_APPLIANCE_CLASS] == "washer"
    assert entry.data[CONF_POWER_ENTITY] == "sensor.new_power"
    assert entry.data[CONF_DOOR_ENTITY] is None
    assert CONF_PENDING_ACTIONS not in entry.options
    assert CONF_PENDING_DELAY_SECONDS not in entry.options
    assert CONF_PENDING_INTERVAL_SECONDS not in entry.options
    assert CONF_PENDING_REPEATS not in entry.options


@pytest.mark.asyncio
async def test_options_flow_shows_immutable_category_and_mode(
    hass, enable_custom_integrations
):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Washer",
        data={
            "name": "Washer",
            CONF_APPLIANCE_TYPE: "washer",
            CONF_POWER_ENTITY: "sensor.washer_power",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    fields = {marker.schema: field for marker, field in result["data_schema"].schema.items()}
    assert fields[CONF_APPLIANCE_GROUP].config["options"] == ["large_appliances"]
    assert fields[CONF_APPLIANCE_CLASS].config["options"] == ["washer"]
    assert fields["activity_mode"].config["options"] == ["power"]
    assert fields[CONF_APPLIANCE_GROUP].config["read_only"] is True
    assert fields[CONF_APPLIANCE_CLASS].config["read_only"] is True
    assert fields["activity_mode"].config["read_only"] is True
    flow_id = result["flow_id"]
    result = await hass.config_entries.options.async_configure(
        flow_id,
        {
            "name": "Washer",
            CONF_APPLIANCE_GROUP: "openings",
            CONF_APPLIANCE_CLASS: "door",
            "activity_mode": "power",
        },
    )
    assert result["errors"] == {"base": "appliance_type_immutable"}
    result = await hass.config_entries.options.async_configure(
        flow_id,
        {
            "name": "Washer",
            CONF_APPLIANCE_GROUP: "large_appliances",
            CONF_APPLIANCE_CLASS: "washer",
            "activity_mode": "climate",
        },
    )
    assert result["errors"] == {"base": "appliance_type_immutable"}
    result = await hass.config_entries.options.async_configure(
        flow_id,
        {"name": "Washer"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sensors_washer"


@pytest.mark.asyncio
async def test_migrate_saved_duration_options_from_minutes_to_seconds(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        options={
            "start_duration_minutes": 0.25,
            "finish_duration_minutes": 1,
            "max_runtime_minutes": 90,
            "start_power_w": 4,
        },
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)

    assert entry.version == 12
    assert entry.options == {
        "start_duration_seconds": 15,
        "finish_duration_seconds": 60,
        "max_runtime_seconds": 5400,
        "start_power_w": 4,
    }


@pytest.mark.asyncio
async def test_migrate_cover_door_to_access_class(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=9,
        data={
            "category": "openings",
            "appliances": [
                {
                    "id": "garage-access",
                    "data": {
                        CONF_APPLIANCE_TYPE: "opening_cover",
                        CONF_APPLIANCE_CLASS: "door",
                        CONF_COVER_ENTITY: "cover.garage_door",
                    },
                    "options": {},
                },
                {
                    "id": "front-door",
                    "data": {
                        CONF_APPLIANCE_TYPE: "opening",
                        CONF_APPLIANCE_CLASS: "door",
                        CONF_RUNNING_ENTITY: "binary_sensor.front_door",
                        CONF_SHUTTER_COVER_ENTITY: "cover.front_door_shutter",
                    },
                    "options": {},
                },
            ],
        },
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)

    assert entry.version == 13
    access, door = entry.data["appliances"]
    assert access["data"][CONF_APPLIANCE_CLASS] == "access"
    assert door["data"][CONF_APPLIANCE_CLASS] == "door"
    assert door["data"][CONF_SHUTTER_COVER_ENTITY] == "cover.front_door_shutter"


@pytest.mark.asyncio
async def test_migrate_future_config_entry_version_is_rejected(hass):
    entry = MockConfigEntry(domain=DOMAIN, version=14)
    entry.add_to_hass(hass)

    assert not await async_migrate_entry(hass, entry)
    assert entry.version == 14


@pytest.mark.asyncio
async def test_migrate_updates_localized_appliance_group_title(hass):
    hass.config.language = "ca"
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=12,
        title="Tancament",
        data={"category": "openings", "appliances": []},
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)

    assert entry.title == "Tancaments"
    assert entry.version == 13


@pytest.mark.asyncio
async def test_migrate_laundry_and_refrigeration_preserves_group_actions(hass):
    entries = [
        MockConfigEntry(
            domain=DOMAIN,
            version=8,
            title="Washer",
            data={
                "category": "laundry",
                "appliances": [
                    {
                        "id": "washer-1",
                        "data": {
                            "name": "Washer",
                            CONF_APPLIANCE_TYPE: "washer",
                            CONF_POWER_ENTITY: "sensor.washer_power",
                        },
                        "options": {},
                    }
                ],
            },
            options={
                CONF_GROUP_ACTIONS: {
                    CONF_PENDING_ACTIONS: [{"action": "test.pending"}],
                    CONF_EMPTIED_ACTIONS: [{"action": "test.emptied"}],
                }
            },
        ),
        MockConfigEntry(
            domain=DOMAIN,
            version=8,
            title="Refrigerator",
            data={
                "category": "refrigeration",
                "appliances": [
                    {
                        "id": "refrigerator-1",
                        "data": {
                            "name": "Refrigerator",
                            CONF_APPLIANCE_TYPE: "refrigerator",
                            CONF_POWER_ENTITY: "sensor.refrigerator_power",
                        },
                        "options": {},
                    }
                ],
            },
            options={
                CONF_GROUP_ACTIONS: {
                    CONF_PENDING_ACTIONS: [{"action": "test.pending"}],
                    CONF_DOOR_OPEN_ACTIONS: [{"action": "test.door_open"}],
                }
            },
        ),
    ]
    for entry in entries:
        entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entries[0])
    survivor = next(
        entry
        for entry in entries
        if entry in hass.config_entries.async_entries(DOMAIN)
    )
    actions = survivor.options[CONF_GROUP_ACTIONS]

    assert survivor.version == 13
    assert survivor.data["category"] == "large_appliances"
    assert len(survivor.data["appliances"]) == 2
    assert actions[CONF_PENDING_ACTIONS] == [{"action": "test.pending"}]
    assert actions[CONF_EMPTIED_ACTIONS] == [{"action": "test.emptied"}]
    assert actions[CONF_DOOR_OPEN_ACTIONS] == [{"action": "test.door_open"}]


@pytest.mark.asyncio
async def test_migrate_merges_same_category_entries_and_preserves_registry_state(
    hass, monkeypatch
):
    entries = [
        MockConfigEntry(
            domain=DOMAIN,
            version=7,
            title=f"Washer {index}",
            data={
                "name": f"Washer {index}",
                CONF_APPLIANCE_TYPE: "washer",
                CONF_POWER_ENTITY: f"sensor.washer_{index}_power",
            },
        )
        for index in (1, 2)
    ]
    for entry in entries:
        entry.add_to_hass(hass)

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    dryer_entry = MockConfigEntry(
        domain=DOMAIN,
        version=8,
        title="Dryer",
        data={"category": "dryer", "appliances": []},
    )
    dryer_entry.add_to_hass(hass)
    dryer_parent = device_registry.async_get_or_create(
        config_entry_id=dryer_entry.entry_id,
        identifiers={(DOMAIN, "category:dryer")},
        name="Dryer",
    )
    original_update_device = device_registry.async_update_device

    def reject_category_parent_transfer(device_id, **updates):
        device = device_registry.async_get(device_id)
        if any(
            domain == DOMAIN and identifier.startswith("category:")
            for domain, identifier in device.identifiers
        ):
            assert "add_config_entry_id" not in updates
            assert "new_config_entry_id" not in updates
        return original_update_device(device_id, **updates)

    monkeypatch.setattr(
        device_registry, "async_update_device", reject_category_parent_transfer
    )
    appliance_devices = []
    for index, entry in enumerate(entries):
        entity_registry.async_get_or_create(
            "sensor",
            DOMAIN,
            f"{entry.entry_id}_power",
            config_entry=entry,
        )
        appliance_devices.append(
            device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                identifiers={(DOMAIN, entry.entry_id)},
                name=entry.title,
            )
        )
        if index == 0:
            device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                identifiers={(DOMAIN, "category:washer")},
                name="Washer",
            )
        await Store(hass, 1, f"{DOMAIN}_{entry.entry_id}").async_save(
            {"preserved": entry.entry_id}
        )

    migration_results = await asyncio.gather(
        *(async_migrate_entry(hass, entry) for entry in entries)
    )
    assert all(migration_results)
    survivor = next(
        entry
        for entry in entries
        if entry in hass.config_entries.async_entries(DOMAIN)
    )
    merged = next(entry for entry in entries if entry is not survivor)

    assert survivor.version == 13
    assert survivor.data["category"] == "large_appliances"
    assert all(
        record["data"][CONF_APPLIANCE_TYPE] == "laundry"
        and record["data"]["appliance_class"] == "washer"
        for record in survivor.data["appliances"]
    )
    assert {record["id"] for record in survivor.data["appliances"]} == {
        entry.entry_id for entry in entries
    }
    assert merged not in hass.config_entries.async_entries(DOMAIN)
    migrated_dryer_parent = device_registry.async_get(dryer_parent.id)
    assert dryer_entry not in hass.config_entries.async_entries(DOMAIN)
    assert migrated_dryer_parent is None or not (
        {survivor.entry_id, merged.entry_id, dryer_entry.entry_id}
        & _device_config_entry_ids(migrated_dryer_parent)
    )
    merged_entity = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{merged.entry_id}_power"
    )
    assert entity_registry.async_get(merged_entity).config_entry_id == survivor.entry_id
    for device in appliance_devices:
        migrated_device = device_registry.async_get(device.id)
        assert migrated_device is not None
        config_entry_ids = _device_config_entry_ids(migrated_device)
        assert survivor.entry_id in config_entry_ids
        assert merged.entry_id not in config_entry_ids
    assert await Store(hass, 1, f"{DOMAIN}_{merged.entry_id}").async_load() == {
        "preserved": merged.entry_id
    }


@pytest.mark.parametrize(
    "version",
    (5, 6, 9, 10),
)
@pytest.mark.parametrize(
    ("initial_hidden_by", "expected_hidden_by"),
    (
        (None, None),
        (er.RegistryEntryHider.INTEGRATION, None),
        (er.RegistryEntryHider.USER, er.RegistryEntryHider.USER),
    ),
)
@pytest.mark.asyncio
async def test_migrate_shows_existing_proxies_without_overriding_user_choice(
    hass, version, initial_hidden_by, expected_hidden_by
):
    entry = MockConfigEntry(domain=DOMAIN, version=version)
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    proxy = registry.async_get_or_create(
        "climate",
        DOMAIN,
        f"{entry.entry_id}_climate_proxy",
        config_entry=entry,
    )
    appliance_proxy = registry.async_get_or_create(
        "climate",
        DOMAIN,
        "another_appliance_climate_proxy",
        config_entry=entry,
    )
    proxies = (proxy, appliance_proxy)
    if initial_hidden_by is not None:
        for proxy_entry in proxies:
            registry.async_update_entity(
                proxy_entry.entity_id, hidden_by=initial_hidden_by
            )

    assert await async_migrate_entry(hass, entry)

    assert all(
        registry.async_get(proxy_entry.entity_id).hidden_by == expected_hidden_by
        for proxy_entry in proxies
    )
    assert entry.version == 12


@pytest.mark.asyncio
async def test_migrate_releases_legacy_climate_device_assignment(hass):
    climate_entry = MockConfigEntry(domain="climate_source")
    climate_entry.add_to_hass(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=5,
        data={
            CONF_APPLIANCE_TYPE: "thermostat_climate",
            CONF_CLIMATE_ENTITY: "climate.ac",
        },
    )
    entry.add_to_hass(hass)
    appliance_device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name="Air conditioner",
    )
    climate_entity = er.async_get(hass).async_get_or_create(
        "climate",
        climate_entry.domain,
        "air_conditioner",
        config_entry=climate_entry,
        device_id=appliance_device.id,
    )
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_CLIMATE_ENTITY: climate_entity.entity_id}
    )

    assert await async_migrate_entry(hass, entry)

    assert entry.version == 13
    assert er.async_get(hass).async_get(climate_entity.entity_id).device_id is None


@pytest.mark.parametrize(
    ("version", "appliance_type", "source_key", "source_entity"),
    (
        (2, "air_conditioner_power", CONF_POWER_ENTITY, "sensor.ac_power"),
        (3, "air_conditioner_climate", CONF_CLIMATE_ENTITY, "climate.ac"),
    ),
)
@pytest.mark.asyncio
async def test_migrate_removes_unsupported_ac_contact_sensor(
    hass, version, appliance_type, source_key, source_entity
):
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=version,
        data={
            CONF_APPLIANCE_TYPE: appliance_type,
            source_key: source_entity,
            CONF_RUNNING_ENTITY: "binary_sensor.ac_louver",
        },
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)

    assert entry.version == 13
    assert entry.data["category"] == "climate"
    expected_type = (
        "thermostat_climate"
        if appliance_type == "air_conditioner_climate"
        else appliance_type
    )
    assert entry.data["appliances"][0]["data"] == {
        CONF_APPLIANCE_TYPE: expected_type,
        CONF_APPLIANCE_CLASS: "air_conditioner",
        source_key: source_entity,
    }
    assert entry.data["appliances"][0]["options"] == {}


@pytest.mark.parametrize("appliance_type", ("refrigerator", "refrigerator_switch"))
@pytest.mark.asyncio
async def test_migrate_removes_refrigerator_compressor_and_plug_alarms(
    hass, appliance_type
):
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=4,
        data={CONF_APPLIANCE_TYPE: appliance_type},
        options={
            CONF_START_ACTIONS: [{"action": "test.start"}],
            CONF_FINISH_ACTIONS: [{"action": "test.finish"}],
            CONF_DOOR_OPEN_ACTIONS: [{"action": "test.door"}],
            CONF_COMPRESSOR_INACTIVE_ACTIONS: [{"action": "test.compressor"}],
            CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS: 3600,
            CONF_PLUG_OFF_ACTIONS: [{"action": "test.plug_off"}],
            CONF_PLUG_OFF_REPEAT_COUNT: 3,
            CONF_PLUG_OFF_REPEAT_INTERVAL_SECONDS: 900,
            CONF_ALARM_REPEAT_COUNT: 2,
            CONF_ALARM_REPEAT_INTERVAL_SECONDS: 600,
        },
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)

    assert entry.version == 13
    assert entry.data["appliances"][0]["data"][CONF_APPLIANCE_CLASS] == "refrigerator"
    assert entry.options == {}
    assert entry.data["appliances"][0]["options"] == {
        CONF_START_ACTIONS: [{"action": "test.start"}],
        CONF_FINISH_ACTIONS: [{"action": "test.finish"}],
        CONF_DOOR_OPEN_ACTIONS: [{"action": "test.door"}],
        CONF_ALARM_REPEAT_COUNT: 2,
        CONF_ALARM_REPEAT_INTERVAL_SECONDS: 600,
    }


@pytest.mark.parametrize(
    "appliance_type",
    tuple(
        dict.fromkeys(
            profile
            for classes in APPLIANCE_GROUPS.values()
            for modes in classes.values()
            for profile in modes.values()
        )
    ),
)
@pytest.mark.asyncio
async def test_every_profile_supports_config_entry_crud(
    hass, enable_custom_integrations, appliance_type
):
    profile = APPLIANCE_PROFILES[appliance_type]
    flow_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = flow_result["flow_id"]

    async def submit_identity(name: str):
        return await _select_profile_for_setup(
            hass, flow_id, name, appliance_type
        )

    def sensor_values(revision: str) -> tuple[dict[str, str], dict[str, str]]:
        form_values: dict[str, str] = {}
        stored_values: dict[str, str] = {}
        for sensor_input in profile.sensor_inputs:
            if sensor_input.config_key == CONF_SHUTTER_COVER_ENTITY:
                continue
            if sensor_input.config_key == CONF_POWER_ENTITY:
                entity_id = f"sensor.{revision}_power"
            elif sensor_input.config_key == CONF_ENERGY_ENTITY:
                entity_id = f"sensor.{revision}_energy"
            elif sensor_input.config_key == CONF_PLUG_ENTITY:
                entity_id = f"switch.{revision}_plug"
            elif sensor_input.config_key == CONF_RUNNING_ENTITY:
                entity_id = f"binary_sensor.{revision}_activity"
            elif sensor_input.config_key == CONF_CLIMATE_ENTITY:
                climate_source = MockConfigEntry(domain="climate_source")
                climate_source.add_to_hass(hass)
                entity_entry = er.async_get(hass).async_get_or_create(
                    "climate",
                    climate_source.domain,
                    revision,
                    config_entry=climate_source,
                )
                entity_id = entity_entry.entity_id
            elif sensor_input.config_key == CONF_MEDIA_PLAYER_ENTITY:
                media_player_source = MockConfigEntry(domain="media_player_source")
                media_player_source.add_to_hass(hass)
                entity_entry = er.async_get(hass).async_get_or_create(
                    "media_player",
                    media_player_source.domain,
                    revision,
                    config_entry=media_player_source,
                )
                entity_id = entity_entry.entity_id
            elif sensor_input.domain in {"fan", "vacuum"}:
                source_entry = MockConfigEntry(
                    domain=f"{sensor_input.domain}_source"
                )
                source_entry.add_to_hass(hass)
                entity_entry = er.async_get(hass).async_get_or_create(
                    sensor_input.domain,
                    source_entry.domain,
                    revision,
                    config_entry=source_entry,
                )
                entity_id = entity_entry.entity_id
                hass.states.async_set(
                    entity_id, "off" if sensor_input.domain == "fan" else "docked"
                )
            elif sensor_input.domain == "sensor":
                entity_id = f"sensor.{revision}_{sensor_input.output_entity or 'input'}"
            elif sensor_input.config_key == CONF_COVER_ENTITY:
                entity_id = f"cover.{revision}_cover"
            elif sensor_input.config_key == CONF_LOCK_ENTITY:
                entity_id = f"lock.{revision}_lock"
            elif sensor_input.config_key in {
                CONF_MAIL_MOTION_ENTITY,
                CONF_MAIL_SLOT_ENTITY,
            }:
                entity_id = f"binary_sensor.{revision}_arrival"
            else:
                entity_id = f"binary_sensor.{revision}_door"
            if sensor_input.required or sensor_input.config_key not in stored_values:
                form_values[sensor_input.form_key] = entity_id
            stored_values[sensor_input.config_key] = entity_id
        return form_values, stored_values

    def parameter_values() -> dict[str, int | float]:
        values: dict[str, int | float] = {}
        if "power_cycle" in profile.parameter_groups:
            values.update(
                {
                    "start_power_w": 4,
                    "start_duration_seconds": 15,
                    "finish_power_w": 1,
                    "finish_duration_seconds": 60,
                }
            )
        if "max_runtime" in profile.parameter_groups:
            values[CONF_MAX_RUNTIME_SECONDS] = 3600
        if "pending_unload" in profile.parameter_groups:
            values.update(
                {
                    CONF_PENDING_DELAY_SECONDS: 120,
                    CONF_PENDING_INTERVAL_SECONDS: 300,
                    CONF_PENDING_REPEATS: 2,
                }
            )
        if "door_alarm" in profile.parameter_groups:
            values[CONF_DOOR_OPEN_DELAY_SECONDS] = 120
        if "compressor_alarm" in profile.parameter_groups:
            values[CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS] = 3600
        if "alarm_repeats" in profile.parameter_groups:
            values[CONF_ALARM_REPEAT_INTERVAL_SECONDS] = 900
            values[CONF_ALARM_REPEAT_COUNT] = 3
        if "plug_off_alarm" in profile.parameter_groups:
            values[CONF_PLUG_OFF_REPEAT_INTERVAL_SECONDS] = 900
            values[CONF_PLUG_OFF_REPEAT_COUNT] = 3
        return values

    action_keys = {
        "cycle_start": CONF_START_ACTIONS,
        "cycle_finish": CONF_FINISH_ACTIONS,
        "emptied": CONF_EMPTIED_ACTIONS,
        "max_runtime": CONF_MAX_RUNTIME_ACTIONS,
        "pending_unload": CONF_PENDING_ACTIONS,
        "door_open_alarm": CONF_DOOR_OPEN_ACTIONS,
        "compressor_inactive_alarm": CONF_COMPRESSOR_INACTIVE_ACTIONS,
        "plug_off_alarm": CONF_PLUG_OFF_ACTIONS,
        "lock_locked": CONF_LOCK_LOCKED_ACTIONS,
        "lock_unlocked": CONF_LOCK_UNLOCKED_ACTIONS,
        "shutter_open": CONF_SHUTTER_OPEN_ACTIONS,
        "shutter_close": CONF_SHUTTER_CLOSE_ACTIONS,
    }
    action_values = {action_keys[group]: [] for group in profile.action_groups}

    result = await submit_identity(f"{appliance_type} appliance")
    assert result["step_id"] == f"sensors_{appliance_type}"
    first_sensor_form, first_sensor_storage = sensor_values(
        f"{appliance_type}_first"
    )
    result = await hass.config_entries.flow.async_configure(
        flow_id, first_sensor_form
    )
    if profile.parameter_groups:
        assert result["step_id"] == f"parameters_{appliance_type}"
        result = await hass.config_entries.flow.async_configure(
            flow_id, parameter_values()
        )
    assert result["step_id"] == f"actions_{appliance_type}"
    result = await hass.config_entries.flow.async_configure(flow_id, action_values)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    appliance = entry.data["appliances"][0]
    assert appliance["data"][CONF_APPLIANCE_TYPE] == appliance_type
    assert appliance["data"] == {
        "name": f"{appliance_type} appliance",
        CONF_APPLIANCE_TYPE: appliance_type,
        CONF_APPLIANCE_CLASS: _group_class_mode_for_profile(appliance_type)[1],
        **first_sensor_storage,
    }
    category = _group_class_mode_for_profile(appliance_type)[0]
    assert entry.data["category"] == category
    assert entry.title == get_appliance_group_name(category)
    assert entry in hass.config_entries.async_entries(DOMAIN)

    options_result = await hass.config_entries.options.async_init(entry.entry_id)
    assert "appliance_action" in {
        marker.schema for marker in options_result["data_schema"].schema
    }
    options_flow_id = options_result["flow_id"]
    result = await hass.config_entries.options.async_configure(
        options_flow_id,
        {"appliance_action": "edit"},
    )
    assert result["step_id"] == "select_appliance"
    result = await hass.config_entries.options.async_configure(
        options_flow_id, {"appliance_id": appliance["id"]}
    )
    assert result["step_id"] == "edit_appliance"
    result = await hass.config_entries.options.async_configure(
        options_flow_id,
        {"name": f"{appliance_type} updated"},
    )
    assert result["step_id"] == f"sensors_{appliance_type}"
    second_sensor_form, second_sensor_storage = sensor_values(
        f"{appliance_type}_second"
    )
    if "media_player" in profile.detection_sources:
        invalid_sensor_form = dict(second_sensor_form)
        media_player_input = next(
            item
            for item in profile.sensor_inputs
            if item.config_key == CONF_MEDIA_PLAYER_ENTITY
        )
        invalid_sensor_form[media_player_input.form_key] = "switch.invalid_source"
        with pytest.raises(InvalidData):
            await hass.config_entries.options.async_configure(
                options_flow_id, invalid_sensor_form
            )
    for source_domain in ("fan", "vacuum"):
        native_input = next(
            (item for item in profile.sensor_inputs if item.domain == source_domain),
            None,
        )
        if native_input is None:
            continue
        wrong_domain_entry = MockConfigEntry(domain="wrong_domain_source")
        wrong_domain_entry.add_to_hass(hass)
        wrong_domain_entity = er.async_get(hass).async_get_or_create(
            "switch",
            wrong_domain_entry.domain,
            f"{source_domain}_{appliance_type}",
            config_entry=wrong_domain_entry,
        )
        invalid_sensor_form = dict(second_sensor_form)
        invalid_sensor_form[native_input.form_key] = wrong_domain_entity.entity_id
        with pytest.raises(InvalidData):
            await hass.config_entries.options.async_configure(
                options_flow_id, invalid_sensor_form
            )
    if appliance_type == "opening":
        assert "clear_associated_shutter" not in {
            marker.schema for marker in result["data_schema"].schema
        }
        second_sensor_form.pop("opening_shutter_contact_entity")
        second_sensor_storage[CONF_SHUTTER_CONTACT_ENTITY] = None
        action_values.pop(CONF_SHUTTER_OPEN_ACTIONS, None)
        action_values.pop(CONF_SHUTTER_CLOSE_ACTIONS, None)
    result = await hass.config_entries.options.async_configure(
        options_flow_id, second_sensor_form
    )
    if profile.parameter_groups:
        assert result["step_id"] == f"parameters_{appliance_type}"
        result = await hass.config_entries.options.async_configure(
            options_flow_id, parameter_values()
        )
    assert result["step_id"] == f"actions_{appliance_type}"
    result = await hass.config_entries.options.async_configure(
        options_flow_id, action_values
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    updated_appliance = entry.data["appliances"][0]
    assert entry.title == get_appliance_group_name(category)
    assert updated_appliance["data"] == {
        "name": f"{appliance_type} updated",
        CONF_APPLIANCE_TYPE: appliance_type,
        CONF_APPLIANCE_CLASS: _group_class_mode_for_profile(appliance_type)[1],
        **second_sensor_storage,
        **(
            {
                CONF_SHUTTER_CONTACT_ENTITY: None,
            }
            if appliance_type == "opening"
            else {}
        ),
    }

    await hass.config_entries.async_remove(entry.entry_id)
    assert entry not in hass.config_entries.async_entries(DOMAIN)


@pytest.mark.asyncio
async def test_options_flow_keeps_optional_climate_inputs_cleared(
    hass, enable_custom_integrations
):
    climate_entry = MockConfigEntry(domain="climate_source")
    climate_entry.add_to_hass(hass)
    climate_entity = er.async_get(hass).async_get_or_create(
        "climate",
        climate_entry.domain,
        "living_room",
        config_entry=climate_entry,
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "name": "Air conditioner",
            CONF_APPLIANCE_TYPE: "thermostat_climate",
            CONF_CLIMATE_ENTITY: climate_entity.entity_id,
            CONF_POWER_ENTITY: "sensor.ac_power",
            CONF_PLUG_ENTITY: "switch.ac_plug",
            CONF_ENERGY_ENTITY: "sensor.ac_energy",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    flow_id = result["flow_id"]
    result = await hass.config_entries.options.async_configure(
        flow_id,
        {
            "name": "Thermostat",
            CONF_APPLIANCE_GROUP: "climate",
            CONF_APPLIANCE_CLASS: "thermostat",
            "activity_mode": "climate",
        },
    )
    assert result["step_id"] == "sensors_thermostat_climate"

    result = await hass.config_entries.options.async_configure(
        flow_id,
        {
            "thermostat_climate_climate_entity": climate_entity.entity_id,
        },
    )
    assert result["step_id"] == "actions_thermostat_climate"
    await hass.config_entries.options.async_configure(
        flow_id,
        {CONF_START_ACTIONS: [], CONF_FINISH_ACTIONS: []},
    )

    assert entry.data[CONF_POWER_ENTITY] is None
    assert entry.data[CONF_PLUG_ENTITY] is None
    assert entry.data[CONF_ENERGY_ENTITY] is None

    result = await hass.config_entries.options.async_init(entry.entry_id)
    flow_id = result["flow_id"]
    result = await hass.config_entries.options.async_configure(
        flow_id,
        {
            "name": "Thermostat",
            CONF_APPLIANCE_GROUP: "climate",
            CONF_APPLIANCE_CLASS: "thermostat",
            "activity_mode": "climate",
        },
    )
    defaults = result["data_schema"]({})
    assert "thermostat_climate_power_entity" not in defaults
    assert "thermostat_climate_plug_entity" not in defaults
    assert "thermostat_climate_energy_entity" not in defaults


@pytest.mark.asyncio
async def test_options_flow_removes_one_appliance_and_preserves_group_members(
    hass, enable_custom_integrations
):
    removed_id = "washer_to_remove"
    retained_id = "washer_to_keep"
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Large appliances",
        data={
            "category": "large_appliances",
            "appliances": [
                {
                    "id": appliance_id,
                    "data": {
                        "name": name,
                        CONF_APPLIANCE_TYPE: "laundry",
                        CONF_APPLIANCE_CLASS: "washer",
                    },
                    "options": {},
                }
                for appliance_id, name in (
                    (removed_id, "Washer to remove"),
                    (retained_id, "Washer to keep"),
                )
            ],
        },
    )
    entry.add_to_hass(hass)

    device_registry = dr.async_get(hass)
    removed_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, removed_id)},
        name="Washer to remove",
    )
    retained_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, retained_id)},
        name="Washer to keep",
    )
    entity_registry = er.async_get(hass)
    removed_entity = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{removed_id}_power",
        config_entry=entry,
        device_id=removed_device.id,
    )
    retained_entity = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{retained_id}_power",
        config_entry=entry,
        device_id=retained_device.id,
    )
    store = Store(hass, 1, f"{DOMAIN}_{removed_id}")
    await store.async_save({"last_cycle_duration_seconds": 60})

    result = await hass.config_entries.options.async_init(entry.entry_id)
    flow_id = result["flow_id"]
    result = await hass.config_entries.options.async_configure(
        flow_id, {"appliance_action": "remove"}
    )
    assert result["step_id"] == "select_appliance"
    result = await hass.config_entries.options.async_configure(
        flow_id, {"appliance_id": removed_id}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "confirm_remove"
    assert result["description_placeholders"] == {"name": "Washer to remove"}
    assert len(entry.data["appliances"]) == 2
    assert entity_registry.async_get(removed_entity.entity_id) is not None

    result = await hass.config_entries.options.async_configure(
        flow_id, {"next_step_id": "cancel_remove_appliance"}
    )
    assert result["type"] is FlowResultType.FORM
    assert entity_registry.async_get(removed_entity.entity_id) is not None
    assert await store.async_load() == {"last_cycle_duration_seconds": 60}

    result = await hass.config_entries.options.async_configure(
        flow_id, {"appliance_action": "remove"}
    )
    assert result["step_id"] == "select_appliance"
    result = await hass.config_entries.options.async_configure(
        flow_id, {"appliance_id": removed_id}
    )
    assert result["step_id"] == "confirm_remove"
    result = await hass.config_entries.options.async_configure(
        flow_id, {"next_step_id": "confirm_remove_appliance"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert [record["id"] for record in entry.data["appliances"]] == [retained_id]
    assert entity_registry.async_get(removed_entity.entity_id) is None
    assert entity_registry.async_get(retained_entity.entity_id) is not None
    assert device_module._get_device_by_identifier(
        device_registry, (DOMAIN, removed_id), entry.entry_id
    ) is None
    assert device_registry.async_get(retained_device.id) is not None
    assert await Store(hass, 1, f"{DOMAIN}_{removed_id}").async_load() is None


@pytest.mark.asyncio
async def test_removing_last_appliance_requires_confirmation(
    hass, enable_custom_integrations
):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Openings",
        data={
            "category": "openings",
            "appliances": [
                {
                    "id": "only-window",
                    "data": {
                        "name": "Bedroom window",
                        CONF_APPLIANCE_TYPE: "opening",
                        CONF_APPLIANCE_CLASS: "window",
                    },
                    "options": {},
                }
            ],
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    flow_id = result["flow_id"]
    result = await hass.config_entries.options.async_configure(
        flow_id, {"appliance_action": "remove"}
    )
    result = await hass.config_entries.options.async_configure(
        flow_id, {"appliance_id": "only-window"}
    )

    assert result["type"] is FlowResultType.MENU
    assert entry in hass.config_entries.async_entries(DOMAIN)
    assert len(entry.data["appliances"]) == 1

    result = await hass.config_entries.options.async_configure(
        flow_id, {"next_step_id": "confirm_remove_appliance"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "last_appliance_removed"
    assert entry not in hass.config_entries.async_entries(DOMAIN)