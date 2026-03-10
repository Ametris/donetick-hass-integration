"""The Donetick integration."""
import logging
from datetime import date
import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import DOMAIN, CONF_URL, CONF_TOKEN, CONF_SHOW_DUE_IN
from .api import DonetickApiClient

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.TODO, Platform.SENSOR, Platform.SWITCH, Platform.NUMBER, Platform.TEXT]


SERVICE_COMPLETE_TASK = "complete_task"
SERVICE_CREATE_TASK = "create_task"
SERVICE_UPDATE_TASK = "update_task"
SERVICE_DELETE_TASK = "delete_task"
SERVICE_SKIP_TASK = "skip_task"
SERVICE_UNDO_COMPLETE = "undo_complete"
SERVICE_UPDATE_SCHEDULE = "update_schedule"

COMPLETE_TASK_SCHEMA = vol.Schema({
    vol.Required("task_id"): cv.positive_int,
    vol.Optional("completed_by"): cv.positive_int,
    vol.Optional("config_entry_id"): cv.string,
})

CREATE_TASK_SCHEMA = vol.Schema({
    vol.Required("name"): cv.string,
    vol.Optional("description"): cv.string,
    vol.Optional("due_date"): cv.string,
    vol.Optional("created_by"): cv.positive_int,
    vol.Optional("config_entry_id"): cv.string,
})

UPDATE_TASK_SCHEMA = vol.Schema({
    vol.Required("task_id"): cv.positive_int,
    vol.Optional("name"): cv.string,
    vol.Optional("description"): cv.string,
    vol.Optional("due_date"): cv.string,
    vol.Optional("config_entry_id"): cv.string,
})

DELETE_TASK_SCHEMA = vol.Schema({
    vol.Required("task_id"): cv.positive_int,
    vol.Optional("config_entry_id"): cv.string,
})

SKIP_TASK_SCHEMA = vol.Schema({
    vol.Required("task_id"): cv.positive_int,
    vol.Optional("config_entry_id"): cv.string,
})

UNDO_COMPLETE_SCHEMA = vol.Schema({
    vol.Required("task_id"): cv.positive_int,
    vol.Optional("config_entry_id"): cv.string,
})

UPDATE_SCHEDULE_SCHEMA = vol.Schema({
    vol.Required("task_id"): cv.positive_int,
    vol.Optional("frequency_type"): cv.string,
    vol.Optional("frequency"): cv.positive_int,
    vol.Optional("is_rolling"): cv.boolean,
    vol.Optional("time_of_day"): cv.string,   # HH:MM in local time
    vol.Optional("timezone"): cv.string,
    vol.Optional("next_due_date"): cv.string,
    vol.Optional("config_entry_id"): cv.string,
})

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Donetick from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        CONF_URL: entry.data[CONF_URL],
        CONF_TOKEN: entry.data[CONF_TOKEN],
        CONF_SHOW_DUE_IN: entry.data.get(CONF_SHOW_DUE_IN,7),
    }
    
    # Register services before setting up platforms
    async def complete_task_handler(call: ServiceCall) -> None:
        await async_complete_task_service(hass, call)
    
    async def create_task_handler(call: ServiceCall) -> None:
        await async_create_task_service(hass, call)
    
    async def update_task_handler(call: ServiceCall) -> None:
        await async_update_task_service(hass, call)
    
    async def delete_task_handler(call: ServiceCall) -> None:
        await async_delete_task_service(hass, call)

    async def skip_task_handler(call: ServiceCall) -> None:
        await async_skip_task_service(hass, call)

    async def undo_complete_handler(call: ServiceCall) -> None:
        await async_undo_complete_service(hass, call)

    async def update_schedule_handler(call: ServiceCall) -> None:
        await async_update_schedule_service(hass, call)
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_COMPLETE_TASK,
        complete_task_handler,
        schema=COMPLETE_TASK_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_TASK,
        create_task_handler,
        schema=CREATE_TASK_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_TASK,
        update_task_handler,
        schema=UPDATE_TASK_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_TASK,
        delete_task_handler,
        schema=DELETE_TASK_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SKIP_TASK,
        skip_task_handler,
        schema=SKIP_TASK_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_UNDO_COMPLETE,
        undo_complete_handler,
        schema=UNDO_COMPLETE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_SCHEDULE,
        update_schedule_handler,
        schema=UPDATE_SCHEDULE_SCHEMA,
    )
    _LOGGER.debug(
        "Registered services: %s.%s, %s.%s, %s.%s, %s.%s, %s.%s, %s.%s, %s.%s",
        DOMAIN, SERVICE_COMPLETE_TASK, DOMAIN, SERVICE_CREATE_TASK,
        DOMAIN, SERVICE_UPDATE_TASK, DOMAIN, SERVICE_DELETE_TASK,
        DOMAIN, SERVICE_SKIP_TASK, DOMAIN, SERVICE_UNDO_COMPLETE,
        DOMAIN, SERVICE_UPDATE_SCHEDULE,
    )
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.add_update_listener(async_reload_entry)
    
    return True

