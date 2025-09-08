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

import dapr.ext.workflow as wf
import time

wfr = wf.WorkflowRuntime()


@wfr.activity
def app3_activity(ctx: wf.DaprWorkflowContext) -> int:
    print(f'app3 - received activity call', flush=True)
    print(f'app3 - returning activity result', flush=True)
    return 3


if __name__ == '__main__':
    wfr.start()
    time.sleep(15)  # wait for workflow runtime to start
    wfr.shutdown()
