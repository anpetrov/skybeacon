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

import logging
import threading
import voluptuous as vol
from uuid import UUID

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME,
                                 CONF_MAC,
                                 TEMP_CELSIUS,
                                 STATE_UNKNOWN,
                                 EVENT_HOMEASSISTANT_STOP)

REQUIREMENTS = ['pygatt==3.0.0']

CONNECT_LOCK = threading.Lock()

_LOGGER = logging.getLogger(__name__)

ATTR_DEVICE = 'device'
ATTR_MODEL = 'model'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MAC): cv.string,
    vol.Optional(CONF_NAME, default=""): cv.string,
})

BLE_TEMP_UUID = '0000ff92-0000-1000-8000-00805f9b34fb'
BLE_TEMP_HANDLE = 0x24
SKIP_HANDLE_LOOKUP = True
CONNECT_TIMEOUT = 30


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor."""
    name = config.get(CONF_NAME)
    mac = config.get(CONF_MAC)
    _LOGGER.error("setting up..")
    mon = Monitor(hass, mac, name)
    add_devices([SkybeaconTemp(name, mon)])
    add_devices([SkybeaconHumid(name, mon)])

    def monitor_stop(_service_or_event):
        """Stop the monitor thread"""
        _LOGGER.info("skybeacon: stopping monitor for %s ", name)
        mon.terminate()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, monitor_stop)
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
        return self.mon.data['humid']

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return "%"

    @property
    def device_state_attributes(self):
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
        return self.mon.data['temp']

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return TEMP_CELSIUS

    @property
    def device_state_attributes(self):
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
        self.daemon = False
        self.hass = hass
        self.mac = mac
        self.name = name
        self.data = {'temp': STATE_UNKNOWN, 'humid': STATE_UNKNOWN}
        self.keep_going = True
        self.event = threading.Event()

    def run(self):
        """Thread that keeps connection alive."""
        import pygatt
        from pygatt.backends import Characteristic
        from pygatt.exceptions import (BLEError,
                                       NotConnectedError,
                                       NotificationTimeout)

        cached_char = Characteristic(BLE_TEMP_UUID, BLE_TEMP_HANDLE)
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
                    device._characteristics[UUID(BLE_TEMP_UUID)] = cached_char
                # magic: writing this makes device happy
                device.char_write_handle(0x1b, bytearray([255]), False)
                device.subscribe(BLE_TEMP_UUID, self._update)
                _LOGGER.info("subscribed to %s", self.name)
                while self.keep_going:
                    # protect against stale connections, just read temperature
                    device.char_read(BLE_TEMP_UUID, timeout=CONNECT_TIMEOUT)
                    self.event.wait(60)
                break
            except (BLEError, NotConnectedError, NotificationTimeout) as ex:
                _LOGGER.error("Exception: %s ", str(ex))
            finally:
                adapter.stop()

    def _update(self, handle, value):
        """Notification callback from pygatt."""
        _LOGGER.info("%s: %15s temperature = %-2d.%-2d, humidity = %3d",
                     handle, self.name, value[0], value[2], value[1])
        self.data['temp'] = float(("%d.%d" % (value[0], value[2])))
        self.data['humid'] = value[1]

    def terminate(self):
        """Terminate"""
        self.keep_going = False
        self.event.set()
        self.join()
