import json
import re
import subprocess
from builtins import object
from builtins import str
from os.path import join, exists, dirname
from subprocess import check_output
from threading import Timer

import pygeoip
import requests
from adapt.intent import IntentBuilder
from geopy.geocoders import Yandex, Nominatim
from mycroft.api import DeviceApi
from mycroft.configuration.config import LocalConf, USER_CONFIG
from mycroft.messagebus.message import Message
from mycroft.skills.core import MycroftSkill, intent_handler
from mycroft.util import connected
from mycroft.util.log import LOG
from timezonefinder import TimezoneFinder

__author__ = 'jarbas'


def scan_wifi(interface="wlan0", sudo=False):
    class _LineMatcher(object):
        def __init__(self, regexp, handler):
            self.regexp = re.compile(regexp)
            self.handler = handler

    def _handle_new_network(line, result, networks):
        # group(1) is the mac address
        networks.append({})
        networks[-1]['Address'] = result.group(1)

    def _handle_essid(line, result, networks):
        # group(1) is the essid name
        networks[-1]['ESSID'] = result.group(1)

    def _handle_quality(line, result, networks):
        # group(1) is the quality value
        # group(2) is probably always 100
        networks[-1]['Quality'] = result.group(1) + '/' + result.group(2)

    def _handle_unknown(line, result, networks):
        # group(1) is the key, group(2) is the rest of the line
        networks[-1][result.group(1)] = result.group(2)

    # if you are not using sudo you will only find your own wifi
    if sudo:
        args = ['sudo', '/sbin/iwlist', interface, 'scanning']
    else:
        args = ['/sbin/iwlist', interface, 'scanning']
    proc = subprocess.Popen(args,
                            stdout=subprocess.PIPE)
    stdout, stderr = proc.communicate()

    lines = str(stdout)[2:-2].replace("\\n", "\n").split("\n")[1:-1]
    networks = []
    matchers = []

    # catch the line 'Cell ## - Address: XX:YY:ZZ:AA:BB:CC'
    matchers.append(_LineMatcher(r'\s+Cell \d+ - Address: (\S+)',
                                 _handle_new_network))

    # catch the line 'ESSID:"network name"
    matchers.append(_LineMatcher(r'\s+ESSID:"([^"]+)"',
                                 _handle_essid))

    # catch the line 'Quality:X/Y Signal level:X dBm Noise level:Y dBm'
    matchers.append(_LineMatcher(r'\s+Quality:(\d+)/(\d+)',
                                 _handle_quality))

    # catch any other line that looks like this:
    # Key:value
    matchers.append(_LineMatcher(r'\s+([^:]+):(.+)',
                                 _handle_unknown))

    # read each line of output, testing against the matches above
    # in that order (so that the key:value matcher will be tried last)
    for line in lines:
        # hack for signal strenght TODO use a matcher
        if line.rstrip().lstrip().startswith("Quality="):
            index = line.find("Signal level=") + len("Signal level=")
            line = line[index:].strip()
            networks[-1]["strength"] = line
            continue

        for m in matchers:
            result = m.regexp.match(line)
            if result:
                m.handler(line, result, networks)
                break
    LOG.info("scanned networks: " + str(networks))
    return networks


def get_essids():
    networks = scan_wifi()
    essids = []
    for n in networks:
        essids.append(n["ESSID"])
    return essids


def get_bssids():
    networks = scan_wifi()
    bssids = []
    for n in networks:
        bssids.append(n["Address"])
    return bssids


def get_aps(sudo=False):
    mac_ssid_list = []
    networks = scan_wifi(sudo=sudo)
    for n in networks:
        net = (n["Address"], int(n["strength"].replace(" dBm", "")),
               int(n["Channel"]))
        mac_ssid_list.append(net)
    return mac_ssid_list


def wifi_geolocate(mac_ssid_list=None,
                   api="",
                   sudo=False):
    mac_ssid_list = mac_ssid_list or get_aps(sudo)
    aps = []
    for (mac, strength, channel) in mac_ssid_list:
        data = {
            "macAddress": mac,
            "signalStrength": strength,
            "channel": channel
        }
        aps.append(data)
    try:
        r = requests.post(
            "https://www.googleapis.com/geolocation/v1/geolocate?key=" + api,
            headers={"Content-Type": "application/json"},
            json={"wifiAccessPoints": aps})
        r = dict(r.json())
        location = r["location"]
        accuracy = r["accuracy"]
        return location["lat"], location["lng"], accuracy
    except:
        return None, None, 0


