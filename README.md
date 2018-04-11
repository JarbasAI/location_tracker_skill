## Location Tracker Skill

Track location on device

## Description

Updates device location, the mycroft home location configuration remains
unchanged

* gives you privacy
* skills that need location still work ( date time correct by default, unified new selects correct feed)
* fully configurable

Current localization sources:

* ip api - https://ipapi.co/json/
* local ip database - https://dev.maxmind.com/geoip/legacy/geolite/

## Examples

* "current location"
* "activate location tracking"
* "deactivate location tracking"
* "update location"
* "where am i"
* "location is wrong"

## TODO

* use dialog files instead of hard coded speech
* use options in settingsmeta instead of text field (avoid user screw ups)
* more accurate sources (GPS, wifi geo location)
* take device uuid into account for skill settings
* get timezone from system time


## known issues

* ip address location is unreliable, weather skill may be completely off for example
* if using proxy/vpn location will be wrong
* if using multiple devices settings changes (not location data) will propagate via mycroft.home


## Credits

* JarbasAI
