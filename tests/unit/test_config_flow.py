"""Unit tests for configuration schemas and translation coverage."""

import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import pytest
import voluptuous as vol

from custom_components.home_activity_manager.config_flow import (
    ApplianceCycleMonitorConfigFlow,
    ApplianceCycleMonitorOptionsFlow,
    _action_schema,
    _identity_schema,
    _entry_data,
    _entry_options,
    _group_action_schema,
    _normalize_sensor_values,
    _options_identity_schema,
    _sensor_form_values,
    _sensor_schema,
    _threshold_schema,
    _clear_pending_settings,
    _validate_alarm_settings,
    _validate_duration_limits,
    _validate_plug_off_alarm_settings,
    _validate_pending,
    _validate_sensor_values,
    _validate_thresholds,
)
from custom_components.home_activity_manager.appliance_types import (
    APPLIANCE_CLASS_NAMES,
    APPLIANCE_CATEGORIES,
    APPLIANCE_GROUP_NAMES,
    APPLIANCE_GROUP_TRANSLATIONS,
    APPLIANCE_GROUPS,
    APPLIANCE_MODEL_NAMES,
    APPLIANCE_PROFILES,
    APPLIANCE_TYPES,
    get_appliance_class_name,
    get_appliance_group_for_profile,
    get_appliance_model,
    get_group_action_groups,
    get_legacy_appliance_class,
    get_appliance_profile,
)
from custom_components.home_activity_manager.const import (
    CONF_ALARM_REPEAT_COUNT,
    CONF_ALARM_REPEAT_INTERVAL_SECONDS,
    CONF_APPLIANCE_CLASS,
    CONF_APPLIANCE_GROUP,
    CONF_APPLIANCE_TYPE,
    CONF_COMPRESSOR_INACTIVE_ACTIONS,
    CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS,
    CONF_DOOR_ENTITY,
    CONF_DOOR_OPEN_ACTIONS,
    CONF_DOOR_OPEN_DELAY_SECONDS,
    CONF_EMPTIED_ACTIONS,
    CONF_ENERGY_ENTITY,
    CONF_FINISH_ACTIONS,
    CONF_GROUP_ACTIONS,
    CONF_LOCK_ENTITY,
    CONF_LOCK_LOCKED_ACTIONS,
    CONF_LOCK_UNLOCKED_ACTIONS,
    CONF_MAIL_ARRIVAL_ACTIONS,
    CONF_MAIL_MOTION_ENTITY,
    CONF_MAIL_SLOT_ENTITY,
    CONF_MAX_RUNTIME_ACTIONS,
    CONF_MAX_RUNTIME_SECONDS,
    CONF_PENDING_ACTIONS,
    CONF_PENDING_DELAY_SECONDS,
    CONF_PENDING_INTERVAL_SECONDS,
    CONF_PENDING_REPEATS,
    CONF_PLUG_ENTITY,
    CONF_PLUG_OFF_ACTIONS,
    CONF_PLUG_OFF_REPEAT_COUNT,
    CONF_PLUG_OFF_REPEAT_INTERVAL_SECONDS,
    CONF_POWER_ENTITY,
    CONF_RUNNING_ENTITY,
    CONF_SHUTTER_CONTACT_ENTITY,
    CONF_SHUTTER_COVER_ENTITY,
    CONF_SHUTTER_OPEN_ACTIONS,
    CONF_SHUTTER_CLOSE_ACTIONS,
    CONF_START_ACTIONS,
    DEFAULT_PENDING_DELAY_SECONDS,
    DEFAULT_PENDING_INTERVAL_SECONDS,
    DEFAULT_PENDING_REPEATS,
)


