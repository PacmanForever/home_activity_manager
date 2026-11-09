"""Capabilities and detection sources for supported appliance types."""

from dataclasses import dataclass, replace

from .const import (
    CONF_DOOR_ENTITY,
    CONF_ENERGY_ENTITY,
    CONF_FAN_ENTITY,
    CONF_ILLUMINANCE_ENTITY,
    CONF_CLIMATE_ENTITY,
    CONF_COVER_ENTITY,
    CONF_LOCK_ENTITY,
    CONF_MEDIA_PLAYER_ENTITY,
    CONF_MAIL_MOTION_ENTITY,
    CONF_MAIL_SLOT_ENTITY,
    CONF_PLUG_ENTITY,
    CONF_POWER_ENTITY,
    CONF_PH_ENTITY,
    CONF_RUNNING_ENTITY,
    CONF_TEMPERATURE_ENTITY,
    CONF_VACUUM_ENTITY,
    CONF_SHUTTER_CONTACT_ENTITY,
    CONF_SHUTTER_COVER_ENTITY,
    CONF_WATER_LEVEL_ENTITY,
)


@dataclass(frozen=True, slots=True)
class SensorInput:
    """Describe one profile-owned entity selector and its stored setting."""

    form_key: str
    config_key: str
    domain: str
    device_classes: tuple[str, ...] = ()
    required: bool = False
    detection_source: str | None = None
    output_entity: str | None = None
    create_wrapper: bool = True
    proxy_always: bool = False

    @property
    def requires_source_representation(self) -> bool:
        """Return whether this input is represented by a visible source entity."""
        if self.domain in ("climate", "cover", "lock", "media_player", "fan", "vacuum"):
            return True
        if self.output_entity == "running":
            return False
        return self.create_wrapper


@dataclass(frozen=True, slots=True)
class ApplianceTypeProfile:
    """Describe the inputs and entities supported by an appliance type."""

    sensor_inputs: tuple[SensorInput, ...]
    parameter_groups: tuple[str, ...]
    action_groups: tuple[str, ...]
    output_entities: tuple[str, ...]
    supports_pending_unload: bool
    estimates_remaining: bool
    supports_max_runtime: bool = True

    @property
    def inputs_requiring_wrapper(self) -> tuple[SensorInput, ...]:
        return tuple(
            item
            for item in self.sensor_inputs
            if item.domain not in ("climate", "media_player", "fan", "vacuum")
            and item.create_wrapper
            and item.output_entity is None
        )

    @property
    def detection_sources(self) -> tuple[str, ...]:
        return tuple(
            item.detection_source
            for item in self.sensor_inputs
            if item.detection_source is not None
        )

    @property
    def supports_door_sensor(self) -> bool:
        return self.door_sensor_input is not None

    @property
    def door_sensor_input(self) -> SensorInput | None:
        return next(
            (item for item in self.sensor_inputs if item.config_key == CONF_DOOR_ENTITY),
            None,
        )

    @property
    def requires_door_sensor(self) -> bool:
        door_input = self.door_sensor_input
        return door_input is not None and door_input.required

    @property
    def supports_smart_plug(self) -> bool:
        return any(item.config_key == CONF_PLUG_ENTITY for item in self.sensor_inputs)


