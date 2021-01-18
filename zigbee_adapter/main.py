import os

from fastapi import FastAPI

from thingtalk import MultipleThings
from thingtalk.models.thing import Server
from thingtalk.app import restapi
from thingtalk.routers import websockets


from .mqtt import Zigbee2Mqtt
from .device import Zigbee

app = FastAPI()
server = Server()
server.href_prefix = f"/things/{server.id}"
app.state.things = MultipleThings({server.id: server}, "things")

host = os.environ.get("MQTT_HOST", "10.10.10.8")
username = os.environ.get("MQTT_USERNAME", "longan")
password = os.environ.get("MQTT_PASSWORD", "longan")

mqtt = Zigbee2Mqtt(host, "1883", username=username, password=password, device_c=Zigbee)


@app.on_event("startup")
async def init():

    await mqtt.set_app(app)
    await mqtt.connect()


@app.on_event("shutdown")
async def mqtt_disconnect():
    await mqtt.disconnect()


app.include_router(restapi)
app.include_router(websockets.router)