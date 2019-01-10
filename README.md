## Location Tracker Skill
[![Donate with Bitcoin](https://en.cryptobadges.io/badge/micro/1QJNhKM8tVv62XSUrST2vnaMXh5ADSyYP8)](https://en.cryptobadges.io/donate/1QJNhKM8tVv62XSUrST2vnaMXh5ADSyYP8)
[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://paypal.me/jarbasai)
<span class="badge-patreon"><a href="https://www.patreon.com/jarbasAI" title="Donate to this project using Patreon"><img src="https://img.shields.io/badge/patreon-donate-yellow.svg" alt="Patreon donate button" /></a></span>
[![Say Thanks!](https://img.shields.io/badge/Say%20Thanks-!-1EAEDB.svg)](https://saythanks.io/to/JarbasAl)

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