APPLIANCE_PROFILES = {
    "thermostat_climate": ApplianceTypeProfile(
        sensor_inputs=(
            SensorInput(
                form_key="thermostat_climate_climate_entity",
                config_key=CONF_CLIMATE_ENTITY,
                domain="climate",
                required=True,
                detection_source="climate",
            ),
            SensorInput(
                form_key="thermostat_climate_power_entity",
                config_key=CONF_POWER_ENTITY,
                domain="sensor",
                device_classes=("power",),
                output_entity="power",
            ),
            SensorInput(
                form_key="thermostat_climate_plug_entity",
                config_key=CONF_PLUG_ENTITY,
                domain="switch",
                output_entity="plug",
            ),
            SensorInput(
                form_key="thermostat_climate_energy_entity",
                config_key=CONF_ENERGY_ENTITY,
                domain="sensor",
                device_classes=("energy",),
                output_entity="total_energy",
                proxy_always=True,
            ),
        ),
        parameter_groups=("plug_off_alarm",),
        action_groups=("cycle_start", "cycle_finish", "plug_off_alarm"),
        output_entities=("last_cycle_duration", "last_cycle_energy", "running", "plug"),
        supports_pending_unload=False,
        estimates_remaining=False,
        supports_max_runtime=False,
    ),
    "washer": ApplianceTypeProfile(
        sensor_inputs=(
            SensorInput(
                form_key="washer_power_entity",
                config_key=CONF_POWER_ENTITY,
                domain="sensor",
                device_classes=("power",),
                required=True,
                detection_source="power",
                output_entity="power",
            ),
            SensorInput(
                form_key="washer_door_entity",
                config_key=CONF_DOOR_ENTITY,
                domain="binary_sensor",
                device_classes=("door", "opening"),
                output_entity="door",
            ),
            SensorInput(
                form_key="washer_plug_entity", config_key=CONF_PLUG_ENTITY, domain="switch",
                output_entity="plug",
            ),
            SensorInput(
                form_key="washer_energy_entity",
                config_key=CONF_ENERGY_ENTITY,
                domain="sensor",
                device_classes=("energy",),
                output_entity="total_energy",
                proxy_always=True,
            ),
        ),
        parameter_groups=("power_cycle", "max_runtime", "pending_unload", "plug_off_alarm"),
        action_groups=("cycle_start", "cycle_finish", "max_runtime", "pending_unload", "emptied", "plug_off_alarm"),
        output_entities=(
            "power", "total_energy", "last_cycle_duration", "last_cycle_energy", "estimated_remaining",
            "running", "door", "pending_unload", "clear_pending", "plug",
        ),
        supports_pending_unload=True,
        estimates_remaining=True,
    ),
    "dishwasher": ApplianceTypeProfile(
        sensor_inputs=(
            SensorInput(
                form_key="dishwasher_power_entity",
                config_key=CONF_POWER_ENTITY,
                domain="sensor",
                device_classes=("power",),
                required=True,
                detection_source="power",
                output_entity="power",
            ),
            SensorInput(
                form_key="dishwasher_door_entity",
                config_key=CONF_DOOR_ENTITY,
                domain="binary_sensor",
                device_classes=("door", "opening"),
                output_entity="door",
            ),
            SensorInput(
                form_key="dishwasher_plug_entity", config_key=CONF_PLUG_ENTITY, domain="switch",
                output_entity="plug",
            ),
            SensorInput(
                form_key="dishwasher_energy_entity",
                config_key=CONF_ENERGY_ENTITY,
                domain="sensor",
                device_classes=("energy",),
                output_entity="total_energy",
                proxy_always=True,
            ),
        ),
        parameter_groups=("power_cycle", "max_runtime", "pending_unload", "plug_off_alarm"),
        action_groups=("cycle_start", "cycle_finish", "max_runtime", "pending_unload", "emptied", "plug_off_alarm"),
        output_entities=(
            "power", "total_energy", "last_cycle_duration", "last_cycle_energy", "estimated_remaining",
            "running", "door", "pending_unload", "clear_pending", "plug",
        ),
        supports_pending_unload=True,
        estimates_remaining=True,
    ),
    "dryer": ApplianceTypeProfile(
        sensor_inputs=(
            SensorInput(
                form_key="dryer_power_entity",
                config_key=CONF_POWER_ENTITY,
                domain="sensor",
                device_classes=("power",),
                required=True,
                detection_source="power",
                output_entity="power",
            ),
            SensorInput(
                form_key="dryer_door_entity",
                config_key=CONF_DOOR_ENTITY,
                domain="binary_sensor",
                device_classes=("door", "opening"),
                output_entity="door",
            ),
            SensorInput(
                form_key="dryer_plug_entity", config_key=CONF_PLUG_ENTITY, domain="switch",
                output_entity="plug",
            ),
            SensorInput(
                form_key="dryer_energy_entity",
                config_key=CONF_ENERGY_ENTITY,
                domain="sensor",
                device_classes=("energy",),
                output_entity="total_energy",
                proxy_always=True,
            ),
        ),
        parameter_groups=("power_cycle", "max_runtime", "pending_unload", "plug_off_alarm"),
        action_groups=("cycle_start", "cycle_finish", "max_runtime", "pending_unload", "emptied", "plug_off_alarm"),
        output_entities=(
            "power", "total_energy", "last_cycle_duration", "last_cycle_energy", "estimated_remaining",
            "running", "door", "pending_unload", "clear_pending", "plug",
        ),
        supports_pending_unload=True,
        estimates_remaining=True,
    ),
    "air_conditioner_contact": ApplianceTypeProfile(
        sensor_inputs=(
            SensorInput(
                form_key="air_conditioner_contact_running_entity",
                config_key=CONF_RUNNING_ENTITY,
                domain="binary_sensor",
                device_classes=("opening",),
                required=True,
                detection_source="running_sensor",
                output_entity="running",
            ),
            SensorInput(
                form_key="air_conditioner_contact_plug_entity", config_key=CONF_PLUG_ENTITY, domain="switch",
                output_entity="plug",
            ),
            SensorInput(
                form_key="air_conditioner_contact_power_entity",
                config_key=CONF_POWER_ENTITY,
                domain="sensor",
                device_classes=("power",),
                output_entity="power",
            ),
            SensorInput(
                form_key="air_conditioner_contact_energy_entity",
                config_key=CONF_ENERGY_ENTITY,
                domain="sensor",
                device_classes=("energy",),
                output_entity="total_energy",
                proxy_always=True,
            ),
        ),
        parameter_groups=("plug_off_alarm",),
        action_groups=("cycle_start", "cycle_finish", "plug_off_alarm"),
        output_entities=("last_cycle_duration", "last_cycle_energy", "running", "plug"),
        supports_pending_unload=False,
        estimates_remaining=False,
        supports_max_runtime=False,
    ),
    "air_conditioner_power": ApplianceTypeProfile(
        sensor_inputs=(
            SensorInput(
                form_key="air_conditioner_power_power_entity",
                config_key=CONF_POWER_ENTITY,
                domain="sensor",
                device_classes=("power",),
                required=True,
                detection_source="power",
                output_entity="power",
            ),
            SensorInput(
                form_key="air_conditioner_power_plug_entity", config_key=CONF_PLUG_ENTITY, domain="switch",
                output_entity="plug",
            ),
            SensorInput(
                form_key="air_conditioner_power_energy_entity",
                config_key=CONF_ENERGY_ENTITY,
                domain="sensor",
                device_classes=("energy",),
                output_entity="total_energy",
                proxy_always=True,
            ),
        ),
        parameter_groups=("power_cycle", "plug_off_alarm"),
        action_groups=("cycle_start", "cycle_finish", "plug_off_alarm"),
        output_entities=("power", "total_energy", "last_cycle_duration", "last_cycle_energy", "running", "plug"),
        supports_pending_unload=False,
        estimates_remaining=False,
        supports_max_runtime=False,
    ),
    "air_conditioner_climate": ApplianceTypeProfile(
        sensor_inputs=(
            SensorInput(
                form_key="air_conditioner_climate_climate_entity",
                config_key=CONF_CLIMATE_ENTITY,
                domain="climate",
                required=True,
                detection_source="climate",
            ),
            SensorInput(
                form_key="air_conditioner_climate_power_entity",
                config_key=CONF_POWER_ENTITY,
                domain="sensor",
                device_classes=("power",),
                output_entity="power",
            ),
            SensorInput(
                form_key="air_conditioner_climate_plug_entity",
                config_key=CONF_PLUG_ENTITY,
                domain="switch",
                output_entity="plug",
            ),
            SensorInput(
                form_key="air_conditioner_climate_energy_entity",
                config_key=CONF_ENERGY_ENTITY,
                domain="sensor",
                device_classes=("energy",),
                output_entity="total_energy",
                proxy_always=True,
            ),
        ),
        parameter_groups=("plug_off_alarm",),
        action_groups=("cycle_start", "cycle_finish", "plug_off_alarm"),
        output_entities=("last_cycle_duration", "last_cycle_energy", "running", "plug"),
        supports_pending_unload=False,
        estimates_remaining=False,
        supports_max_runtime=False,
    ),
    "fan_power": ApplianceTypeProfile(
        sensor_inputs=(
            SensorInput(
                form_key="fan_power_power_entity",
                config_key=CONF_POWER_ENTITY,
                domain="sensor",
                device_classes=("power",),
                required=True,
                detection_source="power",
                output_entity="power",
            ),
            SensorInput(
                form_key="fan_power_energy_entity",
                config_key=CONF_ENERGY_ENTITY,
                domain="sensor",
                device_classes=("energy",),
                output_entity="total_energy",
                proxy_always=True,
            ),
        ),
        parameter_groups=("power_cycle",),
        action_groups=("cycle_start", "cycle_finish"),
        output_entities=("power", "total_energy", "last_cycle_duration", "last_cycle_energy", "running"),
        supports_pending_unload=False,
        estimates_remaining=False,
        supports_max_runtime=False,
    ),
    "fan_switch": ApplianceTypeProfile(
        sensor_inputs=(
            SensorInput(
                form_key="fan_switch_plug_entity",
                config_key=CONF_PLUG_ENTITY,
                domain="switch",
                required=True,
                detection_source="smart_plug",
                output_entity="plug",
            ),
            SensorInput(
                form_key="fan_switch_power_entity",
                config_key=CONF_POWER_ENTITY,
                domain="sensor",
                device_classes=("power",),
                output_entity="power",
            ),
            SensorInput(
                form_key="fan_switch_energy_entity",
                config_key=CONF_ENERGY_ENTITY,
                domain="sensor",
                device_classes=("energy",),
                output_entity="total_energy",
                proxy_always=True,
            ),
        ),
        parameter_groups=(),
        action_groups=("cycle_start", "cycle_finish"),
        output_entities=("power", "total_energy", "last_cycle_duration", "last_cycle_energy", "running", "plug"),
        supports_pending_unload=False,
        estimates_remaining=False,
        supports_max_runtime=False,
    ),
    "fan_entity": ApplianceTypeProfile(
        sensor_inputs=(
            SensorInput(
                form_key="fan_entity_fan_entity",
                config_key=CONF_FAN_ENTITY,
                domain="fan",
                required=True,
                detection_source="fan",
                create_wrapper=False,
            ),
            SensorInput(
                form_key="fan_entity_power_entity",
                config_key=CONF_POWER_ENTITY,
                domain="sensor",
                device_classes=("power",),
                output_entity="power",
            ),
            SensorInput(
                form_key="fan_entity_energy_entity",
                config_key=CONF_ENERGY_ENTITY,
                domain="sensor",
                device_classes=("energy",),
                output_entity="total_energy",
                proxy_always=True,
            ),
        ),
        parameter_groups=(),
        action_groups=("cycle_start", "cycle_finish"),
        output_entities=("power", "total_energy", "last_cycle_duration", "last_cycle_energy", "running"),
        supports_pending_unload=False,
        estimates_remaining=False,
        supports_max_runtime=False,
    ),
    "generic_switch": ApplianceTypeProfile(
        sensor_inputs=(
            SensorInput(
                form_key="generic_switch_plug_entity",
                config_key=CONF_PLUG_ENTITY,
                domain="switch",
                required=True,
                detection_source="smart_plug",
                output_entity="plug",
            ),
            SensorInput(
                form_key="generic_switch_power_entity",
                config_key=CONF_POWER_ENTITY,
                domain="sensor",
                device_classes=("power",),
                output_entity="power",
            ),
            SensorInput(
                form_key="generic_switch_energy_entity",
                config_key=CONF_ENERGY_ENTITY,
                domain="sensor",
                device_classes=("energy",),
                output_entity="total_energy",
                proxy_always=True,
            ),
        ),
        parameter_groups=(),
        action_groups=("cycle_start", "cycle_finish"),
        output_entities=("power", "total_energy", "last_cycle_duration", "last_cycle_energy", "running", "plug"),
        supports_pending_unload=False,
        estimates_remaining=False,
        supports_max_runtime=False,
    ),
    "robot_vacuum_vacuum": ApplianceTypeProfile(
        sensor_inputs=(
            SensorInput(
                form_key="robot_vacuum_vacuum_entity",
                config_key=CONF_VACUUM_ENTITY,
                domain="vacuum",
                required=True,
                detection_source="vacuum",
                create_wrapper=False,
            ),
        ),
        parameter_groups=(),
        action_groups=("cycle_start", "cycle_finish"),
        output_entities=("last_cycle_duration", "running"),
        supports_pending_unload=False,
        estimates_remaining=False,
        supports_max_runtime=False,
    ),
    "refrigerator": ApplianceTypeProfile(
        sensor_inputs=(
            SensorInput(
                form_key="refrigerator_power_entity",
                config_key=CONF_POWER_ENTITY,
                domain="sensor",
                device_classes=("power",),
                required=True,
                detection_source="power",
                output_entity="power",
            ),
            SensorInput(
                form_key="refrigerator_door_entity",
                config_key=CONF_DOOR_ENTITY,
                domain="binary_sensor",
                device_classes=("door", "opening"),
                required=True,
                output_entity="door",
            ),
            SensorInput(
                form_key="refrigerator_plug_entity", config_key=CONF_PLUG_ENTITY, domain="switch",
                output_entity="plug",
            ),
            SensorInput(
                form_key="refrigerator_energy_entity",
                config_key=CONF_ENERGY_ENTITY,
                domain="sensor",
                device_classes=("energy",),
                output_entity="total_energy",
                proxy_always=True,
            ),
        ),
        parameter_groups=(
            "power_cycle",
            "door_alarm",
            "alarm_repeats",
        ),
        action_groups=(
            "cycle_start",
            "cycle_finish",
            "door_open_alarm",
        ),
        output_entities=("power", "total_energy", "last_cycle_duration", "last_cycle_energy", "running", "door", "plug"),
        supports_pending_unload=False,
        estimates_remaining=False,
        supports_max_runtime=False,
    ),
        "refrigerator_switch": ApplianceTypeProfile(
            sensor_inputs=(
                SensorInput(
                    form_key="refrigerator_switch_smart_plug_entity",
                    config_key=CONF_PLUG_ENTITY,
                    domain="switch",
                    required=True,
                    detection_source="smart_plug",
                    output_entity="plug",
                ),
                SensorInput(
                    form_key="refrigerator_switch_door_entity",
                    config_key=CONF_DOOR_ENTITY,
                    domain="binary_sensor",
                    device_classes=("door",),
                    required=True,
                    output_entity="door",
                ),
                SensorInput(
                    form_key="refrigerator_switch_power_entity",
                    config_key=CONF_POWER_ENTITY,
                    domain="sensor",
                    device_classes=("power",),
                    output_entity="power",
                ),
                SensorInput(
                    form_key="refrigerator_switch_energy_entity",
                    config_key=CONF_ENERGY_ENTITY,
                    domain="sensor",
                    device_classes=("energy",),
                    output_entity="total_energy",
                    proxy_always=True,
                ),
            ),
            parameter_groups=("door_alarm", "alarm_repeats"),
            action_groups=(
                "cycle_start",
                "cycle_finish",
                "door_open_alarm",
            ),
            output_entities=("last_cycle_duration", "last_cycle_energy", "running", "door", "plug"),
            supports_pending_unload=False,
            estimates_remaining=False,
            supports_max_runtime=False,
        ),
    "sun_protection_contact": ApplianceTypeProfile(
        sensor_inputs=(
            SensorInput(
                form_key="sun_protection_contact_sensor",
                config_key=CONF_RUNNING_ENTITY,
                domain="binary_sensor",
                device_classes=("opening", "door", "window"),
                required=True,
                detection_source="running_sensor",
            ),
        ),
        parameter_groups=(),
        action_groups=("cycle_start", "cycle_finish"),
        output_entities=("last_cycle_duration",),
        supports_pending_unload=False,
        estimates_remaining=False,
        supports_max_runtime=False,
    ),
    "sun_protection_cover": ApplianceTypeProfile(
        sensor_inputs=(
            SensorInput(
                form_key="sun_protection_cover_entity",
                config_key=CONF_COVER_ENTITY,
                domain="cover",
                required=True,
                detection_source="cover",
                create_wrapper=False,
            ),
        ),
        parameter_groups=(),
        action_groups=("cycle_start", "cycle_finish"),
        output_entities=("last_cycle_duration", "running"),
        supports_pending_unload=False,
        estimates_remaining=False,
        supports_max_runtime=False,
    ),
    "opening": ApplianceTypeProfile(
        sensor_inputs=(
            SensorInput(
                form_key="opening_sensor",
                config_key=CONF_RUNNING_ENTITY,
                domain="binary_sensor",
                device_classes=("opening", "door", "window"),
                required=True,
                detection_source="running_sensor",
            ),
            SensorInput(
                form_key="opening_lock_entity",
                config_key=CONF_LOCK_ENTITY,
                domain="lock",
                create_wrapper=False,
            ),
            SensorInput(
                form_key="opening_shutter_contact_entity",
                config_key=CONF_SHUTTER_CONTACT_ENTITY,
                domain="binary_sensor",
                device_classes=("opening", "door", "window"),
                output_entity="shutter",
            ),
            SensorInput(
                form_key="opening_shutter_cover_entity",
                config_key=CONF_SHUTTER_COVER_ENTITY,
                domain="cover",
                output_entity="shutter",
                create_wrapper=False,
            ),
        ),
        parameter_groups=(),
        action_groups=(
            "cycle_start",
            "cycle_finish",
            "lock_locked",
            "lock_unlocked",
            "shutter_open",
            "shutter_close",
        ),
        output_entities=(
            "last_cycle_duration",
            "lock_unlock_duration",
            "shutter",
            "shutter_last_cycle_duration",
        ),
        supports_pending_unload=False,
        estimates_remaining=False,
        supports_max_runtime=False,
    ),
    "access_contact": ApplianceTypeProfile(
        sensor_inputs=(
            SensorInput(
                form_key="access_contact_sensor",
                config_key=CONF_RUNNING_ENTITY,
                domain="binary_sensor",
                device_classes=("opening", "door", "window"),
                required=True,
                detection_source="running_sensor",
            ),
            SensorInput(
                form_key="access_lock_entity",
                config_key=CONF_LOCK_ENTITY,
                domain="lock",
                create_wrapper=False,
            ),
        ),
        parameter_groups=(),
        action_groups=("cycle_start", "cycle_finish", "lock_locked", "lock_unlocked"),
        output_entities=("last_cycle_duration", "lock_unlock_duration"),
        supports_pending_unload=False,
        estimates_remaining=False,
        supports_max_runtime=False,
    ),
    "opening_cover": ApplianceTypeProfile(
        sensor_inputs=(
            SensorInput(
                form_key="opening_cover_entity",
                config_key=CONF_COVER_ENTITY,
                domain="cover",
                required=True,
                detection_source="cover",
                create_wrapper=False,
            ),
            SensorInput(
                form_key="opening_cover_lock_entity",
                config_key=CONF_LOCK_ENTITY,
                domain="lock",
                create_wrapper=False,
            ),
        ),
        parameter_groups=(),
        action_groups=("cycle_start", "cycle_finish", "lock_locked", "lock_unlocked"),
        output_entities=("last_cycle_duration", "lock_unlock_duration", "running"),
        supports_pending_unload=False,
        estimates_remaining=False,
        supports_max_runtime=False,
    ),
    "mailbox_motion": ApplianceTypeProfile(
        sensor_inputs=(
            SensorInput(
                form_key="mailbox_motion_arrival_entity",
                config_key=CONF_MAIL_MOTION_ENTITY,
                domain="binary_sensor",
                device_classes=("motion",),
                required=True,
                detection_source="mail_motion",
                create_wrapper=False,
            ),
            SensorInput(
                form_key="mailbox_motion_door_entity",
                config_key=CONF_DOOR_ENTITY,
                domain="binary_sensor",
                device_classes=("door",),
                required=True,
                output_entity="door",
            ),
        ),
        parameter_groups=("pending_unload",),
        action_groups=("cycle_start", "cycle_finish", "pending_unload", "emptied"),
        output_entities=("door", "pending_unload", "clear_pending"),
        supports_pending_unload=True,
        estimates_remaining=False,
        supports_max_runtime=False,
    ),
    "mailbox_slot": ApplianceTypeProfile(
        sensor_inputs=(
            SensorInput(
                form_key="mailbox_slot_arrival_entity",
                config_key=CONF_MAIL_SLOT_ENTITY,
                domain="binary_sensor",
                device_classes=("door", "opening"),
                required=True,
                detection_source="mail_slot",
                output_entity="mail_slot",
            ),
            SensorInput(
                form_key="mailbox_slot_door_entity",
                config_key=CONF_DOOR_ENTITY,
                domain="binary_sensor",
                device_classes=("door",),
                required=True,
                output_entity="door",
            ),
        ),
        parameter_groups=("pending_unload",),
        action_groups=("cycle_start", "cycle_finish", "pending_unload", "emptied"),
        output_entities=("door", "mail_slot", "pending_unload", "clear_pending"),
        supports_pending_unload=True,
        estimates_remaining=False,
        supports_max_runtime=False,
    ),
}

