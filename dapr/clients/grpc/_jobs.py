# -*- coding: utf-8 -*-

# Copyright 2025 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
This module contains the Job class and related utilities for the Dapr Jobs API.
"""

from dataclasses import dataclass
from typing import Optional

from google.protobuf.any_pb2 import Any as GrpcAny


@dataclass
class Job:
    """Represents a Dapr job for scheduling.

    At least one of schedule or due_time must be provided but can also be provided together.

    Attributes:
        name (str): The unique name for the job.
        schedule (Optional[str]): Schedule at which the job is to be run.
            Accepts both systemd timer style cron expressions, as well as human
            readable '@' prefixed period strings.
        repeats (Optional[int]): The optional number of times in which the job should be
            triggered. If not set, the job will run indefinitely or until expiration.
        due_time (Optional[str]): The optional time at which the job should be active, or the
            "one shot" time if other scheduling type fields are not provided. Accepts
            a "point in time" string in the format of RFC3339, Go duration string
            (calculated from job creation time), or non-repeating ISO8601.
        ttl (Optional[str]): The optional time to live or expiration of the job. Accepts a
            "point in time" string in the format of RFC3339, Go duration string
            (calculated from job creation time), or non-repeating ISO8601.
        data (Optional[GrpcAny]): The serialized job payload that will be sent to the recipient
            when the job is triggered. If not provided, an empty Any proto will be used.
        overwrite (bool): If true, allows this job to overwrite an existing job with the same name.
    """

    name: str
    schedule: Optional[str] = None
    repeats: Optional[int] = None
    due_time: Optional[str] = None
    ttl: Optional[str] = None
    data: Optional[GrpcAny] = None
    overwrite: bool = False

    def _get_proto(self):
        """Convert this Job instance to a Dapr Job proto message.

        This is an internal method for SDK use only. Not part of the public API.

        Returns:
            api_v1.Job: The proto representation of this job.
        """
        from dapr.proto.runtime.v1 import dapr_pb2 as api_v1
        from google.protobuf.any_pb2 import Any as GrpcAny

        # Build the job proto
        job_proto = api_v1.Job(name=self.name, overwrite=self.overwrite)

        if self.schedule:
            job_proto.schedule = self.schedule
        if self.repeats is not None:
            job_proto.repeats = self.repeats
        if self.due_time:
            job_proto.due_time = self.due_time
        if self.ttl:
            job_proto.ttl = self.ttl
        # overwrite is already set in the constructor above

        # data field is required, set empty Any if not provided
        if self.data:
            job_proto.data.CopyFrom(self.data)
        else:
            # Set empty Any proto
            job_proto.data.CopyFrom(GrpcAny())

        return job_proto

    @classmethod
    def _from_proto(cls, job_proto):
        """Create a Job instance from a Dapr Job proto message.

        This is an internal method for SDK use only. Not part of the public API.

        Args:
            job_proto (api_v1.Job): The proto message to convert.

        Returns:
            Job: A new Job instance.
        """
        return cls(
            name=job_proto.name,
            schedule=job_proto.schedule if job_proto.HasField('schedule') else None,
            repeats=job_proto.repeats if job_proto.HasField('repeats') else None,
            due_time=job_proto.due_time if job_proto.HasField('due_time') else None,
            ttl=job_proto.ttl if job_proto.HasField('ttl') else None,
            data=job_proto.data if job_proto.HasField('data') and job_proto.data.value else None,
            overwrite=job_proto.overwrite,
        )
