# Newsletter Generation Task

You are generating a JSON-formatted newsletter. Your response MUST be pure JSON with no other text.

## Required JSON Structure

Respond with this exact structure filled in (single object, no array, no markdown):
```
{"raw_markdown": "...", "html": "...", "top_story_summary": "..."}
```

## Required Fields

**raw_markdown**: Complete newsletter content as markdown string
- Include headline, all sections from topic brief above
- Use markdown formatting (headers, lists, links)
- Include source URLs where applicable

**html**: Complete HTML document as a string
- Start with the template below and fill all {{PLACEHOLDER}} markers
- Return as single string, do NOT wrap in code fences
- Ensure valid HTML and proper escaping

**top_story_summary**: One sentence string
- Summarize the most important story from this issue
- Example: "Google released Gemini 2.0 Ultra."

## The Template

{{TEMPLATE_CONTENT}}

## Your Task

Replace the placeholders in the template above with compiled newsletter content from the topic brief. Return ONLY the JSON object—no explanations, no code blocks, nothing else.
