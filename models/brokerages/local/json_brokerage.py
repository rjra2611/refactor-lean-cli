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

from typing import Any, Dict, List
import click
from lean.components.util.logger import Logger
from lean.container import container
from lean.models.brokerages.local.json_module_base import LocalBrokerage
from lean.models.logger import Option
from lean.models.configuration import Configuration

class JsonBrokerage(LocalBrokerage):
    """A LocalBrokerage implementation for the Binance brokerage."""
    _is_module_installed = False
    _testnet = False
    _lean_configs = []

    def __init__(self, json_brokerage_data: Dict[str, Any]) -> None:
        for key,value in json_brokerage_data.items():
            if key == "configurations":
                for config in value:
                    self._lean_configs.append(Configuration.factory(config))
            setattr(self, self._convert_json_key_to_property(key), value)
                
    def get_name(self) -> str:
        return self._name

    def update_configs(self, key_and_values: Dict[str, str]):
        for key, value in key_and_values.items():
            self.update_value_for_given_config(key,value)
            
    def get_live_name(self, is_brokerage) -> str:
        if is_brokerage:
            return self._configurations["environments"]["live-mode-brokerage"]
        return self._configurations["environments"]["data-queue-handler"]

    def update_value_for_given_config(self, target_name: str, value: Any) -> None:
        idx = [i for i in range(len(self._configurations)) if self._configurations[i]["Name"] == target_name][0]
        self._configurations[idx]["Value"] = value

    def get_config_value_from_name(self, target_name: str) -> Any:
        idx = [i for i in range(len(self._configurations)) if self._configurations[i]["Name"] == target_name][0]
        return self._configurations[idx]["Value"]

    def _build(self, lean_config: Dict[str, Any], logger: Logger, skip_build: bool = False) -> LocalBrokerage:
        
        if skip_build:
            return self
        
        api_client = container.api_client()
        organizations = api_client.organizations.get_all()
        options = [Option(id=organization.id, label=organization.name) for organization in organizations]
        organization_id = logger.prompt_list(
            "Select the organization with the {} module subscription".format(self.get_name()),
            options
        )
        logger.info("""
Create an API key by logging in and accessing the Binance API Management page (https://www.binance.com/en/my/settings/api-management).
        """.strip())

        for configuration in self._configurations:

            if configuration["Name"] == "environments":
                continue
            
            if "required" in configuration.keys() and configuration["required"]:
                
                if configuration["requirement-type"] == "prompt":
                    user_choice = click.prompt(configuration["Name"], self._get_default(lean_config, configuration["Name"]))
                
                elif configuration["requirement-type"] == "prompt_password":
                    user_choice = logger.prompt_password(configuration["Name"], self._get_default(lean_config, configuration["Name"]))
                
                elif configuration["requirement-type"] == "confirm":
                    user_choice = click.confirm(configuration["requirement-statement"])
                    self._testnet = user_choice
                elif configuration["requirement-type"] == "choice":
                    user_choice = click.prompt(
                        configuration["Name"],
                        self._get_default(lean_config, configuration["Name"]),
                        type=click.Choice(configuration["Value"], case_sensitive=False)
                    )
                self.update_value_for_given_config(configuration["Name"], user_choice)
        
        organization_id_obj = {
           "Help": "",
           "required": True,
           "Name": "job-organization-id",
           "Value": organization_id,
           "requirement-type": "prompt",
           "environment": [
             "live",
             "paper"
           ]
        }
        self._configurations.append(organization_id_obj)
        return self

    def get_required_properties(self) -> List[str]:
        return [config["Name"] for config in self._configurations if "required" in config.keys() and config["required"]]
    
    def update_properties(self, properties: Dict[str, str]):
        raise NotImplementedError()

    def _configure_environment(self, lean_config: Dict[str, Any], environment_name: str) -> None:
        self.ensure_module_installed()

        environment_obj = [x["Value"] for x in self.get_config_value_from_name("environments") if x["Name"] == environment_name][0]
        for environment_config in environment_obj:
            lean_config["environments"][environment_name][environment_config["Name"]] = environment_config["Value"]

    def configure_credentials(self, lean_config: Dict[str, Any]) -> None:
        lean_config["job-organization-id"] = self.get_config_value_from_name("job-organization-id")
        save_properties_keys = ["job-organization-id"]

        for configuration in self._configurations:
            if configuration["Name"] == "environments":
                continue
            elif (self._testnet and not "paper" in configuration["environment"]) or (not self._testnet and not "live" in configuration["environment"]):
                continue
            elif "required" in configuration.keys() and configuration["required"]:
                save_properties_keys.append(configuration["Name"])
            
            lean_config[configuration["Name"]] = configuration["Value"]
        
        self._save_properties(lean_config, save_properties_keys)

    def ensure_module_installed(self) -> None:
        if not self._is_module_installed and self._installs:
            container.module_manager().install_module(self._product_id, self.get_config_value_from_name("job-organization-id"))
            self._is_module_installed = True