APPLIANCE_CATEGORIES = {
    "thermostat": {
        "running_sensor": "air_conditioner_contact",
        "power": "air_conditioner_power",
        "climate": "thermostat_climate",
    },
    "air_conditioner": {
        "climate": "air_conditioner_climate",
    },
    "dryer": {"power": "dryer"},
    "mailbox": {"mail_slot": "mailbox_slot", "mail_motion": "mailbox_motion"},
    "opening": {"running_sensor": "opening"},
    "access": {"running_sensor": "access_contact", "cover": "opening_cover"},
    "refrigerator": {"smart_plug": "refrigerator_switch", "power": "refrigerator"},
    "sun_protection": {
        "running_sensor": "sun_protection_contact",
        "cover": "sun_protection_cover",
    },
    "washer": {"power": "washer"},
    "dishwasher": {"power": "dishwasher"},
    "small_appliances": {
        "smart_plug": "generic_switch",
        "vacuum": "robot_vacuum_vacuum",
    },
}

APPLIANCE_GROUPS = {
    "climate": {
        "air_conditioner": {
            "running_sensor": "air_conditioner_contact",
            "power": "air_conditioner_power",
            "climate": "air_conditioner_climate",
        },
        "fan": {"power": "fan_power", "smart_plug": "fan_switch", "fan": "fan_entity"},
        "thermostat": {"climate": "thermostat_climate"},
    },
    "large_appliances": {
        "washer": {"power": "laundry"},
        "dryer": {"power": "dryer"},
        "dishwasher": {"power": "dishwasher"},
        "refrigerator": {
            "smart_plug": "refrigerator_switch",
            "power": "refrigerator",
        },
        "freezer": {"smart_plug": "refrigerator_switch", "power": "refrigerator"},
    },
    "animal_care": {
        "aquarium": {
            "smart_plug": "aquarium_plug",
            "power": "aquarium_power",
        },
    },
    "openings": {
        "door": {"running_sensor": "opening"},
        "sliding_door": {"running_sensor": "opening"},
        "window": {"running_sensor": "opening"},
        "access": {"running_sensor": "access_contact", "cover": "opening_cover"},
    },
    "sun_protection": {
        "awning": {
            "running_sensor": "sun_protection_contact",
            "cover": "sun_protection_cover",
        },
    },
    "deliveries": {
        "mailbox": {"mail_slot": "mailbox_slot", "mail_motion": "mailbox_motion"}
    },
    "electronics": {
        "screen": {
            "smart_plug": "screen_switch",
            "media_player": "screen_media_player",
        },
        "av_equipment": {
            "smart_plug": "av_equipment_switch",
            "media_player": "av_equipment_media_player",
        },
        "console": {"smart_plug": "console_switch"},
        "computer": {"smart_plug": "computer_switch"},
    },
    "small_appliances": {
        "generic": {"smart_plug": "generic_switch"},
        "robot_vacuum": {"vacuum": "robot_vacuum_vacuum"},
    },
}

