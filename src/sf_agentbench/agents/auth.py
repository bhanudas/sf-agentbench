"""Authentication utilities for AI agents.

Supports multiple authentication methods:
1. Environment variables (API keys)
2. OAuth browser flow (Google)
3. System keychain/keyring storage
4. Config file credentials
"""

import os
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel

console = Console()

# Credentials cache directory
CREDENTIALS_DIR = Path.home() / ".sf-agentbench" / "credentials"

# Provider configuration
PROVIDER_INFO = {
    "anthropic": {
        "name": "Anthropic (Claude)",
        "env_var": "ANTHROPIC_API_KEY",
        "get_url": "https://console.anthropic.com/settings/keys",
        "supports_oauth": False,
        "test_endpoint": "https://api.anthropic.com/v1/messages",
    },
    "openai": {
        "name": "OpenAI (GPT)",
        "env_var": "OPENAI_API_KEY",
        "get_url": "https://platform.openai.com/api-keys",
        "supports_oauth": False,
        "test_endpoint": "https://api.openai.com/v1/models",
    },
    "google": {
        "name": "Google (Gemini)",
        "env_var": "GOOGLE_API_KEY",
        "get_url": "https://aistudio.google.com/app/apikey",
        "supports_oauth": True,
        "test_endpoint": "https://generativelanguage.googleapis.com/v1beta/models",
    },
}


def get_anthropic_credentials() -> str | None:
    """Get Anthropic API key from various sources."""
    # 1. Environment variable
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        return api_key
    
    # 2. Cached credentials file
    creds_file = CREDENTIALS_DIR / "anthropic.json"
    if creds_file.exists():
        try:
            data = json.loads(creds_file.read_text())
            key = data.get("api_key")
            if key:
                return key
        except Exception:
            pass
    
    # 3. System keychain (macOS)
    api_key = _get_from_keychain("sf-agentbench", "anthropic-api-key")
    if api_key:
        return api_key
    
    return None


def get_openai_credentials() -> str | None:
    """Get OpenAI API key from various sources."""
    # 1. Environment variable
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        return api_key
    
    # 2. Cached credentials file
    creds_file = CREDENTIALS_DIR / "openai.json"
    if creds_file.exists():
        try:
            data = json.loads(creds_file.read_text())
            key = data.get("api_key")
            if key:
                return key
        except Exception:
            pass
    
    # 3. System keychain (macOS)
    api_key = _get_from_keychain("sf-agentbench", "openai-api-key")
    if api_key:
        return api_key
    
    return None


def get_google_credentials() -> Any:
    """
    Get Google credentials using OAuth or API key.
    
    Supports:
    1. GOOGLE_API_KEY environment variable
    2. Cached API key file
    3. Application Default Credentials (gcloud auth)
    4. OAuth browser flow
    """
    # 1. API key from environment
    api_key = os.getenv("GOOGLE_API_KEY")
    if api_key:
        return {"type": "api_key", "api_key": api_key}
    
    # 2. Cached API key file
    creds_file = CREDENTIALS_DIR / "google.json"
    if creds_file.exists():
        try:
            data = json.loads(creds_file.read_text())
            key = data.get("api_key")
            if key:
                return {"type": "api_key", "api_key": key}
        except Exception:
            pass
    
    # 3. Try Application Default Credentials (from gcloud CLI)
    try:
        import google.auth
        credentials, project = google.auth.default()
        if credentials:
            return {"type": "adc", "credentials": credentials, "project": project}
    except Exception:
        pass
    
    # 4. Check for cached OAuth credentials
    oauth_file = CREDENTIALS_DIR / "google_oauth.json"
    if oauth_file.exists():
        try:
            from google.oauth2.credentials import Credentials
            creds = Credentials.from_authorized_user_file(str(oauth_file))
            if creds and creds.valid:
                return {"type": "oauth", "credentials": creds}
            elif creds and creds.expired and creds.refresh_token:
                from google.auth.transport.requests import Request
                creds.refresh(Request())
                # Save refreshed credentials
                oauth_file.write_text(creds.to_json())
                return {"type": "oauth", "credentials": creds}
        except Exception:
            pass
    
    return None


