# Donetick Home Assistant Integration

A Home Assistant integration for [Donetick](https://donetick.com) that exposes chores, todo lists, and "things" as native Home Assistant entities — and provides service calls to manage them directly from automations and dashboards.

> [!WARNING]
> This fork requires Donetick server version **0.1.53** or greater.

> [!NOTE]
> This is a community fork of the [official integration](https://github.com/donetick/donetick-hass-integration) with additional features for label-based todo lists, schedule management, undo/skip actions, and bug fixes.

---

## Features

### 📋 Todo Lists

- **All Tasks** — a unified `todo` entity containing every active chore
- **Per-Assignee Lists** — individual `todo` entities per circle member (optional)
- **Per-Label Lists** — one `todo` entity per Donetick label/room (optional, e.g. `todo.kitchen`, `todo.master_bedroom`)
- Full task attributes exposed: name, due date, priority, frequency type, assigned user, labels, and description

### 🏷️ Label-Based Lists

When **Create Label Task Lists** is enabled, one `todo` entity is created for each label in your Donetick circle. This makes it easy to build room-by-room dashboards — each entity only shows chores tagged with that label.

Entity naming follows the pattern `todo.<label_name>` (e.g. `todo.kitchen`, `todo.master_bedroom`).

Each entity exposes a `tasks` attribute with the following fields per task:

| Field | Description |
|---|---|
| `id` | Donetick chore ID |
| `name` | Chore name |
| `status` | Completion status |
| `priority` | 0–4 (4 = highest) |
| `frequency_type` | `daily`, `weekly`, `monthly`, etc. |
| `frequency` | Frequency multiplier |
| `next_due_date` | ISO 8601 datetime |
| `labels` | List of `{id, name, color}` objects |
| `assigned_to` | User ID |
| `description` | Chore description |
| `is_active` | Active status |

### 🔧 Things Integration

Control Donetick "things" as Home Assistant entities:

- **Switch** — boolean things (on/off)
- **Number** — numeric things with increment/decrement
- **Text** — free-text input things

### ⚙️ Services

All services are accessible from **Developer Tools → Services** or from automations and scripts.

#### `donetick.complete_task`
Mark a chore as complete.

| Field | Required | Description |
|---|---|---|
| `task_id` | ✅ | Donetick chore ID |
| `completed_by` | ❌ | User ID to attribute the completion to |
| `config_entry_id` | ❌ | Integration entry (auto-detected if only one) |

#### `donetick.create_task`
Create a new chore.

| Field | Required | Description |
|---|---|---|
| `name` | ✅ | Chore name |
| `description` | ❌ | Chore description |
| `due_date` | ❌ | Due date (RFC 3339, e.g. `2026-04-01T00:00:00Z`) |
| `created_by` | ❌ | User ID of the creator |
| `config_entry_id` | ❌ | Integration entry |

#### `donetick.update_task`
Update a chore's name, description, or due date.

| Field | Required | Description |
|---|---|---|
| `task_id` | ✅ | Donetick chore ID |
| `name` | ❌ | New name |
| `description` | ❌ | New description (empty string clears it) |
| `due_date` | ❌ | New due date (RFC 3339) |
| `config_entry_id` | ❌ | Integration entry |

#### `donetick.delete_task`
Permanently delete a chore.

| Field | Required | Description |
|---|---|---|
| `task_id` | ✅ | Donetick chore ID |
| `config_entry_id` | ❌ | Integration entry |

#### `donetick.skip_task`
Skip the current occurrence of a recurring chore, advancing the due date to the next occurrence without marking it complete.

| Field | Required | Description |
|---|---|---|
| `task_id` | ✅ | Donetick chore ID |
| `config_entry_id` | ❌ | Integration entry |

#### `donetick.undo_complete`
Undo the most recent completion of a chore, restoring its previous due date. Useful when a chore is accidentally marked complete from a dashboard tap action.

| Field | Required | Description |
|---|---|---|
| `task_id` | ✅ | Donetick chore ID |
| `config_entry_id` | ❌ | Integration entry |

#### `donetick.update_schedule`
Update a chore's recurring schedule without deleting and recreating it. Fetches the full chore from Donetick, merges your changes, and PUTs the complete object back — avoiding partial-payload errors from the Donetick API.

| Field | Required | Description |
|---|---|---|
| `task_id` | ✅ | Donetick chore ID |
| `frequency_type` | ❌ | `daily`, `weekly`, `monthly`, `yearly`, `days_of_the_week`, `interval_based`, `once` |
| `frequency` | ❌ | Frequency multiplier (e.g. `2` for every 2 weeks) |
| `is_rolling` | ❌ | `true` = next due calculated from completion time; `false` = fixed schedule anchored to `time_of_day` |
| `time_of_day` | ❌ | Anchor time in `HH:MM` 24-hour format (e.g. `00:00` for midnight) |
| `timezone` | ❌ | Timezone name (default: `America/Chicago`) |
| `next_due_date` | ❌ | Override next due date (ISO 8601) |
| `config_entry_id` | ❌ | Integration entry |

**Example — fix a daily chore to midnight, non-rolling:**
```yaml
service: donetick.update_schedule
data:
  task_id: 189
  is_rolling: false
  time_of_day: "00:00"
  timezone: "America/Chicago"
```

---

## Installation

### Via HACS (recommended)

1. Open HACS in Home Assistant
2. Navigate to **Integrations**
3. Click **⋮** → **Custom repositories**
4. Add: `https://github.com/Ametris/donetick-hass-integration`
5. Category: **Integration**
6. Search for "Donetick" and install
7. Restart Home Assistant

### Manual

1. Copy the `custom_components/donetick/` folder into your HA `custom_components/` directory
2. Restart Home Assistant

---

## Configuration

Go to **Settings → Devices & Services → Add Integration → Donetick**

### Required

| Setting | Description |
|---|---|
| **Server URL** | `https://api.donetick.com` (cloud) or `http://your-host:2021` (self-hosted) |
| **API Token** | Generate from Donetick → Profile → API Token |

### Optional

| Setting | Default | Description |
|---|---|---|
| **Show Due In** | `7` | Days ahead to include in todo lists |
| **Create Unified List** | `true` | Creates `todo.all_tasks` with every active chore |
| **Create Assignee Lists** | `false` | Creates one `todo` entity per circle member |
| **Create Label Task Lists** | `false` | Creates one `todo` entity per Donetick label |

Options can be changed after setup via **Settings → Devices & Services → Donetick → Configure**.

---

## Dashboard Usage

### Room-based chore cards

With **Create Label Task Lists** enabled, you can build per-room chore dashboards using the `tasks` attribute on each label entity:

```yaml
type: custom:button-card
entity: todo.kitchen
tap_action:
  action: call-service
  service: donetick.complete_task
  service_data:
    task_id: "[[[ return entity.attributes.tasks[0].id ]]]"
```

### Undo accidental completions

Add an undo button to recently-completed chore cards:

```yaml
type: custom:button-card
name: Undo
icon: mdi:undo
tap_action:
  action: call-service
  service: donetick.undo_complete
  service_data:
    task_id: 189
```

---

## Notes

- The Donetick external API (`/eapi/v1/`) does not expose a dedicated label endpoint. Label lists are derived by scanning the `labelsV2` field on each task — no additional API requests are made.
- `donetick.update_schedule` performs a read-modify-write (GET then PUT) to work around the Donetick API requirement for a complete chore payload on updates.
- The `undo_complete` service calls Donetick's `/eapi/v1/chore/{id}/uncomplete` endpoint. If a chore has no completion history, the call will fail gracefully and log an error.
- All service calls trigger a refresh of all Donetick `todo` entities after execution.