APPLIANCE_PROFILES["laundry"] = replace(
    APPLIANCE_PROFILES["washer"],
    sensor_inputs=tuple(
        replace(item, form_key=item.form_key.replace("washer_", "laundry_"))
        for item in APPLIANCE_PROFILES["washer"].sensor_inputs
    ),
)


def _aquarium_optional_inputs(prefix: str) -> tuple[SensorInput, ...]:
    return (
        SensorInput(
            form_key=f"{prefix}_illuminance_entity",
            config_key=CONF_ILLUMINANCE_ENTITY,
            domain="sensor",
            device_classes=("illuminance",),
            output_entity="illuminance",
        ),
        SensorInput(
            form_key=f"{prefix}_temperature_entity",
            config_key=CONF_TEMPERATURE_ENTITY,
            domain="sensor",
            device_classes=("temperature",),
            output_entity="water_temperature",
        ),
        SensorInput(
            form_key=f"{prefix}_ph_entity",
            config_key=CONF_PH_ENTITY,
            domain="sensor",
            output_entity="ph",
        ),
        SensorInput(
            form_key=f"{prefix}_water_level_entity",
            config_key=CONF_WATER_LEVEL_ENTITY,
            domain="sensor",
            output_entity="water_level",
        ),
    )


APPLIANCE_PROFILES["aquarium_plug"] = ApplianceTypeProfile(
    sensor_inputs=(
        SensorInput(
            form_key="aquarium_plug_entity",
            config_key=CONF_PLUG_ENTITY,
            domain="switch",
            required=True,
            detection_source="smart_plug",
            output_entity="plug",
        ),
        SensorInput(
            form_key="aquarium_plug_power_entity",
            config_key=CONF_POWER_ENTITY,
            domain="sensor",
            device_classes=("power",),
            output_entity="power",
        ),
        SensorInput(
            form_key="aquarium_plug_energy_entity",
            config_key=CONF_ENERGY_ENTITY,
            domain="sensor",
            device_classes=("energy",),
            output_entity="total_energy",
            proxy_always=True,
        ),
        *_aquarium_optional_inputs("aquarium_plug"),
    ),
    parameter_groups=(),
    action_groups=("cycle_start", "cycle_finish"),
    output_entities=(
        "plug",
        "power",
        "total_energy",
        "illuminance",
        "water_temperature",
        "ph",
        "water_level",
        "last_cycle_duration",
        "last_cycle_energy",
        "running",
    ),
    supports_pending_unload=False,
    estimates_remaining=False,
    supports_max_runtime=False,
)

