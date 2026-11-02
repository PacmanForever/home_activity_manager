"""Capabilities and detection sources for supported appliance types."""

from dataclasses import dataclass, replace

from .const import (
    CONF_DOOR_ENTITY,
    CONF_ENERGY_ENTITY,
    CONF_CLIMATE_ENTITY,
    CONF_COVER_ENTITY,
    CONF_LOCK_ENTITY,
    CONF_MAIL_MOTION_ENTITY,
    CONF_MAIL_SLOT_ENTITY,
    CONF_PLUG_ENTITY,
    CONF_POWER_ENTITY,
    CONF_RUNNING_ENTITY,
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
            if item.domain != "climate"
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
            ),
        ),
        parameter_groups=("plug_off_alarm",),
        action_groups=("cycle_start", "cycle_finish", "plug_off_alarm"),
        output_entities=("last_cycle_duration", "running", "plug"),
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
            ),
        ),
        parameter_groups=("power_cycle", "max_runtime", "pending_unload", "plug_off_alarm"),
        action_groups=("cycle_start", "cycle_finish", "max_runtime", "pending_unload", "emptied", "plug_off_alarm"),
        output_entities=(
            "power", "total_energy", "last_cycle_duration", "estimated_remaining",
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
            ),
        ),
        parameter_groups=("power_cycle", "max_runtime", "pending_unload", "plug_off_alarm"),
        action_groups=("cycle_start", "cycle_finish", "max_runtime", "pending_unload", "emptied", "plug_off_alarm"),
        output_entities=(
            "power", "total_energy", "last_cycle_duration", "estimated_remaining",
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
            ),
        ),
        parameter_groups=("power_cycle", "max_runtime", "pending_unload", "plug_off_alarm"),
        action_groups=("cycle_start", "cycle_finish", "max_runtime", "pending_unload", "emptied", "plug_off_alarm"),
        output_entities=(
            "power", "total_energy", "last_cycle_duration", "estimated_remaining",
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
            ),
        ),
        parameter_groups=("plug_off_alarm",),
        action_groups=("cycle_start", "cycle_finish", "plug_off_alarm"),
        output_entities=("last_cycle_duration", "running", "plug"),
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
            ),
        ),
        parameter_groups=("power_cycle", "plug_off_alarm"),
        action_groups=("cycle_start", "cycle_finish", "plug_off_alarm"),
        output_entities=("power", "total_energy", "last_cycle_duration", "running", "plug"),
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
        output_entities=("power", "total_energy", "last_cycle_duration", "running", "door", "plug"),
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
                ),
            ),
            parameter_groups=("door_alarm", "alarm_repeats"),
            action_groups=(
                "cycle_start",
                "cycle_finish",
                "door_open_alarm",
            ),
            output_entities=("last_cycle_duration", "running", "door", "plug"),
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
        ),
        parameter_groups=(),
        action_groups=("cycle_start", "cycle_finish"),
        output_entities=("last_cycle_duration",),
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
    "dryer": {"power": "dryer"},
    "mailbox": {"mail_slot": "mailbox_slot", "mail_motion": "mailbox_motion"},
    "opening": {"running_sensor": "opening"},
    "refrigerator": {"smart_plug": "refrigerator_switch", "power": "refrigerator"},
    "sun_protection": {
        "running_sensor": "sun_protection_contact",
        "cover": "sun_protection_cover",
    },
    "washer": {"power": "washer"},
    "dishwasher": {"power": "dishwasher"},
}

APPLIANCE_GROUPS = {
    "climate": {
        "air_conditioner": {
            "running_sensor": "air_conditioner_contact",
            "power": "air_conditioner_power",
        },
        "thermostat": {"climate": "thermostat_climate"},
    },
    "laundry": {
        "washer": {"power": "laundry"},
        "dryer": {"power": "laundry"},
        "dishwasher": {"power": "laundry"},
    },
    "openings": {"door": {"running_sensor": "opening"}, "window": {"running_sensor": "opening"}},
    "sun_protection": {
        "blind": {
            "running_sensor": "sun_protection_contact",
            "cover": "sun_protection_cover",
        },
        "awning": {
            "running_sensor": "sun_protection_contact",
            "cover": "sun_protection_cover",
        },
    },
    "deliveries": {
        "mailbox": {"mail_slot": "mailbox_slot", "mail_motion": "mailbox_motion"}
    },
    "refrigeration": {
        "refrigerator": {
            "smart_plug": "refrigerator_switch",
            "power": "refrigerator",
        },
        "freezer": {"smart_plug": "refrigerator_switch", "power": "refrigerator"},
    },
}

APPLIANCE_PROFILES["laundry"] = replace(
    APPLIANCE_PROFILES["washer"],
    sensor_inputs=tuple(
        replace(item, form_key=item.form_key.replace("washer_", "laundry_"))
        for item in APPLIANCE_PROFILES["washer"].sensor_inputs
    ),
)

APPLIANCE_GROUP_NAMES = {
    "climate": "Climate control",
    "laundry": "Laundry and drying",
    "openings": "Openings",
    "sun_protection": "Sun protection",
    "deliveries": "Deliveries",
    "refrigeration": "Refrigeration",
}

