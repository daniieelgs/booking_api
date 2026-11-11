

import datetime

import pytz

from globals import DEFAULT_LOCATION_TIME

DATETIME_NOW = -1

# TIMEZONE CONVENTION: every `datetime` stored in the database (bookings, closed days, timetables, SMTP reset
# dates...) is naive and means WALL-CLOCK TIME IN THE LOCAL'S OWN TIMEZONE (`LocalModel.location`). To compare
# it with the present or with another instant, localize it with naiveToAware(value, local.location) and use
# now(local.location). DEFAULT_LOCATION_TIME is only a fallback when no local is available.
# Absolute instants (JWT `exp`, timestamps) must be converted with an explicit timezone (UTC), never with the
# server's own timezone.


def now(location=DEFAULT_LOCATION_TIME):
    timezone = pytz.timezone(location)
    return datetime.datetime.now(timezone)

def naiveToAware(datetime, timezone=DEFAULT_LOCATION_TIME):
    timezone = pytz.timezone(timezone)
    return timezone.localize(datetime)

def isAware(dt):
    return dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None