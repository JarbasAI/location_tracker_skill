from adapt.intent import IntentBuilder
from mycroft.skills.core import MycroftSkill, intent_handler
from mycroft.messagebus.message import Message
from mycroft.util import connected
from mycroft.api import DeviceApi
from mycroft.configuration.config import LocalConf, USER_CONFIG
from os.path import join, exists, dirname
from threading import Timer
import unirest
import json
import pygeoip
import ipgetter

__author__ = 'jarbas'


class LocationTrackerSkill(MycroftSkill):
    def __init__(self):
        super(LocationTrackerSkill, self).__init__()
        if "update_mins" not in self.settings:
            self.settings["update_mins"] = 15
        if "update_source" not in self.settings:
            self.settings["update_source"] = "local_ip"
        if "tracking" not in self.settings:
            self.settings["tracking"] = False
        if "auto_context" not in self.settings:
            self.settings["auto_context"] = False
        if "ip_api_url" not in self.settings:
            self.settings["ip_api_url"] = "https://ipapi.co/json/"
        if "geo_ip_db" not in self.settings:
            self.settings["geo_ip_db"] = join(dirname(__file__), 'GeoLiteCity.dat')

        self.timer = Timer(60 * int(self.settings["update_mins"]),
                           self.update_location)
        self.timer.setDaemon(True)

        self.create_settings_meta()
        self.settings.set_changed_callback(self.reset_location)

    def initialize(self):
        if self.settings["tracking"]:
            self.update_location()
            self.timer.start()

    def create_settings_meta(self):
        meta = {
            "name": "Device Location Tracker Skill",
            "skillMetadata":
                {"sections": [

                    {
                        "name": "Configuration",
                        "fields":
                            [
                                {
                                    "type": "label",
                                    "label": "Currently this skill can only track location from IP address, soon wifi geolocation wil be added, and eventually GPS, available options are 'local_ip' and 'remote_ip', using a local database or a web api"
                                },
                                {
                                    "type": "text",
                                    "name": "update_source",
                                    "value": "remote_ip",
                                    "label": "where to get location data from"
                                },
                                {
                                    "type": "label",
                                    "label": "Is location tracking active? disabling this reverts location"
                                },
                                {
                                    "type": "checkbox",
                                    "name": "tracking",
                                    "value": "false",
                                    "label": "tracking"
                                },
                                {
                                    "type": "label",
                                    "label": "At which interval, in minutes, should location be updated?"
                                },
                                {
                                    "type": "number",
                                    "name": "update_mins",
                                    "value": "15",
                                    "label": "update interval"
                                },
                                {
                                    "type": "label",
                                    "label": "This is the api where we get remote_ip location data from"
                                },
                                {
                                    "type": "text",
                                    "name": "ip_api_url",
                                    "value": "https://ipapi.co/json/",
                                    "label": "url"
                                },
                                {
                                    "type": "label",
                                    "label": "This is the path to the database where we get local_ip location data from"
                                },
                                {
                                    "type": "text",
                                    "name": "geo_ip_db",
                                    "value": self.settings["geo_ip_db"],
                                    "label": "geo ip database"
                                }
                            ]
                    }
                ]
                }
        }
        settings_path = join(self._dir, "settingsmeta.json")
        if not exists(settings_path):
            with open(settings_path, "w") as f:
                f.write(json.dumps(meta))

    @intent_handler(IntentBuilder("UnsetLocationContextIntent")
                    .require("InjectionKeyword").require("LocationKeyword")
                    .require("DeactivateKeyword"))
    def handle_deactivate_context_intent(self, message):
        if not self.settings["auto_context"]:
            self.speak("Location context injection is not active")
        else:
            self.settings["auto_context"] = False
            self.speak("Location context injection deactivated")
        self.settings.store()

    @intent_handler(IntentBuilder("SetLocationContextIntent")
                    .require("InjectionKeyword").require("LocationKeyword").require("ActivateKeyword"))
    def handle_activate_context_intent(self, message):
        if self.settings["auto_context"]:
            self.speak("Location context injection is already active")
        else:
            self.settings["auto_context"] = True
            self.speak("Location context injection activated")
        self.settings.store()

    @intent_handler(IntentBuilder("UnSetLocationTrackingIntent")
                    .require("TrackingKeyword").require("LocationKeyword")
                    .require("DeactivateKeyword"))
    def handle_deactivate_tracking_intent(self, message):
        if not self.settings["tracking"]:
            self.speak("Location tracking from " +
                       self.settings["update_source"] + " is not active")
        else:
            self.settings["tracking"] = False
            self.timer.cancel()
            self.speak("Location tracking from " +
                       self.settings["update_source"] + " deactivated")
            self.reset_location()

    @intent_handler(IntentBuilder("SetLocationTrackingIntent")
                    .require("TrackingKeyword").require("LocationKeyword")
                    .require("ActivateKeyword"))
    def handle_activate_tracking_intent(self, message):
        if self.settings["tracking"]:
            self.speak("Location tracking from " +
                       self.settings["update_source"] + " is active")
        else:
            self.settings["tracking"] = True
            self.timer.start()
            self.speak("Location tracking from " +
                       self.settings["update_source"] + " activated")
        self.settings.store()

    @intent_handler(IntentBuilder("CurrentLocationIntent")
                    .require("CurrentKeyword").require("LocationKeyword"))
    def handle_current_location_intent(self, message):
        config = self.location
        city = config.get("city", {}).get("name", "unknown city")
        country = config.get("city", {}).get("region") \
            .get("country").get("name", "unknown country")
        self.speak("configuration location is " + city + ", " + country)
        if self.settings["auto_context"]:
            self.set_context('Location', city + ', ' + country)

    @intent_handler(IntentBuilder("TestLocationTrackingIntent")
                    .require("WhereAmIKeyword"))
    def handle_test_tracking(self, message):
        # TODO dialog files
        if connected():
            ip = message.context.get("ip")
            if ip:
                config = self.from_remote_ip(update=False)
                if config:
                    city = config.get("location", {}).get("city", {}) \
                        .get("name", "unknown city")
                    country = config.get("location", {}).get("city", {}).get(
                        "region", {}).get("country", {}).get("name", "unknown country")
                    self.log.info("location tracking: " + str(config))
                    self.speak(
                        "your ip address says you are in " + city + " in " +
                        country)
                    return
            else:
                config = self.update_location(save=False).get("location", {})
                if config != {}:
                    city = config.get("city", {}).get("name", "unknown city")
                    country = config.get("city", {}).get("region", {}) \
                        .get("country", {}).get("name", "unknown country")
                    self.speak(
                        "your ip address says you are in " + city + ", " + country)
                    return
                self.speak("could not get location data for unknown reasons")
        else:
            self.speak("No internet connection, could not update "
                       "location from ip address")

    @intent_handler(IntentBuilder("UpdateLocationIntent") \
                    .require("UpdateKeyword").require(
        "LocationKeyword").optionally("ConfigKeyword"))
    def handle_update_intent(self, message):
        if connected():
            # TODO source select from utterance
            source = self.settings["update_source"]
            self.speak("updating location from ip address")
            self.update_location(source)
            self.speak(self.location_pretty)
        else:
            self.speak("Cant do that offline")

    # location tracking
    @staticmethod
    def get_ip():
        return ipgetter.myip()

    def from_ip_db(self, ip=None, update=True):
        self.log.info("Retrieving location data from ip database")
        ip = ip or self.get_ip()
        g = pygeoip.GeoIP(self.settings["geo_ip_db"])
        data = g.record_by_addr(ip) or {}
        city = data.get("city", "")
        region_code = data.get("region_code", "")
        country_code = data.get("country_code", "")
        country_name = data.get("country_name", "")
        region = city
        longitude = data.get("longitude", "")
        latitude = data.get("latitude", "")
        timezone = data.get("time_zone", "")
        city_code = data.get("postal_code", "")
        data = self.build_location_dict(city, region_code, country_code, country_name,
                                        region, longitude, latitude, timezone, city_code)
        config = {"location": data}
        if update:
            self.emitter.emit(Message("configuration.patch",
                                      {"config": config}))
            self.config_core["location"] = data
            conf = LocalConf(USER_CONFIG)
            conf['location'] = data
            conf.store()
        return config

    def from_remote_ip(self, update=True):
        self.log.info("Retrieving location data from ip address api")
        if connected():
            response = unirest.get("https://ipapi.co/json/")
            city = response.body.get("city")
            region_code = response.body.get("region_code")
            country = response.body.get("country")
            country_name = response.body.get("country_name")
            region = response.body.get("region")
            lon = response.body.get("longitude")
            lat = response.body.get("latitude")
            timezone = response.body.get("timezone")
            if timezone is None:
                timezone_data = self.location.get("timezone", self.home_location.get("timezone", {}))
            else:
                timezone_data = {"code": timezone, "name": timezone,
                                 "dstOffset": 3600000,
                                 "offset": -21600000}

            region_data = {"code": region_code, "name": region,
                           "country": {"code": country, "name": country_name}}
            city_data = {"code": city, "name": city, "state": region_data,
                         "region": region_data}

            coordinate_data = {"latitude": float(lat), "longitude": float(lon)}
            location_data = {"city": city_data, "coordinate": coordinate_data,
                             "timezone": timezone_data}
            config = {"location": location_data}
            if update:
                self.emitter.emit(Message("configuration.patch",
                                          {"config": config}))
                self.config_core["location"] = location_data
                conf = LocalConf(USER_CONFIG)
                conf['location'] = location_data
                conf.store()
            return config
        else:
            self.log.warning("No internet connection, could not update "
                             "location from ip address")
            return {}

    # internals
    @property
    def home_location(self):
        return DeviceApi().get_location()

    def reset_location(self):
        if not self.settings["tracking"]:
            self.emitter.emit(Message("configuration.patch", {"config": self.home_location}))
            conf = LocalConf(USER_CONFIG)
            conf['location'] = self.home_location
            conf.store()

    def update_location(self, source=None, save=True):
        if source is None:
            source = self.settings["update_source"]
        if source == "remote_ip":
            config = self.from_remote_ip(save)
            if config != {}:
                city = config.get("location", {}).get("city", {}) \
                    .get("name", "unknown city")
                country = config.get("location", {}).get("city", {}).get(
                    "region").get("country").get("name", "unknown country")
                if self.settings["auto_context"]:
                    self.set_context('Location', city + ', ' + country)
        elif source == "local_ip":
            config = self.from_ip_db(update=save)
            if config != {}:
                city = config.get("location", {}).get("city", {}) \
                    .get("name", "unknown city")
                country = config.get("location", {}).get("city", {}).get(
                    "region", {}).get("country", {}).get("name", "unknown country")
                if self.settings["auto_context"]:
                    self.set_context('Location', city + ', ' + country)
        else:
            self.log.info("Failed to retrieve location data from " + source)
            config = {}
        return config

    @staticmethod
    def build_location_dict(city="", region_code="", country_code="",
                            country_name="", region="", longitude=0, latitude=0,
                            timezone="", city_code=""):
        region_data = {"code": region_code, "name": region,
                       "country": {
                           "code": country_code,
                           "name": country_name}}
        city_data = {"code": city_code or city, "name": city,
                     "state": region_data,
                     "region": region_data}
        timezone_data = {"code": timezone, "name": timezone,
                         "dstOffset": 3600000,
                         "offset": -21600000}
        coordinate_data = {"latitude": float(latitude),
                           "longitude": float(longitude)}
        return {"city": city_data,
                "coordinate": coordinate_data,
                "timezone": timezone_data}


def create_skill():
    return LocationTrackerSkill()
