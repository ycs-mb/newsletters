# Operations Guide — Newsletter Delivery

## ACTIONS (execute in order)

Today's date: determine from system clock (format YYYY-MM-DD).

1. Search the web thoroughly for all sections in the topic brief above.

2. Compile newsletter content.

3. Save raw markdown to:
   `~/newsletters/topics/{SLUG}/YYYY-MM-DD.md`
   (replace YYYY-MM-DD with today's date)

4. Read the template:
   `~/newsletters/topics/{SLUG}/site/template.html`

5. Fill all {{PLACEHOLDERS}} with compiled content following the design guide above.
   Save generated HTML to:
   `~/newsletters/topics/{SLUG}/site/index.html`

6. Save dated archive copy:
   `cp ~/newsletters/topics/{SLUG}/site/index.html ~/newsletters/topics/{SLUG}/site/YYYY-MM-DD.html`

7. Build portal:
   `cd ~/newsletters && uv run shared/build.py`

8. Send one Telegram message to chat_id 1538018072:
   Link: `http://100.110.249.12:8787/{SLUG}/`
   Include: today's date, 1-sentence summary of top story.

9. Exit — do not start or restart the HTTP server (handled by run.sh).