def test_api_key(provider: str, api_key: str) -> tuple[bool, str]:
    """Test if an API key is valid by making a simple API call."""
    import urllib.request
    import urllib.error
    
    info = PROVIDER_INFO.get(provider, {})
    
    try:
        if provider == "anthropic":
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                method="POST",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                data=json.dumps({
                    "model": "claude-3-haiku-20240307",
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "hi"}],
                }).encode(),
            )
            urllib.request.urlopen(req, timeout=10)
            return True, "API key is valid"
            
        elif provider == "openai":
            req = urllib.request.Request(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            urllib.request.urlopen(req, timeout=10)
            return True, "API key is valid"
            
        elif provider == "google":
            req = urllib.request.Request(
                f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
            )
            urllib.request.urlopen(req, timeout=10)
            return True, "API key is valid"
            
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, "Invalid API key (401 Unauthorized)"
        elif e.code == 403:
            return False, "API key forbidden (403) - may lack permissions"
        elif e.code == 429:
            return True, "API key valid (rate limited)"  # Rate limited means it's valid
        else:
            return False, f"API error: {e.code} {e.reason}"
    except urllib.error.URLError as e:
        return False, f"Network error: {e.reason}"
    except Exception as e:
        return False, f"Error testing key: {e}"
    
    return True, "API key appears valid"


def store_api_key(provider: str, api_key: str, use_keychain: bool = True) -> bool:
    """Store an API key securely."""
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Try system keychain first
    if use_keychain:
        if _store_in_keychain("sf-agentbench", f"{provider}-api-key", api_key):
            console.print(f"  [dim]Stored in system keychain[/dim]")
    
    # Also store in file as backup
    creds_file = CREDENTIALS_DIR / f"{provider}.json"
    
    try:
        creds_file.write_text(json.dumps({"api_key": api_key}))
        creds_file.chmod(0o600)  # Restrict permissions
        console.print(f"  [dim]Stored in {creds_file}[/dim]")
        return True
    except Exception as e:
        console.print(f"  [red]Failed to store: {e}[/red]")
        return False


def add_to_shell_config(provider: str, api_key: str) -> bool:
    """Add API key export to shell configuration file."""
    info = PROVIDER_INFO.get(provider, {})
    env_var = info.get("env_var", f"{provider.upper()}_API_KEY")
    
    # Determine shell config file
    shell = os.environ.get("SHELL", "/bin/bash")
    if "zsh" in shell:
        config_file = Path.home() / ".zshrc"
    elif "bash" in shell:
        config_file = Path.home() / ".bashrc"
    else:
        config_file = Path.home() / ".profile"
    
    export_line = f'\nexport {env_var}="{api_key}"\n'
    
    try:
        # Check if already set
        if config_file.exists():
            content = config_file.read_text()
            if f"export {env_var}=" in content:
                console.print(f"  [yellow]Warning: {env_var} already in {config_file}[/yellow]")
                if Confirm.ask("  Replace existing?", default=False):
                    # Remove old line and add new
                    lines = [l for l in content.split("\n") if f"export {env_var}=" not in l]
                    content = "\n".join(lines) + export_line
                    config_file.write_text(content)
                else:
                    return False
            else:
                # Append to file
                with open(config_file, "a") as f:
                    f.write(export_line)
        else:
            config_file.write_text(export_line)
        
        console.print(f"  [green]✓ Added to {config_file}[/green]")
        console.print(f"  [dim]Run: source {config_file}[/dim]")
        return True
        
    except Exception as e:
        console.print(f"  [red]Failed to update {config_file}: {e}[/red]")
        return False


def setup_google_oauth(client_id: str | None = None, client_secret: str | None = None) -> bool:
    """
    Set up Google OAuth via browser flow.
    
    If client_id/secret not provided, uses the installed app flow.
    """
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        
        # Scopes needed for Gemini API
        SCOPES = ["https://www.googleapis.com/auth/generative-language"]
        
        # Check for client secrets file
        client_secrets_file = CREDENTIALS_DIR / "google_client_secrets.json"
        
        if client_secrets_file.exists():
            flow = InstalledAppFlow.from_client_secrets_file(
                str(client_secrets_file),
                scopes=SCOPES,
            )
        elif client_id and client_secret:
            # Create client config from provided credentials
            client_config = {
                "installed": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost"],
                }
            }
            flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
        else:
            console.print("[yellow]No OAuth client credentials found.[/yellow]")
            console.print("\n[bold]To set up OAuth:[/bold]")
            console.print("1. Go to https://console.cloud.google.com/apis/credentials")
            console.print("2. Create an OAuth 2.0 Client ID (Desktop app)")
            console.print("3. Download the JSON and save to:")
            console.print(f"   {client_secrets_file}")
            return False
        
        console.print("[cyan]Opening browser for Google authentication...[/cyan]")
        
        # Run the OAuth flow
        credentials = flow.run_local_server(
            port=8080,
            prompt="consent",
            success_message="Authentication successful! You can close this window.",
        )
        
        # Save credentials
        CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
        creds_file = CREDENTIALS_DIR / "google_oauth.json"
        creds_file.write_text(credentials.to_json())
        
        console.print("[green]✓ Google OAuth credentials saved![/green]")
        return True
        
    except ImportError:
        console.print("[red]Please install google-auth-oauthlib:[/red]")
        console.print("  pip install google-auth-oauthlib")
        return False
    except Exception as e:
        console.print(f"[red]OAuth setup failed: {e}[/red]")
        return False