APPLIANCE_PROFILES["aquarium_power"] = ApplianceTypeProfile(
    sensor_inputs=(
        SensorInput(
            form_key="aquarium_power_entity",
            config_key=CONF_POWER_ENTITY,
            domain="sensor",
            device_classes=("power",),
            required=True,
            detection_source="power",
            output_entity="power",
        ),
        SensorInput(
            form_key="aquarium_power_plug_entity",
            config_key=CONF_PLUG_ENTITY,
            domain="switch",
            output_entity="plug",
        ),
        SensorInput(
            form_key="aquarium_power_energy_entity",
            config_key=CONF_ENERGY_ENTITY,
            domain="sensor",
            device_classes=("energy",),
            output_entity="total_energy",
            proxy_always=True,
        ),
        *_aquarium_optional_inputs("aquarium_power"),
    ),
    parameter_groups=("power_cycle",),
    action_groups=("cycle_start", "cycle_finish"),
    output_entities=(
        "power",
        "total_energy",
        "plug",
        "illuminance",
        "water_temperature",
        "ph",
        "water_level",
        "last_cycle_duration",
        "last_cycle_energy",
        "running",
    ),
    supports_pending_unload=False,
    estimates_remaining=False,
    supports_max_runtime=False,
)

APPLIANCE_PROFILES["screen_switch"] = ApplianceTypeProfile(
    sensor_inputs=(
        SensorInput(
            form_key="screen_switch_plug_entity",
            config_key=CONF_PLUG_ENTITY,
            domain="switch",
            required=True,
            detection_source="smart_plug",
            output_entity="plug",
        ),
        SensorInput(form_key="screen_switch_power_entity", config_key=CONF_POWER_ENTITY, domain="sensor", device_classes=("power",), output_entity="power"),
        SensorInput(form_key="screen_switch_energy_entity", config_key=CONF_ENERGY_ENTITY, domain="sensor", device_classes=("energy",), output_entity="total_energy", proxy_always=True),
    ),
    parameter_groups=(),
    action_groups=("cycle_start", "cycle_finish"),
    output_entities=("power", "total_energy", "last_cycle_duration", "last_cycle_energy", "running", "plug"),
    supports_pending_unload=False,
    estimates_remaining=False,
    supports_max_runtime=False,
)
APPLIANCE_PROFILES["screen_media_player"] = ApplianceTypeProfile(
    sensor_inputs=(
        SensorInput(form_key="screen_media_player_entity", config_key=CONF_MEDIA_PLAYER_ENTITY, domain="media_player", required=True, detection_source="media_player", create_wrapper=False),
        SensorInput(form_key="screen_media_player_power_entity", config_key=CONF_POWER_ENTITY, domain="sensor", device_classes=("power",), output_entity="power"),
        SensorInput(form_key="screen_media_player_energy_entity", config_key=CONF_ENERGY_ENTITY, domain="sensor", device_classes=("energy",), output_entity="total_energy", proxy_always=True),
    ),
    parameter_groups=(),
    action_groups=("cycle_start", "cycle_finish"),
    output_entities=("power", "total_energy", "last_cycle_duration", "last_cycle_energy", "running"),
    supports_pending_unload=False,
    estimates_remaining=False,
    supports_max_runtime=False,
)
APPLIANCE_PROFILES["av_equipment_switch"] = ApplianceTypeProfile(
    sensor_inputs=(
        SensorInput(form_key="av_equipment_switch_plug_entity", config_key=CONF_PLUG_ENTITY, domain="switch", required=True, detection_source="smart_plug", output_entity="plug"),
        SensorInput(form_key="av_equipment_switch_power_entity", config_key=CONF_POWER_ENTITY, domain="sensor", device_classes=("power",), output_entity="power"),
        SensorInput(form_key="av_equipment_switch_energy_entity", config_key=CONF_ENERGY_ENTITY, domain="sensor", device_classes=("energy",), output_entity="total_energy", proxy_always=True),
    ),
    parameter_groups=(),
    action_groups=("cycle_start", "cycle_finish"),
    output_entities=("power", "total_energy", "last_cycle_duration", "last_cycle_energy", "running", "plug"),
    supports_pending_unload=False,
    estimates_remaining=False,
    supports_max_runtime=False,
)
APPLIANCE_PROFILES["av_equipment_media_player"] = ApplianceTypeProfile(
    sensor_inputs=(
        SensorInput(form_key="av_equipment_media_player_entity", config_key=CONF_MEDIA_PLAYER_ENTITY, domain="media_player", required=True, detection_source="media_player", create_wrapper=False),
        SensorInput(form_key="av_equipment_media_player_power_entity", config_key=CONF_POWER_ENTITY, domain="sensor", device_classes=("power",), output_entity="power"),
        SensorInput(form_key="av_equipment_media_player_energy_entity", config_key=CONF_ENERGY_ENTITY, domain="sensor", device_classes=("energy",), output_entity="total_energy", proxy_always=True),
    ),
    parameter_groups=(),
    action_groups=("cycle_start", "cycle_finish"),
    output_entities=("power", "total_energy", "last_cycle_duration", "last_cycle_energy", "running"),
    supports_pending_unload=False,
    estimates_remaining=False,
    supports_max_runtime=False,
)
APPLIANCE_PROFILES["console_switch"] = ApplianceTypeProfile(
    sensor_inputs=(
        SensorInput(form_key="console_switch_plug_entity", config_key=CONF_PLUG_ENTITY, domain="switch", required=True, detection_source="smart_plug", output_entity="plug"),
        SensorInput(form_key="console_switch_power_entity", config_key=CONF_POWER_ENTITY, domain="sensor", device_classes=("power",), output_entity="power"),
        SensorInput(form_key="console_switch_energy_entity", config_key=CONF_ENERGY_ENTITY, domain="sensor", device_classes=("energy",), output_entity="total_energy", proxy_always=True),
    ),
    parameter_groups=(),
    action_groups=("cycle_start", "cycle_finish"),
    output_entities=("power", "total_energy", "last_cycle_duration", "last_cycle_energy", "running", "plug"),
    supports_pending_unload=False,
    estimates_remaining=False,
    supports_max_runtime=False,
)
APPLIANCE_PROFILES["computer_switch"] = ApplianceTypeProfile(
    sensor_inputs=(
        SensorInput(form_key="computer_switch_plug_entity", config_key=CONF_PLUG_ENTITY, domain="switch", required=True, detection_source="smart_plug", output_entity="plug"),
        SensorInput(form_key="computer_switch_power_entity", config_key=CONF_POWER_ENTITY, domain="sensor", device_classes=("power",), output_entity="power"),
        SensorInput(form_key="computer_switch_energy_entity", config_key=CONF_ENERGY_ENTITY, domain="sensor", device_classes=("energy",), output_entity="total_energy", proxy_always=True),
    ),
    parameter_groups=(),
    action_groups=("cycle_start", "cycle_finish"),
    output_entities=("power", "total_energy", "last_cycle_duration", "last_cycle_energy", "running", "plug"),
    supports_pending_unload=False,
    estimates_remaining=False,
    supports_max_runtime=False,
)