def geolocate(address, yandex=False, try_all=True):
    data = {}
    if yandex:
        geolocator = Yandex(lang='en_US')
        location = geolocator.geocode(address, timeout=10)
        if location is None and try_all:
            return geolocate(address, False, False)
        elif location is None:
            return {"address": address}
        data["country"] = location.address.split(",")[-1].strip()
        try:
            data["city"] = location.address.split(",")[-3].strip()
        except:
            data["city"] = location.address.split(",")[0].strip()
        try:
            data["street"] = " ".join(location.address.split(",")[:-3]).strip()
        except:
            data["street"] = location.address
    else:
        geolocator = Nominatim()
        location = geolocator.geocode(address, timeout=10)
        if location is None and try_all:
            return geolocate(address, True, False)
        data["country"] = location.address.split(",")[-1].strip()
        # check for zip code
        if location.address.split(",")[-2].strip().replace("-", "").replace(
                "_", "").replace(" ", "").isdigit():
            data["zip"] = location.address.split(",")[-2].strip()
            data["state"] = location.address.split(",")[-3].strip()
            try:
                data["region"] = location.address.split(",")[-4].strip()
                data["city"] = location.address.split(",")[-5].strip()
            except:
                data["city"] = location.address.split(",")[-0].strip()
        else:
            data["state"] = location.address.split(",")[-2].strip()
            try:
                data["region"] = location.address.split(",")[-3].strip()
                data["city"] = location.address.split(",")[-4].strip()
            except:
                data["city"] = location.address.split(",")[-0].strip()

        data["street"] = location.address

    data["address"] = location.address
    data["latitude"] = location.latitude
    data["longitude"] = location.longitude
    return data


def reverse_geolocate(lat, lon, yandex=False, try_all=True):
    data = {}
    if yandex:
        geolocator = Yandex(lang='en_US')
        location = geolocator.reverse(str(lat) + ", " + str(lon), timeout=10)
        if location is None or not len(location):
            if try_all:
                return reverse_geolocate(lat, lon, False, False)
            return data
        location = location[0]
        data["country"] = location.address.split(",")[-1].strip()
        try:
            data["city"] = location.address.split(",")[-3].strip()
        except:
            data["city"] = location.address.split(",")[0].strip()
        try:
            data["street"] = " ".join(location.address.split(",")[:-3]).strip()
        except:
            data["street"] = location.address
    else:
        geolocator = Nominatim()
        location = geolocator.reverse(str(lat) + ", " + str(lon), timeout=10)
        if location is None and try_all:
            return reverse_geolocate(lat, lon, True, False)
        data["country"] = location.address.split(",")[-1].strip()
        data["zip"] = None
        # check for zip code
        if location.address.split(",")[-2].strip().replace("-", "").replace(
                "_", "").replace(" ", "").isdigit():
            data["zip"] = location.address.split(",")[-2].strip()
            data["state"] = location.address.split(",")[-3].strip()
            try:
                data["region"] = location.address.split(",")[-4].strip()
                data["city"] = location.address.split(",")[-5].strip()
                data["street"] = " ".join(
                    location.address.strip().split(",")[:-5])
            except:
                data["city"] = location.address.split(",")[-0].strip()
                data["region"] = data["state"]
                data["street"] = data["city"]
        else:
            data["state"] = location.address.split(",")[-2].strip()
            try:
                data["region"] = location.address.split(",")[-3].strip()
                data["city"] = location.address.split(",")[-4].strip()
                data["street"] = " ".join(
                    location.address.strip().split(",")[:-4])
            except:
                data["city"] = location.address.split(",")[-0].strip()
                data["street"] = location.address

    data["latitude"] = location.latitude
    data["longitude"] = location.longitude
    data["country"] = location.address.split(",")[-1].strip()
    data["address"] = location.address
    return data


def get_timezone(latitude, longitude):
    tf = TimezoneFinder()
    return tf.timezone_at(lng=longitude, lat=latitude)


