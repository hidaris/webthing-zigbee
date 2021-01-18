import os
import uuid
import ujson as json

from thingtalk.toolkits import Mqtt, ee
from thingtalk.toolkits.mqtt import Client
from thingtalk.schema import IntermediateMsg

from pydantic import ValidationError

from thingtalk import Thing
from loguru import logger
from .pp import (
    Binary,
    Composite,
    Enum,
    Numeric,
    Text,
    visit_numeric,
    visit_binary,
    visit_enum,
    visit_text,
    visit_composite,
)


def get_generic_type_property(data):
    try:
        if data.get("type") == "numeric":
            _, p = visit_numeric(Numeric(**data))
        elif data.get("type") == "binary":
            _, p = visit_binary(Binary(**data))
        elif data.get("type") == "enum":
            _, p = visit_enum(Enum(**data))
        elif data.get("type") == "text":
            _, p = visit_text(Text(**data))
        elif data.get("type") == "composite":
            _, p = visit_composite(Composite(**data))
        else:
            p = None
    except ValidationError as e:
        logger.error(str(e))
        p = None
    return p


async def sync_property(thing_id, name, value):
    try:
        message = IntermediateMsg(**{"messageType": "syncProperty", "data": {name: value}})
        ee.emit(f"things/{thing_id}", message)
    except ValidationError as e:
        logger.error(e.json())


class Zigbee2Mqtt(Mqtt):
    

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.running_state_table = {}
        self.ir_devices = set()
        self.device_c = kwargs.get("device_c")

    def on_connect(self, client, flags, rc, properties):
        logger.info(f"[CONNECTED {client._client_id}]")
        client_ids = client._client_id.split(":")
        if client_ids[0] == "sub_client":
            self.sub_client.subscribe("zigbee2mqtt/#", qos=1, subscription_identifier=1)

    async def on_message(self, client, topic: str, payload: bytes, qos, properties):
        topic_words = topic.split("/")
        """ logger.debug(topic) """
        if topic == "zigbee2mqtt/bridge/state":
            value = payload.decode()
            await sync_property("urn:thingtalk:server", "availability", value)
        if topic == "zigbee2mqtt/bridge/devices":
            devices = json.loads(payload.decode())
            for device in devices:
                definition = device.get("definition")
                if not definition:
                    continue
                thing = self.device_c(
                    device.get("friendly_name"),
                    definition.get("description"),
                    type_=[],
                )
                exposes = definition.get("exposes")
                endpoints = []
                for expose in exposes:
                    if expose.get("endpoint"):
                        endpoint = self.device_c(
                            f"{device.get('friendly_name')}_{expose.get('endpoint')}",
                            f"{definition.get('description')}_{expose.get('endpoint')}",
                            type_=[],
                        )
                        endpoints.append(endpoint)
                    if expose.get("type") in [
                        "light",
                        "switch",
                        "cover",
                        "fan",
                        "climate",
                    ]:
                        if len(endpoints) > 0:
                            for endpoint in endpoints:
                                endpoint._type.add(expose.get("type").capitalize())    
                        else:
                            thing._type.add(expose.get("type").capitalize())
                        for feature in expose.get("features"):
                            p = get_generic_type_property(feature)
                            if p:
                                if len(endpoints) > 0:
                                    for endpoint in endpoints:
                                        endpoint.add_property(p)
                                else:
                                    thing.add_property(p)
                    else:
                        if expose.get("type") == "binary":
                            if len(endpoints) > 0:
                                for endpoint in endpoints:
                                    endpoint._type.add("BinarySensor")
                            else:
                                thing._type.add("BinarySensor")
                        else:
                            if len(endpoints) > 0:
                                for endpoint in endpoints:
                                    endpoint._type.add("Sensor")
                            else:
                                thing._type.add("Sensor")
                        p = get_generic_type_property(expose)
                        if p:
                            if len(endpoints) > 0:
                                for endpoint in endpoints:
                                    endpoint.add_property(p)
                            else:
                                thing.add_property(p)
                """ logger.debug(await thing.as_thing_description()) """
                if len(endpoints) > 0:
                    for endpoint in endpoints:
                        await client.app.state.things.add_thing(endpoint)
                else:
                    await client.app.state.things.add_thing(thing)
            """ logger.debug(
            f"[RECV MSG {client._client_id}] TOPIC: {topic} PAYLOAD: {payload} QOS: {qos} PROPERTIES: {properties}") """


host = os.environ.get("MQTT_HOST", "10.10.10.8")
# host = os.environ.get('MQTT_HOST', '127.0.0.1')
username = os.environ.get("MQTT_USERNAME", "longan")
password = os.environ.get("MQTT_PASSWORD", "longan")

mqtt = Zigbee2Mqtt(host, "1883", username=username, password=password)
