#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import math
import os
import sys
import threading
import time

script_dir = os.path.dirname(__file__)
with open(script_dir + "/lacrossegw.conf") as jfile:
    config = json.load(jfile)

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
    print("influx init error: " + ex.__class__.__name__ + " " + (''.join(ex.args)))
