# mqtt_spaceAPI
MQTT to SpaceAPI bridge.
This script is used to connect the internal (or home user) MQTT broker with the public spaceAPI, updating the sensors spacestate and annexes (branch location) states.

# setup
Assuming python3 is installed and the system is debian-alike;

* install `git`, `pip` and `paho-mqtt`:
  * `sudo apt install git python3-pip`
  * `pip3 install paho-mqtt`
* clone this repo locally:
  * git clone https://github.com/ACKspace/mqtt_spaceAPI
* Copy over systemd service file (edit `Environment` variables, `User` and `ExecStart` path) and enable the service
  * `sudo cp mqtt_spaceapi.service /etc/systemd/system/`
  * `sudo systemctl enable mqtt_spaceapi.service`
* optionally modify `mqtt_spaceapi.py` and change "Custom annex topic" `mqtt_sensor_topics` and `mqtt_spacestate_topic`
* run the script inside a screen/tmux (or nohup) session (change `BROKER`, `API_KEY` and `ANNEX` accordingly):
  * `BROKER=192.168.1.42 API_KEY=ABC ANNEX="@xopr's" USER=ackspace PASS=ackspace ./mqtt_spaceapi.py`

Note that the values can also be set as environment variables.

Mandatory variables:
* `BROKER`: IP or FQDN/hostname of MQTT (mosquitto) broker/server
* `API_KEY`: The ACKspace API key for updating the spaceAPI

Optional variables:
* `ANNEX`: name of an annex location, for example `@xopr's`: omit completely to update the actual spacestate
* `DEBUG`: enable debug data on both client and spaceAPI server
* `USER`: MQTT username, `ackspace` for read-only access
* `PASS`: MQTT password, `ackspace` for read-only access