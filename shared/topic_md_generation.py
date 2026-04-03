"""OpenRouter-based topic.md generation."""
import json

from shared.openrouter_client import chat_completion


def _build_topic_md_prompt(
    name: str,
    description: str,
    focus_areas: str,
    slug: str,
) -> str:
    return f"""You are a newsletter topic architect. Create a topic.md file for a new daily intelligence briefing.

Topic Name: {name}
Description: {description}
Focus Areas: {focus_areas}
Slug: {slug}

The topic.md must have this structure (markdown format):

## Identity
- Role: [one sentence describing the newsletter's voice]
- Audience: [who reads this]
- Signal Label: [one word for the signal indicator, e.g., "Signal", "Escalation"]

## Sources
Organize URLs by category (Official, APIs, Research, Community, etc.).
Use markdown lists with links.

## Sections
Create 4-5 sections. For each section, provide:
### Section NN: Title
Description of what this section covers
- Sub-category 1
- Sub-category 2
- Sub-category 3
Aim: [target number of items, e.g., "4-6 items"]

Return ONLY the markdown content. No explanations, no code fences."""


def generate_topic_md(
    name: str,
    description: str,
    focus_areas: str,
    slug: str
) -> str:
    """
    Generate topic.md content using OpenRouter.

    Builds a prompt asking for a topic identity brief in the standard format
    (Identity section, Sources, Sections) and returns the raw markdown.

    Args:
        name: Topic name (e.g., 'Google AI')
        description: Brief description
        focus_areas: Comma-separated focus areas
        slug: Topic slug (e.g., 'google-ai')

    Returns:
        The topic.md content as a string

    Raises:
        RuntimeError: On OpenRouter errors or response issues
    """
    prompt = _build_topic_md_prompt(name, description, focus_areas, slug)
    response_text = chat_completion(prompt)
    return response_text.strip()
