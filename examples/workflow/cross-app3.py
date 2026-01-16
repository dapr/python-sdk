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
import os
import time

import dapr.ext.workflow as wf

wfr = wf.WorkflowRuntime()


@wfr.activity
def app3_activity(ctx: wf.DaprWorkflowContext) -> int:
    print('app3 - received activity call', flush=True)
    if os.getenv('ERROR_ACTIVITY_MODE', 'false') == 'true':
        print('app3 - raising error in activity due to error mode being enabled', flush=True)
        raise ValueError('Error in activity due to error mode being enabled')
    print('app3 - returning activity result', flush=True)
    return 3


if __name__ == '__main__':
    wfr.start()
    time.sleep(15)  # Keep the workflow runtime alive for a while to process requests
    wfr.shutdown()
