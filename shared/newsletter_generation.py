"""OpenRouter-based newsletter generation."""
import json
from datetime import datetime
from pathlib import Path

from shared.openrouter_client import chat_completion


def generate_newsletter_issue(slug: str, *, date: str | None = None) -> dict[str, str]:
    """
    Generate a newsletter issue using OpenRouter.

    Reads the assembled prompt, injects the template, calls OpenRouter with the
    Step 3.5 Flash model, parses the JSON response, and writes files.

    Args:
        slug: Topic slug (e.g., 'google-ai')
        date: Date string (YYYY-MM-DD). Defaults to today.

    Returns:
        Dict with keys: raw_markdown, html, top_story_summary

    Raises:
        FileNotFoundError: If topic files don't exist
        RuntimeError: On OpenRouter errors or JSON parse failure
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    repo_root = Path(__file__).parent.parent
    topic_dir = repo_root / "topics" / slug
    prompt_path = topic_dir / "prompt.md"
    template_path = topic_dir / "site" / "template.html"

    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt not found: {prompt_path}")
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    # Read assembled prompt and template
    prompt_text = prompt_path.read_text()
    template_html = template_path.read_text()

    # Inject template into ops-guide section
    full_prompt = prompt_text.replace("{{TEMPLATE_CONTENT}}", template_html)

    # Call OpenRouter
    response_text = chat_completion(full_prompt)

    # Parse JSON response (strip markdown fences defensively)
    response_text = response_text.strip()
    if response_text.startswith("```json"):
        response_text = response_text[7:]  # Remove ```json
    if response_text.startswith("```"):
        response_text = response_text[3:]  # Remove ```
    if response_text.endswith("```"):
        response_text = response_text[:-3]  # Remove trailing ```
    response_text = response_text.strip()

    # Try to find and extract JSON from the response
    parsed = None

    # First attempt: direct parse
    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError:
        # Second attempt: look for JSON object in response
        import re
        # Find the first { and last } to extract JSON substring
        start_idx = response_text.find("{")
        end_idx = response_text.rfind("}")
        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            try:
                json_str = response_text[start_idx:end_idx + 1]
                parsed = json.loads(json_str)
            except json.JSONDecodeError:
                pass

    if parsed is None:
        raise RuntimeError(
            f"Failed to parse OpenRouter JSON response\n"
            f"Response text (first 500 chars): {response_text[:500]}"
        )

    # Validate required keys
    required_keys = {"raw_markdown", "html", "top_story_summary"}
    missing_keys = required_keys - set(parsed.keys())
    if missing_keys:
        raise RuntimeError(f"Missing required keys in response: {missing_keys}")

    # Write files
    (topic_dir / f"{date}.md").write_text(parsed["raw_markdown"])
    (topic_dir / "site" / "index.html").write_text(parsed["html"])
    (topic_dir / "site" / f"{date}.html").write_text(parsed["html"])

    return parsed
