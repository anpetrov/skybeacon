# Skybeacon sensor

Bluetooth LE temperature/humidity component for Home Assistant.

### Table of Contents
* [Information](#information)
* [Getting Started](#getting-started)
* [Design notes](#design-notes)
* [Known bugs and workarounds](#known-bugs-workarounds)

## Information

Skybeacons are cheap CR2477-powered ibeacon/eddystone sensors that come with temperature/sensor module.
They are advertised to last 2+ years. More information: http://cnsky9.en.alibaba.com

## Getting Started

### Configure device

The device(s) need to have password disabled:

  * Run provided Skybeacon Android app
  * Connect to the device
  * Enter default password (was 888888) for me
  * Click 'more'
  * Set empty new password
  * Click 'Submit'

### Install component:

    pip install -r requirements.txt
    cp skybeacon.py /path/to/homeassistant/custom_components/sensor

### Configuration of Home Assistant

Edit `configuration.yaml` and add:

    sensor:
       - platform: skybeacon
          mac: 'F7:BE:12:02:47:31'
          name: 'living room'

## Design notes

### Operation mode

Subscribe to temperature/humidity notifications. Keep connection active.

## Known bugs / workarounds

### Hardware bugs

#### direct sensor read does not work

It is possible to read temperature/humidity directly (as opposed to get notified of change) with 0xff92.
However sometimes it just gets stale, but correct value is received by notification. So the code does not
rely on reading the characteristic directly and merely waits for notifications to arrive.

#### weak connection from faraway devices

Devices that are far away do not seem to be able transmit burst of data. Not sure if this is specific to
Skybeacon or general BT issue. The sympthom is that connection gets due to timeout which seem to be originating
from host controller. As result, when gatttool goes out to discover all characterstic, connection drops and
reconnection is needed. Subsequent connection attemps keep on failing, so device can not be used at all. This
is work-arounded by sneaking a UUID-handle mapping into pygatt, which is hacky. However the hack is effective
and even faraway devices seem to able to maintain connection for many hours and deliver notifications.

#### password handling is not implemented

Much of my knoweledge of skybeacon behavour comes from reverse-engineering. However I didn't figure out yet how
password is supposed to work. As result only passwordless mode is supported.