async def async_complete_task_service(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the complete_task service call."""
    task_id = call.data["task_id"]
    completed_by = call.data.get("completed_by")
    config_entry_id = call.data.get("config_entry_id")
    
    # Find the config entry to use
    entry = None
    if config_entry_id:
        # Check if it's a config entry ID
        entry = hass.config_entries.async_get_entry(config_entry_id)
        
        # If not found, check if it's an entity ID and extract config entry from it
        if not entry and config_entry_id.startswith("todo."):
            entity_registry = er.async_get(hass)
            entity_entry = entity_registry.async_get(config_entry_id)
            if entity_entry:
                entry = hass.config_entries.async_get_entry(entity_entry.config_entry_id)
        
        if not entry:
            _LOGGER.error("Config entry not found for: %s", config_entry_id)
            return
    else:
        # Use the first Donetick integration if no specific entry provided
        entries = [entry for entry in hass.config_entries.async_entries(DOMAIN)]
        if not entries:
            _LOGGER.error("No Donetick integration found")
            return
        entry = entries[0]
    
    # Get API client
    session = async_get_clientsession(hass)
    client = DonetickApiClient(
        hass.data[DOMAIN][entry.entry_id][CONF_URL],
        hass.data[DOMAIN][entry.entry_id][CONF_TOKEN],
        session,
    )
    
    try:
        result = await client.async_complete_task(task_id, completed_by)
        _LOGGER.info("Task %d completed successfully by user %s", task_id, completed_by or "default")
        
        # Trigger coordinator refresh for all todo entities
        entity_registry = er.async_get(hass)
        for entity_id in hass.states.async_entity_ids("todo"):
            if entity_id.startswith("todo.dt_"):
                entity_entry = entity_registry.async_get(entity_id)
                if entity_entry and entity_entry.config_entry_id == entry.entry_id:
                    # Trigger update - this will refresh the coordinator
                    hass.async_create_task(
                        hass.helpers.entity_component.async_update_entity(entity_id)
                    )
                    
    except Exception as e:
        _LOGGER.error("Failed to complete task %d: %s", task_id, e)

async def async_create_task_service(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the create_task service call."""
    name = call.data["name"]
    description = call.data.get("description")
    due_date = call.data.get("due_date")
    created_by = call.data.get("created_by")
    config_entry_id = call.data.get("config_entry_id")
    
    # Find the config entry to use
    entry = await _get_config_entry(hass, config_entry_id)
    if not entry:
        return
    
    # Get API client
    session = async_get_clientsession(hass)
    client = DonetickApiClient(
        hass.data[DOMAIN][entry.entry_id][CONF_URL],
        hass.data[DOMAIN][entry.entry_id][CONF_TOKEN],
        session,
    )
    
    try:
        result = await client.async_create_task(name, description, due_date, created_by)
        _LOGGER.info("Task '%s' created successfully with ID %d", name, result.id)
        
        # Trigger coordinator refresh for all todo entities
        await _refresh_todo_entities(hass, entry.entry_id)
                    
    except Exception as e:
        _LOGGER.error("Failed to create task '%s': %s", name, e)

async def async_update_task_service(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the update_task service call."""
    task_id = call.data["task_id"]
    name = call.data.get("name")
    description = call.data.get("description")
    due_date = call.data.get("due_date")
    config_entry_id = call.data.get("config_entry_id")
    
    # Find the config entry to use
    entry = await _get_config_entry(hass, config_entry_id)
    if not entry:
        return
    
    # Get API client
    session = async_get_clientsession(hass)
    client = DonetickApiClient(
        hass.data[DOMAIN][entry.entry_id][CONF_URL],
        hass.data[DOMAIN][entry.entry_id][CONF_TOKEN],
        session,
    )
    
    try:
        result = await client.async_update_task(task_id, name, description, due_date)
        _LOGGER.info("Task %d updated successfully", task_id)
        
        # Trigger coordinator refresh for all todo entities
        await _refresh_todo_entities(hass, entry.entry_id)
                    
    except Exception as e:
        _LOGGER.error("Failed to update task %d: %s", task_id, e)

async def async_delete_task_service(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the delete_task service call."""
    task_id = call.data["task_id"]
    config_entry_id = call.data.get("config_entry_id")
    
    # Find the config entry to use
    entry = await _get_config_entry(hass, config_entry_id)
    if not entry:
        return
    
    # Get API client
    session = async_get_clientsession(hass)
    client = DonetickApiClient(
        hass.data[DOMAIN][entry.entry_id][CONF_URL],
        hass.data[DOMAIN][entry.entry_id][CONF_TOKEN],
        session,
    )
    
    try:
        success = await client.async_delete_task(task_id)
        if success:
            _LOGGER.info("Task %d deleted successfully", task_id)
            
            # Trigger coordinator refresh for all todo entities
            await _refresh_todo_entities(hass, entry.entry_id)
        else:
            _LOGGER.error("Failed to delete task %d", task_id)
                    
    except Exception as e:
        _LOGGER.error("Failed to delete task %d: %s", task_id, e)

async def async_skip_task_service(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the skip_task service call."""
    task_id = call.data["task_id"]
    config_entry_id = call.data.get("config_entry_id")

    entry = await _get_config_entry(hass, config_entry_id)
    if not entry:
        return

    session = async_get_clientsession(hass)
    client = DonetickApiClient(
        hass.data[DOMAIN][entry.entry_id][CONF_URL],
        hass.data[DOMAIN][entry.entry_id][CONF_TOKEN],
        session,
    )

    try:
        await client.async_skip_task(task_id)
        _LOGGER.info("Task %d skipped successfully", task_id)
        await _refresh_todo_entities(hass, entry.entry_id)
    except Exception as e:
        _LOGGER.error("Failed to skip task %d: %s", task_id, e)


async def async_undo_complete_service(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the undo_complete service call."""
    task_id = call.data["task_id"]
    config_entry_id = call.data.get("config_entry_id")

    entry = await _get_config_entry(hass, config_entry_id)
    if not entry:
        return

    session = async_get_clientsession(hass)
    client = DonetickApiClient(
        hass.data[DOMAIN][entry.entry_id][CONF_URL],
        hass.data[DOMAIN][entry.entry_id][CONF_TOKEN],
        session,
    )

    try:
        await client.async_uncomplete_task(task_id)
        _LOGGER.info("Task %d completion undone successfully", task_id)
        await _refresh_todo_entities(hass, entry.entry_id)
    except Exception as e:
        _LOGGER.error("Failed to undo completion for task %d: %s", task_id, e)


async def async_update_schedule_service(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the update_schedule service call.

    Accepts human-friendly fields (time_of_day, timezone) and builds the
    correct frequencyMetadata dict before delegating to the API client.
    """
    task_id = call.data["task_id"]
    config_entry_id = call.data.get("config_entry_id")

    entry = await _get_config_entry(hass, config_entry_id)
    if not entry:
        return

    session = async_get_clientsession(hass)
    client = DonetickApiClient(
        hass.data[DOMAIN][entry.entry_id][CONF_URL],
        hass.data[DOMAIN][entry.entry_id][CONF_TOKEN],
        session,
    )

    # Build frequencyMetadata from convenience fields
    frequency_metadata = None
    time_of_day = call.data.get("time_of_day")
    timezone = call.data.get("timezone", "America/Chicago")
    if time_of_day:
        # Donetick expects a full datetime string for the time field, but
        # the API will extract just the HH:MM portion. We send today's date
        # with the requested time in the configured timezone.
        today = date.today().isoformat()
        frequency_metadata = {"time": f"{today}T{time_of_day}:00", "timezone": timezone}

    try:
        await client.async_update_task_schedule(
            task_id=task_id,
            frequency_type=call.data.get("frequency_type"),
            frequency=call.data.get("frequency"),
            frequency_metadata=frequency_metadata,
            is_rolling=call.data.get("is_rolling"),
            next_due_date=call.data.get("next_due_date"),
        )
        _LOGGER.info("Schedule for task %d updated successfully", task_id)
        await _refresh_todo_entities(hass, entry.entry_id)
    except Exception as e:
        _LOGGER.error("Failed to update schedule for task %d: %s", task_id, e)


async def _get_config_entry(hass: HomeAssistant, config_entry_id: str = None) -> ConfigEntry:
    """Get the config entry to use for the service call."""
    entry = None
    if config_entry_id:
        # Check if it's a config entry ID
        entry = hass.config_entries.async_get_entry(config_entry_id)
        
        # If not found, check if it's an entity ID and extract config entry from it
        if not entry and config_entry_id.startswith("todo."):
            entity_registry = er.async_get(hass)
            entity_entry = entity_registry.async_get(config_entry_id)
            if entity_entry:
                entry = hass.config_entries.async_get_entry(entity_entry.config_entry_id)
        
        if not entry:
            _LOGGER.error("Config entry not found for: %s", config_entry_id)
            return None
    else:
        # Use the first Donetick integration if no specific entry provided
        entries = [entry for entry in hass.config_entries.async_entries(DOMAIN)]
        if not entries:
            _LOGGER.error("No Donetick integration found")
            return None
        entry = entries[0]
    
    return entry

async def _refresh_todo_entities(hass: HomeAssistant, config_entry_id: str) -> None:
    """Refresh all todo entities for the given config entry."""
    entity_registry = er.async_get(hass)
    for entity_id in hass.states.async_entity_ids("todo"):
        if entity_id.startswith("todo.dt_"):
            entity_entry = entity_registry.async_get(entity_id)
            if entity_entry and entity_entry.config_entry_id == config_entry_id:
                # Trigger update - this will refresh the coordinator
                hass.async_create_task(
                    hass.helpers.entity_component.async_update_entity(entity_id)
                )

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        
        # Remove services if this is the last config entry
        if not hass.data[DOMAIN]:
            for service_name in [
                SERVICE_COMPLETE_TASK, SERVICE_CREATE_TASK,
                SERVICE_UPDATE_TASK, SERVICE_DELETE_TASK,
                SERVICE_SKIP_TASK, SERVICE_UNDO_COMPLETE,
                SERVICE_UPDATE_SCHEDULE,
            ]:
                if hass.services.has_service(DOMAIN, service_name):
                    hass.services.async_remove(DOMAIN, service_name)
            _LOGGER.debug(
                "Removed services: %s.%s, %s.%s, %s.%s, %s.%s, %s.%s, %s.%s, %s.%s",
                DOMAIN, SERVICE_COMPLETE_TASK, DOMAIN, SERVICE_CREATE_TASK,
                DOMAIN, SERVICE_UPDATE_TASK, DOMAIN, SERVICE_DELETE_TASK,
                DOMAIN, SERVICE_SKIP_TASK, DOMAIN, SERVICE_UNDO_COMPLETE,
                DOMAIN, SERVICE_UPDATE_SCHEDULE,
            )
    
    return unload_ok

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
