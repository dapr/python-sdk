import re
from datetime import timedelta

# Regex to parse Go Duration datatype, e.g. 4h15m50s
GO_DURATION_PARSER = re.compile(r'((?P<hours>\d+)h)?((?P<mins>\d+)m)?((?P<seconds>\d+)s)?')

def convert_from_dapr_duration(duration: str) -> timedelta:
    matched = GO_DURATION_PARSER.match(duration)
    days, hours = divmod(matched.group('hours'), 24)
    return timedelta(
        days=days,
        hours=hours,
        minutes=int(matched.group('mins')),
        seconds=int(matched.group('seconds')))

def convert_to_dapr_duration(td: timedelta) -> str:
    totalMinute, secs = divmod(td.total_seconds(), 60)
    hours, mins = divmod(totalMinute, 60)

    return "{}h{}m{}s".format(hours, mins, secs)
