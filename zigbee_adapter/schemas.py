from typing import Optional, Union, Literal, List
from zigbee_adapter.device import vendor
from pydantic import BaseModel


class BaseType(BaseModel):
    endpoint: Optional[str]


class GenericWithoutAccess(BaseType):
    description: Optional[str]
    name: str
    property: str


class GenericType(GenericWithoutAccess):
    access: Literal[1, 7, 2, 3, 5]


class Numeric(GenericType):
    type: Literal["numeric"]
    unit: Optional[str]
    value_max: Optional[int]
    value_min: Optional[int]
    value_step: Optional[int]


class Binary(GenericType):
    type: Literal["binary"]
    value_on: Union[Literal["ON", "OPEN"], bool]
    value_off: Union[Literal["OFF", "CLOSE"], bool]
    value_toggle: Optional[Literal["TOGGLE"]]


class Enum(GenericType):
    type: Literal["enum"]
    values: List[str]


class Text(GenericType):
    type: Literal["text"]


class Composite(GenericWithoutAccess):
    type: Literal["composite"]
    features: List[Union[Numeric, Binary, Enum, Text]]


class SpecificType(BaseType):
    features: List[Union[Numeric, Binary, Enum, Text, Composite]]


class Light(SpecificType):
    type: Literal["light"]


class Switch(SpecificType):
    type: Literal["switch"]


class Fan(SpecificType):
    type: Literal["fan"]


class Cover(SpecificType):
    type: Literal["cover"]


class Lock(SpecificType):
    type: Literal["lock"]


class Climate(SpecificType):
    type: Literal["climate"]


class BaseData(BaseModel):
    friendly_name: str
    ieee_address: str


class DeviceInterViewStartedData(BaseData):
    status: Literal["started"]


class Definition(BaseModel):
    model: str
    vendor: str
    description: str


class DeviceInterViewSuccessfulData(BaseData):
    status: Literal["successful"]
    supported: bool
    definition: Definition


class DeviceInterViewFailedData(BaseData):
    status: Literal["failed"]


class DeviceLeaveData(BaseModel):
    ieee_address: str


class DeviceJoinedEvent(BaseModel):
    type: Literal["device_joined"]
    data: BaseData


class DeviceAnnounceEvent(BaseModel):
    type: Literal["device_announce"]
    data: BaseData


class DeviceInterviewEvent(BaseModel):
    type: Literal["device_interview"]
    data: Union[
        DeviceInterViewStartedData,
        DeviceInterViewSuccessfulData,
        DeviceInterViewFailedData,
    ]


class DeviceLeaveEvent(BaseModel):
    type: Literal["device_leave"]
    data: DeviceLeaveData