class LocationTrackerSkill(MycroftSkill):
    def __init__(self):
        super(LocationTrackerSkill, self).__init__()
        if "update_mins" not in self.settings:
            self.settings["update_mins"] = 15
        if "wifi_sudo" not in self.settings:
            self.settings["wifi_sudo"] = False
        if "google_geolocate_key" not in self.settings:
            self.settings["google_geolocate_key"] = "xxxxxxxx"
        if "update_source" not in self.settings:
            self.settings["update_source"] = "wifi"
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
        self.settings.store()

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
                                    "value": "wifi",
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
                                    "label": "Wifi geolocation requires a google api key, get yours here: https://developers.google.com/maps/documentation/geolocation/get-api-key"
                                },
                                {
                                    "type": "text",
                                    "name": "google_geolocate_key",
                                    "value": "xxxxxxx",
                                    "label": "google api key"
                                },
                                {
                                    "type": "checkbox",
                                    "name": "wifi_sudo",
                                    "value": "true",
                                    "label": "use sudo when scanning for wifi access points?"
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
                    .require("InjectionKeyword").require("LocationKeyword")
                    .require("ActivateKeyword"))
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
        config = self.location or {}
        city = config.get("city", {}).get("name", "unknown city")
        country = config.get("city", {}).get("state", {}).get("country",
                                                              {}).get("name",
                                                                      "unknown country")
        text = config.get("address", city + ", " + country)
        self.speak("configuration location is " + text)
        if self.settings["auto_context"]:
            self.set_context('Location', city + ', ' + country)
        self.set_context("adapt_trigger")

    @intent_handler(IntentBuilder("TestLocationTrackingIntent")
                    .require("WhereAmIKeyword"))
    def handle_test_tracking(self, message):
        # TODO dialog files
        if connected():
            ip = message.context.get("ip")
            if ip:
                self.set_context("adapt_trigger")
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

                self.set_context("adapt_trigger")
                if config != {}:
                    city = config.get("city", {}).get("name", "unknown city")
                    country = config.get("city", {}).get("region", {}) \
                        .get("country", {}).get("name", "unknown country")
                    if self.settings["update_source"] in ["local_ip",
                                                          "remote_ip"]:
                        self.speak(
                            "your ip address says you are in " + city + ", " + country)
                    else:
                        self.speak(
                            "the wifi access points around you say you are in " + city + ", " + country)
                    return
                self.speak("could not get location data for unknown reasons")
        else:
            self.speak("No internet connection, could not update "
                       "location")

    @intent_handler(IntentBuilder("UpdateLocationIntent")
                    .require("UpdateKeyword").require("LocationKeyword")
                    .optionally("ConfigKeyword"))
    def handle_update_intent(self, message):
        if connected():
            # TODO source select from utterance
            source = self.settings["update_source"]
            self.speak(
                "updating location from " + source.replace("-", " ").replace(
                    "_", " "))
            self.update_location(source)
            city = self.location.get("city", {}).get("name", "unknown city")
            country = self.location.get("city", {}).get("state", {}).get(
                "country",
                                                                  {}).get(
                "name", "unknown country")
            text = self.location.get("address", city + ", " + country)
            self.speak(text)
        else:
            self.speak("Cant do that offline")

    @intent_handler(IntentBuilder("WrongLocationIntent")
                    .require("wrong").one_of("LocationKeyword", "adapt_trigger")
                    .optionally("ConfigKeyword"))
    def handle_wrong_location_intent(self, message):
        if self.settings["tracking"]:
            if self.settings["update_source"] != "wifi":
                self.speak("IP geolocation is inherently imprecise. "
                           "Locations are often near the center of the population. "
                           "Any location provided by a IP database should not be used to identify a particular address")
            else:
                self.speak(
                    "Try again later, wifi geolocation depends on google's database")
        else:
            self.speak("Fix me by configuring my location in home.mycroft.ai or in the configuration files")

    # location tracking
    @staticmethod
    def get_ip():
        return \
        str(check_output(['hostname', '--all-ip-addresses'])).split(" ")[0][2:]
        # return ipgetter.myip()

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
            response = requests.get("https://ipapi.co/json/").json()
            respone = json.loads(response)
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

    def from_wifi(self, update=True):
        if not self.settings["google_geolocate_key"]:
            self.speak("you need a google geolocation services api key "
                       "in order to use wifi geolocation")
            self.log.error("you need a google geolocation services api key "
                           "in order to use wifi geolocation")
            return {}
        lat, lon, accuracy = wifi_geolocate(
            api=self.settings["google_geolocate_key"],
            sudo=self.settings["wifi_sudo"])
        LOG.info("\nlatitude: " + str(lat) + "\nlongitude: " + str(
            lon) + "\naccuracy (meters) : " + str(accuracy))
        data = reverse_geolocate(lat, lon)
        data["accuracy"] = accuracy
        LOG.info("reverse geocoding data: " + str(data))
        location = self.location.copy()
        location["city"]["code"] = data["city"]
        location["city"]["name"] = data["city"]
        location["city"]["state"]["name"] = data["state"]
        # TODO state code
        location["city"]["state"]["code"] = data["state"]
        location["city"]["state"]["country"]["name"] = data["country"]
        # TODO country code
        location["city"]["state"]["country"]["code"] = data["country"]
        location["coordinate"]["latitude"] = data["latitude"]
        location["coordinate"]["longitude"] = data["longitude"]

        timezone = get_timezone(data["latitude"], data["longitude"])
        # TODO timezone name
        location["timezone"]["name"] = timezone
        location["timezone"]["code"] = timezone

        config = {"location": location}
        if update:
            self.emitter.emit(Message("configuration.patch",
                                      {"config": config}))
            self.config_core["location"] = location
            conf = LocalConf(USER_CONFIG)
            conf['location'] = location
            conf.store()
        return config

    # internals
    @property
    def home_location(self):
        return DeviceApi().get_location()

    def reset_location(self, dummy=None):
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
        elif source == "wifi":
            config = self.from_wifi(update=save)
            if config != {}:
                city = config.get("location", {}).get("city", {}) \
                    .get("name", "unknown city")
                country = config.get("location", {}).get("city", {}).get(
                    "region", {}).get("country", {}).get("name",
                                                         "unknown country")
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
