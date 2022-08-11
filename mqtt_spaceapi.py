#!/usr/bin/env python3
# MQTT spaceAPI 'bridge': listen to sensors and update the spaceAPI regularly

# Make sure paho-mqtt and urllib are installed using pip/apt/yum
# Don't use requests: it has a memory leak
# https://www.fugue.co/blog/diagnosing-and-fixing-memory-leaks-in-python.html

# Set the BROKER and API_KEY environment variables or run with:
# `BROKER=127.0.0.1 API_KEY=ABC ./mqtt_spaceapi.py`

import time
import paho.mqtt.client as paho
import json
import sys, signal
from urllib import request, parse
import os
import threading
import ssl

TLS = False

__location__ = os.path.realpath(
    os.path.join(os.getcwd(), os.path.dirname(__file__)))

def set_interval(func, sec):
    def func_wrapper():
        set_interval(func, sec)
        func()
    t = threading.Timer(sec, func_wrapper)
    t.start()
    return t

username = os.environ.get('USER', None)
password = os.environ.get('PASS', None)
debug = os.environ.get('DEBUG', None)
annex = os.environ.get('ANNEX', None)
broker = os.environ.get('BROKER', None)
if not broker:
    raise ValueError('You must have "BROKER" variable')

spaceapi_uri = "https://ackspace.nl/spaceAPI/"
spaceapi_key = os.environ.get('API_KEY', None)

if not spaceapi_key:
    raise ValueError('You must have "API_KEY" variable')

if not annex:
    # Assume it's the space (without a floor level in its topic)
    # [base]/[room]/[device]/[prefix]/[type]
    # base: ackspace, common, outside, services, offsite, [participant]
    # room: slackspace, hackspace, stackspace, courtyard
    # device: spacestate, temperature, hackswitch, fluorescent1
    mqtt_sensor_topics = "+/+/+/tele/SENSOR"
    mqtt_spacestate_topic = "ackspace/hackspace/spacestate/"
else:
    # Custom annex topic (modify to suit your personal settings)
    mqtt_sensor_topics = "+/+/+/+/tele/SENSOR"
    mqtt_spacestate_topic = "mancave/groundfloor/office/hackcorner/"


print( "Starting mqtt-spaceAPI bridge" )

sensor_queue = {}
state = None
def send_update():
    global client, state, sensor_queue, throttle

    if throttle > 0:
        throttle -= 1

    # Special state: we're busy updating
    if throttle < 0:
        return

    if (client and not client.connected_flag) or ( len( sensor_queue ) == 0 and state == None ):
        return

    # Only do sensors after throttling (state has priority)
    if (throttle == 0) and len( sensor_queue ) > 0:
        throttle = -1
        print( "Update sensor(s)" )
        sensors = {
            "name": [],
            "location": [],
            "value": [],
            "type": [],
            "unit": []
        }

        # Read sensor queue
        for name in sensor_queue:
            sensors["type"].append( sensor_queue[name][2] )
            sensors["name"].append( name )
            sensors["value"].append( sensor_queue[name][1] )
            sensors["unit"].append( sensor_queue[name][3] )
            sensors["location"].append( sensor_queue[name][0] )
        sensor_queue = {}
        http_request( {
            "update": "sensors",
            "type[]" : sensors["type"], # temperature, power_consumption, ..
            "address[]": sensors["name"], # name (sensor id); topic[-3]
            "value[]": sensors["value"],
            "unit[]" : sensors["unit"], # celcius, W, ..
            "location[]": sensors["location"] # topic[-4]
        } )

    # Always do spacestate if it was provided
    if state is not None:
        throttle = -1
        print( "Update state: %s" % state )
        if annex is not None:
            http_request( {
                "update": "sensors",
                "type" : "service",
                "address": "annex",
                annex: "true" if state else "false"
            } )
        else:
            http_request( {
                "update": "state",
                "state": "1" if state else "0"
            } )

    # Reset state and throttle
    state = None
    throttle = 10

def http_request( data ):
    data["key"] = spaceapi_key

    if debug:
        data["debug"] = True

    parsed_data = parse.urlencode(data).encode("ascii")
    
    if debug:
        print( parsed_data )

    with request.urlopen(spaceapi_uri, parsed_data) as response:
        response_text = response.read()     

        if response.status == 200 and '{"message":"ok"}' in response_text.decode( 'UTF-8' ):
            print( "API update: ok" )
            if debug:
                print( response.headers )
                print( response_text ) # expect {"message":"ok"}
        else:
            print( "API update went wrong:" )
            print( responser.status ) # expect 200
            print( response.headers )
            print( response_text ) # expect {"message":"ok"}

