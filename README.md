# Location Tracker Skill

Track location

# usage

current location - current config location
where am i - update and speak location
activate location tracking - start updating location
deactivate location tracking - stop updating location
activate location injection - start injecting location adapt context
deactivate location injection - stop injecting location adapt context
update location - trigger update

# TODO

- more sources (GPS)


# configurable

timer minutes

        self.minutes = self.config.get("location").get("update_mins", 15)

source of location update (ip only for now)

        self.source = self.config.get("location").get("update_source", "ip")

active

        self.active = self.config.get("location").get("tracking", True)

inject adapt "Location" context

        self.auto_context = self.config.get("location").get("auto_context",True)

# Requires

run time update of config [PR980](https://github.com/MycroftAI/mycroft-core/pull/980)


# know issues

if using proxy/vpn location will be wrong