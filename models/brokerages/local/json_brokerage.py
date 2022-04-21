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
from lean.components.util.logger import Logger
from lean.container import container
from lean.models.brokerages.local.json_module_base import LocalBrokerage
from lean.models.logger import Option
from lean.models.configuration import Configuration
import copy

class JsonBrokerage(LocalBrokerage):
    """A LocalBrokerage implementation for the Binance brokerage."""
    _is_module_installed = False

    def __init__(self, json_brokerage_data: Dict[str, Any]) -> None:
        for key,value in json_brokerage_data.items():
            if key == "configurations":
                temp_list = []
                for config in value:
                    temp_list.append(Configuration.factory(config))
                self._lean_configs = temp_list
                continue
            setattr(self, self._convert_lean_key_to_attribute(key), value)
        self._organization_name = f"{self._name.lower()}-organization"
                
    def get_name(self) -> str:
        return self._name

    @property
    def _testnet(self):
        return not [config for config in self._lean_configs if config._is_type_brokerage_env][0]._is_paper_environment

    def update_configs(self, key_and_values: Dict[str, str]):
        for key, value in key_and_values.items():
            self.update_value_for_given_config(key,value)
            
    def get_live_name(self, environment_name: str, is_brokerage=False) -> str:
        environment_obj = self.get_configurations_env_values_from_name(environment_name)
        if is_brokerage:
            return [x["Value"] for x in environment_obj if x["Name"] == "live-mode-brokerage"][0]
        return [x["Value"] for x in environment_obj if x["Name"] == "data-queue-handler"][0]

    def get_configurations_env_values_from_name(self, target_env: str): 
        env_config = [config for config in self._lean_configs if config._is_type_configurations_env][0]
        return env_config._env_and_values[target_env]

    def get_organzation_id(self) -> str:
        return [config._value for config in self._lean_configs if self._organization_name == config._name][0]

    def update_value_for_given_config(self, target_name: str, value: Any) -> None:
        idx = [i for i in range(len(self._lean_configs)) if self._lean_configs[i]._name == target_name][0]
        self._lean_configs[idx]._value = value

    def get_config_value_from_name(self, target_name: str) -> Any:
        idx = [i for i in range(len(self._lean_configs)) if self._lean_configs[i]._name == target_name][0]
        return self._lean_configs[idx]._value

    def get_required_properties(self) -> List[str]:
        return [config._name for config in self._lean_configs if config.is_required_from_user()]

    def get_required_configs(self) -> List[str]:
        return [copy.copy(config) for config in self._lean_configs if config.is_required_from_user()]

    def _build(self, lean_config: Dict[str, Any], logger: Logger, skip_build: bool = False) -> LocalBrokerage:
        
        self._is_installed_and_build = skip_build
        if self._is_installed_and_build:
            return self
        
        logger.info("""
Create an API key by logging in and accessing the Binance API Management page (https://www.binance.com/en/my/settings/api-management).
        """.strip())

        for configuration in self._lean_configs:
            if not configuration.is_required_from_user():
                continue
            if self._organization_name == configuration._name:
                api_client = container.api_client()
                organizations = api_client.organizations.get_all()
                options = [Option(id=organization.id, label=organization.name) for organization in organizations]
                organization_id = logger.prompt_list(
                    "Select the organization with the {} module subscription".format(self.get_name()),
                    options
                )
                user_choice = organization_id
            else:
                user_choice = configuration.AskUserForInput(self._get_default(lean_config, configuration._name), logger)
            self.update_value_for_given_config(configuration._name, user_choice)
        
        return self

    def _configure_environment(self, lean_config: Dict[str, Any], environment_name: str) -> None:
        if hasattr(self, '_is_installed_and_build') and self._is_installed_and_build:
            return 
        self.ensure_module_installed()

        for environment_config in self.get_configurations_env_values_from_name(environment_name):
            lean_config["environments"][environment_name][environment_config["Name"]] = environment_config["Value"]

    def configure_credentials(self, lean_config: Dict[str, Any]) -> None:
        if hasattr(self, '_is_installed_and_build') and self._is_installed_and_build:
            return 
        lean_config["job-organization-id"] = self.get_organzation_id()
        for configuration in self._lean_configs:
            if configuration._is_type_configurations_env:
                continue
            elif (self._testnet and not "paper" in configuration._envrionment) or (not self._testnet and not "live" in configuration._envrionment):
                continue
            lean_config[configuration._name] = configuration._value
        self._save_properties(lean_config, self.get_required_properties())

    def ensure_module_installed(self) -> None:
        if not self._is_module_installed and self._installs:
            container.module_manager().install_module(self._product_id, self.get_organzation_id())
            self._is_module_installed = True
