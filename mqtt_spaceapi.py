#!/usr/bin/python
# MQTT spaceAPI 'bridge': listen to (all) sensors and update the spaceAPI regularly

# Make sure paho-mqtt and requests are installed using pip/apt/yum

# Set the BROKER and API_KEY environment variables (or run with:
# `BROKER=127.0.0.1 API_KEY=ABC ./mqtt_spaceapi.py`

# For Synology docker:
# run with replacement script in a loop
# Launch with command: pip install paho-mqtt requests
# Stop container and update script

# TODO: group/throttle http requests
#       try and connect directly to MySQL/MariaDB (hosting limitation)
import time
import paho.mqtt.client as paho
import json
import sys, signal
import requests
import os

broker = os.environ.get('BROKER', None)
if not broker:
    raise ValueError('You must have "BROKER" variable')

spaceapi_uri = "https://ackspace.nl/spaceAPI/?"
spaceapi_key = os.environ.get('API_KEY', None)

if not spaceapi_key:
    raise ValueError('You must have "API_KEY" variable')

print( "Starting mqtt-spaceAPI bridge" );

def spaceapi_update( _topic, _value, _type ):
    uri = spaceapi_uri + "key=" + spaceapi_key + "&update=sensors&type=" + _type + "&address=" + _topic + "&value=" + str( _value ) + "&unit=W&location=ACKspace"
    #print( uri )
    r = requests.get(uri)
    if ( r.status_code == 200 and r.content.decode('UTF-8') =='{"message":"ok"}'):
        print( "API update: ok" )
    else:
        print( "API update went wrong:" )
        print( r.status_code ) # expect 200
        print( r.headers )
        print( r.content ) # expect {"message":"ok"}

def on_connect(client, userdata, flags, rc):                                                 
    # Subscribe to default tasmota sensor topics
    client.subscribe( "tele/+/SENSOR" )

def on_mqtt_message( client, userdata, message ):
    # parse payload
    payload = json.loads( message.payload )

    # Targeted status request (cmnd/+/STATUS 10) are in StatusSNS
    if ( u"StatusSNS" in payload ):
        payload = payload["StatusSNS"]

    print( "received message" )
    #print( "topic: ", str( message.topic.decode( "utf-8" )))
    print( "topic: ", str( message.topic.split("/")[1] ) )

    if ( u"ENERGY" in payload ):
        print( "received message: ", payload["ENERGY"]["Power"], "W" )
        print( "received message: ", payload["ENERGY"]["Voltage"], "V" )
        spaceapi_update( str( message.topic.split("/")[1] ), payload["ENERGY"]["Power"], "power_consumption" )
    elif ( u"DHT11" in payload ):
        print( "received message: ", payload["DHT11"]["Temperature"], "C" )
        print( "received message: ", payload["DHT11"]["Humidity"], "%" )
        spaceapi_update( str( message.topic.split("/")[1] ), payload["DHT11"]["Temperature"], "temperature" )
    elif ( u"MAX6675" in payload ):
        print( "received message: ", payload["MAX6675"]["ProbeTemperature"], "C" )
        spaceapi_update( str( message.topic.split("/")[1] ), payload["MAX6675"]["ProbeTemperature"], "temperature" )    
    else:
        print( "unknown message: ", payload )

client = paho.Client("syn-ack")

def signal_handler(signal, frame):
    print('You pressed Ctrl+C!')
    client.disconnect()
    client.loop_stop()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
client.on_connect = on_connect
client.on_message = on_mqtt_message

client.connect( broker )
time.sleep( 2 )
client.loop_forever()