APPLIANCE_GROUP_NAMES = {
    "climate": "Climate control",
    "large_appliances": "Large appliances",
    "animal_care": "Animal care",
    "openings": "Openings",
    "sun_protection": "Sun protection",
    "deliveries": "Deliveries",
    "electronics": "Electronics",
    "small_appliances": "Small appliances",
}

APPLIANCE_GROUP_TRANSLATIONS = {
    "ca": {
        "climate": "Climatització",
        "large_appliances": "Grans electrodomèstics",
        "animal_care": "Cura d'animals",
        "openings": "Tancaments",
        "sun_protection": "Protecció solar",
        "deliveries": "Lliuraments",
        "electronics": "Electrònica",
        "small_appliances": "Petits electrodomèstics",
    },
    "es": {
        "climate": "Climatización",
        "large_appliances": "Grandes electrodomésticos",
        "animal_care": "Cuidado de animales",
        "openings": "Aberturas",
        "sun_protection": "Protección solar",
        "deliveries": "Entregas",
        "electronics": "Electrónica",
        "small_appliances": "Pequeños electrodomésticos",
    },
}

APPLIANCE_CLASS_NAMES = {
    "air_conditioner": "Air conditioner",
    "fan": "Fan",
    "thermostat": "Thermostat",
    "washer": "Washer",
    "dryer": "Dryer",
    "dishwasher": "Dishwasher",
    "door": "Door",
    "sliding_door": "Sliding",
    "window": "Window",
    "access": "Access",
    "blind": "Blind",
    "awning": "Awning",
    "mailbox": "Mailbox",
    "refrigerator": "Refrigerator",
    "freezer": "Freezer",
    "aquarium": "Aquarium",
    "opening": "Opening",
    "sun_protection": "Sun protection",
    "screen": "Screen",
    "av_equipment": "AV equipment",
    "console": "Console",
    "computer": "Computer",
    "generic": "Generic appliance",
    "robot_vacuum": "Robot vacuum",
}

