"""CLI-based newsletter generation using agentic AI tools.

Runs a CLI agent in agentic mode with the assembled prompt.md.
The agent performs research and writes output files to disk directly.
"""
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

_AGENT_LABELS = {
    "claude":      "Claude CLI",
    "gemini":      "Gemini CLI",
    "copilot":     "Copilot GH CLI",
    "opencode":    "OpenCode",
}

VALID_AGENTS = list(_AGENT_LABELS.keys())


def generate_with_cli(slug: str, agent: str) -> None:
    """Run newsletter generation via a CLI agent.

    Args:
        slug:  Topic slug (e.g. 'google-ai').
        agent: One of 'claude', 'gemini', 'copilot', 'opencode'.

    Raises:
        FileNotFoundError: If the assembled prompt.md is missing.
        ValueError:        If *agent* is not recognised.
        RuntimeError:      If the CLI exits non-zero.
    """
    if agent not in _AGENT_LABELS:
        raise ValueError(f"Unknown agent '{agent}'. Valid: {VALID_AGENTS}")

    prompt_path = REPO_ROOT / "topics" / slug / "prompt.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt not found: {prompt_path}")

    prompt_text = prompt_path.read_text()
    label = _AGENT_LABELS[agent]

    if agent == "claude":
        cmd = ["claude", "-p", prompt_text, "--dangerously-skip-permissions"]
    elif agent == "gemini":
        cmd = ["gemini", "-p", prompt_text]
    elif agent == "copilot":
        cmd = ["gh", "copilot", "suggest", "-t", "shell", prompt_text]
    elif agent == "opencode":
        cmd = ["opencode", "run", str(prompt_path)]

    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        snippet = (result.stderr or result.stdout or "")[:600]
        raise RuntimeError(f"{label} exited {result.returncode}:\n{snippet}")
