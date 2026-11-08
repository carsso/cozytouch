"""The name a room's device is shown under.

A device is registered under its subentry's title, which is the `name` the API
gives it. For a gateway or an appliance that is a product name (`CozyBox`,
`Naema 2 Micro 25`). For a room it is the slot, `ROOM_0`, and what its user
called it lives on the zone the room serves : the Thermor app shows a CozyBox's
room as *Salon*, the zone's name, and nothing calls it ROOM_0.

These pin that the connectivity sensor, the entity that sets the device's name,
uses the zone's name for a room and the title for everything else, and for a
room whose zone the account does not name. `Hub.get_room_name` is called
unbound against a stand-in, the way tests/test_topology.py calls
`get_via_device`.
"""

from types import SimpleNamespace

import pytest

from custom_components.cozytouch.binary_sensor import CloudConnectivity
from custom_components.cozytouch.hub import Hub
from custom_components.cozytouch.infos import ModelInfos
from custom_components.cozytouch.model import CozytouchDeviceType

ROOM_ID = 1001
ZONES = {2001: "Salon", 2002: None}


def hub_over(deviceType, zoneId=2001):
    hub = SimpleNamespace(
        _deviceId=ROOM_ID,
        _account=SimpleNamespace(
            devices=[{"deviceId": ROOM_ID, "name": "ROOM_0", "zoneId": zoneId}]
        ),
        get_model_infos=lambda: ModelInfos(name="Room (Salon)", type=deviceType),
        get_zone_name=ZONES.get,
        get_serial_number=lambda: "1234-5678-0000",
        get_software_version=lambda: None,
        get_via_device=lambda: None,
    )
    hub.get_room_name = lambda: Hub.get_room_name(hub)
    return hub


def device_name(hub, title="ROOM_0"):
    sensor = object.__new__(CloudConnectivity)
    sensor.coordinator = hub
    sensor._title = title
    sensor._device_uniq_id = "sub-1"
    return sensor.device_info["name"]


def test_a_room_is_named_after_its_zone():
    assert device_name(hub_over(CozytouchDeviceType.ROOM)) == "Salon"


def test_a_room_whose_zone_has_no_name_keeps_its_title():
    assert device_name(hub_over(CozytouchDeviceType.ROOM, zoneId=2002)) == "ROOM_0"


@pytest.mark.parametrize(
    "deviceType",
    [CozytouchDeviceType.HUB, CozytouchDeviceType.ZONE, CozytouchDeviceType.AC],
)
def test_anything_else_keeps_its_title(deviceType):
    assert device_name(hub_over(deviceType), title="CozyBox") == "CozyBox"


def test_a_device_the_account_no_longer_holds_keeps_its_title():
    hub = hub_over(CozytouchDeviceType.ROOM)
    hub._account.devices = []
    assert device_name(hub) == "ROOM_0"
