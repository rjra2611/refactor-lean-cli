# QUANTCONNECT.COM - Democratizing Finance, Empowering Individuals.
# Lean CLI v1.0. Copyright 2021 QuantConnect Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import Any, Dict
from lean.models.brokerages.local.json_module import JsonModule

class JsonDataFeed(JsonModule):
    """A JsonModule implementation for the Json data feed module."""

    def __init__(self, json_datafeed_data: Dict[str, Any]) -> None:
        super().__init__(json_datafeed_data)

    def get_live_name(self, environment_name: str) -> str:
        environment_obj = self.get_configurations_env_values_from_name(environment_name)
        [live_name] = [x["Value"] for x in environment_obj if x["Name"] == "data-queue-handler"]
        return live_name
    
    
