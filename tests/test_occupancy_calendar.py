"""The occupancy program of a room behind a CozyBox, as a week.

A Thermor connected floor-heating thermostat behind a CozyBox stores no
heating block. Its room holds an occupancy program instead : one capability
per day (100334-100339, then 100341 for sunday), each slot a start in minutes
and an ambiance -- 1 presence, 2 absence, 3 night -- whose setpoint lives on
100198, 100196 and 100197.

The two weeks below are that room's, read before and after the Thermor app's
programming assistant rewrote it on 2026-11-08, beside screenshots of the
app's week view. The first one starts its days at 02:00, and the app draws
00:00-02:00 as night, the ambiance the day before ended on ; that is what
these pin, with the mapping from ambiance to setpoint and the platform's
condition for building the calendar at all.
"""

import asyncio
import datetime
import json
from types import SimpleNamespace

from _harness import SUBENTRY_ID, entry_over, set_up
import pytest

from custom_components.cozytouch import calendar as calendar_platform
from custom_components.cozytouch.calendar import CozytouchOccupancyCalendar
from custom_components.cozytouch.const import OCCUPANCY_DAYS
from custom_components.cozytouch.infos import ModelInfos
from homeassistant.util import dt as dt_util

MONDAY = datetime.date(2026, 8, 24)
SATURDAY = datetime.date(2026, 8, 29)

SETPOINTS = {100198: "[19,0]", 100196: "[15.5,0]", 100197: "[17,0]"}


def stored(*slots):
    entries = [list(slot) for slot in slots]
    entries += [[0, 0]] * (10 - len(entries))
    return json.dumps(entries, separators=(",", ":"))


# Read before the assistant ran : no slot at 00:00.
APP_WEEKDAY = stored((120, 1), (360, 2), (840, 1), (1200, 3))
APP_WEEKEND = stored((120, 1), (1200, 3))

# What the assistant wrote : wake 06:00, out 07:00-21:00 on weekdays, bed 22:00.
ASSISTANT_WEEKDAY = stored((0, 3), (360, 1), (420, 2), (1260, 1), (1320, 3))
ASSISTANT_WEEKEND = stored((0, 3), (360, 1), (1320, 3))


def week(weekday, weekend, setpoints=SETPOINTS):
    days = dict(zip(OCCUPANCY_DAYS, [weekday] * 5 + [weekend] * 2, strict=True))
    return days | setpoints


def make_hub(values):
    return SimpleNamespace(
        get_capability_value=lambda capabilityId, default="0": values.get(
            capabilityId, default
        ),
        get_model_infos=lambda: ModelInfos(name="Room (Salon)"),
        get_serial_number=lambda: "1234-5678-0000",
        get_software_version=lambda: None,
        get_via_device=lambda: None,
        get_room_name=lambda: None,
    )


def calendar_over(values):
    return CozytouchOccupancyCalendar(
        coordinator=make_hub(values), config_uniq_id=SUBENTRY_ID
    )


def at(day, hour, minute=0):
    return datetime.datetime.combine(
        day, datetime.time(hour, minute), tzinfo=dt_util.DEFAULT_TIME_ZONE
    )


def day_of(calendar, day):
    found = asyncio.run(
        calendar.async_get_events(None, at(day, 0), at(day, 23, 59))
    )
    return [(event.start.strftime("%H:%M"), event.summary) for event in found]


def test_the_room_gets_an_occupancy_calendar():
    built = set_up(
        calendar_platform,
        entry_over(make_hub(week(ASSISTANT_WEEKDAY, ASSISTANT_WEEKEND))),
    )
    assert [entity.translation_key for entity in built] == ["occupancy_program"]


def test_a_week_missing_its_sunday_gets_none():
    """100340 is the catalogue's other sunday ; a device reporting it instead
    of 100341 has never been seen, so it gets no calendar rather than a guess.
    """
    values = week(ASSISTANT_WEEKDAY, ASSISTANT_WEEKEND)
    values[100340] = values.pop(100341)
    built = set_up(calendar_platform, entry_over(make_hub(values)))
    assert built == []


def test_it_cannot_be_edited():
    calendar = calendar_over(week(ASSISTANT_WEEKDAY, ASSISTANT_WEEKEND))
    assert not calendar.supported_features


def test_each_ambiance_shows_its_setpoint():
    calendar = calendar_over(week(ASSISTANT_WEEKDAY, ASSISTANT_WEEKEND))
    assert day_of(calendar, MONDAY) == [
        ("00:00", "17 °C"),
        ("06:00", "19 °C"),
        ("07:00", "15.5 °C"),
        ("21:00", "19 °C"),
        ("22:00", "17 °C"),
    ]


def test_the_weekend_is_its_own():
    calendar = calendar_over(week(ASSISTANT_WEEKDAY, ASSISTANT_WEEKEND))
    assert day_of(calendar, SATURDAY) == [
        ("00:00", "17 °C"),
        ("06:00", "19 °C"),
        ("22:00", "17 °C"),
    ]


def test_a_day_starting_late_opens_on_the_night_before():
    """The app's week view shows 00:00-02:00 as night on every day."""
    calendar = calendar_over(week(APP_WEEKDAY, APP_WEEKEND))
    assert day_of(calendar, MONDAY) == [
        ("00:00", "17 °C"),
        ("02:00", "19 °C"),
        ("06:00", "15.5 °C"),
        ("14:00", "19 °C"),
        ("20:00", "17 °C"),
    ]


def test_a_slot_runs_until_the_next_and_the_last_until_midnight():
    calendar = calendar_over(week(ASSISTANT_WEEKDAY, ASSISTANT_WEEKEND))
    found = asyncio.run(
        calendar.async_get_events(None, at(MONDAY, 0), at(MONDAY, 23, 59))
    )
    assert found[2].end == at(MONDAY, 21)
    assert found[-1].end == at(MONDAY + datetime.timedelta(days=1), 0)


@pytest.mark.parametrize(
    "setpoints",
    [
        {100198: "[19,0]", 100196: "[15.5,0]"},
        {100198: "[19,0]", 100196: "[15.5,0]", 100197: "garbage"},
    ],
)
def test_an_ambiance_with_no_setpoint_is_left_out(setpoints):
    """The day still renders, without the slots it cannot price."""
    calendar = calendar_over(
        week(ASSISTANT_WEEKDAY, ASSISTANT_WEEKEND, setpoints=setpoints)
    )
    assert day_of(calendar, MONDAY) == [
        ("06:00", "19 °C"),
        ("07:00", "15.5 °C"),
        ("21:00", "19 °C"),
    ]


def test_an_unreadable_day_renders_empty():
    values = week(ASSISTANT_WEEKDAY, ASSISTANT_WEEKEND)
    values[OCCUPANCY_DAYS[0]] = "not a matrix"
    values[OCCUPANCY_DAYS[6]] = "not a matrix"
    assert day_of(calendar_over(values), MONDAY) == []


def test_a_slot_past_midnight_is_left_out():
    values = week(stored((0, 3), (360, 1), (1500, 2)), ASSISTANT_WEEKEND)
    assert day_of(calendar_over(values), MONDAY) == [
        ("00:00", "17 °C"),
        ("06:00", "19 °C"),
    ]