class ConfigFlowSchemaTests(unittest.TestCase):
    def test_groups_map_classes_to_compatible_profiles(self) -> None:
        self.assertEqual(
            set(APPLIANCE_GROUPS),
            {
                "climate",
                "large_appliances",
                "animal_care",
                "openings",
                "sun_protection",
                "deliveries",
            },
        )
        mapped_classes = {
            appliance_class
            for classes in APPLIANCE_GROUPS.values()
            for appliance_class in classes
        }
        self.assertTrue(mapped_classes <= set(APPLIANCE_CLASS_NAMES))
        self.assertEqual(
            set(APPLIANCE_CLASS_NAMES) - mapped_classes,
            {"blind", "opening", "sun_protection"},
        )
        for classes in APPLIANCE_GROUPS.values():
            for modes in classes.values():
                for mode, profile_name in modes.items():
                    self.assertIn(profile_name, APPLIANCE_PROFILES)
                    self.assertEqual(
                        APPLIANCE_PROFILES[profile_name].detection_sources, (mode,)
                    )

    def test_group_actions_include_the_union_of_descendant_profiles(self) -> None:
        self.assertEqual(
            get_group_action_groups("climate"),
            ("cycle_start", "cycle_finish", "plug_off_alarm"),
        )
        self.assertEqual(
            get_group_action_groups("large_appliances"),
            (
                "cycle_start",
                "cycle_finish",
                "max_runtime",
                "pending_unload",
                "emptied",
                "plug_off_alarm",
                "door_open_alarm",
            ),
        )
        self.assertEqual(get_group_action_groups("animal_care"), ("cycle_start", "cycle_finish"))
        self.assertEqual(
            get_group_action_groups("deliveries"),
            ("cycle_start", "cycle_finish", "pending_unload", "emptied"),
        )

    def test_group_actions_include_hooks_from_heterogeneous_profiles(self) -> None:
        with patch.dict(
            APPLIANCE_GROUPS,
            {
                "heterogeneous": {
                    "opening": {"contact": "opening"},
                    "washer": {"power": "washer"},
                }
            },
        ):
            self.assertEqual(
                get_group_action_groups("heterogeneous"),
                (
                    "cycle_start",
                    "cycle_finish",
                    "lock_locked",
                    "lock_unlocked",
                    "shutter_open",
                    "shutter_close",
                    "max_runtime",
                    "pending_unload",
                    "emptied",
                    "plug_off_alarm",
                ),
            )

    def test_group_action_schema_offers_all_group_hooks(self) -> None:
        schema = _group_action_schema("climate", {})
        fields = {marker.schema for marker in schema.schema}

        self.assertEqual(
            fields,
            {CONF_START_ACTIONS, CONF_FINISH_ACTIONS, CONF_PLUG_OFF_ACTIONS},
        )
        with self.assertRaises(vol.Invalid):
            schema({CONF_MAX_RUNTIME_ACTIONS: []})
        self.assertEqual(CONF_GROUP_ACTIONS, "group_actions")

    def test_categories_map_each_profile_to_one_compatible_mode(self) -> None:
        mapped = [
            profile
            for modes in APPLIANCE_CATEGORIES.values()
            for profile in modes.values()
        ]
        self.assertEqual(len(mapped), len(set(mapped)))
        self.assertEqual(
            set(mapped),
            set(APPLIANCE_PROFILES) - {"laundry", "aquarium_plug", "aquarium_power"},
        )
        for modes in APPLIANCE_CATEGORIES.values():
            for mode, profile in modes.items():
                self.assertEqual(APPLIANCE_PROFILES[profile].detection_sources, (mode,))

    def test_device_models_cover_and_distinguish_all_profiles(self) -> None:
        self.assertEqual(set(APPLIANCE_MODEL_NAMES), set(APPLIANCE_PROFILES))
        self.assertEqual(
            get_appliance_model("air_conditioner_contact"),
            "Climate control · Air conditioner · Contact/opening sensor",
        )
        self.assertEqual(
            get_appliance_model("air_conditioner_contact", "air_conditioner", "ca"),
            "Climatització · Aire condicionat · Sensor de contacte/obertura",
        )
        self.assertEqual(
            get_appliance_model("air_conditioner_contact", "air_conditioner", "es"),
            "Climatización · Aire acondicionado · Sensor de contacto/apertura",
        )
        self.assertEqual(
            get_appliance_model("opening", "opening", "ca"),
            "Tancaments · Desconegut · Sensor de contacte/obertura",
        )
        self.assertEqual(
            get_appliance_model("opening", "opening", "en"),
            "Openings · Unknown · Contact/opening sensor",
        )
        self.assertEqual(
            get_appliance_model("opening", "opening", "es"),
            "Aberturas · Desconocido · Sensor de contacto/apertura",
        )
        self.assertEqual(
            get_appliance_model("laundry", language="ca"),
            "Grans electrodomèstics · Dispositiu de rentat i assecat · Sensor de potència",
        )
        self.assertEqual(
            get_appliance_model("air_conditioner_power"),
            "Climate control · Air conditioner · Power sensor",
        )
        self.assertEqual(
            get_appliance_model("air_conditioner_power", "air_conditioner"),
            "Climate control · Air conditioner · Power sensor",
        )
        self.assertEqual(
            get_appliance_model("air_conditioner_power", "air_conditioner", "ca"),
            "Climatització · Aire condicionat · Sensor de potència",
        )
        self.assertEqual(
            get_appliance_model("air_conditioner_power", "air_conditioner", "es"),
            "Climatización · Aire acondicionado · Sensor de potencia",
        )
        self.assertEqual(
            get_appliance_model("mailbox_slot"),
            "Deliveries · Mailbox · Mail-slot contact/opening sensor",
        )

    def test_device_models_include_details_for_all_grouped_profiles(self) -> None:
        for group, classes in APPLIANCE_GROUPS.items():
            for appliance_class, modes in classes.items():
                for appliance_type in modes.values():
                    for language in ("ca", "en", "es"):
                        with self.subTest(
                            group=group,
                            appliance_class=appliance_class,
                            appliance_type=appliance_type,
                            language=language,
                        ):
                            model = get_appliance_model(
                                appliance_type, appliance_class, language
                            )
                            self.assertIsNotNone(model)
                            self.assertEqual(model.count(" · "), 2)

    def test_appliance_class_names_follow_configured_language(self) -> None:
        self.assertEqual(get_appliance_class_name("washer", "ca"), "Rentadora")
        self.assertEqual(get_appliance_class_name("door", "es"), "Puerta")
        self.assertEqual(get_appliance_class_name("access", "ca"), "Accés")
        self.assertEqual(get_appliance_class_name("access", "es"), "Acceso")
        self.assertEqual(get_appliance_class_name("washer"), "Washer")
        self.assertTrue(APPLIANCE_PROFILES["washer"].supports_smart_plug)
        self.assertFalse(APPLIANCE_PROFILES["opening"].supports_smart_plug)

    def test_access_contact_profile_has_no_associated_shutter(self) -> None:
        profile = get_appliance_profile("access_contact")
        input_keys = {item.config_key for item in profile.sensor_inputs}
        action_keys = set(profile.action_groups)

        self.assertIn(CONF_RUNNING_ENTITY, input_keys)
        self.assertIn(CONF_LOCK_ENTITY, input_keys)
        self.assertNotIn(CONF_SHUTTER_CONTACT_ENTITY, input_keys)
        self.assertNotIn(CONF_SHUTTER_COVER_ENTITY, input_keys)
        self.assertNotIn("shutter_open", action_keys)
        self.assertNotIn("shutter_close", action_keys)

    def test_access_selector_label_includes_examples_in_all_languages(self) -> None:
        root = Path(__file__).parents[2] / "custom_components" / "home_activity_manager"
        expected = {
            "strings.json": "Access (garage, shop, warehouse, etc.)",
            "en.json": "Access (garage, shop, warehouse, etc.)",
            "ca.json": "Accés (garatge, botiga, magatzem, etc.)",
            "es.json": "Acceso (garaje, tienda, almacén, etc.)",
        }
        paths = {
            "strings.json": root / "strings.json",
            "en.json": root / "translations" / "en.json",
            "ca.json": root / "translations" / "ca.json",
            "es.json": root / "translations" / "es.json",
        }
        for name, path in paths.items():
            translation = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(
                translation["selector"]["appliance_class"]["options"]["access"],
                expected[name],
            )

    def test_group_labels_are_plural_in_all_languages(self) -> None:
        root = Path(__file__).parents[2] / "custom_components" / "home_activity_manager"
        expected = {
            "en": {"openings": "Openings", "deliveries": "Deliveries"},
            "ca": {"openings": "Tancaments", "deliveries": "Lliuraments"},
            "es": {"openings": "Aberturas", "deliveries": "Entregas"},
        }
        self.assertEqual(
            {key: APPLIANCE_GROUP_NAMES[key] for key in expected["en"]},
            expected["en"],
        )
        for language in ("ca", "es"):
            self.assertEqual(
                {key: APPLIANCE_GROUP_TRANSLATIONS[language][key] for key in expected[language]},
                expected[language],
            )

        for filename, language in (
            ("strings.json", "en"),
            ("en.json", "en"),
            ("ca.json", "ca"),
            ("es.json", "es"),
        ):
            path = (
                root / filename
                if filename == "strings.json"
                else root / "translations" / filename
            )
            translation = json.loads(path.read_text(encoding="utf-8"))
            options = translation["selector"]["appliance_group"]["options"]
            self.assertEqual(
                {key: options[key] for key in expected[language]},
                expected[language],
            )

    def test_translation_strings_do_not_contain_jinja_delimiters(self) -> None:
        root = Path(__file__).parents[2] / "custom_components" / "home_activity_manager"
        paths = (
            root / "strings.json",
            root / "translations" / "en.json",
            root / "translations" / "es.json",
            root / "translations" / "ca.json",
        )

        def assert_no_jinja(value, path: str) -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    assert_no_jinja(child, f"{path}.{key}")
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    assert_no_jinja(child, f"{path}[{index}]")
            elif isinstance(value, str):
                self.assertNotIn("{{", value, path)
                self.assertNotIn("}}", value, path)

        for path in paths:
            assert_no_jinja(json.loads(path.read_text(encoding="utf-8")), str(path))

    def test_legacy_blind_class_remains_editable_but_is_not_a_new_choice(self) -> None:
        self.assertNotIn("blind", APPLIANCE_GROUPS["sun_protection"])
        self.assertEqual(
            get_appliance_group_for_profile("sun_protection_contact", "blind"),
            "sun_protection",
        )
        schema = _options_identity_schema(
            {
                CONF_APPLIANCE_TYPE: "sun_protection_contact",
                CONF_APPLIANCE_CLASS: "blind",
            },
            "sun_protection",
        )
        class_marker = next(
            marker
            for marker in schema.schema
            if marker.schema == CONF_APPLIANCE_CLASS
        )
        self.assertEqual(class_marker.default(), "blind")

    def test_unknown_profile_metadata_returns_none(self) -> None:
        self.assertIsNone(get_appliance_model("unknown_profile"))
        self.assertIsNone(get_legacy_appliance_class("unknown_profile"))
        self.assertIsNone(get_appliance_group_for_profile("unknown_profile"))
        self.assertIsNone(get_appliance_model(None))
        self.assertIsNone(get_legacy_appliance_class(None))
        self.assertIsNone(get_appliance_group_for_profile(None))
        self.assertEqual(
            get_appliance_model("thermostat_climate", "unknown_class"),
            "Thermostat (climate entity)",
        )
        self.assertEqual(
            get_appliance_group_for_profile("laundry", "washer"),
            "large_appliances",
        )

    def test_identity_schema_requires_name_and_group(self) -> None:
        schema = _identity_schema({})
        with self.assertRaises(vol.Invalid):
            schema({"name": "Washer"})

        values = schema(
            {"name": "Washer", CONF_APPLIANCE_GROUP: "large_appliances"}
        )

        self.assertEqual(values[CONF_APPLIANCE_GROUP], "large_appliances")
        self.assertNotIn(CONF_POWER_ENTITY, values)

        catalan_schema = _identity_schema({}, language="ca")
        group_selector = next(
            value
            for marker, value in catalan_schema.schema.items()
            if marker.schema == CONF_APPLIANCE_GROUP
        )
        self.assertEqual(
            group_selector.config["options"],
            [
                "climate",
                "animal_care",
                "large_appliances",
                "deliveries",
                "sun_protection",
                "openings",
            ],
        )

    def test_sensor_selection_fields_prefill_during_edit(self) -> None:
        values = {
            CONF_POWER_ENTITY: "sensor.dishwasher_power",
            "door_entity": "binary_sensor.dishwasher_door",
            "plug_entity": "switch.dishwasher_plug",
        }
        profile = get_appliance_profile("dishwasher")
        schema = _sensor_schema(_sensor_form_values(values, profile), profile)

        form_values = {
            marker.schema: marker.default()
            for marker in schema.schema
            if marker.default is not vol.UNDEFINED
        }
        self.assertEqual(
            form_values["dishwasher_power_entity"], "sensor.dishwasher_power"
        )
        self.assertEqual(
            form_values["dishwasher_door_entity"], "binary_sensor.dishwasher_door"
        )
        self.assertEqual(form_values["dishwasher_plug_entity"], "switch.dishwasher_plug")
        normalized = _normalize_sensor_values(form_values, profile)
        self.assertEqual(
            normalized["door_entity"],
            "binary_sensor.dishwasher_door",
        )
        self.assertEqual(normalized[CONF_POWER_ENTITY], "sensor.dishwasher_power")

    def test_omitted_optional_sensors_are_cleared_for_every_profile(self) -> None:
        for appliance_type, profile in APPLIANCE_PROFILES.items():
            with self.subTest(appliance_type=appliance_type):
                form_values = {
                    sensor_input.form_key: "sensor.required"
                    for sensor_input in profile.sensor_inputs
                    if sensor_input.required
                }
                existing_values = {
                    sensor_input.config_key: "sensor.previous"
                    for sensor_input in profile.sensor_inputs
                    if not sensor_input.required
                }
                normalized = _normalize_sensor_values(
                    form_values,
                    profile,
                    clear_missing_optional=True,
                    existing_values=existing_values,
                )
                untouched = _normalize_sensor_values(
                    form_values, profile, clear_missing_optional=True
                )
                entry_data = _entry_data(
                    {CONF_APPLIANCE_TYPE: appliance_type, **normalized}
                )

                for sensor_input in profile.sensor_inputs:
                    if sensor_input.required:
                        continue
                    self.assertIsNone(normalized[sensor_input.config_key])
                    self.assertIsNone(entry_data[sensor_input.config_key])
                    self.assertNotIn(sensor_input.config_key, untouched)

    def test_opening_shutter_sources_are_optional_but_mutually_exclusive(self) -> None:
        profile = get_appliance_profile("opening")
        cases = (
            ({}, True),
            ({CONF_SHUTTER_CONTACT_ENTITY: "binary_sensor.shutter"}, True),
            ({CONF_SHUTTER_COVER_ENTITY: "cover.shutter"}, True),
            (
                {
                    CONF_SHUTTER_CONTACT_ENTITY: "binary_sensor.shutter",
                    CONF_SHUTTER_COVER_ENTITY: "cover.shutter",
                },
                False,
            ),
            (
                {
                    CONF_RUNNING_ENTITY: "binary_sensor.opening",
                    CONF_SHUTTER_CONTACT_ENTITY: "binary_sensor.opening",
                },
                False,
            ),
        )
        for values, expected in cases:
            with self.subTest(values=values):
                self.assertEqual(_validate_sensor_values(values, profile), expected)

    def test_opening_local_actions_follow_configured_capabilities(self) -> None:
        profile = get_appliance_profile("opening")
        action_keys = lambda values: {
            marker.schema for marker in _action_schema(values, profile).schema
        }
        self.assertNotIn(CONF_LOCK_LOCKED_ACTIONS, action_keys({}))
        self.assertNotIn(CONF_SHUTTER_OPEN_ACTIONS, action_keys({}))
        self.assertIn(
            CONF_LOCK_LOCKED_ACTIONS,
            action_keys({CONF_LOCK_ENTITY: "lock.front_door"}),
        )
        self.assertNotIn(
            CONF_SHUTTER_OPEN_ACTIONS,
            action_keys({CONF_LOCK_ENTITY: "lock.front_door"}),
        )
        self.assertIn(
            CONF_SHUTTER_OPEN_ACTIONS,
            action_keys(
                {CONF_SHUTTER_CONTACT_ENTITY: "binary_sensor.shutter_contact"}
            ),
        )
        options = _entry_options(
            {
                CONF_APPLIANCE_TYPE: "opening",
                CONF_LOCK_LOCKED_ACTIONS: [{"action": "test.locked"}],
                CONF_LOCK_UNLOCKED_ACTIONS: [{"action": "test.unlocked"}],
                CONF_SHUTTER_OPEN_ACTIONS: [{"action": "test.shutter_open"}],
                CONF_SHUTTER_CLOSE_ACTIONS: [{"action": "test.shutter_close"}],
            }
        )
        self.assertNotIn(CONF_LOCK_LOCKED_ACTIONS, options)
        self.assertNotIn(CONF_SHUTTER_OPEN_ACTIONS, options)

    def test_ac_profiles_offer_auxiliary_sources(self) -> None:
        contact_profile = get_appliance_profile("air_conditioner_contact")
        climate_profile = get_appliance_profile("thermostat_climate")
        power_profile = get_appliance_profile("air_conditioner_power")
        contact_schema = _sensor_schema({}, contact_profile)
        climate_schema = _sensor_schema({}, climate_profile)
        power_schema = _sensor_schema({}, power_profile)

        self.assertIn("air_conditioner_contact_running_entity", contact_schema.schema)
        self.assertIn("air_conditioner_contact_power_entity", contact_schema.schema)
        self.assertIn("thermostat_climate_climate_entity", climate_schema.schema)
        self.assertNotIn("thermostat_climate_running_entity", climate_schema.schema)
        self.assertIn("air_conditioner_power_power_entity", power_schema.schema)
        self.assertNotIn("air_conditioner_power_running_entity", power_schema.schema)
        self.assertIn("air_conditioner_contact_plug_entity", contact_schema.schema)
        self.assertIn("air_conditioner_power_plug_entity", power_schema.schema)
        self.assertFalse(contact_profile.supports_pending_unload)
        self.assertFalse(contact_profile.estimates_remaining)
        self.assertFalse(power_profile.supports_pending_unload)
        self.assertFalse(power_profile.estimates_remaining)

    def test_each_profile_schema_matches_its_declared_contract(self) -> None:
        parameter_keys = {
            "power_cycle": {
                "start_power_w",
                "start_duration_seconds",
                "finish_power_w",
                "finish_duration_seconds",
            },
            "max_runtime": {"max_runtime_seconds"},
            "pending_unload": {
                CONF_PENDING_DELAY_SECONDS,
                CONF_PENDING_INTERVAL_SECONDS,
                CONF_PENDING_REPEATS,
            },
            "door_alarm": {CONF_DOOR_OPEN_DELAY_SECONDS},
            "compressor_alarm": {CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS},
            "alarm_repeats": {
                CONF_ALARM_REPEAT_INTERVAL_SECONDS,
                CONF_ALARM_REPEAT_COUNT,
            },
            "plug_off_alarm": {
                CONF_PLUG_OFF_REPEAT_INTERVAL_SECONDS,
                CONF_PLUG_OFF_REPEAT_COUNT,
            },
        }
        action_keys = {
            "cycle_start": "start_actions",
            "cycle_finish": "finish_actions",
            "emptied": CONF_EMPTIED_ACTIONS,
            "max_runtime": "max_runtime_actions",
            "pending_unload": CONF_PENDING_ACTIONS,
            "door_open_alarm": CONF_DOOR_OPEN_ACTIONS,
            "compressor_inactive_alarm": CONF_COMPRESSOR_INACTIVE_ACTIONS,
            "plug_off_alarm": CONF_PLUG_OFF_ACTIONS,
        }
        expected_input_wrappers = {
            "opening": {CONF_RUNNING_ENTITY},
            "access_contact": {CONF_RUNNING_ENTITY},
            "sun_protection_contact": {CONF_RUNNING_ENTITY},
        }
        internal_only_inputs = {
            ("air_conditioner_contact", CONF_RUNNING_ENTITY),
            ("mailbox_motion", CONF_MAIL_MOTION_ENTITY),
        }
        for appliance_type, profile in APPLIANCE_PROFILES.items():
            with self.subTest(appliance_type=appliance_type):
                self.assertEqual(
                    {
                        input_config.config_key
                        for input_config in profile.sensor_inputs
                        if input_config.requires_source_representation
                    },
                    {
                        input_config.config_key
                        for input_config in profile.sensor_inputs
                        if (appliance_type, input_config.config_key)
                        not in internal_only_inputs
                    },
                )
                for input_config in profile.sensor_inputs:
                    if input_config.proxy_always:
                        self.assertEqual(input_config.config_key, CONF_ENERGY_ENTITY)
                        self.assertEqual(input_config.output_entity, "total_energy")
                self.assertEqual(
                    {
                        item.config_key
                        for item in profile.inputs_requiring_wrapper
                    },
                    expected_input_wrappers.get(appliance_type, set()),
                )
                for input_config in profile.sensor_inputs:
                    if input_config.domain == "climate":
                        self.assertIsNone(input_config.output_entity)
                    else:
                        self.assertTrue(
                            input_config.output_entity
                            or not input_config.create_wrapper
                            or input_config in profile.inputs_requiring_wrapper
                        )
                self.assertTrue(
                    all(
                        input_config.domain == "binary_sensor"
                        for input_config in profile.inputs_requiring_wrapper
                    )
                )
                values = {
                    CONF_POWER_ENTITY: "sensor.appliance_power",
                    CONF_RUNNING_ENTITY: "binary_sensor.appliance_activity",
                    "door_entity": "binary_sensor.appliance_door",
                }
                if profile.supports_smart_plug:
                    values[CONF_PLUG_ENTITY] = "switch.appliance_plug"
                sensor_schema = _sensor_schema(_sensor_form_values(values, profile), profile)
                parameter_schema = _threshold_schema(values, profile)
                action_schema = _action_schema(values, profile)
                duration_selectors = {
                    marker.schema: field_selector
                    for marker, field_selector in parameter_schema.schema.items()
                    if marker.schema.endswith("_seconds")
                }
                self.assertTrue(
                    all(
                        field_selector.selector_type == "duration"
                        and not field_selector.config.get("enable_day", False)
                        and not field_selector.config.get("allow_negative", True)
                        for field_selector in duration_selectors.values()
                    ),
                    appliance_type,
                )

                expected_source = next(
                    item.form_key
                    for item in profile.sensor_inputs
                    if item.detection_source is not None
                )
                self.assertIn(expected_source, sensor_schema.schema)
                self.assertEqual(
                    any(item.config_key == CONF_POWER_ENTITY for item in profile.sensor_inputs),
                    any(
                        item.form_key in sensor_schema.schema
                        for item in profile.sensor_inputs
                        if item.config_key == CONF_POWER_ENTITY
                    ),
                )
                self.assertEqual(
                    any(item.config_key == CONF_RUNNING_ENTITY for item in profile.sensor_inputs),
                    any(
                        item.form_key in sensor_schema.schema
                        for item in profile.sensor_inputs
                        if item.config_key == CONF_RUNNING_ENTITY
                    ),
                )
                self.assertEqual(
                    profile.supports_door_sensor,
                    profile.door_sensor_input is not None
                    and profile.door_sensor_input.form_key in sensor_schema.schema,
                )
                if "power" in profile.detection_sources:
                    self.assertIn("total_energy", profile.output_entities)
                if "total_energy" in profile.output_entities:
                    self.assertTrue(
                        any(
                            item.config_key == CONF_POWER_ENTITY
                            for item in profile.sensor_inputs
                        )
                    )
                self.assertEqual(
                    "estimated_remaining" in profile.output_entities,
                    profile.estimates_remaining,
                )
                self.assertEqual(
                    "pending_unload" in profile.output_entities,
                    profile.supports_pending_unload,
                )

                for group, keys in parameter_keys.items():
                    for key in keys:
                        self.assertEqual(
                            group in profile.parameter_groups,
                            key in parameter_schema.schema,
                        )
                for group, key in action_keys.items():
                    self.assertEqual(
                        group in profile.action_groups
                        and (group != "plug_off_alarm" or profile.supports_smart_plug),
                        key in action_schema.schema,
                    )

                if profile.supports_smart_plug:
                    no_plug_parameters = _threshold_schema(
                        {CONF_POWER_ENTITY: "sensor.appliance_power"}, profile
                    )
                    no_plug_actions = _action_schema(
                        {CONF_POWER_ENTITY: "sensor.appliance_power"}, profile
                    )
                    self.assertNotIn(
                        CONF_PLUG_OFF_REPEAT_COUNT, no_plug_parameters.schema
                    )
                    self.assertNotIn(CONF_PLUG_OFF_ACTIONS, no_plug_actions.schema)

    def test_plug_off_alarm_settings_validation(self) -> None:
        profile = get_appliance_profile("washer")
        valid = {
            CONF_PLUG_ENTITY: "switch.washer",
            CONF_PLUG_OFF_REPEAT_INTERVAL_SECONDS: 900,
            CONF_PLUG_OFF_REPEAT_COUNT: 3,
        }

        self.assertTrue(_validate_plug_off_alarm_settings(valid, profile))
        self.assertFalse(
            _validate_plug_off_alarm_settings(
                {**valid, CONF_PLUG_OFF_REPEAT_INTERVAL_SECONDS: 0}, profile
            )
        )
        self.assertFalse(
            _validate_plug_off_alarm_settings(
                {**valid, CONF_PLUG_OFF_REPEAT_COUNT: -1}, profile
            )
        )
        self.assertTrue(_validate_plug_off_alarm_settings({}, profile))

    def test_sensor_selectors_filter_by_domain_and_device_class(self) -> None:
        for profile in APPLIANCE_PROFILES.values():
            schema = _sensor_schema(_sensor_form_values(
                {"door_entity": "binary_sensor.door"}, profile
            ), profile)
            selectors = {
                marker.schema: entity_selector
                for marker, entity_selector in schema.schema.items()
            }
            source_input = next(
                item for item in profile.sensor_inputs
                if item.detection_source is not None
            )
            if source_input.device_classes:
                self.assertEqual(
                    selectors[source_input.form_key].config["filter"],
                    [
                        {
                            "domain": [source_input.domain],
                            "device_class": [device_class],
                        }
                        for device_class in source_input.device_classes
                    ],
                )
            else:
                self.assertEqual(
                    selectors[source_input.form_key].config["domain"],
                    [source_input.domain],
                )
            if profile.door_sensor_input is not None:
                self.assertEqual(
                    selectors[
                        profile.door_sensor_input.form_key
                    ].config["filter"],
                    [
                        {
                            "domain": [profile.door_sensor_input.domain],
                            "device_class": [device_class],
                        }
                        for device_class in profile.door_sensor_input.device_classes
                    ],
                )

        for appliance_type in ("opening", "sun_protection_contact"):
            with self.subTest(appliance_type=appliance_type):
                contact_input = next(
                    item
                    for item in APPLIANCE_PROFILES[appliance_type].sensor_inputs
                    if item.detection_source is not None
                )
                self.assertEqual(
                    contact_input.device_classes,
                    ("opening", "door", "window"),
                )

    def test_refrigerator_requires_door_and_valid_alarm_limits(self) -> None:
        profile = get_appliance_profile("refrigerator")
        sensor_schema = _sensor_schema({}, profile)
        with self.assertRaises(vol.Invalid):
            sensor_schema({CONF_POWER_ENTITY: "sensor.fridge_power"})

        self.assertTrue(
            _validate_alarm_settings(
                {
                    CONF_DOOR_OPEN_DELAY_SECONDS: 120,
                    CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS: 3600,
                    CONF_ALARM_REPEAT_INTERVAL_SECONDS: 900,
                    CONF_ALARM_REPEAT_COUNT: 3,
                }
            )
        )
        self.assertFalse(
            _validate_alarm_settings(
                {
                    CONF_DOOR_OPEN_DELAY_SECONDS: 0,
                    CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS: 3600,
                    CONF_ALARM_REPEAT_INTERVAL_SECONDS: 900,
                    CONF_ALARM_REPEAT_COUNT: 3,
                }
            )
        )

    def test_threshold_and_alarm_validators_reject_missing_or_invalid_values(self) -> None:
        contact_profile = get_appliance_profile("air_conditioner_contact")
        self.assertTrue(_validate_thresholds({}, contact_profile))
        self.assertTrue(
            _validate_thresholds(
                {CONF_MAX_RUNTIME_SECONDS: 60}, contact_profile
            )
        )
        self.assertFalse(
            _validate_thresholds(
                {CONF_MAX_RUNTIME_SECONDS: "invalid"}, contact_profile
            )
        )
        self.assertFalse(
            _validate_thresholds({"start_power_w": 4})
        )
        self.assertFalse(_validate_pending({}))
        self.assertFalse(_validate_alarm_settings({}))

    def test_profile_change_discards_actions_not_declared_by_new_profile(self) -> None:
        options = _entry_options(
            {
                CONF_APPLIANCE_TYPE: "refrigerator",
                CONF_START_ACTIONS: [{"action": "test.start"}],
                CONF_FINISH_ACTIONS: [{"action": "test.finish"}],
                CONF_MAX_RUNTIME_ACTIONS: [{"action": "test.timeout"}],
                CONF_DOOR_OPEN_ACTIONS: [{"action": "test.door"}],
                CONF_COMPRESSOR_INACTIVE_ACTIONS: [{"action": "test.compressor"}],
                CONF_ALARM_REPEAT_COUNT: 3,
                CONF_ALARM_REPEAT_INTERVAL_SECONDS: 900,
            }
        )

        self.assertIn(CONF_START_ACTIONS, options)
        self.assertIn(CONF_FINISH_ACTIONS, options)
        self.assertNotIn(CONF_MAX_RUNTIME_ACTIONS, options)
        self.assertIn(CONF_DOOR_OPEN_ACTIONS, options)
        self.assertNotIn(CONF_COMPRESSOR_INACTIVE_ACTIONS, options)
        self.assertNotIn(CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS, options)
        self.assertNotIn(CONF_PLUG_OFF_ACTIONS, options)
        self.assertNotIn(CONF_PLUG_OFF_REPEAT_COUNT, options)
        self.assertIn(CONF_ALARM_REPEAT_COUNT, options)
        self.assertIn(CONF_ALARM_REPEAT_INTERVAL_SECONDS, options)

    def test_duration_parameters_use_native_selector_and_store_seconds(self) -> None:
        schema = _threshold_schema(
            {
                CONF_DOOR_ENTITY: "binary_sensor.washer_door",
                CONF_MAX_RUNTIME_SECONDS: 90061,
            },
            get_appliance_profile("washer"),
        )
        defaults = {
            marker.schema: marker.default()
            for marker in schema.schema
            if marker.schema
            in (
                "start_duration_seconds",
                CONF_PENDING_DELAY_SECONDS,
                CONF_MAX_RUNTIME_SECONDS,
            )
        }
        self.assertEqual(
            defaults["start_duration_seconds"],
            {"hours": 0, "minutes": 0, "seconds": 15},
        )
        self.assertEqual(
            defaults[CONF_PENDING_DELAY_SECONDS],
            {"hours": 0, "minutes": 15, "seconds": 0},
        )
        self.assertEqual(
            defaults[CONF_MAX_RUNTIME_SECONDS],
            {"hours": 25, "minutes": 1, "seconds": 1},
        )

        values = schema(
            {
                "start_power_w": 4,
                "start_duration_seconds": {
                    "days": 0,
                    "hours": 0,
                    "minutes": 0,
                    "seconds": 30,
                },
                "finish_power_w": 1,
                "finish_duration_seconds": {"minutes": 2, "seconds": 30},
                CONF_MAX_RUNTIME_SECONDS: {
                    "hours": 25,
                    "minutes": 1,
                    "seconds": 1,
                },
                CONF_PENDING_DELAY_SECONDS: {
                    "hours": 1,
                    "minutes": 2,
                    "seconds": 3,
                },
                CONF_PENDING_INTERVAL_SECONDS: {"minutes": 15},
                CONF_PENDING_REPEATS: 3,
            }
        )
        self.assertEqual(values["start_duration_seconds"], 30)
        self.assertEqual(values["finish_duration_seconds"], 150)
        self.assertEqual(values[CONF_MAX_RUNTIME_SECONDS], 90061)
        self.assertEqual(values[CONF_PENDING_DELAY_SECONDS], 3723)
        self.assertEqual(values[CONF_PENDING_INTERVAL_SECONDS], 900)

        duration_selector = next(
            field_selector
            for marker, field_selector in schema.schema.items()
            if marker.schema == "start_duration_seconds"
        )
        with self.assertRaises(vol.Invalid):
            duration_selector({"seconds": -1})

        for duration_key in (
            "start_duration_seconds",
            "finish_duration_seconds",
            CONF_MAX_RUNTIME_SECONDS,
            CONF_PENDING_DELAY_SECONDS,
            CONF_PENDING_INTERVAL_SECONDS,
            CONF_DOOR_OPEN_DELAY_SECONDS,
            CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS,
            CONF_ALARM_REPEAT_INTERVAL_SECONDS,
            CONF_PLUG_OFF_REPEAT_INTERVAL_SECONDS,
        ):
            self.assertTrue(_validate_duration_limits({duration_key: 86400}))
            self.assertFalse(_validate_duration_limits({duration_key: 86401}))

        optional_schema = _threshold_schema(
            {}, get_appliance_profile("washer")
        )
        optional_values = optional_schema(
            {"start_power_w": 4, "finish_power_w": 1}
        )
        self.assertNotIn(CONF_MAX_RUNTIME_SECONDS, optional_values)

        with self.assertRaises(vol.Invalid):
            schema(
                {
                    "start_power_w": 4,
                    "finish_power_w": 1,
                    "start_duration_seconds": "not a duration",
                }
            )

    def test_duration_parameter_accepts_stored_seconds(self) -> None:
        schema = _threshold_schema({}, get_appliance_profile("washer"))
        values = schema(
            {
                "start_power_w": 4,
                "start_duration_seconds": 15,
                "finish_power_w": 1,
                "finish_duration_seconds": 60,
            }
        )
        self.assertEqual(values["start_duration_seconds"], 15)
        self.assertEqual(values["finish_duration_seconds"], 60)

    def test_default_thresholds_and_coherence_validation(self) -> None:
        values = _threshold_schema({}, get_appliance_profile("washer"))(
            {
                "start_power_w": 4,
                "finish_power_w": 1,
            }
        )

        self.assertEqual(values["start_power_w"], 4)
        self.assertEqual(values["start_duration_seconds"], 15)
        self.assertEqual(values["finish_duration_seconds"], 60)
        self.assertTrue(_validate_thresholds(values))
        self.assertFalse(
            _validate_thresholds(
                {
                    **values,
                    "start_power_w": 1,
                    "finish_power_w": 1,
                }
            )
        )

    def test_pending_fields_are_only_shown_with_door_sensor(self) -> None:
        profile = get_appliance_profile("washer")
        without_door = _threshold_schema({}, profile)
        with_door = _threshold_schema({"door_entity": "binary_sensor.door"}, profile)
        actions_without_door = _action_schema({}, profile)
        actions_with_door = _action_schema({"door_entity": "binary_sensor.door"}, profile)

        self.assertNotIn(CONF_PENDING_DELAY_SECONDS, without_door.schema)
        self.assertIn(CONF_PENDING_DELAY_SECONDS, with_door.schema)
        self.assertNotIn(CONF_PENDING_DELAY_SECONDS, actions_with_door.schema)
        self.assertNotIn(CONF_PENDING_INTERVAL_SECONDS, actions_with_door.schema)
        self.assertNotIn(CONF_PENDING_REPEATS, actions_with_door.schema)
        self.assertNotIn(CONF_PENDING_ACTIONS, actions_without_door.schema)
        self.assertNotIn(CONF_EMPTIED_ACTIONS, actions_without_door.schema)
        self.assertIn(CONF_PENDING_ACTIONS, actions_with_door.schema)
        self.assertIn(CONF_EMPTIED_ACTIONS, actions_with_door.schema)
        values = with_door(
            {
                "start_power_w": 4,
                "finish_power_w": 1,
            }
        )
        self.assertEqual(values[CONF_PENDING_DELAY_SECONDS], DEFAULT_PENDING_DELAY_SECONDS)
        self.assertEqual(
            values[CONF_PENDING_INTERVAL_SECONDS], DEFAULT_PENDING_INTERVAL_SECONDS
        )
        self.assertEqual(values[CONF_PENDING_REPEATS], DEFAULT_PENDING_REPEATS)

    def test_pending_limits_require_positive_integer_seconds(self) -> None:
        self.assertTrue(
            _validate_pending(
                {
                    CONF_PENDING_DELAY_SECONDS: 900,
                    CONF_PENDING_INTERVAL_SECONDS: 900,
                    CONF_PENDING_REPEATS: 3,
                }
            )
        )
        self.assertFalse(
            _validate_pending(
                {
                    CONF_PENDING_DELAY_SECONDS: 0,
                    CONF_PENDING_INTERVAL_SECONDS: 900,
                    CONF_PENDING_REPEATS: 3,
                }
            )
        )
        self.assertFalse(
            _validate_pending(
                {
                    CONF_PENDING_DELAY_SECONDS: 900,
                    CONF_PENDING_INTERVAL_SECONDS: 1.5,
                    CONF_PENDING_REPEATS: 3,
                }
            )
        )

    def test_removing_door_clears_saved_pending_actions(self) -> None:
        values = {
            CONF_PENDING_ACTIONS: [{"action": "notify.send_message"}],
            CONF_PENDING_DELAY_SECONDS: 120,
            CONF_PENDING_INTERVAL_SECONDS: 300,
            CONF_PENDING_REPEATS: 5,
        }

        _clear_pending_settings(values)

        self.assertEqual(values[CONF_PENDING_ACTIONS], [])
        self.assertEqual(values[CONF_PENDING_DELAY_SECONDS], 900)
        self.assertEqual(values[CONF_PENDING_INTERVAL_SECONDS], 900)
        self.assertEqual(values[CONF_PENDING_REPEATS], 3)

    def test_cycle_action_labels_are_consistent_outside_openings(self) -> None:
        root = Path(__file__).parents[2] / "custom_components" / "home_activity_manager"
        paths = (
            root / "strings.json",
            root / "translations" / "en.json",
            root / "translations" / "es.json",
            root / "translations" / "ca.json",
        )
        for path in paths:
            translation = json.loads(path.read_text(encoding="utf-8"))
            for flow in ("config", "options"):
                for group, key in (
                    ("cycle_start", "start_actions"),
                    ("cycle_finish", "finish_actions"),
                ):
                    labels = {
                        translation[flow]["step"][f"actions_{profile_name}"]["data"][key]
                        for profile_name, profile in APPLIANCE_PROFILES.items()
                        if group in profile.action_groups
                        and profile_name
                        not in {"opening", "access_contact", "opening_cover"}
                    }
                    self.assertEqual(len(labels), 1, (path, flow, group))

    def test_opening_action_labels_describe_open_and_closed_states(self) -> None:
        root = Path(__file__).parents[2] / "custom_components" / "home_activity_manager"
        paths = (
            root / "strings.json",
            root / "translations" / "en.json",
            root / "translations" / "es.json",
            root / "translations" / "ca.json",
        )
        for path in paths:
            translation = json.loads(path.read_text(encoding="utf-8"))
            for flow in ("config", "options"):
                opening_actions = translation[flow]["step"]["actions_opening"]["data"]
                cover_actions = translation[flow]["step"]["actions_opening_cover"]["data"]
                self.assertNotEqual(
                    opening_actions["start_actions"],
                    cover_actions["start_actions"],
                )
                self.assertNotEqual(
                    opening_actions["finish_actions"],
                    cover_actions["finish_actions"],
                )

    def test_duration_translation_labels_do_not_describe_text_format(self) -> None:
        root = Path(__file__).parents[2] / "custom_components" / "home_activity_manager"
        paths = (
            root / "strings.json",
            root / "translations" / "en.json",
            root / "translations" / "es.json",
            root / "translations" / "ca.json",
        )
        for path in paths:
            translation = json.loads(path.read_text(encoding="utf-8"))
            for flow in ("config", "options"):
                for step_name, step in translation[flow]["step"].items():
                    if not step_name.startswith("parameters_"):
                        continue
                    for key, label in step["data"].items():
                        if key.endswith("_seconds"):
                            self.assertNotIn("HH:MM:SS", label, (path, flow, key))

    def test_all_translation_files_have_matching_keys(self) -> None:
        root = Path(__file__).parents[2] / "custom_components" / "home_activity_manager"
        translations = [
            json.loads((root / "strings.json").read_text(encoding="utf-8")),
            json.loads((root / "translations" / "en.json").read_text(encoding="utf-8")),
            json.loads((root / "translations" / "es.json").read_text(encoding="utf-8")),
            json.loads((root / "translations" / "ca.json").read_text(encoding="utf-8")),
        ]

        def key_shape(value):
            if isinstance(value, dict):
                return {key: key_shape(child) for key, child in value.items()}
            if isinstance(value, list):
                return [key_shape(child) for child in value]
            return None

        expected = key_shape(translations[0])
        self.assertEqual(key_shape(translations[1]), expected)
        self.assertEqual(key_shape(translations[2]), expected)
        self.assertEqual(key_shape(translations[3]), expected)
        expected_status_names = (
            ("State", "Occupied"),
            ("State", "Occupied"),
            ("Estado", "Ocupada"),
            ("Estat", "Ocupada"),
        )
        for translation, expected_names in zip(translations, expected_status_names):
            binary_sensor_names = translation["entity"]["binary_sensor"]
            for key, expected_name in zip(
                ("state", "occupied"), expected_names
            ):
                self.assertEqual(binary_sensor_names[key]["name"], expected_name)
        expected_input_names = (
            ("Motion sensor (HAM Proxy)", "Main-door contact/opening sensor (HAM Proxy)", "Mail-slot contact/opening sensor (HAM Proxy)"),
            ("Motion sensor (HAM Proxy)", "Main-door contact/opening sensor (HAM Proxy)", "Mail-slot contact/opening sensor (HAM Proxy)"),
            ("Sensor de movimiento (HAM Proxy)", "Sensor de contacto/apertura de la puerta principal (HAM Proxy)", "Sensor de contacto/apertura de la trampilla (HAM Proxy)"),
            ("Sensor de moviment (HAM Proxy)", "Sensor de contacte/obertura de la porta principal (HAM Proxy)", "Sensor de contacte/obertura de la portella (HAM Proxy)"),
        )
        expected_running_names = (
            "State (HAM Proxy)",
            "State (HAM Proxy)",
            "Estado (HAM Proxy)",
            "Estat (HAM Proxy)",
        )
        for translation, expected_name in zip(translations, expected_running_names):
            self.assertEqual(
                translation["entity"]["binary_sensor"]["input_running"]["name"],
                expected_name,
            )
        expected_entity_state_names = (
            ("Door state", "Window state", "Access state", "Awning state", "Shutter state"),
            ("Door state", "Window state", "Access state", "Awning state", "Shutter state"),
            ("Estado de la puerta", "Estado de la ventana", "Estado del acceso", "Estado del toldo", "Estado de la persiana"),
            ("Estat de la porta", "Estat de la finestra", "Estat de l’accés", "Estat del tendal", "Estat de la persiana"),
        )
        for translation, expected_names in zip(translations, expected_entity_state_names):
            binary_sensor_names = translation["entity"]["binary_sensor"]
            for key, expected_name in zip(
                ("door_state", "window_state", "access_state", "awning_state", "shutter_state"),
                expected_names,
            ):
                self.assertEqual(binary_sensor_names[key]["name"], expected_name)
        expected_duration_names = (
            (
                "Last cycle duration",
                "Duration of the last door opening",
                "Duration of the last window opening",
                "Duration of the last access opening",
                "Duration of the last awning opening",
                "Duration of the last shutter opening",
            ),
            (
                "Last cycle duration",
                "Duration of the last door opening",
                "Duration of the last window opening",
                "Duration of the last access opening",
                "Duration of the last awning opening",
                "Duration of the last shutter opening",
            ),
            (
                "Duración del último ciclo",
                "Duración de la última apertura de la puerta",
                "Duración de la última apertura de la ventana",
                "Duración de la última apertura del acceso",
                "Duración de la última apertura del toldo",
                "Duración de la última apertura de la persiana",
            ),
            (
                "Durada de l’últim cicle",
                "Durada de l’última obertura de la porta",
                "Durada de l’última obertura de la finestra",
                "Durada de l’última obertura de l’accés",
                "Durada de l’última obertura del tendal",
                "Durada de l’última obertura de la persiana",
            ),
        )
        for translation, expected_names in zip(translations, expected_duration_names):
            sensor_names = translation["entity"]["sensor"]
            for key, expected_name in zip(
                (
                    "last_cycle_duration",
                    "door_open_duration",
                    "window_open_duration",
                    "access_open_duration",
                    "awning_open_duration",
                    "shutter_open_duration",
                ),
                expected_names,
            ):
                self.assertEqual(sensor_names[key]["name"], expected_name)
        for translation, expected_names in zip(translations, expected_input_names):
            binary_sensor_names = translation["entity"]["binary_sensor"]
            for key, expected_name in zip(
                ("input_mail_motion", "input_door", "input_mail_slot"),
                expected_names,
            ):
                self.assertEqual(binary_sensor_names[key]["name"], expected_name)

        for translation in translations:
            for flow in ("config", "options"):
                for shared_step in ("sensors", "parameters", "actions"):
                    self.assertNotIn(shared_step, translation[flow]["step"])
        for translation in translations:
            self.assertNotIn("activity_mode", translation["config"]["step"])

        sensor_form_keys = [
            item.form_key
            for profile in APPLIANCE_PROFILES.values()
            for item in profile.sensor_inputs
        ]
        self.assertEqual(len(sensor_form_keys), len(set(sensor_form_keys)))

        catalan_options = translations[3]["selector"]["appliance_type"]["options"]
        catalan_labels = [catalan_options[appliance_type] for appliance_type in APPLIANCE_TYPES]
        self.assertEqual(catalan_labels, sorted(catalan_labels, key=str.casefold))

        for translation in translations:
            option_labels = translation["selector"]["appliance_type"]["options"]
            self.assertEqual(set(option_labels), set(APPLIANCE_PROFILES))

            for appliance_type, label in option_labels.items():
                self.assertTrue(label.strip())
                self.assertNotEqual(label, appliance_type)

            for flow, identity_step in (("config", "user"), ("options", "init")):
                for profile in APPLIANCE_PROFILES.values():
                    values = {"door_entity": "binary_sensor.door"}
                    profile_name = next(
                        name
                        for name, candidate in APPLIANCE_PROFILES.items()
                        if candidate is profile
                    )
                    step_schemas = {
                        identity_step: _identity_schema({}),
                        f"sensors_{profile_name}": _sensor_schema(
                            _sensor_form_values(values, profile), profile
                        ),
                        f"parameters_{profile_name}": _threshold_schema(values, profile),
                        f"actions_{profile_name}": _action_schema(values, profile),
                    }
                    for step, schema in step_schemas.items():
                        labels = translation[flow]["step"][step]["data"]
                        descriptions = translation[flow]["step"][step].get(
                            "data_description", {}
                        )
                        self.assertTrue(
                            all(";" not in description for description in descriptions.values())
                        )
                        for marker in schema.schema:
                            key = marker.schema
                            self.assertIn(key, labels)
                            self.assertTrue(labels[key].strip())
                            self.assertNotEqual(labels[key], key)
                            if key.endswith("_seconds"):
                                self.assertNotIn("HH:MM:SS", labels[key])
                        if step.startswith("sensors_air_conditioner_"):
                            descriptions = translation[flow]["step"][step][
                                "data_description"
                            ]
                            self.assertEqual(
                                set(descriptions),
                                {marker.schema for marker in schema.schema},
                            )
                            self.assertTrue(
                                all(description.strip() for description in descriptions.values())
                            )
                    sensor_labels = translation[flow]["step"][
                        f"sensors_{profile_name}"
                    ]["data"]
                    for sensor_input in profile.sensor_inputs:
                        if not sensor_input.required:
                            self.assertTrue(
                                "(optional)" in sensor_labels[sensor_input.form_key]
                                or "(opcional)" in sensor_labels[sensor_input.form_key]
                            )
                        else:
                            self.assertTrue(
                                "(required)" in sensor_labels[sensor_input.form_key]
                                or "(obligatori)" in sensor_labels[sensor_input.form_key]
                                or "(obligatorio)" in sensor_labels[sensor_input.form_key]
                            )
                    action_labels = translation[flow]["step"][
                        f"actions_{profile_name}"
                    ]["data"].values()
                    self.assertTrue(
                        all(
                            "(optional)" in label or "(opcional)" in label
                            for label in action_labels
                        )
                    )

            mode_labels = []
            for category, modes in APPLIANCE_CATEGORIES.items():
                step = translation["config"]["step"][
                    f"activity_mode_{category}"
                ]
                labels = step["data"]
                self.assertTrue(step["title"].strip())
                self.assertTrue(labels["activity_mode"].strip())
                self.assertTrue(step["data_description"]["activity_mode"].strip())
                mode_labels.append(labels["activity_mode"])
                options = translation["selector"][
                    f"activity_mode_{category}"
                ]["options"]
                self.assertEqual(set(options), set(modes))
                self.assertTrue(all(label.strip() for label in options.values()))
            self.assertEqual(len(mode_labels), len(set(mode_labels)))

    def test_group_action_help_points_to_readme_without_urls(self) -> None:
        root = Path(__file__).parents[2] / "custom_components" / "home_activity_manager"
        paths = (
            root / "strings.json",
            root / "translations" / "en.json",
            root / "translations" / "es.json",
            root / "translations" / "ca.json",
        )
        for path in paths:
            translation = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn(
                "group_actions",
                translation["selector"]["appliance_action"]["options"],
            )
            self.assertIn(
                "add", translation["selector"]["appliance_action"]["options"]
            )
            action_options = translation["selector"]["appliance_action"]["options"]
            ordered_actions = [
                action_options[key]
                for key in ("add", "group_actions", "edit", "remove")
            ]
            self.assertEqual(ordered_actions, sorted(ordered_actions, key=str.casefold))
            hierarchy_help = translation["config"]["step"]["user"]["description"]
            self.assertTrue(
                any(
                    term in hierarchy_help.casefold()
                    for term in ("group", "agrupació", "agrupación")
                )
            )
            help_text = translation["options"]["step"]["group_actions"]["description"]
            self.assertIn("readme", help_text.casefold())
            self.assertNotIn("https://", help_text)
            self.assertLess(len(help_text), 200)
            self.assertNotIn("{{", help_text)
            self.assertNotIn("}}", help_text)
            action_help = translation["options"]["step"]["group_actions"][
                "data_description"
            ]
            for action_key in (
                "start_actions",
                "finish_actions",
                "max_runtime_actions",
                "pending_actions",
                "emptied_actions",
                "door_open_actions",
                "compressor_inactive_actions",
                "plug_off_actions",
            ):
                self.assertTrue(action_help[action_key].strip(), (path, action_key))

        readme = (Path(__file__).parents[2] / "README.md").read_text(encoding="utf-8")
        for term in (
            "ham_device_name",
            "ham_device_area_name",
            "ham_source_entity_id",
            "ham_appliance_name",
            "ham_area_name",
            "notify.send_message",
        ):
            self.assertIn(term, readme)
        self.assertIn("default('timer', true)", readme)

    def test_last_appliance_removed_abort_uses_options_translation(self) -> None:
        root = Path(__file__).parents[2] / "custom_components" / "home_activity_manager"
        paths = (
            root / "strings.json",
            root / "translations" / "en.json",
            root / "translations" / "es.json",
            root / "translations" / "ca.json",
        )
        for path in paths:
            translation = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(
                translation["options"]["abort"]["last_appliance_removed"].strip()
            )
            self.assertNotIn("last_appliance_removed", translation["config"]["abort"])


