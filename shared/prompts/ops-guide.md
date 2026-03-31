# Operations Guide — Newsletter Generation

## OUTPUT SPECIFICATION

You must return **valid JSON only** (no markdown fences, no explanation text).

The response must be a JSON object with exactly these three keys:

```json
{
  "raw_markdown": "...",
  "html": "...",
  "top_story_summary": "..."
}
```

### `raw_markdown`

The complete newsletter content as markdown. Include:
- Headline/title for today
- All sections from the topic brief
- Proper markdown formatting (headers, lists, emphasis, links)
- Full source URLs in the compiled content

### `html`

The complete HTML document. You MUST:
1. Take the template below (between the `TEMPLATE START` and `TEMPLATE END` markers)
2. Replace every `{{PLACEHOLDER}}` with the corresponding compiled content
3. Return the entire filled-in HTML document as a string
4. Do NOT use markdown fences

**TEMPLATE START**

{{TEMPLATE_CONTENT}}

**TEMPLATE END**

### `top_story_summary`

One sentence summarizing the top/most important story from this issue. Example:
`"Google released Claude 4.5 Sonnet, achieving state-of-the-art performance on benchmark tasks."`

## IMPORTANT

- Return ONLY the JSON object. No additional text before or after.
- Ensure all HTML is valid and properly escaped.
- Fill every placeholder in the template — do not leave any `{{...}}` tokens unfilled.
- Use the topic brief sources as the basis for content (no web search capability available).
- Today's date is in the metadata provided by the topic brief.
