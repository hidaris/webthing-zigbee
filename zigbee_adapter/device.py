from thingtalk.models.thing import Thing
from .mixins import ZigbeeActionMixin


class Zigbee(ZigbeeActionMixin, Thing):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        """ self.add_available_action(Delete)
        self.add_property(linkquality())
        self.add_property(vendor()) """
