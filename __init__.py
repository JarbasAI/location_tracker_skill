from adapt.intent import IntentBuilder
from mycroft.skills.core import MycroftSkill
from mycroft.messagebus.message import Message
from threading import Timer
import unirest
from mycroft.util import connected

__author__ = 'jarbas'


class LocationTrackerSkill(MycroftSkill):
    def __init__(self):
        super(LocationTrackerSkill, self).__init__()
        if "update_mins" not in self.settings:
            self.settings["update_mins"] = 15
        if "update_source" not in self.settings:
            self.settings["update_source"] = "ip"
        if "tracking" not in self.settings:
            self.settings["tracking"] = True
        if "auto_context" not in self.settings:
            self.settings["auto_context"] = False

        self.timer = Timer(60 * self.settings["update_mins"],
                           self.get_location)
        self.timer.setDaemon(True)

    def initialize(self):
        intent = IntentBuilder("UpdateLocationIntent") \
            .require("UpdateKeyword").require(
            "LocationKeyword").optionally("ConfigKeyword").build()
        self.register_intent(intent, self.handle_update_intent)

        intent = IntentBuilder("CurrentLocationIntent") \
            .require("CurrentKeyword").require("LocationKeyword").build()
        self.register_intent(intent, self.handle_current_location_intent)

        intent = IntentBuilder("UnSetLocationTrackingIntent") \
            .require("TrackingKeyword").require("LocationKeyword").require(
            "DeactivateKeyword").build()
        self.register_intent(intent, self.handle_deactivate_tracking_intent)

        intent = IntentBuilder("SetLocationTrackingIntent") \
            .require("TrackingKeyword").require("LocationKeyword").require(
            "ActivateKeyword").build()
        self.register_intent(intent, self.handle_activate_tracking_intent)

        # disabled, now in official skill
        intent = IntentBuilder("WhereAmIIntent") \
            .require("WhereAmIKeyword").build()
        #self.register_intent(intent, self.handle_where_am_i_intent)


        # disabled because of munging,
        # waiting for core fix for universal adapt context
        intent = IntentBuilder("SetLocationContextIntent") \
            .require("InjectionKeyword").require(
            "LocationKeyword").require(
            "ActivateKeyword").build()
        #self.register_intent(intent, self.handle_activate_context_intent)

        intent = IntentBuilder("UnsetLocationContextIntent") \
            .require("InjectionKeyword").require(
            "LocationKeyword").require(
            "DeactivateKeyword").build()
        #self.register_intent(intent, self.handle_deactivate_context_intent)

        if self.settings["tracking"]:
            self.timer.start()

    def handle_deactivate_context_intent(self, message):
        if not self.settings["auto_context"]:
            self.speak("Location context injection is not active")
        else:
            self.settings["auto_context"] = False
            self.speak("Location context injection deactivated")
        self.settings.store()

    def handle_activate_context_intent(self, message):
        if self.settings["auto_context"]:
            self.speak("Location context injection is already active")
        else:
            self.settings["auto_context"] = True
            self.speak("Location context injection activated")
        self.settings.store()

    def handle_deactivate_tracking_intent(self, message):
        if not self.settings["tracking"]:
            self.speak("Location tracking from " +
                       self.settings["update_source"] + " is not active")
        else:
            self.settings["tracking"] = False
            self.timer.cancel()
            self.speak("Location tracking from " +
                       self.settings["update_source"] + " deactivated")
        self.settings.store()

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

    def handle_current_location_intent(self, message):
        config = self.config_core.get("location")
        city = config.get("city", {}).get("name", "unknown city")
        country = config.get("city", {}).get("region")\
            .get("country").get("name", "unknown country")
        self.speak("configuration location is " + city + ", " + country)
        if self.settings["auto_context"]:
            self.set_context('Location', city + ', ' + country)

    def handle_where_am_i_intent(self, message):
        ip = message.context.get("ip")
        if ip:
            config = self.from_ip(update=False)
            if config != {}:
                city = config.get("location", {}).get("city", {})\
                    .get("name","unknown city")
                country = config.get("location", {}).get("city", {}).get(
                    "region").get("country").get("name", "unknown country")
                self.speak(
                    "your ip address says you are in " + city + " in " +
                    country)
        else:
            config = self.get_location()
            if config != {}:
                city = config.get("location", {}).get("city", {})\
                    .get("name", "unknown city")
                country = config.get("location", {}).get("city", {}).get(
                    "region").get("country").get("name", "unknown country")
                self.speak(
                    "your ip address says you are in " + city + " in " +
                    country)

    def handle_update_intent(self, message):
        if connected():
            self.speak("updating location from ip address")
            config = self.get_location("ip")
            city = config.get("city", {}).get("name", "unknown city")
            country = config.get("city", {}).get("region").get("country")\
                .get("name", "unknow country")
            self.speak(city + " " + country)
        else:
            self.speak("Cant do that offline")

    def from_ip(self, update = True):
        self.log.info("Retrieving location data from ip address")
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

            region_data = {"code": region_code, "name": region,
                           "country": {"code": country, "name": country_name}}
            city_data = {"code": city, "name": city, "state": region_data,
                         "region": region_data}
            timezone_data = {"code": timezone, "name": timezone,
                             "dstOffset": 3600000,
                             "offset": -21600000}
            coordinate_data = {"latitude": float(lat), "longitude": float(lon)}
            location_data = {"city": city_data, "coordinate": coordinate_data,
                             "timezone": timezone_data}
            config = {"location": location_data}
            if update:
                self.emitter.emit(Message("configuration.patch",
                                          {"config": config }))
            return config
        else:
            self.log.warning("No internet connection, could not update "
                             "location from ip address")
            return {}

    def get_location(self, source=None):
        if source is None:
            source = self.settings["update_source"]
        if source == "ip":
            config = self.from_ip()
            if config != {}:
                city = config.get("location", {}).get("city", {})\
                    .get("name", "unknown city")
                country = config.get("location", {}).get("city", {}).get(
                    "region").get("country").get("name", "unknown country")
                if self.settings["auto_context"]:
                    self.set_context('Location', city + ', ' + country)
        else:
            self.log.info("Failed to retrieve location data from " + source)
            config = {}
        return config


def create_skill():
    return LocationTrackerSkill()