APPLIANCE_CLASS_TRANSLATIONS = {
    "ca": {
        "air_conditioner": "Aire condicionat",
        "fan": "Ventilador",
        "thermostat": "Termòstat",
        "washer": "Rentadora",
        "dryer": "Assecadora",
        "dishwasher": "Rentaplats",
        "door": "Porta",
        "sliding_door": "Corredís",
        "window": "Finestra",
        "access": "Accés",
        "blind": "Persiana",
        "awning": "Tendal",
        "mailbox": "Bústia",
        "refrigerator": "Nevera",
        "freezer": "Congelador",
        "opening": "Obertura",
        "sun_protection": "Protecció solar",
        "screen": "Pantalla",
        "av_equipment": "Equip AV",
        "console": "Consola",
        "computer": "Ordinador",
        "generic": "Electrodomèstic genèric",
        "robot_vacuum": "Aspirador robòtic",
    },
    "es": {
        "air_conditioner": "Aire acondicionado",
        "fan": "Ventilador",
        "thermostat": "Termostato",
        "washer": "Lavadora",
        "dryer": "Secadora",
        "dishwasher": "Lavavajillas",
        "door": "Puerta",
        "sliding_door": "Corredero",
        "window": "Ventana",
        "access": "Acceso",
        "blind": "Persiana",
        "awning": "Toldo",
        "mailbox": "Buzón",
        "refrigerator": "Frigorífico",
        "freezer": "Congelador",
        "opening": "Abertura",
        "sun_protection": "Protección solar",
        "screen": "Pantalla",
        "av_equipment": "Equipo AV",
        "console": "Consola",
        "computer": "Ordenador",
        "generic": "Electrodoméstico genérico",
        "robot_vacuum": "Aspirador robótico",
    },
}

APPLIANCE_CATEGORY_NAMES = {
    "thermostat": "Thermostat",
    "dryer": "Dryer",
    "mailbox": "Mailbox",
    "opening": "Opening",
    "access": "Access",
    "refrigerator": "Refrigerator",
    "sun_protection": "Sun protection",
    "washer": "Washer",
    "dishwasher": "Dishwasher",
    "aquarium": "Aquarium",
    "aquarium": "Aquari",
    "aquarium": "Acuario",
}

APPLIANCE_CATEGORY_TRANSLATIONS = {
    "ca": {
        "thermostat": "Termòstat",
        "dryer": "Assecadora",
        "mailbox": "Bústia",
        "opening": "Obertura",
        "access": "Accés",
        "refrigerator": "Nevera",
        "sun_protection": "Protecció solar",
        "washer": "Rentadora",
        "dishwasher": "Rentaplats",
    },
    "es": {
        "thermostat": "Termostato",
        "dryer": "Secadora",
        "mailbox": "Buzón",
        "opening": "Apertura",
        "access": "Acceso",
        "refrigerator": "Frigorífico",
        "sun_protection": "Protección solar",
        "washer": "Lavadora",
        "dishwasher": "Lavavajillas",
    },
}


def get_appliance_category_name(category: str, language: str = "en") -> str:
    """Return the category name in the configured Home Assistant language."""
    if category in APPLIANCE_GROUP_NAMES:
        return get_appliance_group_name(category, language)
    translations = APPLIANCE_CATEGORY_TRANSLATIONS.get(language.split("-")[0])
    if translations is None:
        return APPLIANCE_CATEGORY_NAMES[category]
    return translations.get(category, APPLIANCE_CATEGORY_NAMES[category])


def get_appliance_group_name(group: str, language: str = "en") -> str:
    """Return the broad appliance group name in the configured language."""
    translations = APPLIANCE_GROUP_TRANSLATIONS.get(language.split("-")[0])
    if translations is None:
        return APPLIANCE_GROUP_NAMES[group]
    return translations.get(group, APPLIANCE_GROUP_NAMES[group])


def get_appliance_class_name(appliance_class: str, language: str = "en") -> str:
    """Return a user-facing appliance class name in the configured language."""
    translations = APPLIANCE_CLASS_TRANSLATIONS.get(language.split("-")[0])
    if translations is None:
        return APPLIANCE_CLASS_NAMES[appliance_class]
    return translations.get(appliance_class, APPLIANCE_CLASS_NAMES[appliance_class])


# Keep the selector alphabetized by its Catalan display labels.
APPLIANCE_TYPES = (
    "access_contact",
    "air_conditioner_climate",
    "air_conditioner_contact",
    "air_conditioner_power",
    "aquarium_plug",
    "aquarium_power",
    "dryer",
    "mailbox_slot",
    "mailbox_motion",
    "console_switch",
    "laundry",
    "av_equipment_switch",
    "av_equipment_media_player",
    "refrigerator_switch",
    "refrigerator",
    "opening_cover",
    "opening",
    "computer_switch",
    "screen_switch",
    "screen_media_player",
    "sun_protection_cover",
    "sun_protection_contact",
    "washer",
    "dishwasher",
    "thermostat_climate",
    "fan_switch",
    "fan_power",
)


APPLIANCE_MODEL_NAMES = {
        "aquarium_plug": "Aquarium (smart plug)",
        "aquarium_power": "Aquarium (power sensor)",
    "laundry": "Laundry appliance",
    "thermostat_climate": "Thermostat (climate entity)",
    "fan_power": "Fan (power sensor)",
    "fan_switch": "Fan (smart switch)",
    "fan_entity": "Fan (fan entity)",
    "generic_switch": "Generic appliance (smart switch)",
    "robot_vacuum_vacuum": "Robot vacuum (vacuum entity)",
    "washer": "Washer",
    "dishwasher": "Dishwasher",
    "dryer": "Dryer",
    "air_conditioner_contact": "Air conditioner (contact/opening sensor)",
    "air_conditioner_climate": "Air conditioner (climate entity)",
    "air_conditioner_power": "Air conditioner (power sensor)",
    "refrigerator": "Refrigerator (power sensor)",
    "refrigerator_switch": "Refrigerator (smart switch)",
    "mailbox_motion": "Mailbox (interior motion sensor)",
    "mailbox_slot": "Mailbox (mail-slot contact/opening sensor)",
    "access_contact": "Access (contact sensor)",
    "opening": "Opening (contact sensor)",
    "opening_cover": "Opening (cover)",
    "sun_protection_contact": "Sun protection (contact sensor)",
    "sun_protection_cover": "Sun protection (cover)",
    "screen_switch": "Screen (switch)",
    "screen_media_player": "Screen (media player)",
    "av_equipment_switch": "AV equipment (switch)",
    "av_equipment_media_player": "AV equipment (media player)",
    "console_switch": "Console (switch)",
    "computer_switch": "Computer (switch)",
}

APPLIANCE_DETECTION_MODEL_NAMES = {
    "power": {
        "en": "Power sensor",
        "ca": "Sensor de potència",
        "es": "Sensor de potencia",
    },
    "climate": {
        "en": "Climate entity",
        "ca": "Entitat climate",
        "es": "Entidad climate",
    },
    "running_sensor": {
        "en": "Contact/opening sensor",
        "ca": "Sensor de contacte/obertura",
        "es": "Sensor de contacto/apertura",
    },
    "smart_plug": {
        "en": "Smart switch",
        "ca": "Interruptor intel·ligent",
        "es": "Interruptor inteligente",
    },
    "cover": {
        "en": "Cover entity",
        "ca": "Entitat cover",
        "es": "Entidad cover",
    },
    "mail_motion": {
        "en": "Interior motion sensor",
        "ca": "Sensor de moviment interior",
        "es": "Sensor de movimiento interior",
    },
    "mail_slot": {
        "en": "Mail-slot contact/opening sensor",
        "ca": "Sensor de contacte/obertura de portella",
        "es": "Sensor de contacto/apertura de trampilla",
    },
    "media_player": {
        "en": "Media player",
        "ca": "Entitat media_player",
        "es": "Entidad media_player",
    },
    "fan": {
        "en": "Fan entity",
        "ca": "Entitat fan",
        "es": "Entidad fan",
    },
    "vacuum": {
        "en": "Vacuum entity",
        "ca": "Entitat vacuum",
        "es": "Entidad vacuum",
    },
}

