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

**Turn a non-smart appliance into a Home Assistant device.** Home Activity Manager groups its existing entities, such as a smart plug's power sensor and a door contact, under one dedicated device in Home Assistant. The appliance stays physically unchanged, while its activity, controls, reminders, and alarms are managed together. No cloud service, credentials, external helpers, or automations are needed. Its extensible profiles cover climate control, large appliances (laundry and refrigeration), animal care, deliveries, electronics, openings, and sun protection.

**Last updated:** 2026-11-11

## Installation

### Marketplace (formerly HACS)

This integration is not listed in the Marketplace yet. Add it as a custom repository:

1. In Home Assistant 2026.11 or newer, go to **Settings** > **Marketplace**.
2. Select **Add from link**, enter `https://github.com/PacmanForever/home_activity_manager`, and select **Add**. If prompted, choose **Integration**.
3. Open **Home Activity Manager** and select **Install**.
4. Complete the setup flow that opens. If you close it, go to **Settings** > **Devices & services** > **Add integration** and search for **Home Activity Manager**.

On Home Assistant 2026.10 and older, add `https://github.com/PacmanForever/home_activity_manager` as a custom integration repository in HACS.

### Manual

Download or clone this repository and copy `custom_components/home_activity_manager` into the `custom_components` directory of your Home Assistant configuration. Restart Home Assistant, then add **Home Activity Manager** from **Settings > Devices & services**.

The integration works on supported Home Assistant versions; displaying its local icon and logo requires Home Assistant 2026.3 or newer.

## Configuration

Appliances are organized in three levels: **group**, **appliance class**, and **activity-detection mode**. The mode labels use the same wording in the setup selector:

```text
Climate control
|-- Air conditioner
|   |-- Activity detection with a contact sensor
|   |-- Activity detection with a power sensor
|   `-- Activity detection with a climate entity
|-- Fan
|   |-- Activity detection with a power sensor
|   |-- Activity detection with a switch
|   `-- Activity detection with a fan entity
`-- Thermostat
    `-- Activity detection with a climate entity

Deliveries
`-- Mailbox
    |-- Activity detection with a mail-slot contact sensor
    `-- Activity detection with an interior motion sensor

Large appliances
|-- Washer
|   `-- Activity detection with a power sensor
|-- Dryer
|   `-- Activity detection with a power sensor
|-- Dishwasher
|   `-- Activity detection with a power sensor
|-- Refrigerator
|   |-- Activity detection with a power sensor
|   `-- Activity detection with a switch
`-- Freezer
    |-- Activity detection with a power sensor
    `-- Activity detection with a switch

Animal care
`-- Aquarium
    |-- Activity detection with a switch
    `-- Activity detection with a power sensor

Openings
|-- Door
|   `-- Activity detection with a contact sensor
|-- Sliding
|   `-- Activity detection with a contact sensor
|-- Access (garage, shop, warehouse, etc.)
|   |-- Activity detection with a contact sensor
|   `-- Activity detection with a cover entity
`-- Window
    `-- Activity detection with a contact sensor

Sun protection
`-- Awning
    |-- Activity detection with a contact sensor
    `-- Activity detection with a cover entity

Electronics
|-- Screen
|   |-- Activity detection with a switch
|   `-- Activity detection with a media player
|-- AV equipment
|   |-- Activity detection with a switch
|   `-- Activity detection with a media player
|-- Console
|   `-- Activity detection with a switch
`-- Computer (PC or NAS)
    `-- Activity detection with a switch

Small appliances
|-- Generic appliance
|   `-- Activity detection with a switch
`-- Robot vacuum
    `-- Activity detection with a vacuum entity
