# Handoff Report — Wix Blog Integration Analysis

## 1. Observation

### Codebase Configurations
- In `/Users/jessicapiikkila/Documents/kordic-ai-agent/main.py` lines 222-225, the `publisher_config` is defined as follows:
  ```python
  222:     publisher_config = LocalAgentConfig(
  223:         model="gemini-3.5-flash",
  224:         system_instructions=CustomSystemInstructions(text=publisher_instructions)
  225:     )
  ```
- In `/Users/jessicapiikkila/Documents/kordic-ai-agent/publish_jira_backlog.py` lines 72-75 and `/Users/jessicapiikkila/Documents/kordic-ai-agent/publish_whitepaper.py` lines 68-71, the `publisher_config` is identically configured without any `mcp_servers` parameter.

### SDK MCP Connection Logic
- In the SDK file `/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/google/antigravity/agent.py` lines 120-151, the MCP connection is conditionally executed only when `mcp_servers` is populated:
  ```python
  120:       has_mcp_servers = bool(self._config.mcp_servers)
  ...
  144:       if self._config.mcp_servers:
  145:         logging.info("Connecting to MCP servers...")
  146:         self._mcp_bridge = bridge.McpBridge()
  147:         self._exit_stack.push_async_callback(self._mcp_bridge.stop)
  148: 
  149:         for server_cfg in self._config.mcp_servers:
  150:           await self._mcp_bridge.connect(server_cfg)
  151:         all_tools.extend(self._mcp_bridge.tools)
  ```
- In `/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/google/antigravity/connections/local/local_connection_config.py` lines 52-54, the default value for `mcp_servers` is an empty list:
  ```python
  52:   mcp_servers: list[types.McpServerConfig] = pydantic.Field(
  53:       default_factory=list
  54:   )
  ```

### Mismatch in Prompts vs. Instructions
- The Publisher system instructions defined in `gemini.md` under `## Agent - Publisher` (lines 190-230) dictate:
  > "You must publish the finalized content pieces by creating a new draft blog post on the Wix site using the Wix Blog API. Follow this sequence to create and populate a draft blog post: 1. Establish Site Context: ... 2. Retrieve Author/Member ID: ... 3. Format Content to Ricos Rich Content... 4. Create Draft Post: ..."
- However, the execution scripts send a prompt to the Publisher agent asking it to duplicate template pages (e.g. `main.py` lines 349-352):
  ```python
  349:                     publisher_response = await publisher_agent.chat(
  350:                         f"Duplicate the template page corresponding to Category: '{category}' (e.g., Template: Demo, Template: Article, Template: Whitepaper, Template: Solution Guide, Template: Blog) for the article '{polished_title}'. "
  351:                         f"Then populate its page content elements with: '{editor_output}'. Set status to draft/unpublished. Ensure no duplication exists."
  352:                     )
  ```

### Baseline Tests
- Running `python3 -m unittest test_pipeline.py` in the workspace successfully completes:
  ```
  Ran 5 tests in 0.008s
  OK
  ```

---

## 2. Logic Chain

1. **No Automatic Local MCP Discovery:** The Antigravity SDK requires the `mcp_servers` configuration to be explicitly populated in `LocalAgentConfig` (as observed in `agent.py`). If omitted, no `McpBridge` is initialized, meaning the agent cannot access any external tools.
2. **Current Publisher Disconnection:** Because all execution scripts (`main.py`, `publish_jira_backlog.py`, `publish_whitepaper.py`) omit `mcp_servers` in their configurations, the Publisher agent cannot connect to the `wix-mcp` server. It cannot call Wix tools like `ListWixSites`, `ManageWixSite`, or `CallWixSiteAPI`.
3. **Workflow Discrepancy:** The system instructions in `gemini.md` specify a modern Wix Blog API workflow using structured Ricos Rich Content nodes. Meanwhile, the actual python script prompts ask the agent to duplicate standard site template pages.
4. **Safety Policy Requirements:** In `agent.py`, if write tools or MCP servers are enabled without safety policies configured, the agent raises a `ValueError`. Therefore, when connecting `wix-mcp`, safety policies (such as `policies=[policy.allow_all()]` or specific allowed tool list) must be added.

---

## 3. Caveats

- **External Server Execution Details:** We did not identify whether the local `wix-mcp` runs via `stdio` (local process) or `sse` (Server-Sent Events url), but we know the schemas are stored in `/Users/jessicapiikkila/.gemini/antigravity/mcp/wix-mcp/` and their eager registrations are active in the developer's sandbox environment.
- **Wix Site Token Validity:** The credentials inside `.env` (`WIX_ACCOUNT_ID`, `WIX_SITE_ID`, `WIX_API_KEY`) were not verified live because this is a read-only investigation.

---

## 4. Conclusion

The Publisher integration is currently not functional for live publishing due to the lack of `mcp_servers` definition in the configuration and a mismatch in the prompt's workflow (duplicating templates vs. creating Wix Blog draft posts via Ricos Rich Content).

To implement the integration, the following actions are needed:
1. Configure `mcp_servers` in the Publisher agent's `LocalAgentConfig`.
2. Add appropriate safety policies (e.g., `policy.allow_all()` or specific wix-mcp tool list) to satisfy the SDK safety guardrails.
3. Update the Publisher's prompt to use the Wix Blog API and Ricos formatting logic rather than template duplication.

---

## 5. Verification Method

To verify the integration gaps independently:
- **Inspect configurations:** Check `main.py`, `publish_jira_backlog.py`, and `publish_whitepaper.py` to confirm the lack of `mcp_servers` parameters.
- **Verify SDK Guardrails:** Check the `test_pipeline.py` baseline by executing:
  ```bash
  python3 -m unittest test_pipeline.py
  ```

---

## 6. Remaining Work

The following steps are required for the implementer:
- Define the configuration block for `wix-mcp` (using stdio or SSE transport depending on wix-mcp's local runner).
- Pass `mcp_servers` and `policies` into the `LocalAgentConfig` for the Publisher agent.
- Rewrite the publisher invocation in python scripts to instruct the agent to query site context, fetch member/author IDs, format markdown to Ricos Rich Content nodes, and POST to the draft posts API, as defined in `gemini.md`.
