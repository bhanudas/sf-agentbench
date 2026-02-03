"""Configuration screen for SF-AgentBench TUI."""

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, Grid
from textual.screen import Screen
from textual.widgets import (
    Header,
    Footer,
    Static,
    Button,
    Input,
    Label,
    Switch,
    Rule,
    TabbedContent,
    TabPane,
)

from sf_agentbench.config import load_config, BenchmarkConfig


class ConfigScreen(Screen):
    """Configuration editor screen."""

    BINDINGS = [
        ("escape", "app.switch_screen('dashboard')", "Back"),
        ("ctrl+s", "save_config", "Save"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.config = load_config()

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="main-content"):
            yield Static("⚙️ Configuration", classes="title")
            yield Static(
                "Configure agent, evaluation, and runtime settings",
                classes="subtitle",
            )

            yield Rule()

            with TabbedContent():
                with TabPane("Agent", id="tab-agent"):
                    yield self._compose_agent_tab()

                with TabPane("Authentication", id="tab-auth"):
                    yield self._compose_auth_tab()

                with TabPane("Salesforce", id="tab-salesforce"):
                    yield self._compose_salesforce_tab()

                with TabPane("Evaluation", id="tab-evaluation"):
                    yield self._compose_evaluation_tab()

                with TabPane("Advanced", id="tab-advanced"):
                    yield self._compose_advanced_tab()

            yield Rule()

            with Horizontal():
                yield Button("💾 Save Configuration", id="btn-save", variant="success")
                yield Button("🔄 Reset to Defaults", id="btn-reset", variant="warning")
                yield Button("◀ Back", id="btn-back", variant="default")

        yield Footer()

    def _compose_agent_tab(self) -> ComposeResult:
        """Compose the agent configuration tab."""
        with Container(classes="panel"):
            yield Static("🤖 AI Agent Settings", classes="title")

            with Grid(id="agent-grid"):
                yield Label("Agent ID:")
                yield Input(
                    value=self.config.agent.id,
                    id="agent-id",
                    placeholder="e.g., claude-code",
                )

                yield Label("Agent Type:")
                yield Input(
                    value=self.config.agent.type,
                    id="agent-type",
                    placeholder="claude, openai, gemini, custom",
                )

                yield Label("Model:")
                yield Input(
                    value=self.config.agent.model,
                    id="agent-model",
                    placeholder="e.g., claude-sonnet-4-20250514",
                )

                yield Label("API Key Env Var:")
                yield Input(
                    value=self.config.agent.api_key_env,
                    id="agent-api-key-env",
                    placeholder="ANTHROPIC_API_KEY",
                )

                yield Label("Max Iterations:")
                yield Input(
                    value=str(self.config.agent.max_iterations),
                    id="agent-max-iterations",
                    placeholder="50",
                )

                yield Label("Timeout (seconds):")
                yield Input(
                    value=str(self.config.agent.timeout_seconds),
                    id="agent-timeout",
                    placeholder="1800",
                )

    def _compose_auth_tab(self) -> ComposeResult:
        """Compose the authentication configuration tab."""
        from sf_agentbench.agents.auth import get_auth_details
        
        details = get_auth_details()
        
        with Container(classes="panel"):
            yield Static("🔐 API Authentication", classes="title")
            yield Static(
                "Configure API keys for AI providers",
                classes="muted",
            )
            
            for provider, info in details.items():
                with Container(classes="auth-provider"):
                    status = "✅" if info["authenticated"] else "❌"
                    method = f" ({info['method']})" if info.get("method") else ""
                    yield Static(f"{status} {info['name']}{method}", classes="provider-name")
                    
                    with Grid(id=f"auth-{provider}-grid"):
                        yield Label(f"{info['env_var']}:")
                        yield Input(
                            value="",
                            id=f"auth-{provider}-key",
                            placeholder="Enter API key to update",
                            password=True,
                        )
                    
                    with Horizontal():
                        yield Button(
                            f"Save {provider.title()} Key",
                            id=f"btn-save-{provider}",
                            variant="primary" if not info["authenticated"] else "default",
                        )
                        if info["supports_oauth"] and provider == "google":
                            yield Button(
                                "OAuth Login",
                                id="btn-oauth-google",
                                variant="success",
                            )
            
            yield Rule()
            yield Static(
                "💡 API keys are stored securely in your system keychain and ~/.sf-agentbench/credentials/",
                classes="muted",
            )

    def _compose_salesforce_tab(self) -> ComposeResult:
        """Compose the Salesforce configuration tab."""
        with Container(classes="panel"):
            yield Static("☁️ Salesforce Settings", classes="title")

            with Grid(id="sf-grid"):
                yield Label("SF CLI Path:")
                yield Input(
                    value=self.config.sf_cli_path,
                    id="sf-cli-path",
                    placeholder="sf",
                )

                yield Label("DevHub Username:")
                yield Input(
                    value=self.config.devhub_username or "",
                    id="devhub-username",
                    placeholder="admin@devhub.org",
                )

                yield Label("Scratch Org Duration (days):")
                yield Input(
                    value=str(self.config.scratch_org.default_duration_days),
                    id="scratch-duration",
                    placeholder="1",
                )

                yield Label("Scratch Org Edition:")
                yield Input(
                    value=self.config.scratch_org.edition,
                    id="scratch-edition",
                    placeholder="Developer",
                )

                yield Label("Wait Time (minutes):")
                yield Input(
                    value=str(self.config.scratch_org.wait_minutes),
                    id="scratch-wait",
                    placeholder="10",
                )

    def _compose_evaluation_tab(self) -> ComposeResult:
        """Compose the evaluation configuration tab."""
        with Container(classes="panel"):
            yield Static("📊 Evaluation Weights", classes="title")
            yield Static(
                "Weights must sum to 1.0",
                classes="muted",
            )

            with Grid(id="eval-grid"):
                yield Label("Deployment (Layer 1):")
                yield Input(
                    value=str(self.config.evaluation_weights.deployment),
                    id="weight-deployment",
                    placeholder="0.20",
                )

                yield Label("Functional Tests (Layer 2):")
                yield Input(
                    value=str(self.config.evaluation_weights.functional_tests),
                    id="weight-tests",
                    placeholder="0.40",
                )

                yield Label("Static Analysis (Layer 3):")
                yield Input(
                    value=str(self.config.evaluation_weights.static_analysis),
                    id="weight-static",
                    placeholder="0.10",
                )

                yield Label("Metadata Diff (Layer 4):")
                yield Input(
                    value=str(self.config.evaluation_weights.metadata_diff),
                    id="weight-metadata",
                    placeholder="0.15",
                )

                yield Label("Rubric (Layer 5):")
                yield Input(
                    value=str(self.config.evaluation_weights.rubric),
                    id="weight-rubric",
                    placeholder="0.15",
                )

        with Container(classes="panel"):
            yield Static("🔍 PMD Settings", classes="title")

            with Horizontal():
                yield Label("Enable PMD:")
                yield Switch(value=self.config.pmd.enabled, id="pmd-enabled")

            yield Label("Max Penalty:")
            yield Input(
                value=str(self.config.pmd.max_penalty),
                id="pmd-max-penalty",
                placeholder="0.10",
            )

    def _compose_advanced_tab(self) -> ComposeResult:
        """Compose the advanced configuration tab."""
        with Container(classes="panel"):
            yield Static("🔧 Runtime Settings", classes="title")

            with Grid(id="runtime-grid"):
                yield Label("Parallel Runs:")
                yield Input(
                    value=str(self.config.parallel_runs),
                    id="parallel-runs",
                    placeholder="1",
                )

                yield Label("Timeout (minutes):")
                yield Input(
                    value=str(self.config.timeout_minutes),
                    id="timeout-minutes",
                    placeholder="60",
                )

            with Horizontal():
                yield Label("Cleanup Orgs After Run:")
                yield Switch(value=self.config.cleanup_orgs, id="cleanup-orgs")

            with Horizontal():
                yield Label("Verbose Logging:")
                yield Switch(value=self.config.verbose, id="verbose")

        with Container(classes="panel"):
            yield Static("📁 Directories", classes="title")

            with Grid(id="dirs-grid"):
                yield Label("Tasks Directory:")
                yield Input(
                    value=str(self.config.tasks_dir),
                    id="tasks-dir",
                    placeholder="tasks",
                )

                yield Label("Results Directory:")
                yield Input(
                    value=str(self.config.results_dir),
                    id="results-dir",
                    placeholder="results",
                )

                yield Label("Logs Directory:")
                yield Input(
                    value=str(self.config.logs_dir),
                    id="logs-dir",
                    placeholder="logs",
                )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-back":
            self.app.switch_screen("dashboard")
        elif event.button.id == "btn-save":
            self._save_config()
        elif event.button.id == "btn-reset":
            self._reset_config()
        elif event.button.id and event.button.id.startswith("btn-save-"):
            provider = event.button.id.replace("btn-save-", "")
            self._save_api_key(provider)
        elif event.button.id == "btn-oauth-google":
            self._start_oauth_google()
    
    def _save_api_key(self, provider: str) -> None:
        """Save an API key for a provider."""
        from sf_agentbench.agents.auth import store_api_key, test_api_key
        
        try:
            input_widget = self.query_one(f"#auth-{provider}-key", Input)
            api_key = input_widget.value.strip()
            
            if not api_key:
                self.notify(f"Enter an API key for {provider}", severity="warning")
                return
            
            # Test the key
            valid, message = test_api_key(provider, api_key)
            
            if not valid:
                self.notify(f"Invalid API key: {message}", severity="error")
                return
            
            # Store it
            if store_api_key(provider, api_key):
                self.notify(f"✓ {provider.title()} API key saved!", severity="information")
                input_widget.value = ""
                # Refresh to update status
                self.refresh()
            else:
                self.notify(f"Failed to save {provider} API key", severity="error")
                
        except Exception as e:
            self.notify(f"Error: {e}", severity="error")
    
    def _start_oauth_google(self) -> None:
        """Start Google OAuth flow."""
        from sf_agentbench.agents.auth import setup_google_oauth
        
        self.notify("Opening browser for Google OAuth...", severity="information")
        
        # Note: This is a blocking call that opens a browser
        # In a real TUI, we'd want to run this in a worker thread
        try:
            if setup_google_oauth():
                self.notify("✓ Google OAuth completed!", severity="information")
                self.refresh()
            else:
                self.notify("Google OAuth was not completed", severity="warning")
        except Exception as e:
            self.notify(f"OAuth error: {e}", severity="error")

    def _save_config(self) -> None:
        """Save configuration to file."""
        try:
            # Update config from inputs
            self.config.agent.id = self.query_one("#agent-id", Input).value
            self.config.agent.type = self.query_one("#agent-type", Input).value
            self.config.agent.model = self.query_one("#agent-model", Input).value
            self.config.agent.api_key_env = self.query_one("#agent-api-key-env", Input).value
            self.config.agent.max_iterations = int(
                self.query_one("#agent-max-iterations", Input).value or "50"
            )
            self.config.agent.timeout_seconds = int(
                self.query_one("#agent-timeout", Input).value or "1800"
            )

            self.config.sf_cli_path = self.query_one("#sf-cli-path", Input).value
            self.config.devhub_username = (
                self.query_one("#devhub-username", Input).value or None
            )

            self.config.scratch_org.default_duration_days = int(
                self.query_one("#scratch-duration", Input).value or "1"
            )
            self.config.scratch_org.edition = self.query_one("#scratch-edition", Input).value
            self.config.scratch_org.wait_minutes = int(
                self.query_one("#scratch-wait", Input).value or "10"
            )

            self.config.evaluation_weights.deployment = float(
                self.query_one("#weight-deployment", Input).value or "0.20"
            )
            self.config.evaluation_weights.functional_tests = float(
                self.query_one("#weight-tests", Input).value or "0.40"
            )
            self.config.evaluation_weights.static_analysis = float(
                self.query_one("#weight-static", Input).value or "0.10"
            )
            self.config.evaluation_weights.metadata_diff = float(
                self.query_one("#weight-metadata", Input).value or "0.15"
            )
            self.config.evaluation_weights.rubric = float(
                self.query_one("#weight-rubric", Input).value or "0.15"
            )

            self.config.pmd.enabled = self.query_one("#pmd-enabled", Switch).value
            self.config.pmd.max_penalty = float(
                self.query_one("#pmd-max-penalty", Input).value or "0.10"
            )

            self.config.parallel_runs = int(
                self.query_one("#parallel-runs", Input).value or "1"
            )
            self.config.timeout_minutes = int(
                self.query_one("#timeout-minutes", Input).value or "60"
            )
            self.config.cleanup_orgs = self.query_one("#cleanup-orgs", Switch).value
            self.config.verbose = self.query_one("#verbose", Switch).value

            self.config.tasks_dir = Path(self.query_one("#tasks-dir", Input).value)
            self.config.results_dir = Path(self.query_one("#results-dir", Input).value)
            self.config.logs_dir = Path(self.query_one("#logs-dir", Input).value)

            # Validate weights
            if not self.config.evaluation_weights.validate_sum():
                self.notify(
                    "Evaluation weights must sum to 1.0",
                    severity="error",
                )
                return

            # Save to file
            config_path = Path("sf-agentbench.yaml")
            self.config.to_yaml(config_path)

            self.notify("Configuration saved!", severity="information")

        except Exception as e:
            self.notify(f"Error saving config: {e}", severity="error")

    def _reset_config(self) -> None:
        """Reset configuration to defaults."""
        self.config = BenchmarkConfig.default()
        self.refresh()
        self.notify("Configuration reset to defaults")

    def action_save_config(self) -> None:
        """Save configuration (keyboard shortcut)."""
        self._save_config()
