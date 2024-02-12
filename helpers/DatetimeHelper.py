

import datetime

import pytz

from globals import DEFAULT_LOCATION_TIME

DATETIME_NOW = -1


def now(location=DEFAULT_LOCATION_TIME):
    timezone = pytz.timezone(location)
    return datetime.datetime.now(timezone)

def naiveToAware(datetime, timezone=DEFAULT_LOCATION_TIME):
    timezone = pytz.timezone(timezone)

    return timezone.localize(datetime)