APPLIANCE_UNCLASSIFIED_MODEL_NAMES = {
    "laundry": {
        "en": "Laundry device",
        "ca": "Dispositiu de rentat i assecat",
        "es": "Dispositivo de lavado y secado",
    }
}

LEGACY_APPLIANCE_CLASSES = {
    "thermostat_climate": "thermostat",
    "washer": "washer",
    "dishwasher": "dishwasher",
    "dryer": "dryer",
    "air_conditioner_contact": "air_conditioner",
    "air_conditioner_climate": "air_conditioner",
    "air_conditioner_power": "air_conditioner",
    "fan_power": "fan",
    "fan_switch": "fan",
    "fan_entity": "fan",
    "generic_switch": "generic",
    "robot_vacuum_vacuum": "robot_vacuum",
    "refrigerator": "refrigerator",
    "refrigerator_switch": "refrigerator",
        "aquarium_plug": "aquarium",
        "aquarium_power": "aquarium",
    "mailbox_motion": "mailbox",
    "mailbox_slot": "mailbox",
    "access_contact": "access",
    "opening": "opening",
    "opening_cover": "door",
    "sun_protection_contact": "sun_protection",
    "sun_protection_cover": "sun_protection",
}

LEGACY_APPLIANCE_GROUPS = {
    "laundry": "large_appliances",
    "thermostat_climate": "climate",
    "air_conditioner_contact": "climate",
    "air_conditioner_climate": "climate",
    "air_conditioner_power": "climate",
    "fan_power": "climate",
    "fan_switch": "climate",
    "fan_entity": "climate",
    "generic_switch": "small_appliances",
    "robot_vacuum_vacuum": "small_appliances",
    "washer": "large_appliances",
    "dishwasher": "large_appliances",
    "dryer": "large_appliances",
    "opening": "openings",
    "access_contact": "openings",
    "opening_cover": "openings",
    "sun_protection_contact": "sun_protection",
    "sun_protection_cover": "sun_protection",
    "mailbox_motion": "deliveries",
    "mailbox_slot": "deliveries",
    "refrigerator": "large_appliances",
    "refrigerator_switch": "large_appliances",
    "aquarium_plug": "animal_care",
    "aquarium_power": "animal_care",
    "screen_switch": "electronics",
    "screen_media_player": "electronics",
    "av_equipment_switch": "electronics",
    "av_equipment_media_player": "electronics",
    "console_switch": "electronics",
    "computer_switch": "electronics",
}


def get_appliance_model(
    appliance_type: str | None,
    appliance_class: str | None = None,
    language: str = "en",
) -> str | None:
    """Return the localized display model name for an appliance profile."""
    if appliance_type is None:
        return None

    profile = APPLIANCE_PROFILES.get(appliance_type)
    appliance_class = appliance_class or get_legacy_appliance_class(appliance_type)
    group = get_appliance_group_for_profile(appliance_type, appliance_class)
    if appliance_class is None and appliance_type in APPLIANCE_UNCLASSIFIED_MODEL_NAMES:
        group = "large_appliances"
    if profile is not None and profile.detection_sources and group is not None:
        detection_names = APPLIANCE_DETECTION_MODEL_NAMES.get(
            profile.detection_sources[0]
        )
        if detection_names is not None:
            language_code = language.split("-")[0]
            detection_name = detection_names.get(language_code, detection_names["en"])
            group_name = get_appliance_group_name(group, language)
            if appliance_class == "opening":
                class_name = {
                    "ca": "Desconegut",
                    "es": "Desconocido",
                }.get(language_code, "Unknown")
            elif appliance_class in APPLIANCE_CLASS_NAMES:
                class_name = get_appliance_class_name(appliance_class, language)
            else:
                class_names = APPLIANCE_UNCLASSIFIED_MODEL_NAMES.get(appliance_type)
                if class_names is None:
                    class_name = None
                else:
                    class_name = class_names.get(language_code, class_names["en"])
            if class_name is not None:
                return f"{group_name} · {class_name} · {detection_name}"
    if appliance_class in APPLIANCE_CLASS_NAMES:
        return get_appliance_class_name(appliance_class, language)
    return APPLIANCE_MODEL_NAMES.get(appliance_type)


def get_legacy_appliance_class(appliance_type: str | None) -> str | None:
    """Return the unambiguous appliance class for a legacy profile key."""
    if appliance_type is None:
        return None
    return LEGACY_APPLIANCE_CLASSES.get(appliance_type)


def get_appliance_group_for_profile(
    appliance_type: str | None, appliance_class: str | None = None
) -> str | None:
    """Return the current group for a profile and optional class."""
    if appliance_type is None:
        return None
    if appliance_class is not None:
        for group, classes in APPLIANCE_GROUPS.items():
            if appliance_type in classes.get(appliance_class, {}).values():
                return group
    return LEGACY_APPLIANCE_GROUPS.get(appliance_type)


def get_group_action_groups(appliance_group: str) -> tuple[str, ...]:
    """Return all actions supported by profiles below a group, in order."""
    profiles = [
        APPLIANCE_PROFILES[profile_name]
        for classes in APPLIANCE_GROUPS[appliance_group].values()
        for profile_name in classes.values()
    ]
    if not profiles:
        return ()

    action_groups = dict.fromkeys(
        action_group
        for profile in profiles
        for action_group in profile.action_groups
    )
    return tuple(action_groups)


def get_canonical_appliance_type(appliance_type: str) -> str:
    """Map a legacy profile key to its current shared profile key."""
    if appliance_type in {"washer", "dryer", "dishwasher"}:
        return "laundry"
    return appliance_type


def get_appliance_category(appliance_type: str | None) -> str | None:
    """Return the general device category containing a concrete profile."""
    if appliance_type is None:
        return None
    return next(
        (
            category
            for category, modes in APPLIANCE_CATEGORIES.items()
            if appliance_type in modes.values()
        ),
        None,
    )


def get_appliance_profile(appliance_type: str) -> ApplianceTypeProfile:
    """Return the capability profile for an appliance type."""
    return APPLIANCE_PROFILES[appliance_type]