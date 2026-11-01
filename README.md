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

Home Activity Manager brings compatible Home Assistant entities together under a dedicated device, making it easier to monitor household equipment and manage its activity, actions, reminders, and alarms. It is especially useful for non-smart devices monitored with existing sensors. Its extensible profiles cover laundry appliances, air conditioners, thermostats, refrigerators, mailboxes, openings, and sun protection. It needs no cloud service, credentials, external helpers, or automations.

## Features

- **Washer**
	- Detect cycles from power thresholds and configurable confirmation times.
	- Optionally monitor the door and control a smart plug; track pending unloading and reminders.
- **Dishwasher**
	- Detect cycles from power thresholds and configurable confirmation times.
	- Optionally monitor the door and control a smart plug; track pending unloading and reminders.
- **Dryer**
	- Detect cycles from power thresholds and configurable confirmation times.
	- Optionally monitor the door and control a smart plug; track pending unloading and reminders.
- **Air conditioner**
	- **Contact/opening-sensor option:** detect activity from a binary contact/opening sensor.
	- **Power option:** detect activity from power readings and configurable thresholds.
	- The contact/opening sensor is required in contact mode and is not offered in power mode. Other auxiliary sensors and smart-plug controls are available according to each mode. Only the selected activity source determines running state.
- **Thermostat**
	- Use an existing climate entity as the activity source. A native climate proxy is added to the managed device; the original entity remains on its existing device and is not changed. The proxy mirrors standard climate state and controls and forwards standard climate actions to the original entity. Vendor-specific services are not proxied. Activity follows climate mode (`off` versus any active mode), including periods when `hvac_action` is idle.
- **Refrigerator**
	- **Power option:** requires a power sensor and door contact. Cycle-start/end actions follow compressor activity; the door-open alarm is configurable. A controllable smart plug is optional and does not trigger an off alarm.
	- **Smart-switch option:** requires a smart switch and separate door contact. Cycle-start/end actions follow the switch state; optional power and energy sensors do not change activity. The door-open alarm is configurable; the switch does not trigger an off alarm.
- **Mailbox**
	- **Interior-motion option:** detect incoming mail with a motion sensor inside the mailbox.
	- **Mail-slot option:** detect incoming mail with a contact on the letter flap and expose its open/closed state as **Mail slot**.
	- Both options track the mailbox cycle from detected arrival until collection. Cycle-start actions run on arrival; cycle-end actions run when the main door opens or pending collection is cleared. Reminders remain separate, and both options use a separate main-door contact.
- **Opening**
	- Expose the required binary contact's open/closed position; it does not report whether the opening is moving. Contact transitions still track cycle actions and duration. An optional lock is represented by a native lock proxy on the managed device; its standard controls forward to the original lock, which remains unchanged on its existing device.
- **Sun protection**
	- **Contact-sensor option:** expose the binary sensor's open/closed position. It does not indicate motor movement, so this mode has no `running` entity; contact transitions still track cycle actions and duration.
	- **Cover option:** use a cover entity; open, opening, and closing states are active, while closed is inactive. A native cover proxy is added to the managed device and forwards standard cover controls to the original entity without moving or modifying it. Vendor-specific services are not proxied.
- **Across all profiles**
	- Configure consistent actions when a cycle starts and ends, plus any profile-specific reminders or alarms; restore cycle, reminder, and alarm state after Home Assistant restarts.
	- On washer, dishwasher, dryer, and mailbox profiles, configure a separate action for when pending contents are removed or collected; it runs when the main door opens or pending status is cleared.
	- See running state when a profile can infer motion or activity. Opening and contact-only sun-protection profiles show open/closed position instead; last-cycle duration is available for cycle-based profiles.
	- Monitor power and energy independently of activity detection for profiles with a selected power sensor. Use a cumulative energy sensor's total or calculate energy from power.
	- Get a Repairs issue when a configured input is missing or unavailable; the issue clears when the input recovers.
	- Run configured actions in order. Reminders and alarms wait for the previous run to finish before repeating.
	- In compatible profiles, configure an immediate smart-plug-off alarm with its own repeat interval and count; it pauses while the plug state is unavailable and rearms when switched on.

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

Each configured device has a separate config entry. Its profile and any available activity mode are fixed after setup and shown when editing; create a new device to change them. Setup asks for:

In Home Assistant's device registry, every supported profile has a shared parent device, such as "Thermostat (climate entity)". All profile groups appear as soon as at least one Home Activity Manager appliance is configured, even when a profile has no appliances yet. Each appliance remains an independent child device with its own entities, runtime state, and configuration. The profile groups remain while any Home Activity Manager appliance is configured and are removed when the last appliance is deleted.

1. A device profile, name, and activity mode when that profile offers a choice.
2. The required activity source and any optional compatible sensors or controls. A refrigerator requires a door contact; a mailbox requires a separate main-door contact; opening can optionally include a lock.
3. The profile's parameters and actions, when available. Empty parameter forms are skipped.

Editing shows the fixed profile and mode alongside the name, followed by that profile's sensors, parameters, and actions. The activity source can be replaced with a compatible entity. A running cycle retains its start time after replacement unless the new source confirms it has stopped. An unavailable source does not cause a transition.

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