@pytest.mark.asyncio
async def test_config_flow_has_six_forward_steps_and_separates_options():
    flow = ApplianceCycleMonitorConfigFlow()
    shown_steps: list[dict[str, object]] = []
    flow.async_show_form = lambda **result: shown_steps.append(result) or result
    flow.async_create_entry = lambda **result: result

    first_result = await flow.async_step_user()
    assert first_result["step_id"] == "user"
    assert first_result["last_step"] is False

    class_result = await flow.async_step_user(
        {
            "name": "Washer",
            CONF_APPLIANCE_GROUP: "large_appliances",
        }
    )
    assert class_result["step_id"] == "appliance_class"
    mode_result = await flow.async_step_appliance_class(
        {CONF_APPLIANCE_CLASS: "washer"}
    )
    assert mode_result["step_id"] == "activity_mode_large_appliances"
    sensors_result = await flow.async_step_activity_mode({"activity_mode": "power"})
    assert sensors_result["step_id"] == "sensors_laundry"

    parameters_result = await flow.async_step_sensors(
        {"laundry_power_entity": "sensor.washer_power"}
    )
    assert parameters_result["step_id"] == "parameters_laundry"
    assert parameters_result["last_step"] is False

    actions_result = await flow.async_step_parameters(
        {
            "start_power_w": 4,
            "start_duration_seconds": 15,
            "finish_power_w": 1,
            "finish_duration_seconds": 60,
        }
    )
    assert actions_result["step_id"] == "actions_laundry"

    created = await flow.async_step_actions(
        {
            "start_actions": [],
            "finish_actions": [],
            "max_runtime_actions": [],
        }
    )
    assert created["title"] == "Large appliances"
    assert created["data"]["category"] == "large_appliances"
    appliance = created["data"]["appliances"][0]
    assert appliance["data"]["power_entity"] == "sensor.washer_power"
    assert appliance["data"][CONF_APPLIANCE_TYPE] == "laundry"
    assert appliance["data"][CONF_APPLIANCE_CLASS] == "washer"
    assert "start_power_w" not in appliance["data"]
    assert appliance["options"]["start_power_w"] == 4
    assert [result["step_id"] for result in shown_steps] == [
        "user",
        "appliance_class",
        "activity_mode_large_appliances",
        "sensors_laundry",
        "parameters_laundry",
        "actions_laundry",
    ]


