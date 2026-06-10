## 2026-06-09T17:37:50Z

Please complete the implementation of live Wix Blog publishing and deduplication for the Kordic Content Engine.
Follow these steps:
1. Examine the file `/Users/jessicapiikkila/.gemini/config/mcp_config.json` using a Python script or terminal command to find the exact command and arguments for the `wix-mcp` server.
2. Update the `Publisher` agent config in `main.py`, `publish_jira_backlog.py`, and `publish_whitepaper.py`. Configure it to connect to the `wix-mcp` server using `McpStdioServer` and safety policies `policies=[policy.allow_all()]` imported from `google.antigravity.hooks.policy`.
3. Update `main.py` to perform a live duplication check at Step 2a (before generating/publishing content) by querying the Wix Blog API `POST https://www.wixapis.com/blog/v3/draft-posts/query` with the article's title. You can write a helper function in `db.py` or `main.py` using `requests` that queries the Wix API using the credentials from `.env` (`WIX_API_KEY`, `WIX_SITE_ID`, `WIX_ACCOUNT_ID` headers). If a draft post with the same title already exists on the Wix site, skip it.
4. Update the Publisher agent prompt/chat calls in `main.py`, `publish_jira_backlog.py`, and `publish_whitepaper.py`. Instead of telling the agent to "duplicate the template page", instruct it to:
   - Query the site members using `GET https://www.wixapis.com/members/v1/members?fieldsets=PUBLIC&paging.limit=1` to get a valid `memberId`.
   - Check again for title duplicates on Wix using the MCP tool.
   - Format the markdown content to Wix Ricos Rich Content format (strictly nesting all text nodes inside PARAGRAPH nodes, even inside blockquotes and list items, and using proper HEADING, BULLETED_LIST / ORDERED_LIST nodes).
   - Create a draft post on Wix using `POST https://www.wixapis.com/blog/v3/draft-posts` with `"publish": false` and return the created Wix draft post ID.
5. In `db.py`, ensure the SQLite `articles` table is correctly updated with the Wix draft post ID and status set to `'draft'`.
6. Update `test_pipeline.py` to add test cases that mock these live Wix API endpoints (members, draft-posts, and draft-posts query) to verify the new integration flows and deduplication logic, and run the test suite.
7. Document your modifications in `/Users/jessicapiikkila/Documents/kordic-ai-agent/.agents/teamwork_preview_worker_m2_1/handoff.md`. Include the test outputs.

MANDATORY INTEGRITY WARNING: DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Please use `/Users/jessicapiikkila/Documents/kordic-ai-agent/.agents/teamwork_preview_worker_m2_1` as your working directory. You must create your own progress.md and BRIEFING.md files there.