APPLIANCE_GROUP_TRANSLATIONS = {
    "ca": {
        "climate": "Climatització",
        "laundry": "Rentat i assecat",
        "openings": "Tancaments",
        "sun_protection": "Protecció solar",
        "deliveries": "Lliuraments",
        "refrigeration": "Refrigeració",
    },
    "es": {
        "climate": "Climatización",
        "laundry": "Lavado y secado",
        "openings": "Aberturas",
        "sun_protection": "Protección solar",
        "deliveries": "Entregas",
        "refrigeration": "Refrigeración",
    },
}

APPLIANCE_CLASS_NAMES = {
    "air_conditioner": "Air conditioner",
    "thermostat": "Thermostat",
    "washer": "Washer",
    "dryer": "Dryer",
    "dishwasher": "Dishwasher",
    "door": "Door",
    "window": "Window",
    "blind": "Blind",
    "awning": "Awning",
    "mailbox": "Mailbox",
    "refrigerator": "Refrigerator",
    "freezer": "Freezer",
    "opening": "Opening",
    "sun_protection": "Sun protection",
}

APPLIANCE_CLASS_TRANSLATIONS = {
    "ca": {
        "air_conditioner": "Aire condicionat",
        "thermostat": "Termòstat",
        "washer": "Rentadora",
        "dryer": "Assecadora",
        "dishwasher": "Rentaplats",
        "door": "Porta",
        "window": "Finestra",
        "blind": "Persiana",
        "awning": "Tendal",
        "mailbox": "Bústia",
        "refrigerator": "Nevera",
        "freezer": "Congelador",
        "opening": "Obertura",
        "sun_protection": "Protecció solar",
    },
    "es": {
        "air_conditioner": "Aire acondicionado",
        "thermostat": "Termostato",
        "washer": "Lavadora",
        "dryer": "Secadora",
        "dishwasher": "Lavavajillas",
        "door": "Puerta",
        "window": "Ventana",
        "blind": "Persiana",
        "awning": "Toldo",
        "mailbox": "Buzón",
        "refrigerator": "Frigorífico",
        "freezer": "Congelador",
        "opening": "Abertura",
        "sun_protection": "Protección solar",
    },
}

APPLIANCE_CATEGORY_NAMES = {
    "thermostat": "Thermostat",
    "dryer": "Dryer",
    "mailbox": "Mailbox",
    "opening": "Opening",
    "refrigerator": "Refrigerator",
    "sun_protection": "Sun protection",
    "washer": "Washer",
    "dishwasher": "Dishwasher",
}

APPLIANCE_CATEGORY_TRANSLATIONS = {
    "ca": {
        "thermostat": "Termòstat",
        "dryer": "Assecadora",
        "mailbox": "Bústia",
        "opening": "Obertura",
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
        "refrigerator": "Frigorífico",
        "sun_protection": "Protección solar",
        "washer": "Lavadora",
        "dishwasher": "Lavavajillas",
    },
}


def get_appliance_category_name(category: str, language: str = "en") -> str:
    """Return the category name in the configured Home Assistant language."""
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
    "air_conditioner_contact",
    "air_conditioner_power",
    "dryer",
    "mailbox_slot",
    "mailbox_motion",
    "laundry",
    "refrigerator_switch",
    "refrigerator",
    "opening",
    "sun_protection_cover",
    "sun_protection_contact",
    "washer",
    "dishwasher",
    "thermostat_climate",
)


APPLIANCE_MODEL_NAMES = {
    "laundry": "Laundry appliance",
    "thermostat_climate": "Thermostat (climate entity)",
    "washer": "Washer",
    "dishwasher": "Dishwasher",
    "dryer": "Dryer",
    "air_conditioner_contact": "Air conditioner (contact/opening sensor)",
    "air_conditioner_power": "Air conditioner (power sensor)",
    "refrigerator": "Refrigerator (power sensor)",
    "refrigerator_switch": "Refrigerator (smart switch)",
    "mailbox_motion": "Mailbox (interior motion sensor)",
    "mailbox_slot": "Mailbox (mail-slot contact/opening sensor)",
    "opening": "Opening (contact sensor)",
    "sun_protection_contact": "Sun protection (contact sensor)",
    "sun_protection_cover": "Sun protection (cover)",
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
    "air_conditioner_power": "air_conditioner",
    "refrigerator": "refrigerator",
    "refrigerator_switch": "refrigerator",
    "mailbox_motion": "mailbox",
    "mailbox_slot": "mailbox",
    "opening": "opening",
    "sun_protection_contact": "sun_protection",
    "sun_protection_cover": "sun_protection",
}

LEGACY_APPLIANCE_GROUPS = {
    "thermostat_climate": "climate",
    "air_conditioner_contact": "climate",
    "air_conditioner_power": "climate",
    "washer": "laundry",
    "dishwasher": "laundry",
    "dryer": "laundry",
    "opening": "openings",
    "sun_protection_contact": "sun_protection",
    "sun_protection_cover": "sun_protection",
    "mailbox_motion": "deliveries",
    "mailbox_slot": "deliveries",
    "refrigerator": "refrigeration",
    "refrigerator_switch": "refrigeration",
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
        group = "laundry"
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