@pytest.mark.asyncio
async def test_pending_settings_are_validated_on_parameters_step():
    flow = ApplianceCycleMonitorConfigFlow()
    flow.async_show_form = lambda **result: result
    flow.async_create_entry = lambda **result: result

    await flow.async_step_user(
        {
            "name": "Washer",
            CONF_APPLIANCE_GROUP: "large_appliances",
        }
    )
    await flow.async_step_appliance_class({CONF_APPLIANCE_CLASS: "washer"})
    await flow.async_step_activity_mode({"activity_mode": "power"})
    await flow.async_step_sensors(
        {
            "laundry_power_entity": "sensor.washer_power",
            "door_entity": "binary_sensor.washer_door",
        }
    )
    result = await flow.async_step_parameters(
        {
            "start_power_w": 4,
            "start_duration_seconds": 86401,
            "finish_power_w": 1,
            "finish_duration_seconds": 60,
            CONF_PENDING_DELAY_SECONDS: 1200,
            CONF_PENDING_INTERVAL_SECONDS: 1800,
            CONF_PENDING_REPEATS: 2,
        }
    )
    assert result["step_id"] == "parameters_laundry"
    assert result["errors"] == {"base": "invalid_thresholds"}

    result = await flow.async_step_parameters(
        {
            "start_power_w": 4,
            "start_duration_seconds": 15,
            "finish_power_w": 1,
            "finish_duration_seconds": 60,
            CONF_PENDING_DELAY_SECONDS: 0,
            CONF_PENDING_INTERVAL_SECONDS: 900,
            CONF_PENDING_REPEATS: 3,
        }
    )

    assert result["step_id"] == "parameters_laundry"
    assert result["errors"] == {"base": "invalid_pending_settings"}

    result = await flow.async_step_parameters(
        {
            "start_power_w": 4,
            "start_duration_seconds": 15,
            "finish_power_w": 1,
            "finish_duration_seconds": 60,
            CONF_PENDING_DELAY_SECONDS: 1200,
            CONF_PENDING_INTERVAL_SECONDS: 1800,
            CONF_PENDING_REPEATS: 2,
        }
    )
    assert result["step_id"] == "actions_laundry"
    assert CONF_PENDING_DELAY_SECONDS not in result["data_schema"].schema

    created = await flow.async_step_actions(
        {
            "start_actions": [],
            "finish_actions": [],
            "max_runtime_actions": [],
            CONF_PENDING_ACTIONS: [],
        }
    )
    options = created["data"]["appliances"][0]["options"]
    assert options[CONF_PENDING_DELAY_SECONDS] == 1200
    assert options[CONF_PENDING_INTERVAL_SECONDS] == 1800
    assert options[CONF_PENDING_REPEATS] == 2


