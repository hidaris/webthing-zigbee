from thingtalk.models.thing import Thing
from thingtalk import Property, Value
from .mixins import ZigbeeActionMixin


def vendor():
    return Property(
        "vendor",
        Value(""),
        metadata={
            "@type": "VendorProperty",
            "title": "vendor",
            "type": "string",
            "description": "vendor of device",
        },
    )


def availability():
    return Property(
        "availability",
        Value("online"),
        metadata={
            "@type": "EnumProperty",
            "title": "availability",
            "type": "string",
            "enum": ["online", "offline"],
            "description": "availability of zigbee device",
        },
    )


class Zigbee(ZigbeeActionMixin, Thing):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        """ self.add_available_action(Delete)
        self.add_property(linkquality())
        self.add_property(vendor()) """
        self.add_property(availability())
        self.add_property(vendor())
