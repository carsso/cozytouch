"""The name a room is shown under, wherever Home Assistant shows one.

The API's `name` for a gateway or an appliance is a product name (`CozyBox`).
For a room it is the slot, `ROOM_0`, and what its user called it lives on the
zone the room serves : the Thermor app shows a CozyBox's room as *Salon*, the
zone's name, and nothing calls it ROOM_0.

That name was shown in four places : the device, the subentry on the
integration page, the picker that adds a device, and the subentry an existing
install already holds. These pin that a room is its zone's name in all four,
that anything else keeps the API's name, and that a subentry somebody renamed
keeps theirs. The account is the reporter's : a CozyBox (2448), its room (557)
and the floor-heating thermostat's zone (1505).
"""

from types import SimpleNamespace

from custom_components.cozytouch import _rename_rooms
from custom_components.cozytouch.account import CozytouchAccount
from custom_components.cozytouch.binary_sensor import CloudConnectivity
from custom_components.cozytouch.config_flow import _device_options, _subentry_for
from custom_components.cozytouch.hub import Hub

BOX, ROOM, ZONE = 1000, 1001, 1002


def devices(roomZone=2001):
    return [
        {"deviceId": BOX, "name": "CozyBox", "modelId": 2448, "productId": 63,
         "modelFamily": "Connectivity_Box", "masterDeviceId": None,
         "zoneId": 2000, "capabilities": []},
        {"deviceId": ROOM, "name": "ROOM_0", "modelId": 557, "productId": 26,
         "masterDeviceId": BOX, "zoneId": roomZone, "capabilities": []},
        {"deviceId": ZONE, "name": "THZONE_0", "modelId": 1505, "productId": 65,
         "masterDeviceId": BOX, "zoneId": roomZone, "capabilities": []},
    ]  # fmt: skip


def account(roomZone=2001):
    acc = SimpleNamespace(
        devices=devices(roomZone),
        zones=[
            {"id": 2000, "name": "zoneTechnique"},
            {"id": 2001, "name": "Salon"},
        ],
    )
    acc.get_zone_name = lambda zoneId: CozytouchAccount.get_zone_name(acc, zoneId)
    acc.room_name = lambda dev: CozytouchAccount.room_name(acc, dev)
    return acc


def hub_over(acc, deviceId):
    hub = SimpleNamespace(
        _deviceId=deviceId,
        _account=acc,
        get_model_infos=lambda: SimpleNamespace(name="Room (Salon)"),
        get_serial_number=lambda: "1234-5678-0000",
        get_software_version=lambda: None,
        get_via_device=lambda: None,
    )
    hub.get_room_name = lambda: Hub.get_room_name(hub)
    return hub


def device_name(hub, title):
    sensor = object.__new__(CloudConnectivity)
    sensor.coordinator = hub
    sensor._title = title
    sensor._device_uniq_id = "sub-1"
    return sensor.device_info["name"]


# ------------------------------------------------------------- the device


def test_a_room_is_named_after_its_zone():
    assert device_name(hub_over(account(), ROOM), "ROOM_0") == "Salon"


def test_a_room_whose_zone_has_no_name_keeps_its_title():
    assert device_name(hub_over(account(roomZone=2099), ROOM), "ROOM_0") == "ROOM_0"


def test_the_gateway_keeps_its_title():
    assert device_name(hub_over(account(), BOX), "CozyBox") == "CozyBox"


def test_a_device_the_account_no_longer_holds_keeps_its_title():
    acc = account()
    acc.devices = []
    assert device_name(hub_over(acc, ROOM), "ROOM_0") == "ROOM_0"


# ------------------------------------------------- adding a device, and its subentry


def summaries(acc):
    return CozytouchAccount.device_summaries(acc)


def test_the_picker_lists_the_room_by_its_zone():
    options = _device_options(summaries(account()), set())
    labels = [option["label"] for option in options]
    assert labels[1].startswith("Salon (")
    assert labels[0].startswith("CozyBox (")


def test_the_zone_is_left_out_of_the_picker():
    assert [dev["deviceId"] for dev in summaries(account())] == [BOX, ROOM]


def test_a_new_rooms_subentry_is_titled_after_its_zone():
    room = summaries(account())[1]
    subentry = _subentry_for(room)
    assert subentry["title"] == "Salon"
    # The API's name stays in the data : it is how a 1.4 entry is matched.
    assert subentry["data"]["name"] == "ROOM_0"


# --------------------------------------------- an existing install's subentries


class FakeEntries:
    def __init__(self):
        self.updated = []

    def async_update_subentry(self, entry, subentry, *, title):
        self.updated.append((subentry.subentry_id, title))


def rename(title, roomZone=2001):
    acc = account(roomZone)
    entries = FakeEntries()
    subentry = SimpleNamespace(
        subentry_id="sub-room", title=title, data={"deviceId": ROOM, "name": "ROOM_0"}
    )
    box = SimpleNamespace(
        subentry_id="sub-box",
        title="CozyBox",
        data={"deviceId": BOX, "name": "CozyBox"},
    )
    entry = SimpleNamespace(subentries={"sub-room": subentry, "sub-box": box})
    hubs = {"sub-room": hub_over(acc, ROOM), "sub-box": hub_over(acc, BOX)}
    _rename_rooms(SimpleNamespace(config_entries=entries), entry, hubs)
    return entries.updated


def test_a_room_subentry_still_titled_with_its_slot_is_retitled():
    assert rename("ROOM_0") == [("sub-room", "Salon")]


def test_a_subentry_somebody_renamed_is_left_alone():
    assert rename("Séjour") == []


def test_a_subentry_already_titled_after_its_zone_is_left_alone():
    assert rename("Salon") == []


def test_a_room_with_an_unnamed_zone_is_left_alone():
    assert rename("ROOM_0", roomZone=2099) == []