@pytest.mark.asyncio
async def test_options_flow_edits_four_steps_and_clears_removed_door_settings(
    monkeypatch,
):
    entry = SimpleNamespace(
        data={
            "name": "Washer",
            "appliance_type": "washer",
            "power_entity": "sensor.washer_power",
            "door_entity": "binary_sensor.washer_door",
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
        title="Washer",
    )
    updated: list[dict[str, object]] = []
    monkeypatch.setattr(
        ApplianceCycleMonitorOptionsFlow,
        "config_entry",
        property(lambda _self: entry),
    )
    flow = ApplianceCycleMonitorOptionsFlow()
    flow.hass = SimpleNamespace(
        config_entries=SimpleNamespace(
            async_update_entry=lambda _entry, **kwargs: updated.append(kwargs)
        )
    )
    shown_steps: list[dict[str, object]] = []
    flow.async_show_form = lambda **result: shown_steps.append(result) or result
    flow.async_create_entry = lambda **result: result

    first_result = await flow.async_step_init()
    assert first_result["step_id"] == "init"
    assert first_result["data_schema"]({})["name"] == "Washer"
    sensors_result = await flow.async_step_init(
        {
            "name": "Washer 2",
            "appliance_type": "washer",
        }
    )
    assert sensors_result["step_id"] == "sensors_washer"
    parameters_result = await flow.async_step_sensors(
        {"washer_power_entity": "sensor.new_power", "washer_door_entity": None}
    )
    assert parameters_result["step_id"] == "parameters_washer"
    invalid_result = await flow.async_step_parameters(
        {
            "start_power_w": 5,
            "start_duration_seconds": 86401,
            "finish_power_w": 1,
            "finish_duration_seconds": 60,
        }
    )
    assert invalid_result["step_id"] == "parameters_washer"
    assert invalid_result["errors"] == {"base": "invalid_thresholds"}
    actions_result = await flow.async_step_parameters(
        {
            "start_power_w": 5,
            "start_duration_seconds": 30,
            "finish_power_w": 1,
            "finish_duration_seconds": 60,
        }
    )
    assert actions_result["step_id"] == "actions_washer"
    created = await flow.async_step_actions(
        {"start_actions": [], "finish_actions": [], "max_runtime_actions": []}
    )

    assert [result["step_id"] for result in shown_steps] == [
        "init",
        "sensors_washer",
        "parameters_washer",
        "parameters_washer",
        "actions_washer",
    ]
    assert updated[0]["title"] == "Washer 2"
    assert updated[0]["data"]["power_entity"] == "sensor.new_power"
    assert CONF_PENDING_ACTIONS not in created["data"]
    assert CONF_PENDING_DELAY_SECONDS not in created["data"]
    assert CONF_PENDING_INTERVAL_SECONDS not in created["data"]
    assert CONF_PENDING_REPEATS not in created["data"]


@pytest.mark.asyncio
async def test_options_flow_adds_appliance_to_current_group(monkeypatch):
    existing_appliance = {
        "id": "existing-washer",
        "data": {"name": "Washer", "appliance_type": "washer"},
        "options": {},
    }
    entry = SimpleNamespace(
        entry_id="large-appliances-entry",
        data={"category": "large_appliances", "appliances": [existing_appliance]},
        options={},
        title="Large appliances",
    )
    updated: list[dict[str, object]] = []
    monkeypatch.setattr(
        ApplianceCycleMonitorOptionsFlow,
        "config_entry",
        property(lambda _self: entry),
    )
    flow = ApplianceCycleMonitorOptionsFlow()
    flow.hass = SimpleNamespace(
        config_entries=SimpleNamespace(
            async_update_entry=lambda _entry, **kwargs: updated.append(kwargs)
        )
    )
    flow.async_show_form = lambda **result: result
    flow.async_create_entry = lambda **result: result

    result = await flow.async_step_init({"appliance_action": "add"})
    assert result["step_id"] == "add_appliance"
    group_form = next(
        field
        for marker, field in result["data_schema"].schema.items()
        if marker.schema == CONF_APPLIANCE_GROUP
    )
    assert group_form.config["options"] == ["large_appliances"]
    assert group_form.config["read_only"] is True
    add_input = result["data_schema"]({"name": "Second washer"})
    assert add_input[CONF_APPLIANCE_GROUP] == "large_appliances"
    class_result = await flow.async_step_add_appliance(add_input)
    assert class_result["step_id"] == "appliance_class"
    mode_result = await flow.async_step_appliance_class(
        {CONF_APPLIANCE_CLASS: "washer"}
    )
    assert mode_result["step_id"] == "activity_mode_large_appliances"
    sensors_result = await flow.async_step_activity_mode({"activity_mode": "power"})
    assert sensors_result["step_id"] == "sensors_laundry"
    created = await flow.async_step_actions({})

    appliances = updated[0]["data"]["appliances"]
    assert appliances[0] == existing_appliance
    assert appliances[1]["id"] != existing_appliance["id"]
    assert appliances[1]["data"]["name"] == "Second washer"
    assert updated[0]["data"]["category"] == "large_appliances"
    assert created == {"title": "", "data": {}}


def test_select_appliance_uses_localized_class_when_name_is_missing():
    schema = ApplianceCycleMonitorOptionsFlow._category_appliance_schema(
        [
            {
                "id": "window-id",
                "data": {CONF_APPLIANCE_CLASS: "window", "name": ""},
            }
        ],
        "ca",
    )
    selector_field = next(iter(schema.schema.values()))

    assert selector_field.config["options"] == [
        {"value": "window-id", "label": "Finestra"}
    ]


@pytest.mark.asyncio
async def test_options_flow_clears_omitted_air_conditioner_sensors(monkeypatch):
    entry = SimpleNamespace(
        entry_id="air-conditioner-entry",
        data={
            "name": "Air conditioner",
            "appliance_type": "thermostat_climate",
            "climate_entity": "climate.living_room",
            "power_entity": "sensor.ac_power",
            "plug_entity": "switch.ac_plug",
            "energy_entity": "sensor.ac_energy",
        },
        options={},
        title="Air conditioner",
    )
    updated: list[dict[str, object]] = []
    monkeypatch.setattr(
        ApplianceCycleMonitorOptionsFlow,
        "config_entry",
        property(lambda _self: entry),
    )
    monkeypatch.setattr(
        "custom_components.home_activity_manager.config_flow._validate_climate_entity",
        lambda *_args: True,
    )
    monkeypatch.setattr(
        "custom_components.home_activity_manager.config_flow._sensor_schema",
        lambda *_args, **_kwargs: vol.Schema({}),
    )
    flow = ApplianceCycleMonitorOptionsFlow()
    flow.hass = SimpleNamespace(
        config_entries=SimpleNamespace(
            async_update_entry=lambda _entry, **kwargs: updated.append(kwargs)
        )
    )
    flow.async_show_form = lambda **result: result
    flow.async_create_entry = lambda **result: result

    await flow.async_step_init({"name": "Air conditioner"})
    actions_form = await flow.async_step_sensors(
        {"thermostat_climate_climate_entity": "climate.living_room"}
    )
    assert actions_form["step_id"] == "actions_thermostat_climate"

    result = await flow.async_step_actions(
        {"start_actions": [], "finish_actions": [], "plug_off_actions": []}
    )

    assert updated[0]["data"] == {
        "name": "Air conditioner",
        "appliance_type": "thermostat_climate",
        "climate_entity": "climate.living_room",
        "power_entity": None,
        "plug_entity": None,
        "energy_entity": None,
        CONF_APPLIANCE_CLASS: "thermostat",
    }
    assert "power_entity" not in result["data"]
    assert "plug_entity" not in result["data"]
    assert "energy_entity" not in result["data"]


if __name__ == "__main__":
    unittest.main()