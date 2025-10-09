#!/usr/bin/env python3
"""
Ago Registry - Local agent template registry (like Docker images)
"""

import base64
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import yaml
from rich.console import Console

from .config import RegistryConfig, config

console = Console()


class AgentRegistry:
    """Local registry for agent templates (like Docker images)"""

    def __init__(self, registry_dir: Path = Path.home() / ".ago" / "registry"):
        self.registry_dir = registry_dir
        self.registry_dir.mkdir(parents=True, exist_ok=True)

        # Registry structure:
        # ~/.ago/registry/
        # ├── index.json              # Registry index with all templates
        # ├── templates/              # Template storage
        # │   ├── researcher/
        # │   │   ├── v1.0/
        # │   │   │   ├── template.yaml
        # │   │   │   └── prompt.txt
        # │   │   └── v1.1/
        # │   └── assistant/
        # │       └── v1.0/
        # └── cache/                  # Download cache

        self.templates_dir = self.registry_dir / "templates"
        self.cache_dir = self.registry_dir / "cache"
        self.index_file = self.registry_dir / "index.json"

        self.templates_dir.mkdir(exist_ok=True)
        self.cache_dir.mkdir(exist_ok=True)

        # Initialize registry (builtin templates should be pulled from official repo, not hardcoded)
        # self._initialize_builtin_templates() # TODO: Remove this and pull from official ago repo

    def _initialize_builtin_templates(self):
        """Initialize registry with built-in templates from ago/templates/"""
        # Path to built-in templates in the package
        package_templates = Path(__file__).parent.parent / "templates"

        if not package_templates.exists():
            return

        index = self._load_index()

        # Built-in template definitions
        builtin_templates = {
            "researcher": {
                "name": "researcher",
                "description": "Information gathering and analysis specialist",
                "version": "1.0",
                "model": "claude-3-5-sonnet-20241022",
                "tools": ["web_search", "file_manager"],
                "prompt": """You are a Research Agent specializing in information gathering and analysis.

## Your Expertise
You excel at:
- Breaking down complex research questions into manageable tasks
- Using available tools to gather information from multiple sources
- Synthesizing findings into coherent, comprehensive responses
- Providing well-cited and credible research insights

## Research Approach
1. Analyze the research question thoroughly
2. Identify the best tools and sources for investigation
3. Gather information systematically
4. Cross-reference findings when possible
5. Present results in a structured, actionable format

## Inter-Agent Collaboration
- You can delegate data organization or formatting tasks to other agents
- You respond to research requests from other agents in the system
- You provide thorough analysis to support team decision-making

Remember: Be methodical, thorough, and always cite your sources for credibility.""",
            },
            "assistant": {
                "name": "assistant",
                "description": "General purpose helpful assistant",
                "version": "1.0",
                "model": "claude-3-5-haiku-20241022",
                "tools": ["file_manager"],
                "prompt": """You are a helpful Assistant Agent specializing in task completion and organization.

## Your Capabilities
You excel at:
- Processing and organizing information efficiently
- Handling delegated tasks like formatting, summarizing, and analysis
- Providing clear, well-structured outputs
- Supporting other agents with their specialized work

## Core Functions
1. **Data Organization**: Structure and categorize information
2. **Task Processing**: Complete delegated tasks efficiently
3. **Collaborative Support**: Assist other agents with their work
4. **Quality Assurance**: Ensure outputs meet requirements

## Working Style
- Be efficient and accurate in task completion
- Provide clear, well-structured responses
- Use available tools effectively
- Ask for clarification when requirements are unclear
- Always acknowledge task completion with status updates

## Inter-Agent Collaboration
- You can receive task delegation from other agents
- You can request additional information when needed
- You provide reliable support to maintain smooth workflows

Remember: You're the reliable assistant in this system. Focus on quality output and efficient collaboration.""",
            },
            "analyst": {
                "name": "analyst",
                "description": "Data analysis and insights expert",
                "version": "1.0",
                "model": "claude-3-5-sonnet-20241022",
                "tools": ["file_manager", "web_search"],
                "prompt": """You are a Data Analyst Agent specializing in data analysis and insights generation.

## Your Expertise
You excel at:
- Processing and analyzing complex datasets
- Identifying patterns, trends, and insights from data
- Creating visualizations and summaries of findings
- Translating data into actionable business insights
- Statistical analysis and interpretation

## Analysis Approach
1. Understand the data context and objectives thoroughly
2. Explore and validate data quality and completeness
3. Apply appropriate analytical methods and techniques
4. Identify significant patterns, correlations, and outliers
5. Generate clear, actionable insights and recommendations

## Inter-Agent Collaboration
- You can request data gathering from research agents
- You can delegate visualization tasks to other agents
- You provide analytical insights to support decision-making
- You respond to analytical requests from other agents in the system

Remember: Your role is to find the story in the data and translate it into clear, actionable insights.""",
            },
            "writer": {
                "name": "writer",
                "description": "Content creation and documentation specialist",
                "version": "1.0",
                "model": "claude-3-5-haiku-20241022",
                "tools": ["file_manager", "web_search"],
                "prompt": """You are a Writer Agent specializing in content creation and documentation.

## Your Expertise
You excel at:
- Creating clear, engaging, and well-structured content
- Adapting writing style to different audiences and purposes
- Technical documentation and user guides
- Content editing and improvement
- Research-based writing with proper citations

## Writing Approach
1. Understand the target audience and purpose
2. Research and gather relevant information
3. Create structured outlines and content plans
4. Write clear, engaging, and informative content
5. Edit and refine for clarity and impact

## Inter-Agent Collaboration
- You can request research data from research agents
- You can delegate fact-checking to other agents
- You provide well-crafted content to support team objectives
- You respond to writing requests from other agents in the system

Remember: Good writing serves the reader. Focus on clarity, accuracy, and engaging presentation.""",
            },
            "coordinator": {
                "name": "coordinator",
                "description": "Project management and task orchestration",
                "version": "1.0",
                "model": "claude-3-5-sonnet-20241022",
                "tools": ["file_manager"],
                "prompt": """You are a Coordinator Agent specializing in project management and task orchestration.

## Your Expertise
You excel at:
- Breaking down complex projects into manageable tasks
- Coordinating work between multiple agents and team members
- Tracking progress and ensuring deadlines are met
- Identifying dependencies and potential bottlenecks
- Facilitating effective communication and collaboration

## Coordination Approach
1. Analyze project requirements and scope
2. Break down work into clear, actionable tasks
3. Assign tasks based on agent capabilities and availability
4. Monitor progress and provide status updates
5. Resolve conflicts and remove obstacles

## Inter-Agent Collaboration
- You delegate tasks to appropriate specialist agents
- You coordinate multi-agent workflows and dependencies
- You provide project updates and status reports
- You ensure all agents have the information they need to succeed

Remember: Your role is to ensure smooth collaboration and successful project completion through effective coordination.""",
            },
        }

        # Create organized template directory structure
        builtin_dir = self.templates_dir / "builtin"
        pulled_dir = self.templates_dir / "pulled"

        builtin_dir.mkdir(exist_ok=True)
        pulled_dir.mkdir(exist_ok=True)

        # Add built-in templates to registry if not already present
        for template_name, template_config in builtin_templates.items():
            template_key = f"{template_name}:v{template_config['version']}"

            if template_key not in index:
                # Create .agt file directly in builtin directory
                template_agt_path = builtin_dir / f"{template_name}.agt"

                # Create .agt file with embedded prompt in builtin directory
                agt_content = f"""name: {template_name}
version: "{template_config["version"]}"
description: "{template_config["description"]}"
author: "Ago Built-in Templates"
repository: "builtin"
tags: ["builtin", "{template_name}"]

# Model configuration
model: {template_config["model"]}
temperature: 0.7
max_tokens: 4000

# Tool requirements
tools:
{yaml.dump(template_config["tools"], default_flow_style=False).strip()}

# Built-in template metadata
metadata:
  category: "builtin"
  complexity: "intermediate"
  created_at: "{datetime.now().isoformat()}"
  source: "builtin"

# Main agent prompt (embedded directly)
prompt: |
{chr(10).join("  " + line for line in template_config["prompt"].split(chr(10)))}
"""
                template_agt_path.write_text(agt_content)

                # Add to index with new path structure
                index[template_key] = {
                    "name": template_name,
                    "version": template_config["version"],
                    "description": template_config["description"],
                    "model": template_config["model"],
                    "tools": template_config["tools"],
                    "created_at": datetime.now().isoformat(),
                    "source": "builtin",
                    "path": str(
                        template_agt_path.parent
                    ),  # Directory path for compatibility
                    "agt_file": str(template_agt_path),  # Direct .agt file path
                }

        self._save_index(index)

    def _load_index(self) -> Dict[str, Any]:
        """Load registry index"""
        if self.index_file.exists():
            try:
                with open(self.index_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                console.print(f"⚠️ Warning: Could not load registry index: {e}")

        return {}

    def _save_index(self, index: Dict[str, Any]):
        """Save registry index"""
        try:
            with open(self.index_file, "w") as f:
                json.dump(index, f, indent=2)
        except Exception as e:
            console.print(f"❌ Error saving registry index: {e}")

    def _add_template_to_index(self, template_data: Dict[str, Any], template_file_path: Path, source: str, registry_name: str = None):
        """Add template to index for fast lookup"""
        try:
            index = self._load_index()
            
            template_key = f"{template_data['name']}:v{template_data.get('version', '1.0')}"
            
            # Add to index with metadata
            index[template_key] = {
                "name": template_data["name"],
                "version": template_data.get("version", "1.0"),
                "description": template_data.get("description", "Template"),
                "model": template_data.get("model", "claude-3-5-haiku-20241022"),
                "tools": template_data.get("tools", []),
                "created_at": datetime.now().isoformat(),
                "source": source,
                "registry": registry_name,
                "path": str(template_file_path.parent),
                "agt_file": str(template_file_path),
            }
            
            self._save_index(index)
            
        except Exception as e:
            console.print(f"⚠️ Warning: Could not add template to index: {e}")

    def _load_and_validate_index(self) -> Dict[str, Any]:
        """Load index and rebuild if missing or corrupted"""
        index = self._load_index()
        
        # If index is empty or missing, rebuild it
        if not index:
            console.print("🔄 [dim]Rebuilding template index...[/dim]")
            index = self._rebuild_index()
        else:
            # Validate that indexed templates actually exist
            index = self._validate_and_clean_index(index)
            
        return index

    def _rebuild_index(self) -> Dict[str, Any]:
        """Rebuild index by scanning all template directories"""
        index = {}
        
        # Scan builtin templates
        builtin_dir = self.templates_dir / "builtin"
        if builtin_dir.exists():
            for agt_file in builtin_dir.glob("*.agt"):
                try:
                    with open(agt_file, "r") as f:
                        template_data = yaml.safe_load(f)
                    
                    if template_data and template_data.get("name"):
                        template_key = f"{template_data['name']}:v{template_data.get('version', '1.0')}"
                        index[template_key] = {
                            "name": template_data["name"],
                            "version": template_data.get("version", "1.0"),
                            "description": template_data.get("description", "Built-in template"),
                            "model": template_data.get("model", "claude-3-5-haiku-20241022"),
                            "tools": template_data.get("tools", []),
                            "created_at": template_data.get("created_at", datetime.now().isoformat()),
                            "source": "builtin",
                            "path": str(agt_file.parent),
                            "agt_file": str(agt_file),
                        }
                except Exception:
                    continue
        
        # Scan pulled templates
        pulled_dir = self.templates_dir / "pulled"
        if pulled_dir.exists():
            for agt_file in pulled_dir.glob("*.agt"):
                try:
                    with open(agt_file, "r") as f:
                        template_data = yaml.safe_load(f)
                    
                    if template_data and template_data.get("name"):
                        template_key = f"{template_data['name']}:v{template_data.get('version', '1.0')}"
                        index[template_key] = {
                            "name": template_data["name"],
                            "version": template_data.get("version", "1.0"),
                            "description": template_data.get("description", "Pulled template"),
                            "model": template_data.get("model", "claude-3-5-haiku-20241022"),
                            "tools": template_data.get("tools", []),
                            "created_at": template_data.get("created_at", datetime.now().isoformat()),
                            "source": "pulled",
                            "path": str(agt_file.parent),
                            "agt_file": str(agt_file),
                        }
                except Exception:
                    continue
        
        # Save rebuilt index
        self._save_index(index)
        return index

    def _validate_and_clean_index(self, index: Dict[str, Any]) -> Dict[str, Any]:
        """Validate index entries and remove stale entries"""
        cleaned_index = {}
        changed = False
        
        for template_key, template_data in index.items():
            agt_file = template_data.get("agt_file")
            if agt_file and Path(agt_file).exists():
                cleaned_index[template_key] = template_data
            else:
                # Template file no longer exists, remove from index
                changed = True
                console.print(f"🧹 [dim]Removing stale template from index: {template_key}[/dim]")
        
        # Save cleaned index if changes were made
        if changed:
            self._save_index(cleaned_index)
        
        return cleaned_index

    def list_templates(self) -> List[Dict[str, Any]]:
        """List all available templates using index as single source of truth"""
        # Load index and validate it
        index = self._load_and_validate_index()
        
        templates = []
        for template_key, template_data in index.items():
            source_icon = "🏠" if template_data.get('source') == 'builtin' else "🌐" if template_data.get('source') == 'pulled' else "📁"
            templates.append(
                {
                    "key": template_key,
                    "name": template_data["name"],
                    "version": template_data["version"],
                    "description": template_data["description"],
                    "model": template_data["model"],
                    "tools": template_data["tools"],
                    "source": f"{source_icon} {template_data.get('source', 'unknown')}",
                    "created_at": template_data.get("created_at", "unknown"),
                }
            )

        # Add current directory templates (not indexed, always scan)
        local_templates = self._discover_local_templates()
        templates.extend(local_templates)

        # Sort by name then version
        templates.sort(key=lambda x: (x["name"], x["version"]))
        return templates

    def _discover_local_templates(self) -> List[Dict[str, Any]]:
        """Auto-discover local template files using config-based paths and extensions"""
        templates = []

        # Get discovery config
        local_paths = config.get_local_discovery_paths()
        extensions = config.get_template_extensions()

        for search_path in local_paths:
            path = Path(search_path).expanduser()
            if not path.exists():
                continue

            # Search for template files with configured extensions
            for ext in extensions:
                pattern = f"*{ext}"
                for template_file in path.glob(pattern):
                    try:
                        with open(template_file, "r") as f:
                            template_data = yaml.safe_load(f)

                        if not template_data or not template_data.get("name"):
                            continue  # Skip invalid templates

                        templates.append(
                            {
                                "key": f"{template_data['name']}:v{template_data.get('version', '1.0')}",
                                "name": template_data["name"],
                                "version": template_data.get("version", "1.0"),
                                "description": template_data.get(
                                    "description", "Local template"
                                ),
                                "model": template_data.get(
                                    "model", "claude-3-5-haiku-20241022"
                                ),
                                "tools": template_data.get("tools", []),
                                "source": f"📁 {template_file.name}",
                                "created_at": template_data.get(
                                    "created_at", "unknown"
                                ),
                                "file_path": str(template_file),  # For loading later
                            }
                        )
                    except Exception:
                        # Skip invalid template files
                        continue

        return templates

    def get_template(
        self, name: str, version: str = "latest"
    ) -> Optional[Dict[str, Any]]:
        """Get template using config-based resolution order"""
        resolution_order = config.get_template_resolution_order()

        for source in resolution_order:
            template = self._get_template_from_source(name, version, source)
            if template:
                return template

        return None

    def _get_template_from_source(
        self, name: str, version: str, source: str
    ) -> Optional[Dict[str, Any]]:
        """Get template from specific source"""
        if source == "local":
            return self._get_local_template(name, version)
        elif source == "builtin" or source == "registry":
            return self._get_registry_template(name, version)
        else:
            # Future: handle other registry sources (github, etc.)
            return None

    def _get_local_template(self, name: str, version: str) -> Optional[Dict[str, Any]]:
        """Get template from local files"""
        local_paths = config.get_local_discovery_paths()
        extensions = config.get_template_extensions()

        # Search for template files
        search_patterns = []
        if version == "latest":
            # Search for any version
            for ext in extensions:
                search_patterns.append(f"{name}{ext}")
                search_patterns.append(f"{name}-*{ext}")
        else:
            # Search for specific version
            for ext in extensions:
                search_patterns.append(f"{name}-v{version}{ext}")
                search_patterns.append(
                    f"{name}{ext}"
                )  # Check if file has version inside

        for search_path in local_paths:
            path = Path(search_path).expanduser()
            if not path.exists():
                continue

            for pattern in search_patterns:
                for template_file in path.glob(pattern):
                    try:
                        with open(template_file, "r") as f:
                            template_data = yaml.safe_load(f)

                        if not template_data or template_data.get("name") != name:
                            continue

                        # Check version match
                        file_version = template_data.get("version", "1.0")
                        if version != "latest" and file_version != version:
                            continue

                        # Load prompt content if specified
                        if "prompt" in template_data:
                            template_data["prompt_content"] = template_data["prompt"]
                        else:
                            template_data["prompt_content"] = (
                                "You are a helpful AI assistant."
                            )

                        return template_data

                    except Exception:
                        continue

        return None

    def _get_registry_template(
        self, name: str, version: str
    ) -> Optional[Dict[str, Any]]:
        """Get template from built-in registry (existing logic)"""
        index = self._load_index()

        if version == "latest":
            # Find latest version for this template
            matching_templates = [
                (key, data) for key, data in index.items() if data["name"] == name
            ]

            if not matching_templates:
                return None

            # Sort by version and get latest
            matching_templates.sort(key=lambda x: x[1]["version"], reverse=True)
            template_key, template_data = matching_templates[0]
        else:
            template_key = f"{name}:v{version}"
            template_data = index.get(template_key)

            if not template_data:
                return None

        # Load full template data from file system
        template_dir = Path(template_data["path"])

        if not template_dir.exists():
            console.print(f"⚠️ Warning: Template directory missing: {template_dir}")
            return None

        # Load .agt file directly (contains embedded prompt and metadata)
        full_template = template_data.copy()

        # Try direct .agt file path first (new structure)
        if "agt_file" in template_data:
            template_agt_path = Path(template_data["agt_file"])
            if template_agt_path.exists():
                try:
                    with open(template_agt_path, "r") as f:
                        agt_data = yaml.safe_load(f)
                        full_template.update(agt_data)
                        # Use embedded prompt directly
                        if "prompt" in agt_data:
                            full_template["prompt_content"] = agt_data["prompt"]
                except Exception as e:
                    console.print(f"⚠️ Warning: Could not load {template_agt_path}: {e}")
            else:
                console.print(
                    f"⚠️ Warning: Template .agt file missing: {template_agt_path}"
                )
        else:
            # Fallback to old directory-based structure for backward compatibility
            template_dir = Path(template_data["path"])
            if not template_dir.exists():
                console.print(f"⚠️ Warning: Template directory missing: {template_dir}")
                return None

            # Try .agt file in directory
            template_agt = template_dir / f"{name}.agt"
            if template_agt.exists():
                try:
                    with open(template_agt, "r") as f:
                        agt_data = yaml.safe_load(f)
                        full_template.update(agt_data)
                        if "prompt" in agt_data:
                            full_template["prompt_content"] = agt_data["prompt"]
                except Exception as e:
                    console.print(f"⚠️ Warning: Could not load {name}.agt: {e}")
            else:
                # Final fallback to old template.yaml format
                template_yaml = template_dir / "template.yaml"
                if template_yaml.exists():
                    try:
                        with open(template_yaml, "r") as f:
                            yaml_data = yaml.safe_load(f)
                            full_template.update(yaml_data)
                            if "prompt" in yaml_data:
                                full_template["prompt_content"] = yaml_data["prompt"]
                    except Exception as e:
                        console.print(f"⚠️ Warning: Could not load template.yaml: {e}")

        # Ensure prompt_content exists
        if "prompt_content" not in full_template and "prompt" in full_template:
            full_template["prompt_content"] = full_template["prompt"]
        elif "prompt_content" not in full_template:
            full_template["prompt_content"] = "You are a helpful AI assistant."

        return full_template

    def template_exists(self, name: str, version: str = "latest") -> bool:
        """Check if template exists in registry"""
        return self.get_template(name, version) is not None

    def pull_template(
        self, registry_name_template: str, version: str = "latest"
    ) -> bool:
        """Pull/update template from remote source

        Args:
            registry_name_template: Format "registry:template" (e.g., "github:my-template")
            version: Template version (default: "latest")
        """
        try:
            # Parse registry:template format
            if ":" in registry_name_template:
                registry_name, template_name = registry_name_template.split(":", 1)
            else:
                console.print(
                    "❌ [red]Invalid format. Use: registry:template (e.g., github:my-template)[/red]"
                )
                return False

            # Get registry configuration
            registries = config.get_registries()

            # Find the registry by name
            registry_config = None
            for registry in registries:
                if registry.name == registry_name:
                    registry_config = registry
                    break

            if registry_config is None:
                console.print(
                    f"❌ [red]Registry '{registry_name}' not found. Use 'ago registry list' to see available registries.[/red]"
                )
                return False

            registry_type = registry_config.type

            if registry_type == "github":
                return self._pull_from_github(registry_config, template_name, version)
            elif registry_type == "gitlab":
                return self._pull_from_gitlab(registry_config, template_name, version)
            elif registry_type == "http":
                return self._pull_from_http(registry_config, template_name, version)
            else:
                console.print(
                    f"❌ [red]Registry type '{registry_type}' not supported yet[/red]"
                )
                return False

        except Exception as e:
            console.print(f"❌ [red]Error pulling template:[/red] {str(e)}")
            return False

    def _pull_from_github(
        self, registry_config: RegistryConfig, template_name: str, version: str
    ) -> bool:
        """Pull template from GitHub repository"""
        try:
            # Parse GitHub URL (should be like: https://github.com/user/repo)
            url = registry_config.url

            # Handle different GitLab URL formats
            if "github.com" in url:
                # Extract from URLs like: https://gitlab.com/user/repo or https://gitlab.com/user/repo/-/tree/branch/path
                if "/tree/" in url:
                    # Format: https://github.com/user/repo/tree/branch/path
                    parts = url.split("/tree/")
                    base_url = parts[0]
                    tree_path = parts[1]  # branch/path

                    # Split branch and path
                    path_parts = tree_path.split("/", 1)
                    branch = path_parts[0] if path_parts else "main"
                    subfolder = path_parts[1] if len(path_parts) > 1 else ""
                else:
                    # Format: https://github.com/user/repo
                    base_url = url
                    branch = "main"
                    subfolder = ""
            else:
                console.print(
                    "❌ [red]Invalid GitHub URL format. Expected: https://github.com/user/repo[/red]"
                )
                return False

            owner, repo = base_url.replace("https://github.com/", "").split("/")
            template_filename = f"{template_name}.agt"
            template_path = (
                f"{subfolder}/{template_filename}"
                if subfolder
                else f"{template_filename}"
            )

            # GitHub API URL for file content
            api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{template_path}?ref={branch}"

            # Prepare headers with auth token if available
            headers = {"Accept": "application/vnd.github.v3+json"}
            token = registry_config.token
            if token:
                headers["Authorization"] = f"token {token}"

            console.print(
                f"📥 [blue]Fetching template from GitHub:[/blue] {owner}/{repo}/{template_path}"
            )

            # Make API request
            response = requests.get(api_url, headers=headers)

            if response.status_code == 404:
                console.print(
                    f"❌ [red]Template file '{template_filename}' not found in repository {owner}/{repo}[/red]"
                )
                return False
            elif response.status_code == 403:
                console.print(
                    "❌ [red]Access denied. Check your GitHub token permissions for private repositories[/red]"
                )
                return False
            elif response.status_code != 200:
                console.print(
                    f"❌ [red]GitHub API error {response.status_code}: {response.text}[/red]"
                )
                return False

            # Parse response
            file_data = response.json()
            if file_data.get("type") != "file":
                console.print(f"❌ [red]'{template_filename}' is not a file[/red]")
                return False

            # Decode base64 content
            content = base64.b64decode(file_data["content"]).decode("utf-8")

            # Parse and validate template YAML
            try:
                template_data = yaml.safe_load(content)
            except yaml.YAMLError as e:
                console.print(f"❌ [red]Invalid YAML in template file: {e}[/red]")
                return False

            if not template_data or not template_data.get("name"):
                console.print("❌ [red]Invalid template: missing 'name' field[/red]")
                return False

            # Save to pulled templates directory in organized structure
            pulled_templates_dir = (
                Path.home() / ".ago" / "registry" / "templates" / "pulled"
            )
            pulled_templates_dir.mkdir(parents=True, exist_ok=True)

            template_file_path = pulled_templates_dir / template_filename
            with open(template_file_path, "w") as f:
                f.write(content)

            # Add template to index for fast lookup
            self._add_template_to_index(template_data, template_file_path, "pulled", registry_config.name)

            console.print(
                f"✅ [green]Template '{template_name}' pulled successfully to global cache[/green]"
            )
            console.print(f"📁 [dim]Saved to: {template_file_path}[/dim]")

            return True

        except requests.RequestException as e:
            console.print(f"❌ [red]Network error: {e}[/red]")
            return False
        except Exception as e:
            console.print(f"❌ [red]Error pulling from GitHub: {e}[/red]")
            return False

    def _pull_from_gitlab(
        self, registry_config: RegistryConfig, template_name: str, version: str
    ) -> bool:
        """Pull template from GitLab repository"""
        try:
            import urllib.parse

            # Parse GitLab URL (can be gitlab.com or self-hosted)
            url = registry_config.url

            # Handle different GitLab URL formats
            if "gitlab.com" in url:
                # Extract from URLs like: https://gitlab.com/user/repo or https://gitlab.com/user/repo/-/tree/branch/path
                if "/-/tree/" in url:
                    # Format: https://gitlab.com/user/repo/-/tree/branch/path
                    parts = url.split("/-/tree/")
                    base_url = parts[0]
                    tree_path = parts[1]  # branch/path

                    # Split branch and path
                    path_parts = tree_path.split("/", 1)
                    branch = path_parts[0] if path_parts else "main"
                    subfolder = path_parts[1] if len(path_parts) > 1 else ""
                else:
                    # Format: https://gitlab.com/user/repo
                    base_url = url
                    branch = "main"
                    subfolder = ""

                # Extract project path from URL
                project_path = base_url.replace("https://gitlab.com/", "")
                api_base = "https://gitlab.com/api/v4"
            else:
                # Self-hosted GitLab (future support)
                console.print("❌ [red]Self-hosted GitLab not supported yet[/red]")
                return False

            template_filename = f"{template_name}.agt"

            # Construct file path (include subfolder if specified)
            if subfolder:
                file_path = f"{subfolder}/{template_filename}"
            else:
                file_path = template_filename

            # Prepare headers with auth token if available - use browser-like headers to avoid bot detection
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
            token = registry_config.token
            if token:
                # Try PRIVATE-TOKEN first (GitLab's preferred method)
                headers["PRIVATE-TOKEN"] = token

            # Create session for requests
            session = requests.Session()

            # First get the project ID (required for GitLab API)
            project_api_url = (
                f"{api_base}/projects/{urllib.parse.quote(project_path, safe='')}"
            )
            console.print(f"🔍 [dim]Getting project ID from: {project_api_url}[/dim]")

            project_response = session.get(project_api_url, headers=headers)

            console.print(
                f"🔍 [dim]Project API status: {project_response.status_code}[/dim]"
            )
            console.print(
                f"🔍 [dim]Project response content: {project_response.text[:200]}[/dim]"
            )

            if project_response.status_code != 200:
                console.print(
                    f"❌ [red]Could not get project info: {project_response.status_code}[/red]"
                )
                return False

            try:
                # Try direct JSON parsing first (requests often auto-decompresses)
                project_data = project_response.json()
            except json.JSONDecodeError:
                try:
                    # If that fails, try manual decompression
                    if project_response.headers.get("content-encoding") == "br":
                        import brotli

                        decompressed = brotli.decompress(project_response.content)
                        project_data = json.loads(decompressed.decode("utf-8"))
                    elif project_response.headers.get("content-encoding") == "gzip":
                        import gzip

                        decompressed = gzip.decompress(project_response.content)
                        project_data = json.loads(decompressed.decode("utf-8"))
                    else:
                        raise Exception("Could not parse response as JSON")
                except Exception as e:
                    console.print(
                        f"❌ [red]Could not parse project API response: {e}[/red]"
                    )
                    console.print(
                        f"🔍 [dim]Response headers: {dict(project_response.headers)}[/dim]"
                    )
                    return False
            project_id = project_data["id"]
            console.print(f"🔍 [dim]Project ID: {project_id}[/dim]")

            # Now use the correct GitLab API with project ID - for raw content
            # Encode the entire file path, keeping only forward slashes as safe characters
            encoded_file_path = urllib.parse.quote(file_path, safe="/")
            api_url = f"{api_base}/projects/{project_id}/repository/files/backend%2Ftest-private-template%2Eagt/raw?ref={branch}"
            console.print(f"🔍 [dim]API URL with project ID: {api_url}[/dim]")

            console.print(
                f"📥 [blue]Fetching template from GitLab:[/blue] {project_path}/{file_path} (branch: {branch})"
            )

            # Make request to file API with project ID
            response = session.get(api_url, headers=headers)
            console.print(f"🔍 [dim]Response status: {response.status_code}[/dim]")
            console.print(f"🔍 [dim]Response headers: {dict(response.headers)}[/dim]")

            if response.status_code == 200:
                console.print("✅ [green]Successfully fetched file![/green]")
            elif response.status_code == 404:
                console.print(
                    f"❌ [red]Template file '{template_filename}' not found in repository {project_path}[/red]"
                )
                console.print(f"🔍 [dim]Response: {response.text[:200]}[/dim]")
                return False
            elif response.status_code == 403:
                console.print(
                    "❌ [red]Access denied. Check your GitLab token permissions for private repositories[/red]"
                )
                console.print(f"🔍 [dim]Response: {response.text[:200]}[/dim]")
                return False
            elif response.status_code != 200:
                console.print(
                    f"❌ [red]GitLab API error {response.status_code}: {response.text}[/red]"
                )
                console.print(f"🔍 [dim]Full response: {response.text}[/dim]")
                return False

            # Handle response content (try text first, then decompression if needed)
            try:
                content = response.text
                # Quick check if content looks valid (not binary)
                if len(content) < 50 or content.startswith("name:"):
                    pass  # Looks good
                else:
                    raise UnicodeError("Content might be compressed")
            except UnicodeError:
                # Try manual decompression
                if response.headers.get("content-encoding") == "br":
                    import brotli

                    content = brotli.decompress(response.content).decode("utf-8")
                elif response.headers.get("content-encoding") == "gzip":
                    import gzip

                    content = gzip.decompress(response.content).decode("utf-8")
                else:
                    content = response.text

            # Parse and validate template YAML
            try:
                template_data = yaml.safe_load(content)
            except yaml.YAMLError as e:
                console.print(f"❌ [red]Invalid YAML in template file: {e}[/red]")
                return False

            if not template_data or not template_data.get("name"):
                console.print("❌ [red]Invalid template: missing 'name' field[/red]")
                return False

            # Save to pulled templates directory in organized structure
            pulled_templates_dir = (
                Path.home() / ".ago" / "registry" / "templates" / "pulled"
            )
            pulled_templates_dir.mkdir(parents=True, exist_ok=True)

            template_file_path = pulled_templates_dir / template_filename
            with open(template_file_path, "w") as f:
                f.write(content)

            # Add template to index for fast lookup
            self._add_template_to_index(template_data, template_file_path, "pulled", registry_config.name)

            console.print(
                f"✅ [green]Template '{template_name}' pulled successfully from GitLab[/green]"
            )
            console.print(f"📁 [dim]Saved to: {template_file_path}[/dim]")

            return True

        except requests.RequestException as e:
            console.print(f"❌ [red]Network error: {e}[/red]")
            return False
        except Exception as e:
            console.print(f"❌ [red]Error pulling from GitLab: {e}[/red]")
            return False

    def _pull_from_http(
        self, registry_config: RegistryConfig, template_name: str, version: str
    ) -> bool:
        """Pull template from generic HTTP URL (public repositories)"""
        try:
            base_url = registry_config.url
            template_filename = f"{template_name}.agt"

            # Construct full URL
            if base_url.endswith("/"):
                file_url = f"{base_url}{template_filename}"
            else:
                file_url = f"{base_url}/{template_filename}"

            console.print(f"📥 [blue]Downloading template from:[/blue] {file_url}")

            # Simple HTTP GET request
            response = requests.get(file_url)

            if response.status_code == 404:
                console.print(
                    f"❌ [red]Template file '{template_filename}' not found at {file_url}[/red]"
                )
                return False
            elif response.status_code != 200:
                console.print(
                    f"❌ [red]HTTP error {response.status_code}: {response.text}[/red]"
                )
                return False

            content = response.text

            # Parse and validate template YAML
            try:
                template_data = yaml.safe_load(content)
            except yaml.YAMLError as e:
                console.print(f"❌ [red]Invalid YAML in template file: {e}[/red]")
                return False

            if not template_data or not template_data.get("name"):
                console.print("❌ [red]Invalid template: missing 'name' field[/red]")
                return False

            # Save to pulled templates directory in organized structure
            pulled_templates_dir = (
                Path.home() / ".ago" / "registry" / "templates" / "pulled"
            )
            pulled_templates_dir.mkdir(parents=True, exist_ok=True)

            template_file_path = pulled_templates_dir / template_filename
            with open(template_file_path, "w") as f:
                f.write(content)

            # Add template to index for fast lookup
            self._add_template_to_index(template_data, template_file_path, "pulled", registry_config.name)

            console.print(
                f"✅ [green]Template '{template_name}' downloaded successfully[/green]"
            )
            console.print(f"📁 [dim]Saved to: {template_file_path}[/dim]")

            return True

        except requests.RequestException as e:
            console.print(f"❌ [red]Network error: {e}[/red]")
            return False
        except Exception as e:
            console.print(f"❌ [red]Error downloading from HTTP: {e}[/red]")
            return False

    def create_template_from_spec(
        self, spec_data: Dict[str, Any], template_dir: Path
    ) -> bool:
        """Create a new template entry from workflow spec data"""
        try:
            # This would be used when importing templates from external sources
            index = self._load_index()

            template_key = f"{spec_data['name']}:v{spec_data.get('version', '1.0')}"

            # Add to index
            index[template_key] = {
                "name": spec_data["name"],
                "version": spec_data.get("version", "1.0"),
                "description": spec_data.get("description", "Custom template"),
                "model": spec_data.get("model", "claude-3-5-haiku-20241022"),
                "tools": spec_data.get("tools", []),
                "created_at": datetime.now().isoformat(),
                "source": "custom",
                "path": str(template_dir),
            }

            self._save_index(index)
            return True

        except Exception as e:
            console.print(f"❌ Error creating template: {e}")
            return False

    def remove_template(self, name: str, version: Optional[str] = None) -> bool:
        """Remove template(s) from local registry
        
        Args:
            name: Template name
            version: Specific version to remove, or None to remove all versions
        
        Returns:
            bool: True if removal successful, False otherwise
        """
        try:
            index = self._load_index()
            removed_count = 0
            templates_to_remove = []
            
            # Find templates to remove
            for template_key, template_data in index.items():
                template_name = template_data.get("name", "")
                template_version = template_data.get("version", "latest")
                
                if template_name == name:
                    if version is None:  # Remove all versions
                        templates_to_remove.append((template_key, template_data))
                    elif template_version == version:  # Remove specific version
                        templates_to_remove.append((template_key, template_data))
            
            if not templates_to_remove:
                return False
            
            # Remove templates from filesystem and index
            for template_key, template_data in templates_to_remove:
                # Remove from filesystem if it's a pulled template
                if template_data.get("source") == "pulled":
                    template_path = Path(template_data.get("path", ""))
                    if template_path.exists():
                        if template_path.is_file():
                            template_path.unlink()
                        elif template_path.is_dir():
                            import shutil
                            shutil.rmtree(template_path)
                
                # Remove from index
                del index[template_key]
                removed_count += 1
            
            # Save updated index
            self._save_index(index)
            
            return removed_count > 0
            
        except Exception as e:
            console.print(f"❌ [red]Error removing template:[/red] {e}")
            return False


# Global registry instance
registry = AgentRegistry()
