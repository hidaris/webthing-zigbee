from copy import deepcopy

import ujson as json

from thingtalk.toolkits import Mqtt, ee
from thingtalk.toolkits.mqtt import Client
from thingtalk.schema import IntermediateMsg

from pydantic import ValidationError

from thingtalk import Thing
from loguru import logger
from .pp import (
    visit_numeric,
    visit_binary,
    visit_enum,
    visit_text,
    visit_composite,
)
from .schemas import (
    Binary,
    Composite,
    Enum,
    Numeric,
    Text,
    DeviceJoinedEvent,
    DeviceAnnounceEvent,
    DeviceInterviewEvent,
    DeviceLeaveEvent,
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
        message = IntermediateMsg(
            **{"messageType": "syncProperty", "data": {name: value}}
        )
        ee.emit(f"things/{thing_id}", message)
    except ValidationError as e:
        logger.error(e.json())


class Zigbee2Mqtt(Mqtt):
    device_c = Thing

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.running_state_table = {}
        self.availability_table = {}
        self.ir_devices = set()

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
                if client.app.state.things.get_thing(device.get("friendly_name")):
                    continue
                thing = self.device_c(
                    device.get("friendly_name"),
                    definition.get("description"),
                    type_=[],
                )
                exposes = definition.get("exposes")
                endpoints = []
                switch_ids = []
                switch_map = {}
                for expose in exposes:
                    if expose.get("endpoint"):
                        endpoint = self.device_c(
                            f"{device.get('friendly_name')}_{expose.get('endpoint')}",
                            f"{definition.get('description')}_{expose.get('endpoint')}",
                            type_=[],
                        )
                        endpoints.append(endpoint)
                        switch_ids.append(endpoint.id)
                        switch_map.update({device.get("friendly_name"): switch_ids})
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
                    client.app.state.switch_map = switch_map
                    for endpoint in endpoints:
                        await client.app.state.things.add_thing(endpoint)
                else:
                    await client.app.state.things.add_thing(thing)
            """ logger.debug(
            f"[RECV MSG {client._client_id}] TOPIC: {topic} PAYLOAD: {payload} QOS: {qos} PROPERTIES: {properties}") """
        elif topic == "zigbee2mqtt/bridge/event":
            payload = json.loads(payload.decode())
            # logger.debug(payload)
            if payload.get("type") == "device_joined":
                event = DeviceJoinedEvent(**payload)
            elif payload.get("type") == "device_announce":
                event = DeviceAnnounceEvent(**payload)
            elif payload.get("type") == "device_interview":
                event = DeviceInterviewEvent(**payload)
                if event.data.status == "started":
                    ee.emit(
                        "zigbee/pairing",
                        {
                            "id": event.data.friendly_name,
                        },
                    )
                elif event.data.status == "successful":
                    if event.data.supported:
                        ee.emit(
                            "zigbee/paired",
                            {
                                "id": event.data.friendly_name,
                            },
                        )
                    else:
                        logger.error(
                            f"device {event.data.definition.model} is not supported"
                        )
                elif event.data.status == "failed":
                    ee.emit(
                        "zigbee/pair_failed",
                        {
                            "id": event.data.friendly_name,
                        },
                    )
            elif payload.get("type") == "device_leave":
                event = DeviceLeaveEvent(**payload)

        elif topic == "zigbee2mqtt/bridge/logging":
            if payload.get("type") == "zigbee_publish_error":
                logger.error(payload)
                if "205" in payload.get("message") or "233" in payload.get("message"):
                    uid = payload.get("meta").get("friendly_name")
                    thing = await client.app.state.things.get_thing(uid)
                    if thing:
                        await thing.set_property("availability", "offline")

            if payload.get("type") == "device_removed_failed":
                client.publish(
                    "zigbee2mqtt/bridge/config/force_remove",
                    payload.get("message"),
                    qos=1,
                    content_type="json",
                    message_expiry_interval=60,
                    topic_alias=1,
                    user_property=("time", str(time.time())),
                )
            if (
                payload.get("type") == "device_removed"
                and payload.get("message") == "left_network"
            ):
                await handle_remove(
                    client.app,
                    {
                        "id": payload.get("meta").get("friendly_name"),
                    },
                )
            if (
                payload.get("type") in ["device_force_removed", "device_removed"]
                and payload.get("message") != "left_network"
            ):
                await handle_remove(
                    client.app,
                    {
                        "id": payload.get("message"),
                    },
                )

        elif len(topic_words) == 2:
            uid = topic_words[1]
            payload = json.loads(payload.decode())
            # 用于处理多位开关状态同步
            switch_table = {}
            is_switch = False
            # 只要报告状态即表明设备在线
            data = {"availability": "online"}
            for key, value in payload.items():
                if value == "":
                    # 空状态不同步
                    continue
                old_key = ""
                if key == "running":
                    thing = client.app.state.things.get_thing(uid)
                    if thing is None:
                        continue
                    if thing.get_property("vendor") == "Xiaomi":
                        logger.debug("xiaomi")
                        report_num = self.running_state_table.get(uid, 0)
                        logger.debug(report_num)
                        if report_num < 1:
                            self.running_state_table.update({uid: report_num + 1})
                            value = True
                            logger.debug(self.running_state_table.get(uid, 0))
                        else:
                            self.running_state_table.update({uid: 0})
                            value = False
                if key == "contact":
                    payload[key] = not payload[key]
                if key == "brightness":
                    value = round(value / (254 / 100))
                if key.startswith("state_"):
                    # 处理多位开关情况
                    uid = f"{topic_words[1]}_{key}"
                    old_key = key
                    key = "state"
                    is_switch = True
                data.update({key: value})
                if old_key.startswith("state_"):
                    switch_table.update({uid: deepcopy(data)})

            self.availability_table.update({uid: 0})

            if is_switch:
                for k, v in tuple(switch_table.items()):
                    thing = client.app.state.things.get_thing(k)
                    if thing:
                        await thing.bulk_sync_property(v)
            else:
                thing = client.app.state.things.get_thing(uid)
                if thing:
                    await thing.bulk_sync_property(data)
