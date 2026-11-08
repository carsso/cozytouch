"""What a room offers once 103026 says nothing in it can cool.

A room slot behind a gateway is typed from its gateway, and every room
inherits `_AC_ROOM` : the air conditioner's modes, its fan, its louvers, its
quiet and powerful modes. Capability 103026 names the generators actually
driving the room. The fixture is a Thermor connected floor-heating thermostat
(THERMOSTAT PRE CONNECT, 1505) behind a CozyBox (2448), whose room reads 64,
floor heater, beside 73 = 2 (heating only) and 166 = 17 (off and heat) ; the
Thermor app offers it on/off, manual/program, a setpoint and the open window
detection, and nothing of an air conditioner.

These pin that such a room loses what the air conditioner brought, and that a
room whose 103026 names a generator able to cool, or names none, keeps it.
"""

import json
import pathlib

import pytest

from custom_components.cozytouch.capability import get_capability_infos
from custom_components.cozytouch.model import (
    CozytouchDeviceType,
    get_device_model_infos,
    heats_only,
)
from homeassistant.components.climate import HVACMode

FIXTURE = pathlib.Path("scripts/test_ha/floor_heater.json")

# Everything the room reports that only exists because of an air conditioner.
AIR_CONDITIONER_ROWS = (
    162,
    163,
    177,
    350,
    355,
    356,
    357,
    100505,
    100800,
    100801,
    100802,
    100803,
    100804,
    103114,
)


def account(generators=None):
    """The fixture's devices as the API sends them, with 103026 replaced."""
    devices = json.loads(FIXTURE.read_text())["data"]["devices"]
    for device in devices:
        values = dict(device["capabilities"]["values"])
        if device["name"] == "ROOM_0":
            if generators is None:
                values.pop("103026")
            else:
                values["103026"] = generators
        device["capabilities"] = [
            {"capabilityId": int(found), "value": value}
            for found, value in values.items()
        ]
    return devices


def room(generators="64"):
    devices = account(generators)
    dev = next(found for found in devices if found["name"] == "ROOM_0")
    modelInfos = get_device_model_infos(devices, dev, "Salon")
    available = {found["capabilityId"] for found in dev["capabilities"]}
    values = {found["capabilityId"]: found["value"] for found in dev["capabilities"]}
    return modelInfos, available, values


def resolved(modelInfos, available, values, capabilityId):
    return get_capability_infos(
        modelInfos, capabilityId, values.get(capabilityId) or "0", available
    )


@pytest.mark.parametrize(
    ("generators", "expected"),
    [
        ("64", True),  # floor heater
        ("16", True),  # panel heater
        ("4", True),  # boiler
        ("80", True),  # floor and panel heaters together
        ("8", False),  # air-to-air split
        ("2", False),  # air-to-water heat pump, which may be reversible
        ("72", False),  # floor heater beside a split
        ("1", False),  # reserved : unknown is not heat only
        ("0", False),
        (None, False),
        ("", False),
        ("garbage", False),
    ],
)
def test_which_generators_only_heat(generators, expected):
    assert heats_only(generators) is expected


def test_the_floor_heating_room_is_still_a_room():
    modelInfos, _, _ = room()
    assert modelInfos.type is CozytouchDeviceType.ROOM


def test_the_floor_heating_room_offers_off_and_heat_only():
    modelInfos, _, _ = room()
    assert list(modelInfos.HVACModes.values()) == [HVACMode.OFF, HVACMode.HEAT]


def test_the_floor_heating_room_has_no_fan_louver_or_quiet_mode():
    modelInfos, _, _ = room()
    assert "fanModes" not in modelInfos
    assert "swingModes" not in modelInfos
    assert "AirCirculationSpeeds" not in modelInfos
    assert modelInfos.quietModeAvailable is False


def test_its_climate_entity_keeps_the_heating_half_only():
    modelInfos, available, values = room()
    climate = resolved(modelInfos, available, values, 7)
    assert climate.targetCapabilityId == 40
    assert climate.currentValueCapabilityId == 117
    assert climate.progCapabilityId == 184
    for wired in (
        "targetCoolCapabilityId",
        "fanModeCapabilityId",
        "quietModeCapabilityId",
        "swingModeCapabilityId",
        "swingOnCapabilityId",
        "boostCapabilityId",
    ):
        assert wired not in climate, wired


@pytest.mark.parametrize("capabilityId", AIR_CONDITIONER_ROWS)
def test_the_air_conditioner_entities_are_not_built(capabilityId):
    modelInfos, available, values = room()
    assert not resolved(modelInfos, available, values, capabilityId)


@pytest.mark.parametrize("capabilityId", [104050, 100506, 157, 184])
def test_what_the_app_does_offer_is_still_built(capabilityId):
    """Open window detection, presence, the override and the program."""
    modelInfos, available, values = room()
    assert resolved(modelInfos, available, values, capabilityId)


@pytest.mark.parametrize("generators", ["8", "72", None])
def test_a_room_that_may_cool_keeps_the_air_conditioner(generators):
    """A split beside the heater, or no word on it at all, changes nothing."""
    modelInfos, available, values = room(generators)
    assert HVACMode.COOL in modelInfos.HVACModes.values()
    assert modelInfos.quietModeAvailable is True
    assert "fanModes" in modelInfos
    assert resolved(modelInfos, available, values, 177)
    assert resolved(modelInfos, available, values, 7).targetCoolCapabilityId == 177
