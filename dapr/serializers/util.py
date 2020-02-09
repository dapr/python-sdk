import re
from datetime import timedelta

# Regex to parse Go Duration datatype, e.g. 4h15m50s
GO_DURATION_PARSER = re.compile(r'((?P<hours>\d+)h)?((?P<mins>\d+)m)?((?P<seconds>\d+)s)?')

def convert_from_dapr_duration(duration: str) -> timedelta:
    matched = GO_DURATION_PARSER.match(duration)
    days = 0.0
    hours = 0.0

    if matched.group('hours') is not None:
        days, hours = divmod(float(matched.group('hours')), 24)
    mins = 0.0 if not matched.group('mins') else float(matched.group('mins'))
    seconds = 0.0 if not matched.group('seconds') else float(matched.group('seconds'))

    return timedelta(
        days=days,
        hours=hours,
        minutes=mins,
        seconds=seconds)

def convert_to_dapr_duration(td: timedelta) -> str:
    totalMinute, secs = divmod(td.total_seconds(), 60.0)
    hours, mins = divmod(totalMinute, 60.0)

    return "{:.0f}h{:.0f}m{:.0f}s".format(hours, mins, secs)