```
Group, appliance-class, and activity-mode choices are sorted alphabetically by their translated labels in the active Home Assistant language.

### Activity detection examples

The entity IDs below are examples; select entities from your own Home Assistant instance. The activity source answers one question: what state or measurement should start and end this appliance's activity cycle?

| Group | Profile and mode | Example source | What counts as active |
| --- | --- | --- | --- |
| Climate control | Air conditioner: contact | `binary_sensor.air_conditioner_running` | `on` starts activity; `off` ends it. The sensor should represent the air conditioner's active state. |
| Climate control | Air conditioner: power | `sensor.air_conditioner_power` | Power must stay above the configured start threshold for its confirmation time. Activity ends after it stays below the finish threshold for its confirmation time. |
| Climate control | Air conditioner: climate entity | `climate.living_room` | The climate mode is the activity source: `off` is stopped and any other mode is active, including when `hvac_action` is idle. The original climate controls remain available. |
| Climate control | Thermostat | `climate.living_room` | Any climate state other than `off` is active, including when the thermostat is idle; `off` ends activity. |
| Climate control | Fan: power | `sensor.fan_power` | Power must stay above the configured start threshold for its confirmation time; it ends after staying below the finish threshold for its confirmation time. |
| Climate control | Fan: switch | `switch.fan` | `on` starts activity and `off` ends it. Optional power and energy sensors are measurements only. |
| Climate control | Fan: entity | `fan.living_room` | `on` starts activity and `off` ends it. Speed changes do not restart activity; `unknown` and `unavailable` do not change it. |
| Small appliances | Generic appliance | `switch.coffee_maker` | `on` starts activity and `off` ends it. Optional power and energy sensors are measurements only. |
| Small appliances | Robot vacuum | `vacuum.living_room` | `cleaning`, `returning`, and `paused` are active; `idle` and `docked` are inactive. Error and unavailable states do not change activity. |
| Electronics | Screen or AV equipment: switch | `switch.living_room_screen` | `on` starts activity and `off` ends it. Optional power and energy sensors are measurements only. |
| Electronics | Screen or AV equipment: media player | `media_player.living_room_tv` | `off` ends activity; any other available state means active. `unknown` and `unavailable` do not change activity. |
| Electronics | Console or computer (PC/NAS): switch | `switch.home_server` | `on` starts activity and `off` ends it. Optional power and energy sensors are measurements only. |
| Deliveries | Mailbox: interior motion | `binary_sensor.mailbox_motion` plus `binary_sensor.front_door` | A new motion `on` transition records an arrival. Opening the main-door contact ends the pending collection. |
| Deliveries | Mailbox: mail-slot contact | `binary_sensor.mail_slot` plus `binary_sensor.front_door` | A new slot-contact `on` transition records an arrival. Opening the main-door contact ends the pending collection. |
| Large appliances | Washer | `sensor.washer_power` | Uses the configured power thresholds and confirmation times to detect a cycle. |
| Large appliances | Dryer | `sensor.dryer_power` | Uses the configured power thresholds and confirmation times to detect a cycle. |
| Large appliances | Dishwasher | `sensor.dishwasher_power` | Uses the configured power thresholds and confirmation times to detect a cycle. |
| Openings | Door: contact | `binary_sensor.front_door_contact` | `on` means open and starts activity; `off` means closed and ends it. |
| Openings | Access: contact | `binary_sensor.garage_contact` | `on` means open and starts activity; `off` means closed and ends it. |
| Openings | Access: cover | `cover.garage_door` | A settled `open` state starts activity and `closed` ends it. `opening` and `closing` keep the last settled state and do not trigger actions. |
| Openings | Window: contact | `binary_sensor.bedroom_window_contact` | `on` means open and starts activity; `off` means closed and ends it. |
| Large appliances | Refrigerator: power | `sensor.refrigerator_power` plus `binary_sensor.refrigerator_door` | Power detects compressor activity; the required door contact supports the door-open alarm. |
| Large appliances | Refrigerator: switch | `switch.refrigerator_plug` plus `binary_sensor.refrigerator_door` | The switch state detects activity (`on` active, `off` inactive); the required door contact supports the door-open alarm. |
| Large appliances | Freezer: power | `sensor.freezer_power` plus `binary_sensor.freezer_door` | Power detects compressor activity; the required door contact supports the door-open alarm. |
| Large appliances | Freezer: switch | `switch.freezer_plug` plus `binary_sensor.freezer_door` | The switch state detects activity (`on` active, `off` inactive); the required door contact supports the door-open alarm. |
| Animal care | Aquarium: switch | `switch.aquarium_plug` | The switch detects activity; optional sensors can report power, cumulative energy, illuminance, water temperature, pH, and water level. |
| Animal care | Aquarium: power | `sensor.aquarium_power` | Power thresholds detect activity; a switch, cumulative energy sensor, and the same optional readings can also be configured. |
| Sun protection | Awning: contact | `binary_sensor.awning_position` | Tracks open/closed position and cycle duration, not motor movement; it does not create a `running` entity. |
| Sun protection | Awning: cover | `cover.awning` | A settled `open` state is active and `closed` is inactive. `opening` and `closing` keep the last settled state. |

### Climate control

- **Air conditioner:** choose contact-sensor, power-based, or climate-entity activity detection. Contact mode requires its binary sensor; power mode uses configurable thresholds and confirmation times. Climate mode requires an existing climate entity, keeps its original controls, and follows `off` versus any active mode regardless of `hvac_action`.
- **Thermostat:** use an existing climate entity as the activity source. If it has no device, the original entity is associated directly with the managed device and no proxy is created. If it already belongs to a device, that association is preserved and a native climate proxy is added to the managed device. In both cases the source remains owned by its original integration. Proxies mirror standard climate state and controls and forward standard climate actions; vendor-specific services are not proxied. Activity follows climate mode (`off` versus any active mode), including periods when `hvac_action` is idle.
- **Fan:** choose a required power sensor with configurable thresholds, a required switch, or a required fan entity. Switch and fan-entity modes use `on`/`off`; speed changes do not restart fan-entity activity, and unknown or unavailable states do not change it. Optional power and cumulative-energy sensors are measurements only. All modes expose running state, last active duration, and configurable start/end actions.

### Small appliances

The generic appliance profile requires a switch as its activity source; optional power and cumulative-energy sensors provide readings only. The robot-vacuum profile requires a vacuum entity. `cleaning`, `returning`, and `paused` are active, while `idle` and `docked` are inactive; `error`, `unknown`, and `unavailable` preserve the current activity state. The original source remains owned by its integration. If it has no device, it is associated directly with the managed appliance; otherwise, Home Activity Manager adds a native proxy that mirrors supported state and forwards supported controls.

### Deliveries

Mailbox profiles detect arrivals with either an interior motion sensor or a mail-slot contact. Both modes require a separate main-door contact and track the cycle until collection. Mail-slot mode also exposes the contact's open/closed state as **Mail slot**. Pending mail is shown as **Pending to unload** until collection; this is separate from the flap and main-door positions. Start actions run on arrival; finish actions run when the main door opens or pending collection is cleared. Reminders are separate.

### Large appliances

Washer, dryer, and dishwasher profiles detect cycles from power thresholds and configurable confirmation times. Each appliance can optionally monitor its door, control a switch, track pending unloading, and send reminders. Opening the door during an active cycle clears pending unloading without running the **Emptied** action. If the door is closed again before the cycle ends, pending unloading is re-armed at cycle completion so an interim opening to add items does not suppress the post-cycle reminder. An open or unavailable door at cycle completion does not re-arm it. Refrigerator and freezer profiles detect compressor activity from power or use a switch as the activity source; both require a door contact and support the door-open alarm. A switch selected alongside power is an optional control and does not change activity detection.

### Animal care

Aquarium profiles use either a required switch or a required power sensor as the activity source. Both profiles accept an optional cumulative energy sensor; otherwise, the total is calculated from power when available. Optional readings also include power, illuminance, water temperature, pH, and water level, depending on the selected profile. Illuminance is a sensor reading, not a light-control entity. The group exposes cycle-start and cycle-end shared actions.

### Electronics

Screens and AV equipment can use either a required switch or a required media-player entity. Consoles and computers (including PCs and NAS devices, shown as **Ordinador** in Catalan) use a required switch. Switch mode follows `on`/`off`; media-player mode treats `off` as inactive and any other available state as active. `unknown` and `unavailable` preserve the current activity state. Optional power and cumulative-energy sensors provide readings only and never override the selected activity source. Media-player proxies mirror standard state and supported features and forward supported controls.

### Openings

The duration labels refer to the most recently completed period that the door, window, access, awning, or shutter was open. While it is open, the sensor retains the previous completed value; until the first open period ends, its value is unknown. The duration measures the settled open interval, not how long a motor took to open it.

When an optional lock is configured for an opening, the device also exposes **Duration of the last unlocked period**. It measures the stable `unlocked` interval until the lock reports `locked`; transient `unlocking` and `locking` states do not end or restart it. The value is unknown until the first completed unlock interval and is restored after restart. No duration entity is created when no lock is configured.

A configured lock also exposes a binary **Lock state** sensor with Home Assistant's `lock` device class: `on` means unlocked and `off` means locked. Transitional states retain the last stable state; `unknown` and `unavailable` are reflected as unknown or unavailable. The entity is omitted when no lock is configured.

Windows and sliding closures use a required contact sensor, and conventional doors use contact detection with an optional associated shutter. The primary contact state is named for its class, such as **Window state**, **Sliding state**, or **Door state**; an associated shutter is separately named **Shutter state**. Each has its own last-open duration sensor, so the window/door duration is independent of the shutter duration. Optional shutter sources can be cleared directly in their entity selectors; if both source types are selected, clear one of them to resolve the validation error. **Access** is for openings whose primary role is to let people or vehicles enter or leave a space, such as a garage, shop, or warehouse. This is a functional distinction, not a statement about size or motorization. Access can use a required contact sensor or a cover entity as its primary detector; it does not have a second associated cover. Its **Access state** binary sensor means open/closed, not motor movement. A lock is optional in either mode and reports its own state; it does not determine whether the access is open or closed. For a primary cover, `open` starts the duration interval and `closed` ends it; actions run only after the entity settles at one of those states, not while it is `opening` or `closing`. The duration is time open, not time the motor runs. A configured cover or lock with no device is reused directly on the managed device; one already assigned to a device keeps that association and is represented by a native proxy. An associated shutter on a contact-mode door also exposes its open/closed state.
- **Durada d'obertura**: les etiquetes dels sensors indiquen explícitament el temps que la porta, la finestra, l'accés, el tendal o la persiana ha estat oberta. Mesuren l'interval en estat estable obert, no el temps que ha trigat el motor a obrir.
- **Durada de l'últim període actiu**: sensor de sortida amb la durada del període d'activitat més recent detectat.

### Sun protection

- **Contact-sensor mode:** exposes open/closed position, not motor movement, so it has no `running` entity. Contact transitions still track actions and duration.
- **Cover mode:** settled `open` is active and settled `closed` is inactive; `opening` and `closing` retain the last settled state. If the cover has no device, it is associated directly with the managed device. If it already belongs to a device, that association remains unchanged and a native cover proxy is added to the managed device. Proxies forward standard controls; vendor-specific services are not proxied.

### Shared behavior

- Cycle, reminder, and alarm state is restored after Home Assistant restarts. Configured actions run in order; reminders and alarms wait for the previous run to finish before repeating.
- Running state is exposed when a profile can infer activity. Opening and contact-only sun-protection profiles expose position instead; cycle-based profiles expose last-cycle duration.
- Power and energy can be monitored independently of activity detection where supported. Energy uses a selected cumulative sensor or is calculated from power.
- Cycle-capable devices with configured power or cumulative energy also expose **Energy consumed in the last cycle**. It is unknown until a measured cycle completes and retains that completed value while the next cycle runs. A selected cumulative sensor takes precedence and its start-to-finish difference is used; otherwise, power is integrated during confirmed activity. This result is independent of total energy and its reset button. An unavailable or reset cumulative source does not fall back to power.
- One Repairs issue is raised per configured input entity when it is missing or unavailable, even if multiple appliances share that entity. Startup availability is checked after Home Assistant finishes starting, avoiding transient issues while source integrations are still loading. The issue clears when the input recovers.
- Compatible profiles can configure an immediate switch-off alarm with its own repeat interval and count. It pauses while the switch state is unavailable and rearms when switched on.

### Group actions

Configure shared actions from the group's options. The offered hooks are the ordered union of hooks supported by profiles under that group. Each appliance runs a shared action only when its own profile supports that hook and its configured source emits the event; optional lock and shutter hooks, for example, run only for an appliance with that configured capability. A group action is not a single once-per-group event. Each event is determined by that appliance's own activity source and applicable parameters. For timed hooks, timers and repeat limits come from the appliance's parameters, not the group action settings. This applies to maximum-runtime actions, pending reminders, and door, compressor, or switch alarms. A hook runs only when that appliance emits the corresponding event; for example, the maximum-runtime hook requires a maximum runtime to be configured. Omitted optional values use the integration's defaults. Repeat counts are additional runs after the first, so three additional repeats allow up to four runs for that appliance.

For example, the shared switch-off action runs immediately for each appliance whose switch turns off. That appliance's repeat interval and additional-repeat count control later runs independently of the other appliances in the group. The first action is not counted as a repeat. These alarm parameters are configured with the appliance, not in the group actions form.

| Group | Hooks offered across its profiles |
| --- | --- |
| Climate control | Activity starts, activity ends, switch off |
| Deliveries | Arrival, collection reminder, collected |
| Large appliances | Activity starts, activity ends, maximum runtime, pending unload, emptied, switch off, door-open alarm |
| Animal care | Activity starts, activity ends |
| Openings | Activity starts, activity ends, lock locked, lock unlocked, shutter open, shutter closed |
| Sun protection | Activity starts, activity ends |
| Electronics | Activity starts, activity ends |

Group action templates receive `ham_device_name` (the managed Home Assistant device's name), `ham_device_area_name` (its assigned area, or `None`), and `ham_source_class` (the configured appliance class, translated into Home Assistant's language). These describe the appliance whose group action is running, not the entity that triggered it. When a configured input entity triggers the action, `ham_source_entity_id` contains that original entity ID, not this integration's proxy entity. Timer-triggered actions still receive `ham_source_class`, but do not define `ham_source_entity_id`.

For example, add a notification action to the shared activity-start hook. Replace the notify entity with one from your Home Assistant setup:

```yaml
- action: notify.send_message
    target:
        entity_id: notify.mobile_app_phone
    data:
        message: "{{ ham_source_class }}: {{ ham_device_area_name or ham_device_name }}: activity started"
