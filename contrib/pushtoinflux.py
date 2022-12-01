#!/usr/bin/env python
# -*- coding: utf-8 -*-

# id=$1
# temp=$2
# hum=$3
# seq=$4
# lowbatt=$5
# rssi=$6

import json
import math
import os
import sys
import time
from datetime import datetime

configFile = os.path.dirname(__file__) + "/influxdb.conf"

# print("Opening config file from " + configFile)

with open(configFile) as jfile:
    config = json.load(jfile)

# print("Command line: ", sys.argv)

try:
    from influxdb import InfluxDBClient
    
    influxClient = InfluxDBClient(
        host=config["influxdb"]["host"],
        port=config["influxdb"]["port"],
        username=config["influxdb"]["user"],
        password=config["influxdb"]["pass"]
    )

    createDb = True
    for db in influxClient.get_list_database():
        if db["name"] == config["influxdb"]["database"]:
            createDb = False
            break
    
    if createDb:
        influxClient.create_database(config["influxdb"]["database"])
        influxClient.switch_database(config["influxdb"]["database"])
        influxClient.alter_retention_policy("autogen", duration="2h", replication=1, shard_duration="1h")
        influxClient.create_retention_policy("one_week", duration="1w", replication=1, shard_duration='24h')
        influxClient.create_retention_policy("one_year", database=config["influxdb"]["database"], duration="365d", replication=1, shard_duration='1w')
        influxClient.create_continuous_query("three_min", 'SELECT mean(T) as "T", mean(RH) as "RH", mean(AH) as "AH", mean(DEW) as "DEW" INTO "one_week"."lacrosse" from "lacrosse" GROUP BY time(3m),*')
        influxClient.create_continuous_query("three_hour", 'SELECT mean(T) as "T", mean(RH) as "RH", mean(AH) as "AH", mean(DEW) as "DEW" INTO "one_week"."lacrosse" from "lacrosse" GROUP BY time(3h),*')
    else:
        influxClient.switch_database(config["influxdb"]["database"])

except Exception as ex:
    influxClient = None
    print("influx init error: " + ex.__class__.__name__ + " " + (''.join(ex.args)))
    exit(1)

mqttHost = config["mqtt"]["host"]
mqttTopic = config["mqtt"]["topic"]

try:
    import paho.mqtt.client as mqtt
    mqttClient = mqtt.Client()
    mqttClient.connect(mqttHost, 1883, 60)
    mqttClient.loop_start()
except:
    mqttClient = None
#   print("No mqtt")

id = sys.argv[1]

payload = {}

try:
    payload["id"] = id
    payload["T"] = float(sys.argv[2])
    payload["RH"] = float(sys.argv[3])

    payload["rssi"] = int(sys.argv[6])
    payload["batlo"] = sys.argv[5]
    payload["count"] = int(sys.argv[4])
    payload["init"] = "false"
#   payload["time"] = sys.argv[7]
except Exception as ex:
    print("Error: " + ex.__class__.__name__ + " " + (''.join(ex.args)))
    
def getSensorConfig(id):
    for csens in config["sensors"]:
        if id == csens["id"]:
            return csens
    return None

def writeInflux(payload):
    if not influxClient:
        return
    T = payload["T"]
    wr = {
        "measurement": "lacrosse",
        "fields": {
            "T": T
        },
        "tags": {"sensor": payload["id"] if not ("room" in payload) else payload["room"]}
    }

    if ("RH" in payload):
        RH = float(payload["RH"])
        T =  float(payload["T"])

        a = 7.5
        b = 237.4
        SDD = 6.1078 * 10 ** (a * T / (b + T))

        DD = RH / 100.0 * SDD
        v = math.log10(DD / 6.1078)
        
        payload["DEW"] = round(b * v / (a - v), 1)
        payload["AH"] = round(10 ** 5 * 18.016/8314.3 * DD / (T + 273.15), 1)

        wr["fields"]["RH"] = payload['RH']
        wr["fields"]["DEW"] = payload["DEW"]
        wr["fields"]["AH"] = payload["AH"]

    wr["fields"]["room"] = payload['room']    
#   wr["fields"]["time"] = payload["time"]
                
    influxClient.write_points([wr], "s")

def getSensorStatus(id, sensor, sensorConfig):
        if sensorConfig is not None:
            if ('tMax' in sensorConfig) and (sensor["T"] > sensorConfig["tMax"]):
                sensor["tStatus"] = "high"

            if ('tMin' in sensorConfig) and (sensor["T"] < sensorConfig["tMin"]):
                sensor["tStatus"] = "low"

            if ('tStatus' not in sensor) and ('tMax' in sensorConfig or 'tMin' in sensorConfig):
                sensor["tStatus"] = "ok"

            if ('RH' in sensor):
                if ('rhMax' in sensorConfig) and (sensor["RH"] > sensorConfig["rhMax"]):
                    #too wet!
                    sensor["rhStatus"] = "high"
                    if "AHratio" in sensor:
                        if sensor["AHratio"] <= -10:
                            sensor["window"] = "open"
                        elif sensor["AHratio"] >= 10:
                            sensor["window"] = "close"

                if ('rhMin' in sensorConfig) and (sensor["RH"] < sensorConfig["rhMin"]):
                    #too dry
                    sensor["rhStatus"] = "low"
                    if "AHratio" in sensor:
                        if sensor["AHratio"] >= 10:
                            sensor["window"] = "open"
                        elif sensor["AHratio"] <= -10:
                            sensor["window"] = "close"

                if 'rhStatus' not in sensor and ('rhMin' in sensorConfig or 'rhMax' in sensorConfig):
                    sensor["rhStatus"] = "ok"
                    
            sensor["room"] = sensorConfig["name"]
        else:
            sensor["room"] = "unknown"
try:
    sensorConfig = getSensorConfig(id)
    getSensorStatus(id, payload, sensorConfig)
    if influxClient:
        writeInflux(payload)
except Exception as ex:
    print("Error: " + ex.__class__.__name__ + " " + (''.join(ex.args)))
    pass
try:
    if mqttClient:
        mqttClient.publish('home/' + mqttTopic + "/" + payload['id'], json.dumps(payload))
except:
    pass
