## Location Tracker Skill

Track location on device

## Description

Updates device location, the mycroft home location configuration remains
unchanged

* gives you privacy (regarding mycroft.home)
* skills that need location still work ( date time and weather correct by default, unified new selects correct feed)
* fully configurable

Current localization sources:

* wifi geo - [google geolocation service](https://developers.google.com/maps/documentation/geolocation/get-api-key) 
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
* more accurate sources (GPS)


## NOTES

wifi geolocation work better with lots of wifi access points, to scan for wifi networks it is required to use sudo

you need to edit your /etc/sudoers file and allow the wifi scan command to use sudo without password

    sudo nano /etc/sudoers
    
    # Add the following line at the bottom, replace "user" with your username ( pi, mycroft, ...)
    
    user host = (root) NOPASSWD: /sbin/iwlist
    

change the skill settings to use sudo and accuracy should be much better


## known issues

* ip address geolocation is unreliable, weather skill may be completely off for example
* if using proxy/vpn ip geolocation will be wrong
* if using multiple devices settings changes (not location data) will propagate via mycroft.home


## Credits

* JarbasAI
