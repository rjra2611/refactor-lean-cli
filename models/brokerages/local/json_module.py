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
from lean.models.logger import Option
from lean.models.configuration import BrokerageEnvConfiguration, Configuration, InternalInputUserInput
from lean.models.json_module_config import LeanConfigConfigurer
import copy
import abc

class JsonModule(LeanConfigConfigurer, abc.ABC):
    """The JsonModule class is the base class extended for all json modules."""

    def __init__(self, json_module_data: Dict[str, Any]) -> None:
        for key,value in json_module_data.items():
            if key == "configurations":
                temp_list = []
                for config in value:
                    temp_list.append(Configuration.factory(config))
                self._lean_configs = self.sort_configs(temp_list)
                continue
            setattr(self, self._convert_lean_key_to_attribute(key), value)
        self._organization_name = f'{self._name.lower().replace(" ", "-")}-organization'
        self._is_module_installed = False
        self._is_installed_and_build = False


    def configure(self, lean_config: Dict[str, Any], environment_name: str) -> None:
        self._configure_environment(lean_config, environment_name)
        self.configure_credentials(lean_config)

    @property
    def _user_filters(self) -> str:
        return [config._value for config in self._lean_configs if isinstance(config, BrokerageEnvConfiguration)]

    def sort_configs(self, configs: List[Configuration]) -> List[Configuration]:
        sorted_configs = []
        brokerage_configs = []
        for config in configs:
            if isinstance(config, BrokerageEnvConfiguration):
                brokerage_configs.append(config)
            else:
                sorted_configs.append(config)
        return brokerage_configs + sorted_configs

    def get_name(self) -> str:
        return self._name

    def check_if_config_passes_filters(self, config)  -> bool:
        return all(elem in config._filter._options for elem in self._user_filters)

    def update_configs(self, key_and_values: Dict[str, str]):
        for key, value in key_and_values.items():
            self.update_value_for_given_config(key,value)

    def get_configurations_env_values_from_name(self, target_env: str) -> List[Configuration]: 
        [env_config] = [config for config in self._lean_configs if 
                            config._is_type_configurations_env and self.check_if_config_passes_filters(config)
                        ] or [None]
        return [] if env_config is None else env_config._env_and_values[target_env]

    def get_organzation_id(self) -> str:
        [organization_id] = [config._value for config in self._lean_configs if self._organization_name == config._name]
        return organization_id

    def update_value_for_given_config(self, target_name: str, value: Any) -> None:
        [idx] = [i for i in range(len(self._lean_configs)) if self._lean_configs[i]._name == target_name]
        self._lean_configs[idx]._value = value

    def get_config_value_from_name(self, target_name: str) -> str:
        [idx] = [i for i in range(len(self._lean_configs)) if self._lean_configs[i]._name == target_name]
        return self._lean_configs[idx]._value

    def get_required_properties(self) -> List[str]:
        return [config._name for config in self.get_required_configs()]

    def get_required_configs(self) -> List[Configuration]:
        return [copy.copy(config) for config in self._lean_configs if config.is_required_from_user()
                    and self.check_if_config_passes_filters(config)]

    def get_essential_properties(self) -> List[str]:
        return [config._name for config in self.get_essential_configs()]

    def get_essential_configs(self) -> List[Configuration]:
        return [copy.copy(config) for config in self._lean_configs if isinstance(config, BrokerageEnvConfiguration)]

    def get_all_input_configs(self) -> List[Configuration]:
        return [copy.copy(config) for config in self._lean_configs if config.is_required_from_user()]

    def build(self, lean_config: Dict[str, Any], logger: Logger) -> 'JsonModule':
        
        if self._is_installed_and_build:
            return self

        for configuration in self._lean_configs:
            if not configuration.is_required_from_user():
                continue
            if not isinstance(configuration, BrokerageEnvConfiguration) and not self.check_if_config_passes_filters(configuration):
                continue
            if type(configuration) is InternalInputUserInput:
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
                if configuration._log_message is not None:
                    logger.info(configuration._log_message.strip())
                user_choice = configuration.AskUserForInput(self._get_default(lean_config, configuration._name), logger)
            self.update_value_for_given_config(configuration._name, user_choice)
        
        return self

    def _configure_environment(self, lean_config: Dict[str, Any], environment_name: str) -> None:
        if self._is_installed_and_build:
            return 
        self.ensure_module_installed()

        for environment_config in self.get_configurations_env_values_from_name(environment_name):
            lean_config["environments"][environment_name][environment_config["Name"]] = environment_config["Value"]

    def configure_credentials(self, lean_config: Dict[str, Any]) -> None:
        if self._is_installed_and_build:
            return
        if self._installs:
            lean_config["job-organization-id"] = self.get_organzation_id()
        for configuration in self._lean_configs:
            value = None
            if configuration._is_type_configurations_env:
                continue
            elif not self.check_if_config_passes_filters(configuration):
                continue
            elif type(configuration) is InternalInputUserInput:
                for option in configuration._value_options:
                    if option._condition.check(self.get_config_value_from_name(option._condition._dependent_config_id)):
                        value = option._value
                        break
            else:
                value = configuration._value
            lean_config[configuration._name] = value
        self._save_properties(lean_config, self.get_required_properties())

    def ensure_module_installed(self) -> None:
        if not self._is_module_installed and self._installs:
            container.module_manager().install_module(self._product_id, self.get_organzation_id())
            self._is_module_installed = True
