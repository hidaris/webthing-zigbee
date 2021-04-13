import os

from thingtalk import MultipleThings
from thingtalk.models.thing import Server
from thingtalk.toolkits import mb
from thingtalk import app

from .mqtt import Zigbee2Mqtt

server = Server()
server.href_prefix = f"/things/{server.id}"
app.state.things = MultipleThings({server.id: server}, "things")
app.state.mode = "multiple"
host = os.environ.get("MQTT_HOST", "10.10.10.7")
username = os.environ.get("MQTT_USERNAME", "longan")
password = os.environ.get("MQTT_PASSWORD", "longan")

mqtt = Zigbee2Mqtt(host, "1883", username=username, password=password)

from loguru import logger


@app.on_event("startup")
async def init():
    await mqtt.set_app(app)
    await mqtt.connect()


@app.on_event("shutdown")
async def mqtt_disconnect():
    await mqtt.disconnect()


@mb.on("mqtt/publish")
async def mqtt_publish(topic: str, payload: dict):
    logger.debug(topic)
    logger.debug(payload)
    await mqtt.publish(topic, payload)
