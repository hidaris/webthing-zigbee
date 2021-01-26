import os

from fastapi import FastAPI

from thingtalk import MultipleThings
from thingtalk.models.thing import Server
from thingtalk.app import restapi
from thingtalk.routers import websockets
from thingtalk.toolkits import ee


from .mqtt import Zigbee2Mqtt
from .device import Zigbee

app = FastAPI()
server = Server()
server.href_prefix = f"/things/{server.id}"
app.state.things = MultipleThings({server.id: server}, "things")

host = os.environ.get("MQTT_HOST", "10.10.10.8")
username = os.environ.get("MQTT_USERNAME", "longan")
password = os.environ.get("MQTT_PASSWORD", "longan")

mqtt = Zigbee2Mqtt(host, "1883", username=username, password=password)
mqtt.device_c = Zigbee

import os

from loguru import logger
from jsonschema.exceptions import ValidationError
from ormar import NoMatch
import ujson as json

from thingtalk.models.event import (
    ThingPairedEvent,
    ThingPairingEvent,
    ThingPairFailedEvent,
    ThingRemovedEvent,
)

sleep_time = os.environ.get("Z2M_SLEEP_TIME", 3)


@ee.on("zigbee/pairing")
async def handle_discover(data):
    from .action import IncreaseBright, RandomRgb

    zigbee_bridge = await app.state.things.get_thing("urn:thingtalk:bridge:zigbee")
    # 已连接设备数量如果超过限制，停止添加设备
    max_device_num = int(os.environ.get("LONGAN_MAX_DEVICE_NUM", "150"))
    connected_device_num = app.state.things.connected_device_num
    if connected_device_num >= max_device_num:
        await zigbee_bridge.error_notify("当前设备连接数已达到最大值，如需接入新设备，请删除无需使用的设备后重试")
        return None

    app.state.things.connected_device_num += 1
    await zigbee_bridge.set_property(
        "connected_devices", app.state.things.connected_device_num
    )


@ee.on("zigbee/removed")
async def handle_remove(data):
    thing_id = data.get("id")

    switch_map = None

    if hasattr(app.state, "switch_map"):
        switch_map = app.state.switch_map.get(thing_id)

    if switch_map is not None:
        for id_ in switch_map:
            thing = await app.state.things.get_thing(id_)
            if thing:
                await app.state.things.remove_thing(id_)
                if mqtt.availability_table.get(thing.id):
                    del mqtt.availability_table[thing.id]
                event = ThingRemovedEvent(
                    {"@type": list(thing._type), "id": thing.id, "title": thing.title}
                )
    else:
        thing = await app.state.things.get_thing(thing_id)
        if thing:
            await app.state.things.remove_thing(thing_id)
            if mqtt.availability_table.get(thing.id):
                del mqtt.availability_table[thing.id]
            event = ThingRemovedEvent(
                {"@type": list(thing._type), "id": thing.id, "title": thing.title}
            )

    app.state.things.connected_device_num -= 1
    zigbee_bridge = await app.state.things.get_thing("urn:thingtalk:bridge:zigbee")
    await zigbee_bridge.set_property(
        "connected_devices", app.state.things.connected_device_num
    )


@ee.on("zigbee/pairing")
async def handle_pairing(data):
    server = await app.state.things.get_thing("urn:thingtalk:server")
    await server.add_event(
        ThingPairingEvent(
            {
                "id": data.get("id"),
            }
        )
    )


@ee.on("zigbee/paired")
async def handle_paired(data):
    thing = await app.state.things.get_thing(data.get("id"))
    try:
        maybe_thing = await ThingModel.objects.get(uid=thing.id)
        thing.title = maybe_thing.title
    except NoMatch:
        pass

    server = await app.state.things.get_thing("urn:thingtalk:server")
    event = ThingPairedEvent(
        {"@type": list(thing._type), "id": thing.id, "title": thing.title}
    )
    await server.add_event(event)


@ee.on("zigbee/pair_failed")
async def handle_pair_failed(data):
    server = await app.state.things.get_thing("urn:thingtalk:server")
    event = ThingPairFailedEvent(
        {
            "id": data.get("id"),
        }
    )
    await server.add_event(event)


@app.on_event("startup")
async def init():
    await mqtt.set_app(app)
    await mqtt.connect()


@app.on_event("shutdown")
async def mqtt_disconnect():
    await mqtt.disconnect()


@ee.on("mqtt/publish")
async def mqtt_publish(topic: str, payload: dict):
    await mqtt.publish(topic, payload)


app.include_router(restapi)
app.include_router(websockets.router)