from thingtalk.toolkits.event_bus import ee


class ZigbeeActionMixin:

    async def property_action(self, property_):
        value = await property_.get_value()
        if "_" in self.id:
            id_ = self.id.split("_")[0]
            property_name = self.id.replace(f"{id_}_", "")
            ee.emit("mqtt/publish", f"zigbee2mqtt/{id_}/set", {property_name: value})
        elif property_.name == "brightness":
            value = int(value * (254 / 100))
            ee.emit("mqtt/publish", f"zigbee2mqtt/{self.id}/set", {property_.name: value})
        elif "Cover" in self._type:
            # mqtt.running_state_table.update({self.id: 0})
            await self.sync_property("running", False)
            ee.emit("mqtt/publish", f"zigbee2mqtt/{self.id}/set", {property_.name: value})
        else:
            ee.emit("mqtt/publish", f"zigbee2mqtt/{self.id}/set", {property_.name: value})
