"""
Support for SKYBEACON temperature/humidity Bluetooth LE sensor.

These are inexpensive CR2477-powered ibeacon/eddystone sensors
that come with temperature/sensor module.
More information: http://cnsky9.en.alibaba.com

example:
sensor:
  - platform: skybeacon
    mac: 'F7:BE:12:02:47:31'
    name: 'living room'
"""

REQUIREMENTS = ['pygatt>=3.0.0']

import logging
import pygatt
import time
import threading

from datetime import timedelta
from uuid import UUID

from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_MAC, TEMP_CELSIUS, STATE_UNKNOWN)

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from pygatt.backends import Characteristic
from pygatt.exceptions import BLEError, NotConnectedError, NotificationTimeout

CONNECT_LOCK = threading.Lock()

_LOGGER = logging.getLogger(__name__)

ATTR_DEVICE = 'device'
ATTR_MODEL = 'model'

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_MAC, default=""): cv.string,
    vol.Optional(CONF_NAME, default=""): cv.string,
})


BLE_TEMP_UUID = '0000ff92-0000-1000-8000-00805f9b34fb'
BLE_TEMP_HANDLE = 0x24
SKIP_HANDLE_LOOKUP = True

CONNECT_TIMEOUT = 30

CACHED_CHR = Characteristic(BLE_TEMP_UUID, BLE_TEMP_HANDLE)

# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor."""
    name = config.get(CONF_NAME)
    mac = config.get(CONF_MAC)
    _LOGGER.error("setting up..")
    mon = Monitor(hass, mac, name)
    add_devices([SkybeaconTemp(name, mon)])
    add_devices([SkybeaconHumid(name, mon)])
    mon.start()


class SkybeaconHumid(Entity):
    """Representation of a humidity sensor."""

    def __init__(self, name, mon):
        """Initialize a sensor."""
        self.mon = mon
        self._name = name

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self.mon.humid

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return "%"

    @property
    def state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            ATTR_DEVICE: "SKYBEACON",
            ATTR_MODEL: 1,
        }

class SkybeaconTemp(Entity):
    """Representation of a temperature sensor."""

    def __init__(self, name, mon):
        """Initialize a sensor."""
        self.mon = mon
        self._name = name

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self.mon.temp

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return TEMP_CELSIUS

    @property
    def state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            ATTR_DEVICE: "SKYBEACON",
            ATTR_MODEL: 1,
        }

class Monitor(threading.Thread):
    """Connection handling."""

    def __init__(self, hass, mac, name):
        """Construct interface object."""
        threading.Thread.__init__(self)
        self.daemon = True
        self.hass = hass
        self.mac = mac
        self.name = name
        self.temp = STATE_UNKNOWN
        self.humid = STATE_UNKNOWN

    def run(self):
        """Thread that keeps connection alive."""
        adapter = pygatt.backends.GATTToolBackend()
        while True:
            try:
                _LOGGER.info("connecting to %s", self.name)
                # we need concurrent connect, so lets not reset the device
                adapter.start(reset_on_start=False)
                # seems only one connection can be initiated at a time
                with CONNECT_LOCK:
                    device = adapter.connect(self.mac,
                                             CONNECT_TIMEOUT,
                                             pygatt.BLEAddressType.random)
                if SKIP_HANDLE_LOOKUP:
                    # HACK: inject handle mapping collected offline
                    # pylint: disable=protected-access
                    device._characteristics[UUID(BLE_TEMP_UUID)] = CACHED_CHR
                # magic: writing this makes device happy
                device.char_write_handle(0x1b, bytearray([255]), False)
                device.subscribe(BLE_TEMP_UUID, self._update)
                _LOGGER.info("subscribed to %s", self.name)
                while True:
                    # protect against stale connections, just read temperature
                    device.char_read(BLE_TEMP_UUID, timeout=CONNECT_TIMEOUT)
                    time.sleep(60)
            except (BLEError, NotConnectedError, NotificationTimeout) as ex:
                _LOGGER.error("Exception: %s ", str(ex))
            finally:
                adapter.stop()

    def _update(self, handle, value):
        """Notification callback from pygatt."""
        _LOGGER.info("%s: %15s temperature = %-2d.%-2d, humidity = %3d", handle,
                     self.name, value[0], value[2], value[1])
        self.temp = float(("%d.%d" % (value[0], value[2])))
        self.humid = value[1]
