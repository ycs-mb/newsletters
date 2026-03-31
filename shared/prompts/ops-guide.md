# Operations Guide — Newsletter Generation

## CRITICAL: JSON-ONLY OUTPUT

You MUST output a single valid JSON object with no markdown formatting, no code fences, and no explanation text.

## JSON Response Format

Your response must be EXACTLY this structure (replace the ... with actual content):

```
{"raw_markdown":"...","html":"...","top_story_summary":"..."}
```

Do NOT:
- Use markdown code fences (```json)
- Add any text before or after the JSON
- Split JSON across multiple lines
- Add explanations, headers, or any other text

DO:
- Output the JSON as a single line or properly formatted object
- Escape quotes and backslashes in string values
- Fill every `{{PLACEHOLDER}}` in the HTML section

## Content for Each Key

### raw_markdown
The complete newsletter content as markdown. Include:
- Headline/title
- All sections from the topic brief
- Proper markdown formatting (headers, lists, emphasis, links)
- Full source URLs

### html
The complete HTML document (do NOT include markdown fences):
1. Use the template below as your base
2. Replace every `{{PLACEHOLDER}}` with the corresponding content
3. Return the entire HTML as a single string
4. Escape HTML special characters if needed
5. Ensure all {{...}} tokens are filled

Template:
{{TEMPLATE_CONTENT}}

### top_story_summary
One sentence about the top story. Example:
"Google released Gemini 2.0 Ultra with 2M token context."

## Start Output Now

Output ONLY the JSON object. No preamble.