def _get_from_keychain(service: str, account: str) -> str | None:
    """Get a password from the macOS keychain."""
    if sys.platform != "darwin":
        return None
    
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    
    return None


def _store_in_keychain(service: str, account: str, password: str) -> bool:
    """Store a password in the macOS keychain."""
    if sys.platform != "darwin":
        return False
    
    try:
        # Delete existing entry if any
        subprocess.run(
            ["security", "delete-generic-password", "-s", service, "-a", account],
            capture_output=True,
            timeout=5,
        )
        
        # Add new entry
        result = subprocess.run(
            ["security", "add-generic-password", "-s", service, "-a", account, "-w", password],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def interactive_auth_setup(provider: str) -> bool:
    """Interactive setup for authentication with enhanced UX."""
    info = PROVIDER_INFO.get(provider)
    if not info:
        console.print(f"[red]Unknown provider: {provider}[/red]")
        return False
    
    console.print(Panel(
        f"[bold]{info['name']} Authentication Setup[/bold]",
        subtitle=f"Configure access to {info['name']} API",
    ))
    
    if provider == "google":
        console.print("\n[bold]Choose authentication method:[/bold]")
        console.print("  [cyan]1[/cyan]. API Key [dim](simple, recommended)[/dim]")
        console.print("  [cyan]2[/cyan]. OAuth [dim](browser-based login)[/dim]")
        console.print("  [cyan]3[/cyan]. Application Default Credentials [dim](gcloud CLI)[/dim]")
        
        choice = Prompt.ask("\nSelect option", choices=["1", "2", "3"], default="1")
        
        if choice == "1":
            return _setup_api_key(provider, info)
        elif choice == "2":
            return setup_google_oauth()
        else:
            console.print("\n[bold]Using Application Default Credentials[/bold]")
            console.print("Run this command to authenticate:")
            console.print("  [cyan]gcloud auth application-default login[/cyan]")
            return False
    else:
        return _setup_api_key(provider, info)


def _setup_api_key(provider: str, info: dict) -> bool:
    """Set up API key authentication."""
    console.print(f"\n[bold]Get your API key at:[/bold]")
    console.print(f"  [link={info['get_url']}]{info['get_url']}[/link]\n")
    
    if Confirm.ask("Open in browser?", default=True):
        import webbrowser
        webbrowser.open(info["get_url"])
        console.print()
    
    api_key = Prompt.ask("Enter API key", password=True)
    
    if not api_key:
        console.print("[red]No API key provided[/red]")
        return False
    
    # Test the key
    console.print("\n[dim]Testing API key...[/dim]")
    valid, message = test_api_key(provider, api_key)
    
    if valid:
        console.print(f"[green]✓ {message}[/green]")
    else:
        console.print(f"[red]✗ {message}[/red]")
        if not Confirm.ask("Save anyway?", default=False):
            return False
    
    # Store the key
    console.print("\n[bold]Storing credentials...[/bold]")
    if not store_api_key(provider, api_key):
        return False
    
    # Offer to add to shell config
    if Confirm.ask("\nAdd to shell config for persistence?", default=True):
        add_to_shell_config(provider, api_key)
    
    console.print(f"\n[green]✓ {info['name']} authentication configured![/green]")
    return True


def check_auth_status() -> dict[str, bool]:
    """Check authentication status for all providers."""
    return {
        "anthropic": get_anthropic_credentials() is not None,
        "openai": get_openai_credentials() is not None,
        "google": get_google_credentials() is not None,
    }


def get_auth_details() -> dict[str, dict]:
    """Get detailed authentication information for each provider."""
    details = {}
    
    for provider, info in PROVIDER_INFO.items():
        creds = None
        method = None
        
        if provider == "anthropic":
            creds = get_anthropic_credentials()
            if creds:
                if os.getenv("ANTHROPIC_API_KEY"):
                    method = "Environment variable"
                elif (CREDENTIALS_DIR / "anthropic.json").exists():
                    method = "Stored file"
                else:
                    method = "System keychain"
                    
        elif provider == "openai":
            creds = get_openai_credentials()
            if creds:
                if os.getenv("OPENAI_API_KEY"):
                    method = "Environment variable"
                elif (CREDENTIALS_DIR / "openai.json").exists():
                    method = "Stored file"
                else:
                    method = "System keychain"
                    
        elif provider == "google":
            creds = get_google_credentials()
            if creds:
                method = f"{creds.get('type', 'unknown').upper()}"
        
        details[provider] = {
            "authenticated": creds is not None,
            "method": method,
            "name": info["name"],
            "env_var": info["env_var"],
            "supports_oauth": info["supports_oauth"],
        }
    
    return details