```

To include the source entity in a message, use `{{ ham_source_entity_id | default('timer', true) }}` so timer-triggered actions have a fallback value. The previous names `ham_appliance_name` and `ham_area_name` remain available as aliases for existing templates.

Each group has one config entry. From a group's options, choose **Add a device** to add an appliance directly to that group. The add flow asks for the device name, offers an optional area selector, and shows its group as a read-only value. The selected area is applied only to the new appliance; leaving it blank creates the device without an area and does not change existing devices. Initial setup keeps Home Assistant's native name-and-area confirmation, so the first appliance is not asked twice. Unnamed existing devices use their translated appliance class as a fallback name. Management actions are listed alphabetically in the active language, and device removal requires confirmation. The appliance class is stored separately from its functional profile and drives class-specific device metadata; the displayed name remains editable. Existing per-appliance entries are consolidated automatically during migration. Legacy laundry and refrigeration entries become one Large appliances group; their shared action lists are combined, duplicate actions are removed, and appliance IDs, entity IDs, registry customizations, local options, and runtime state are preserved. Setup asks for:

Each group entry groups its appliances on the integration page. Only configured appliances are registered as devices; the group itself is not added as an empty device.

1. A group, appliance class, editable name, and activity mode when that profile offers a choice.
2. The required activity source and any optional compatible sensors or controls. A refrigerator requires a door contact; a mailbox requires a separate main-door contact; a contact-based door can optionally include a lock and one associated shutter source (contact or cover).
3. The profile's parameters and actions, when available. Empty parameter forms are skipped.

Editing shows the fixed group, class, and mode alongside the name, followed by that profile's sensors, parameters, and actions. The activity source can be replaced with a compatible entity. A running cycle retains its start time after replacement unless the new source confirms it has stopped. An unavailable source does not cause a transition.

Each device-type-and-mode profile uses its own sensor, parameter and action fields. Cycle-start and cycle-end actions use the same labels across profiles; opening actions describe open/closed transitions. Optional lock and shutter actions appear only when that input is configured.

Where a profile exposes total energy, a cumulative energy sensor can be selected independently of the activity source. Its total is displayed in kWh and is never changed by this integration. If no external sensor is selected, profiles with a total-energy output calculate a persistent total from power readings. The reset button appears when power and a total-energy output are both available. It resets the integration's displayed energy total to zero without writing to the external sensor; when an external sensor is selected, its current reading becomes the reset baseline and later increases are shown as consumption since reset. The calculated total is maintained separately, so switching energy sources can change the displayed total; an unavailable external sensor does not fall back to the calculated total.

Power-cycle defaults are 4 W for 15 seconds to start and 1 W for 60 seconds to finish. Durations are stored in seconds, selected with native duration controls, and limited to 24 hours. An auxiliary switch controls the managed device's power but does not override its selected activity source. In power-based profiles, the power sensor determines when activity ends; in the switch-based refrigerator profile, the switch itself determines activity. Laundry pending-unload reminders and refrigerator door alarms run once, then repeat up to the configured number of additional repetitions. The switch-off alarm is available only in profiles that declare it; refrigerator switches do not trigger alarms.

## Entities and automations

Outputs depend on the selected profile and configured inputs. A selected power sensor provides a power entity; an energy sensor or power sensor provides an energy entity. Cycle-based profiles provide activity state and last-activity duration; estimated remaining time is limited to laundry profiles. Both refrigerator modes expose activity and a door-open alarm; neither has a compressor-inactivity or switch-off alarm. Mailboxes expose their main-door and pending-collection states, plus a button to clear pending status. Detecting mail starts the mailbox cycle and runs its start actions; opening the main door or pressing the clear button ends the cycle, runs its end actions, and cancels reminders. A selected switch is exposed on the managed device. Contact-based doors with an associated shutter expose its open/closed state.

**HAM proxies** are duplicates: HAM creates a separate entity on the appliance device while leaving the source entity intact. For a visible input that can be reused directly, HAM associates an unassigned source with the appliance and does not create a duplicate; if the source already belongs to another device, that association stays in place and HAM adds a proxy. This applies across supported sensor, switch, contact, climate, media-player, fan, vacuum, cover, and lock inputs. Inputs used only internally, such as mailbox arrival motion, are not shown or associated. Calculated outputs such as **Running**, durations, pending status, and locally calculated energy are not proxies.

An external cumulative-energy sensor is the exception: HAM always creates an energy proxy so its displayed total can use a local reset baseline without writing to the original sensor. By default, every proxy has a name ending in `(HAM Proxy)` and an `entity_id` ending in `_ham_proxy`. It uses the source's custom name, then its integration name, or a translated source-type fallback if neither exists. For covers, the fallback uses the translated device class when available: an awning is **Awning**, a blind is **Blind**, and a shutter is **Shutter** in English. Unclassified covers use the generic **Cover** fallback. In Catalan these are **Tendal** for an awning and **Persiana** for a blind or shutter, with **Coberta** for an unclassified cover. Home Assistant adds the device context where relevant; the proxy's `entity_id` remains stable. Climate, media-player, fan, vacuum, cover, and lock proxies mirror standard state and supported features and forward supported actions. Direct association preserves the source name; the source remains owned by its original integration. On unload or removal, HAM releases only direct associations that still point to its device and removes only its own stale proxies.

Contact-based doors with an associated shutter expose a separate last-open duration sensor for each layer. The shutter duration sensor is present only while a shutter source is configured.

Integration outputs update with their sources, including unknown, unavailable, missing, and recovered states. Power and energy are displayed in W and kWh. When a power source is unavailable, its output does not present the previous reading as current; the integration retains its internal state without falsely ending the cycle.

External automations can react to state changes of the running and pending-status binary sensors. The integration does not currently fire custom events on the Home Assistant event bus. Pending laundry unload or mailbox collection clears when its main door opens or when the clear button is pressed.

Runtime state is restored after Home Assistant restarts. The integration does not create external helpers, scripts, or automations, and it does not remove selected external entities when a device entry is deleted.

## License

This project is distributed under the GNU General Public License v3.0. See [LICENSE](LICENSE) for the full text.