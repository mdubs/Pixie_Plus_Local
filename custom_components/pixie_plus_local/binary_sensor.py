"""Binary sensor platform for Pixie Plus Local."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import (
    DOMAIN,
    PixieEndpoint,
    PixiePlusConfigEntryRuntimeData,
    PixiePlusCoordinatorEntity,
    endpoint_unique_identifier,
    gateway_device_identifier,
    physical_device_identifier,
)

BINARY_SENSOR_DEVICE_CLASSES = {
    "3002": "motion",
}


def _iter_binary_sensor_endpoints(inventory) -> list[PixieEndpoint]:
    """Return binary sensor endpoints from inventory."""
    gateway_identifier = gateway_device_identifier(inventory)
    endpoints: list[PixieEndpoint] = []
    for device_id in sorted(inventory.devices_by_id):
        record = inventory.devices_by_id[device_id]
        
        # Only process devices with presence/motion capabilities
        if record.model_no != "3002":
            continue
            
        parent_identifier = physical_device_identifier(record)

        endpoints.append(
            PixieEndpoint(
                device_id=record.id,
                endpoint_key="motion",
                command_target=None,
                entity_unique_id=endpoint_unique_identifier(record, "motion"),
                device_identifier=parent_identifier,
                device_name=record.name,
                via_device_identifier=gateway_identifier,
                entity_translation_key="motion",
            )
        )

    return endpoints


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Pixie Plus Local binary sensor entities."""
    runtime_data: PixiePlusConfigEntryRuntimeData = entry.runtime_data
    inventory = runtime_data.pixie_runtime.inventory
    if inventory is None:
        return

    async_add_entities(
        PixiePlusBinarySensorEntity(runtime_data, endpoint)
        for endpoint in _iter_binary_sensor_endpoints(inventory)
    )


class PixiePlusBinarySensorEntity(PixiePlusCoordinatorEntity, BinarySensorEntity):
    """Representation of a Pixie Plus binary sensor (motion/presence detector)."""

    def __init__(self, runtime_data: PixiePlusConfigEntryRuntimeData, endpoint: PixieEndpoint) -> None:
        super().__init__(runtime_data, endpoint, domain=DOMAIN)
        device_class = BINARY_SENSOR_DEVICE_CLASSES.get(self.record.model_no, "motion")
        self._attr_device_class = (
            BinarySensorDeviceClass.MOTION if device_class == "motion" else BinarySensorDeviceClass.MOTION
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if motion is detected.
        
        Motion state is derived from the BLE value_byte for model 3002:
        - value_byte bit 0 = 1 → motion detected
        - value_byte bit 0 = 0 → motion cleared
        
        Falls back to presence/online if no BLE update has been received yet.
        """
        runtime = self.record.runtime
        
        # Primary indicator: BLE-derived motion_detected field
        if runtime.motion_detected is not None:
            return runtime.motion_detected
        
        # Fallback before first BLE update: use presence from cloud/hub
        if runtime.presence == "offline":
            return False
        
        return None
