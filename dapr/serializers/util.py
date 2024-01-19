# -*- coding: utf-8 -*-

"""
Copyright 2023 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import re
from datetime import timedelta

# Regex to parse Go Duration datatype, e.g. 4h15m50s123ms345μs
DAPR_DURATION_PARSER = re.compile(
    r'((?P<hours>\d+)h)?((?P<mins>\d+)m)?((?P<seconds>\d+)s)?((?P<milliseconds>\d+)ms)?((?P<microseconds>\d+)(μs|us))?$'
)  # noqa: E501


def convert_from_dapr_duration(duration: str) -> timedelta:
    """Converts Dapr duration format (Go duration format) to datetime.timedelta.

    Args:
        duration (str): Dapr duration string.

    Returns:
        :obj:`datetime.delta`: the python datetime object.
    """

    matched = DAPR_DURATION_PARSER.match(duration)
    if not matched or matched.lastindex == 0:
        raise ValueError(f"Invalid Dapr Duration format: '{duration}'")

    days = 0.0
    hours = 0.0

    if matched.group('hours') is not None:
        days, hours = divmod(float(matched.group('hours')), 24)
    mins = 0.0 if not matched.group('mins') else float(matched.group('mins'))
    seconds = 0.0 if not matched.group('seconds') else float(matched.group('seconds'))
    milliseconds = (
        0.0 if not matched.group('milliseconds') else float(matched.group('milliseconds'))
    )
    microseconds = (
        0.0 if not matched.group('microseconds') else float(matched.group('microseconds'))
    )

    return timedelta(
        days=days,
        hours=hours,
        minutes=mins,
        seconds=seconds,
        milliseconds=milliseconds,
        microseconds=microseconds,
    )


def convert_to_dapr_duration(td: timedelta) -> str:
    """Converts date.timedelta to Dapr duration format.

    Args:
        td (datetime.timedelta): python datetime object.

    Returns:
        str: dapr duration format string.
    """

    total_minutes, seconds = divmod(td.total_seconds(), 60.0)
    milliseconds, microseconds = divmod(td.microseconds, 1000.0)
    hours, mins = divmod(total_minutes, 60.0)

    return f'{hours:.0f}h{mins:.0f}m{seconds:.0f}s{milliseconds:.0f}ms{microseconds:.0f}μs'
