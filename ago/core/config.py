#!/usr/bin/env python3
"""
Ago Configuration System - Docker-inspired global + project config
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from rich.console import Console

console = Console()


@dataclass
class RegistryConfig:
    """Configuration for a template registry"""

    name: str
    url: str
    type: str = "http"  # http, github, local
    enabled: bool = True
    token: Optional[str] = None
    repos: Optional[List[str]] = None  # For GitHub type
    priority: int = 100


class AgoConfig:
    """Ago configuration manager with global + project config merging"""

    def __init__(self):
        self.global_config_dir = Path.home() / ".ago"
        self.global_config_file = self.global_config_dir / "config.yaml"
        self.global_auth_file = self.global_config_dir / "auth.yaml"

        # Project config (search upwards from current directory)
        self.project_config_dir = self._find_project_config_dir()
        self.project_config_file = (
            self.project_config_dir / "config.yaml" if self.project_config_dir else None
        )
        self.project_auth_file = (
            self.project_config_dir / "auth.env" if self.project_config_dir else None
        )

        self._config_cache = None

    def _find_project_config_dir(self) -> Optional[Path]:
        """Find project config by searching upwards for .ago/ directory"""
        current = Path.cwd()

        # Search up to 10 levels or until root
        for _ in range(10):
            ago_dir = current / ".ago"
            if ago_dir.exists() and ago_dir.is_dir():
                return ago_dir

            parent = current.parent
            if parent == current:  # Reached filesystem root
                break
            current = parent

        return None

    def _load_yaml_config(self, config_file: Path) -> Dict[str, Any]:
        """Load YAML config file with error handling"""
        if not config_file.exists():
            return {}

        try:
            with open(config_file, "r") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            console.print(f"⚠️ Warning: Could not load config {config_file}: {e}")
            return {}

    def _load_env_auth(self, auth_file: Path) -> Dict[str, str]:
        """Load environment-style auth file"""
        if not auth_file.exists():
            return {}

        auth = {}
        try:
            with open(auth_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        auth[key.strip()] = value.strip().strip("\"'")
        except Exception as e:
            console.print(f"⚠️ Warning: Could not load auth file {auth_file}: {e}")

        return auth

    def _merge_configs(
        self, global_config: Dict[str, Any], project_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge project config into global config (project overrides global)"""
        merged = global_config.copy()

        for key, value in project_config.items():
            if (
                key in merged
                and isinstance(merged[key], dict)
                and isinstance(value, dict)
            ):
                # Deep merge for nested dicts
                merged[key] = self._merge_configs(merged[key], value)
            else:
                # Direct override for scalars and lists
                merged[key] = value

        return merged

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            "registries": {
                "ago_local": {"type": "builtin", "enabled": True, "priority": 1},
                "ago_remote": {
                    "url": "https://github.com/GluonGrid/ago/tree/main/ago/templates",
                    "type": "github",
                    "enabled": True,
                    "priority": 2,
                },
            },
            "defaults": {
                "template_resolution_order": ["local", "builtin"],
                "auto_update": False,
                "cache_duration": "24h",
            },
            "discovery": {
                "local_paths": ["./", "./templates/", "~/.ago/templates/"],
                "file_extensions": [".agt"],
            },
        }

    def get_config(self, force_reload: bool = False) -> Dict[str, Any]:
        """Get merged configuration (cached unless force_reload=True)"""
        if self._config_cache is not None and not force_reload:
            return self._config_cache

        # 1. Start with defaults
        config = self._get_default_config()

        # 2. Load global config
        global_config = self._load_yaml_config(self.global_config_file)
        config = self._merge_configs(config, global_config)

        # 3. Load project config (if exists)
        if self.project_config_file and self.project_config_file.exists():
            project_config = self._load_yaml_config(self.project_config_file)
            config = self._merge_configs(config, project_config)

        # 4. Load authentication
        auth = {}
        if self.global_auth_file.exists():
            global_auth = self._load_yaml_config(self.global_auth_file)
            auth.update(global_auth)

        if self.project_auth_file and self.project_auth_file.exists():
            project_auth = self._load_env_auth(self.project_auth_file)
            auth.update(project_auth)

        # 5. Apply environment variables
        for key, value in os.environ.items():
            if key.startswith("AGO_"):
                # Convert AGO_REGISTRY_GITHUB_TOKEN to nested dict path
                config_path = key[8:].lower().split("_")  # Remove AGO_ prefix
                self._set_nested_value(config, config_path, value)

        # 6. Merge auth into config
        if auth:
            config["auth"] = auth

        # Cache and return
        self._config_cache = config
        return config

    def _set_nested_value(self, config: Dict[str, Any], path: List[str], value: str):
        """Set nested dictionary value from environment variable"""
        current = config
        for key in path[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[path[-1]] = value

    def get_registries(self) -> List[RegistryConfig]:
        """Get configured registries sorted by priority"""
        config = self.get_config()
        registries = []

        for name, reg_config in config.get("registries", {}).items():
            if not reg_config.get("enabled", True):
                continue

            registry = RegistryConfig(
                name=name,
                url=reg_config.get("url", ""),
                type=reg_config.get("type", "http"),
                enabled=reg_config.get("enabled", True),
                token=reg_config.get("token")
                or config.get("auth", {}).get(f"{name}_token"),
                repos=reg_config.get("repos"),
                priority=reg_config.get("priority", 100),
            )
            registries.append(registry)

        # Sort by priority (lower number = higher priority)
        registries.sort(key=lambda r: r.priority)
        return registries

    def get_template_resolution_order(self) -> List[str]:
        """Get template resolution order"""
        config = self.get_config()
        return config.get("defaults", {}).get(
            "template_resolution_order", ["local", "builtin"]
        )

    def get_local_discovery_paths(self) -> List[str]:
        """Get local template discovery paths (current working directory only)"""
        config = self.get_config()
        # Local discovery should only include current working directory
        # Global builtin/pulled templates are handled separately in registry
        return config.get("discovery", {}).get("local_paths", ["./", "./templates/"])

    def get_template_extensions(self) -> List[str]:
        """Get template file extensions to discover"""
        config = self.get_config()
        return config.get("discovery", {}).get("file_extensions", [".agt"])

    def set_global_config(self, key_path: str, value: Any):
        """Set global configuration value"""
        self.global_config_dir.mkdir(exist_ok=True)

        # Load existing config
        config = self._load_yaml_config(self.global_config_file)

        # Set nested value
        keys = key_path.split(".")
        current = config
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value

        # Save config
        with open(self.global_config_file, "w") as f:
            yaml.dump(config, f, default_flow_style=False)

        # Clear cache
        self._config_cache = None

    def set_project_config(self, key_path: str, value: Any):
        """Set project-level configuration value"""
        if not self.project_config_dir:
            # Create .ago in current directory
            self.project_config_dir = Path.cwd() / ".ago"
            self.project_config_file = self.project_config_dir / "config.yaml"

        self.project_config_dir.mkdir(exist_ok=True)

        # Load existing config
        config = self._load_yaml_config(self.project_config_file)

        # Set nested value
        keys = key_path.split(".")
        current = config
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value

        # Save config
        with open(self.project_config_file, "w") as f:
            yaml.dump(config, f, default_flow_style=False)

        # Clear cache
        self._config_cache = None

    def get_config_value(self, key_path: str, default: Any = None) -> Any:
        """Get configuration value using dot notation"""
        config = self.get_config()
        keys = key_path.split(".")

        current = config
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default

        return current


# Global config instance
config = AgoConfig()