def on_mqtt_message( client, userdata, message ):
    global state, sensor_queue

    # parse payload
    try:
        payload = json.loads( message.payload )
    except:
        payload = {}
    location = message.topic.split("/")[-4]
    name = message.topic.split("/")[-3]
    if debug:
        print( f"incoming message from {name}: {payload}" )

    if not message.topic.endswith( "SENSOR" ):
        if "POWER1" in payload and message.topic.startswith(mqtt_spacestate_topic):
            # Spacestate
            #if (key in temp_list) or key.startswith("POWER"):
            state = payload["POWER1"] in [ "ON", "true", "True", "TRUE", "1" ]
        elif "POWER" in payload and message.topic.startswith(mqtt_spacestate_topic):
            # Spacestate
            #if (key in temp_list) or key.startswith("POWER"):
            state = payload["POWER"] in [ "ON", "true", "True", "TRUE", "1" ]

    temp_list = [ "BME280", "DHT11", "ANALOG" ]

    for key in payload:

        # Spacestate
        if key == "Switch1" and message.topic.startswith(mqtt_spacestate_topic):
            state = payload["Switch1"] in [ "ON", "true", "True", "TRUE", "1" ]

        # Only iterate lists
        if not isinstance(payload[key], dict):
            continue

        #print( key, payload )

        # temperature
        if "Temperature" in payload[key]:
            # Make sure to use the Id if we're reading DS18B20 sensors
            sensor_queue[ payload[key]["Id"] if key.startswith("DS18B20") else name ] = ( location, payload[key]["Temperature"], "temperature", "celcius" )

        # door_locked
        """
        # barometer
        if "Pressure" in payload[key]:
            print( "%s@%s:%shPA" % (name, location, payload[key]["Pressure"]) )
            sensor_queue[ name ] = ( location, payload[key]["Pressure"], "barometer", "hPa" )

        # radiation

        # humidity
        if "Humidity" in payload[key]:
            print( "%s@%s:%s%%" % (name, location, payload[key]["Humidity"]) )
            sensor_queue[ name ] = ( location, payload[key]["Humidity"], "humidity", "hPa" )

        # beverage_supply
        """

        # power_consumption
        # Note that we have "Power", "ApparentPower", "ReactivePower"
        # but also "Factor", "Voltage" and "Current"
        if "Power" in payload[key]:
            #print( "%s@%s:%sW" % (name, location, payload[key]["Power"]) )
            sensor_queue[ name ] = ( location, payload[key]["Power"], "power_consumption", "W" )

        """
        # wind
        # network_connections
        # account_balance
        # total_member_count
        # people_now_present
        # network_traffic
        """
    if debug:
        print( "queue", sensor_queue )

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        client.connected_flag = True
        print( "Connected to broker" )

        client.subscribe( mqtt_sensor_topics )
        client.subscribe( mqtt_spacestate_topic+"#" )
    else:
        print( "Connection to broker unsuccessful:" )
        if rc == 1: print( "incorrect protocol version" )
        elif rc == 2: print( "invalid client identifier" )
        elif rc == 3: print( "server unavailable" )
        elif rc == 4: print( "bad username or password" )
        elif rc == 5: print( "not authorised" )
        elif rc == 7: print( "check unique client id" )
        else: print( "Errorcode: ", rc )

def on_disconnect(client, userdata,  rc):
    print("Disconnected from broker")
    if rc == 7: print( "check unique client id" )
    client.connected_flag = False


def signal_handler(signal, frame):
    print('You pressed Ctrl+C!')
    client.unsubscribe( mqtt_sensor_topics )
    client.unsubscribe( mqtt_spacestate_topic+"#" )
    client.disconnect()
    client.loop_stop()
    # TODO: it doesn't want to exit, but this allows to ctrl+c again
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

throttle = 0
set_interval( send_update, 1 )

if broker:
    client = paho.Client("syn-ack")
    client.on_connect = on_connect
    client.on_message = on_mqtt_message
    client.on_connect=on_connect
    client.on_disconnect = on_disconnect
    client.connected_flag = False

    if username and password:
        client.username_pw_set(username=username,password=password)

    # TODO: differentiate between tls and plain text
    if TLS:
        client.tls_set( ca_certs=os.path.join(__location__, "./ca.crt"),
                        certfile=None,
                        keyfile=None,
                        cert_reqs=ssl.CERT_REQUIRED,
                        ciphers=None )
    client.connect( broker, port = TLS and 8883 or 1883, keepalive = 60 )

    client.loop_forever()
else:
    client = None
