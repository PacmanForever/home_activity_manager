# Home Activity Manager

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://www.hacs.xyz/)
[![Version](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FPacmanForever%2Fhome_activity_manager%2Fmain%2Fcustom_components%2Fhome_activity_manager%2Fmanifest.json&query=%24.version&prefix=v&label=version)](https://github.com/PacmanForever/home_activity_manager/releases)
[![Unit Tests](https://github.com/PacmanForever/home_activity_manager/actions/workflows/tests.yml/badge.svg?branch=main&job=unit)](https://github.com/PacmanForever/home_activity_manager/actions/workflows/tests.yml)
[![Component Tests](https://github.com/PacmanForever/home_activity_manager/actions/workflows/tests.yml/badge.svg?branch=main&job=component)](https://github.com/PacmanForever/home_activity_manager/actions/workflows/tests.yml)
[![HACS Validation Tests](https://github.com/PacmanForever/home_activity_manager/actions/workflows/hacs.yml/badge.svg?branch=main)](https://github.com/PacmanForever/home_activity_manager/actions/workflows/hacs.yml)
[![HA Validation Tests](https://github.com/PacmanForever/home_activity_manager/actions/workflows/hassfest.yml/badge.svg?branch=main)](https://github.com/PacmanForever/home_activity_manager/actions/workflows/hassfest.yml)
[![License](https://img.shields.io/github/license/PacmanForever/home_activity_manager?label=GPLv3)](LICENSE)
[![Coverage](https://img.shields.io/badge/coverage-%3E%3D95%25-brightgreen)](https://github.com/PacmanForever/home_activity_manager/actions/workflows/tests.yml)
[![Home Assistant](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FPacmanForever%2Fhome_activity_manager%2Fmain%2Fdocs%2Fhome_assistant_compatibility.json&query=%24.tested_version&suffix=%20tested&label=home%20assistant&color=blue)](https://github.com/PacmanForever/home_activity_manager/actions/workflows/daily-ha.yml)
[![Daily HA compatibility](https://github.com/PacmanForever/home_activity_manager/actions/workflows/daily-ha.yml/badge.svg?branch=main)](https://github.com/PacmanForever/home_activity_manager/actions/workflows/daily-ha.yml)

Home Activity Manager brings compatible Home Assistant entities together under a dedicated device, making it easier to monitor household equipment and manage its activity, actions, reminders, and alarms. It is especially useful for non-smart devices monitored with existing sensors. Its extensible profiles cover laundry appliances, thermostats (including air conditioners), refrigerators, mailboxes, openings, and sun protection. It needs no cloud service, credentials, external helpers, or automations.

## Installation

### HACS

This integration is not yet in the default HACS store. Add it as a custom repository:

1. In HACS, open **Integrations** and select **Custom repositories** from the menu.
2. Add `https://github.com/PacmanForever/home_activity_manager` with the category **Integration**.
3. Find **Home Activity Manager**, install it, and restart Home Assistant.

### Manual

Download or clone this repository and copy `custom_components/home_activity_manager` into the `custom_components` directory of your Home Assistant configuration. Restart Home Assistant, then add **Home Activity Manager** from **Settings > Devices & services**.

The integration works on supported Home Assistant versions; displaying its local icon and logo requires Home Assistant 2026.3 or newer.

## Configuration

Appliances are organized in three levels: **group**, **appliance class**, and **activity-detection mode**. The mode labels use the same wording in the setup selector:

```text
Climate control
|-- Air conditioner
|   |-- Activity detection with a contact sensor
|   `-- Activity detection with a power sensor
`-- Thermostat
	`-- Activity detection with a climate entity

Laundry and drying
|-- Washer
|   `-- Activity detection with a power sensor
|-- Dryer
|   `-- Activity detection with a power sensor
`-- Dishwasher
	`-- Activity detection with a power sensor

Openings
|-- Door
|   `-- Activity detection with a contact sensor
`-- Window
	`-- Activity detection with a contact sensor

Sun protection
|-- Blind
|   |-- Activity detection with a contact sensor
|   `-- Activity detection with a cover entity
`-- Awning
	|-- Activity detection with a contact sensor
	`-- Activity detection with a cover entity

Deliveries
`-- Mailbox
	|-- Activity detection with a mail-slot contact sensor
	`-- Activity detection with an interior motion sensor

Refrigeration
|-- Refrigerator
|   |-- Activity detection with a power sensor
|   `-- Activity detection with a smart switch
`-- Freezer
	|-- Activity detection with a power sensor
	`-- Activity detection with a smart switch
```

### Climate control

- **Air conditioner:** choose contact-sensor or power-based activity detection. Contact mode requires its binary sensor; power mode uses configurable thresholds and confirmation times.
- **Thermostat:** use an existing climate entity as the activity source. A native climate proxy is added to the managed device; the original remains on its existing device and is not changed. The proxy mirrors standard climate state and controls and forwards standard climate actions; vendor-specific services are not proxied. Activity follows climate mode (`off` versus any active mode), including periods when `hvac_action` is idle.

### Laundry and drying

Washer, dryer, and dishwasher profiles detect cycles from power thresholds and configurable confirmation times. Each appliance can optionally monitor its door, control a smart plug, track pending unloading, and send reminders.

### Openings

Door and window profiles expose the required contact's open/closed position; they do not report whether the opening is moving. Contact transitions track activity actions and duration. An optional lock is represented by a native lock proxy on the managed device; standard controls forward to the original lock, which remains unchanged on its existing device.

### Sun protection

- **Contact-sensor mode:** exposes open/closed position, not motor movement, so it has no `running` entity. Contact transitions still track actions and duration.
- **Cover mode:** open, opening, and closing states are active; closed is inactive. A native cover proxy is added to the managed device and forwards standard controls without moving or modifying the original entity. Vendor-specific services are not proxied.

### Deliveries

Mailbox profiles detect arrivals with either an interior motion sensor or a mail-slot contact. Mail-slot mode also exposes the contact's open/closed state as **Mail slot**. Both modes use a separate main-door contact and track the cycle until collection. Start actions run on arrival; finish actions run when the main door opens or pending collection is cleared. Reminders are separate.

### Refrigeration

Refrigerator and freezer profiles offer the same two modes. Power mode requires a power sensor and door contact; start/end actions follow compressor activity. A controllable smart plug is optional and does not trigger an off alarm. Smart-switch mode requires a smart switch and separate door contact; start/end actions follow switch state, while optional power and energy sensors do not change activity. Both modes support the door-open alarm; neither switch mode nor the optional power-mode plug triggers a plug-off alarm.

### Shared behavior

- Cycle, reminder, and alarm state is restored after Home Assistant restarts. Configured actions run in order; reminders and alarms wait for the previous run to finish before repeating.
- Running state is exposed when a profile can infer activity. Opening and contact-only sun-protection profiles expose position instead; cycle-based profiles expose last-cycle duration.
- Power and energy can be monitored independently of activity detection where supported. Energy uses a selected cumulative sensor or is calculated from power.
- A Repairs issue is raised when a configured input is missing or unavailable and clears when the input recovers.
- Compatible profiles can configure an immediate smart-plug-off alarm with its own repeat interval and count. It pauses while the plug state is unavailable and rearms when switched on.

### Group actions

Configure shared actions from the group's options. Only hooks supported by every activity profile under that group are offered. Each appliance runs the shared action when its own event occurs, before its device-specific actions; a group action is not a single once-per-group event.

| Group | Hooks common to every profile |
| --- | --- |
| Climate control | Activity starts, activity ends, smart plug off |
| Laundry and drying | Activity starts, activity ends, maximum runtime, pending unload, emptied, smart plug off |
| Openings | Activity starts, activity ends |
| Sun protection | Activity starts, activity ends |
| Deliveries | Arrival, collection reminder, collected |
| Refrigeration | Activity starts, activity ends, door-open alarm |

Group action templates receive `ham_appliance_name` (the appliance's Home Assistant device name), `ham_area_name` (the assigned area, or `None`), and `ham_source_entity_id` when an entity event triggered the action. Timer-triggered actions have no source entity. For example, use `{{ ham_area_name or ham_appliance_name }}` in a notification message to prefer the area and fall back to the device name.

Each group has one config entry. Add, edit, or remove appliances from that group's options. The appliance class is stored separately from its functional profile and drives class-specific device metadata; the displayed name remains editable. Existing per-appliance entries are consolidated automatically during migration, preserving appliance IDs, entity IDs, registry customizations, and runtime state. Setup asks for:

Each group entry groups its appliances on the integration page. Only configured appliances are registered as devices; the group itself is not added as an empty device.

1. A group, appliance class, editable name, and activity mode when that profile offers a choice.
2. The required activity source and any optional compatible sensors or controls. A refrigerator requires a door contact; a mailbox requires a separate main-door contact; opening can optionally include a lock.
3. The profile's parameters and actions, when available. Empty parameter forms are skipped.

Editing shows the fixed group, class, and mode alongside the name, followed by that profile's sensors, parameters, and actions. The activity source can be replaced with a compatible entity. A running cycle retains its start time after replacement unless the new source confirms it has stopped. An unavailable source does not cause a transition.

Each device-type-and-mode profile uses its own sensor, parameter and action fields. Cycle-start and cycle-end actions use the same labels across profiles; optional fields are marked explicitly in the selected profile's form.

For profiles with a power sensor, a cumulative energy sensor can be selected independently of the activity source. Its total is displayed in kWh and is never changed by this integration. Leave it empty to calculate a persistent total from power readings. The device reset button is available whenever a power sensor is configured. It resets the integration's displayed energy total to zero without writing to the external sensor; when an external sensor is selected, its current reading becomes the reset baseline and later increases are shown as consumption since reset. The calculated total is maintained separately, so switching energy sources can change the displayed total; an unavailable external sensor does not fall back to the calculated total.

Power-cycle defaults are 4 W for 15 seconds to start and 1 W for 60 seconds to finish. Durations are stored in seconds, selected with native duration controls, and limited to 24 hours. An auxiliary plug controls the managed device's power but does not override its selected activity source. In power-based profiles, the power sensor determines when activity ends; in the switch-based refrigerator profile, the switch itself determines activity. Laundry pending-unload reminders and refrigerator door alarms run once, then repeat up to the configured number of additional repetitions. The plug-off alarm is available only in profiles that declare it; refrigerator plugs do not trigger alarms.

## Entities and automations

Outputs depend on the selected profile and configured inputs. A selected power sensor provides a power entity; an energy sensor or power sensor provides an energy entity. Cycle-based profiles provide activity state and last-activity duration; estimated remaining time is limited to laundry profiles. Both refrigerator modes expose activity and a door-open alarm; neither has a compressor-inactivity or plug-off alarm. Mailboxes expose their main-door and pending-collection states, plus a button to clear pending status. Detecting mail starts the mailbox cycle and runs its start actions; opening the main door or pressing the clear button ends the cycle, runs its end actions, and cancels reminders. A selected smart plug is exposed as a switch on the managed device. Climate, cover, and optional opening-lock sources are represented by native-domain proxy entities on the managed device.

Configured inputs are represented by their corresponding integration output when one exists. The air conditioner's louver sensor is represented by its running state, without a separate input entity. Mailbox sensors likewise do not create standalone input wrappers; the main-door, pending-collection, and mail-slot outputs remain available. Climate, cover, and lock proxies mirror standard state and supported features and forward standard actions to their configured source entities. These proxies are hidden by default to reduce duplicate entries in normal dashboards; they remain active and can be shown from the entity registry. Hidden proxies are not included when an automation targets the whole device or area. The source entities are never reassigned or modified by normal setup, editing, or removal of the managed device. Entries created by older versions that assigned the original climate entity are migrated to use a proxy and release that legacy device association.

Integration outputs update with their sources, including unknown, unavailable, missing, and recovered states. Power and energy are displayed in W and kWh. When a power source is unavailable, its output does not present the previous reading as current; the integration retains its internal state without falsely ending the cycle.

External automations can react to state changes of the running and pending-status binary sensors. The integration does not currently fire custom events on the Home Assistant event bus. Pending laundry unload or mailbox collection clears when its main door opens or when the clear button is pressed.

Runtime state is restored after Home Assistant restarts. The integration does not create external helpers, scripts, or automations, and it does not remove selected external entities when a device entry is deleted.

## License

This project is distributed under the GNU General Public License v3.0. See [LICENSE](LICENSE) for the full text.