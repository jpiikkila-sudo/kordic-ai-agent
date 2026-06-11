import os
import asyncio
import re
import json
import requests
from dotenv import load_dotenv
from google.antigravity import Agent, LocalAgentConfig, types
from google.antigravity.types import CustomSystemInstructions, McpStdioServer, McpStreamableHttpServer, CapabilitiesConfig, BuiltinTools
from google.antigravity.hooks import hooks
import google.antigravity.hooks.policy as policy
import db

def approve_scopes(scopes: list[str]) -> list[policy.Policy]:
    """
    Helper that converts a list of scopes into Policy objects using policy.allow,
    and appends a policy.deny_all() at the end to restrict other tools.
    """
    policies = []
    for scope in scopes:
        policies.append(policy.allow(scope))
    policies.append(policy.deny_all())
    return policies

policy.approve_scopes = approve_scopes


# ANSI Color codes for styled output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

def log_status(status_tag: str, message: str, color: str = Colors.RESET):
    """
    Utility to print styled log status
    """
    print(f"{color}{Colors.BOLD}[{status_tag}]{Colors.RESET} {message}")

# --- Visual SDK Hooks ---
@hooks.on_session_start
async def on_start():
    log_status("⚡ SESSION_START", "Agent session started successfully.", Colors.GREEN)

@hooks.on_session_end
async def on_end():
    log_status("🔌 SESSION_END", "Agent session ended.", Colors.YELLOW)

@hooks.pre_turn
async def pre_turn(data: str) -> types.HookResult:
    # Truncate details
    snippet = (data[:60].replace('\n', ' ') + "...") if len(data) > 60 else data
    log_status("🤖 GEMINI API", f"Sending query: '{snippet}'", Colors.CYAN)
    log_status("⏳ WAITING", "Waiting for Gemini response (network active)...", Colors.YELLOW)
    return types.HookResult(allow=True)

@hooks.post_turn
async def post_turn(data: str):
    log_status("✅ API SUCCESS", "Received response from Gemini.", Colors.GREEN)

@hooks.pre_tool_call_decide
async def pre_tool(data: types.ToolCall) -> types.HookResult:
    log_status("⚙️ MCP TOOL", f"Calling tool '{data.name}' with arguments: {data.args}", Colors.BLUE)
    log_status("⏳ WAITING", f"Waiting for tool '{data.name}' execution to complete...", Colors.YELLOW)
    return types.HookResult(allow=True)

@hooks.post_tool_call
async def post_tool(data):
    output_str = str(data)
    truncated = (output_str[:120].replace('\n', ' ') + "...") if len(output_str) > 120 else output_str
    log_status("✅ TOOL SUCCESS", f"Tool executed successfully. Output: {truncated}", Colors.GREEN)

@hooks.on_tool_error
async def on_error(data: Exception):
    log_status("❌ TOOL ERROR", f"Tool failed with exception: {data}", Colors.RED)
    return None


# Load environment variables (.env file)
load_dotenv(override=True)

# Initialize the local SQLite database
db.init_db()

# Check configuration settings
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MOCK_MODE = os.getenv("MOCK_MODE", "false").lower() == "true"

def get_publisher_mcp_servers():
    """
    Reads mcp_config.json to load wix-mcp server configuration.
    Returns a list of MCP server configuration objects.
    """
    mcp_servers = []
    config_path = "/Users/jessicapiikkila/.gemini/config/mcp_config.json"
    
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                cfg = json.load(f)
                wix_mcp = cfg.get("mcpServers", {}).get("wix-mcp")
                if wix_mcp:
                    if "command" in wix_mcp:
                        mcp_servers.append(
                            McpStdioServer(
                                name="wix-mcp",
                                command=wix_mcp["command"],
                                args=wix_mcp.get("args", [])
                            )
                        )
                    elif "serverUrl" in wix_mcp:
                        mcp_servers.append(
                            McpStreamableHttpServer(
                                name="wix-mcp",
                                url=wix_mcp["serverUrl"],
                                headers=wix_mcp.get("headers")
                            )
                        )
        except Exception as e:
            print(f"Warning: Failed to load wix-mcp config from mcp_config.json: {e}")
            
    if not mcp_servers:
        # Fallback to .env values if mcp_config.json could not be loaded or parsed
        wix_api_key = os.getenv("WIX_API_KEY", "").strip()
        wix_site_id = os.getenv("WIX_SITE_ID", "").strip()
        if wix_api_key:
            mcp_servers.append(
                McpStreamableHttpServer(
                    name="wix-mcp",
                    url="https://mcp.wix.com/mcp",
                    headers={
                        "Authorization": wix_api_key,
                        "wix-account-id": wix_site_id
                    }
                )
            )
    return mcp_servers

def is_wix_duplicate(title: str) -> bool:
    """
    Checks if a draft post with the same title already exists on the live Wix site.
    Disabled: returns False to always create a new blog entry.
    """
    return False

if not GEMINI_API_KEY or "your_gemini" in GEMINI_API_KEY:
    print("No valid GEMINI_API_KEY found. Running in MOCK MODE for pipeline testing.")
    MOCK_MODE = True

def load_system_instructions(agent_name: str) -> str:
    """
    Reads the gemini.md file and extracts the specific system instructions for the requested agent.
    """
    try:
        with open("gemini.md", "r") as f:
            content = f.read()
        
        # Locate the agent section
        start_marker = f"## Agent - {agent_name}"
        if start_marker not in content:
            raise ValueError(f"Agent '{agent_name}' not found in gemini.md")
            
        start_idx = content.find(start_marker)
        
        # Find the next header to delimit the instructions
        next_idx = content.find("## Agent -", start_idx + len(start_marker))
        if next_idx == -1:
            next_idx = content.find("## Summary", start_idx + len(start_marker))
        if next_idx == -1:
            next_idx = len(content)
            
        instructions = content[start_idx:next_idx].strip()
        
        # Replace bracketed email placeholders with the CREATOR_EMAIL env variable
        creator_email = os.getenv("CREATOR_EMAIL", "jpiikkila@kordic.ai")
        instructions = re.sub(r"\[[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\]", creator_email, instructions)
        instructions = instructions.replace("[EMAIL_ADDRESS]", creator_email)
        
        return instructions
    except FileNotFoundError:
        print("Error: gemini.md file not found. Ensure it exists in the workspace.")
        return ""

def parse_topics(marketer_output: str):
    """
    Parses the structured output from the Product Marketer agent.
    Expected format:
    - Title: <title>
      Vertical: <vertical>
      Category: <category>
      Reference Age: <age>
      Rationale: <rationale> (optional)
      Source Links: <links> (optional)
    """
    blocks = marketer_output.split("- Title:")
    topics = []
    for block in blocks[1:]:
        lines = block.split("\n")
        title = lines[0].strip()
        vertical = ""
        category = ""
        ref_age = 0
        rationale = ""
        source_links = ""
        
        for line in lines[1:]:
            if ":" in line:
                key, val = line.split(":", 1)
                key = key.strip().lower()
                val = val.strip()
                if key == "vertical":
                    vertical = val
                elif key == "category":
                    category = val
                elif key in ("reference age", "reference_age"):
                    try:
                        ref_age = int(val)
                    except ValueError:
                        ref_age = 0
                elif key == "rationale":
                    rationale = val
                elif key in ("source links", "source_links", "sources"):
                    source_links = val
        
        if title:
            topics.append({
                "title": title,
                "vertical": vertical,
                "category": category,
                "reference_age": ref_age,
                "rationale": rationale,
                "source_links": source_links
            })
            
    # Fallback if the parser doesn't find any topics
    if not topics:
        print("Warning: Could not parse marketer output format. Using fallback topics.")
        topics = [
            {
                "title": "Auto-Groom Jira Backlogs",
                "vertical": "Atlassian system of work and Rovo agents",
                "category": "How-to",
                "reference_age": 4,
                "rationale": "Backlog management is a key enterprise pain point.",
                "source_links": "https://www.atlassian.com/software/rovo"
            },
            {
                "title": "Enterprise LLM Strategy",
                "vertical": "AI Adoption Trends",
                "category": "Whitepaper",
                "reference_age": 10,
                "rationale": "Enterprise readiness for LLMs governance remains a bottleneck.",
                "source_links": "https://www.mckinsey.com/ai-readiness"
            }
        ]
    return topics

async def get_mock_response(agent_name: str, input_text: str = "") -> str:
    """
    Simulates agent outputs for local testing when API limits are hit or billing is disabled.
    """
    await asyncio.sleep(0.5) # Simulate processing delay
    
    if agent_name == "Product Marketer":
        return """
- Title: Auto-Groom Jira Backlogs
  Vertical: Atlassian system of work and Rovo agents
  Category: How-to
  Reference Age: 4
  Rationale: Backlog management is a key enterprise pain point, especially with high developer friction.
  Source Links: https://www.atlassian.com/software/rovo, https://www.gartner.com/devops, https://dzone.com/jira-automation
- Title: Enterprise LLM Strategy
  Vertical: AI Adoption Trends
  Category: Whitepaper
  Reference Age: 10
  Rationale: Enterprise readiness for LLMs has grown rapidly but governance remains a bottleneck.
  Source Links: https://www.mckinsey.com/ai-readiness, https://www.forbes.com/llm-scaling, https://www.accenture.com/ai-governance
- Title: Design Custom MCP Connectors
  Vertical: MCP Connectors
  Category: Guide
  Reference Age: 2
  Rationale: Model Context Protocol is the standard for connecting LLMs to local data structures.
  Source Links: https://modelcontextprotocol.io, https://github.com/modelcontextprotocol, https://dev.to/mcp-guide
        """.strip()
        
    elif agent_name == "Technical Subject Matter Expert":
        return f"""
[Technical Draft for: {input_text}]
Scenario: Resolving operations bottlenecks.
Business Challenge: High labor costs and duplicate entries.
Implementation steps:
1. Navigate to settings.
2. Select options.
3. Configure authentication parameters.
4. Set up auto-sync logic.
5. Save changes.
        """.strip()
        
    elif agent_name == "Content Editor":
        # Extract title from technical draft text
        title_match = re.search(r"Technical Draft for:\s*(.*?)(?:\n|\]|$)", input_text, re.IGNORECASE)
        clean_title = title_match.group(1).strip() if title_match else "Polished Title"
        
        # Enforce 15-word limit for mock title
        clean_title = " ".join(clean_title.split()[:15])
        
        if "Jira" in clean_title or "Backlog" in clean_title:
            return f"""
Title: Auto-Groom Jira Backlogs
Subtitle: Eliminate backlog noise with Atlassian Rovo and AI agent workflows.

When a deployment fails at 4:45 PM on a Friday, the last thing your team wants is to sort through a messy backlog of duplicate tickets. We found that most teams do this manually. 

So, use this automation model to route tickets and keep your workspace clean.

### Why Auto-Grooming Matters
A cluttered backlog slows down your sprint planning. It breeds confusion.
This guide shows you how to deploy a Rovo agent that sweeps your Jira backlog hourly, closing duplicate tickets and highlighting stale requests.

### Prerequisites
* Administrative access to your Jira Cloud environment.
* Atlassian Rovo API access.
* A secure API token stored in your environment.

### Implementation Blueprint
* **Step 1: Configure the Webhook**
  Navigate to Project Settings > Automation > Webhooks. Create a webhook that triggers on issue creation.
* **Step 2: Initialize Rovo Agent Prompt**
  Configure the agent prompt with specific instructions: "Scan the last 50 issues. If you detect a similarity score above 85%, mark the newer issue as a duplicate."
* **Step 3: Establish the Auto-Close Loop**
  Define the action path in Jira: Link the duplicate issue to the parent issue and transition it to closed status.

### Success Verification
Open a test issue that duplicates an existing ticket. The Rovo agent will automatically link and close the duplicate ticket within 5 minutes.
            """.strip()
        else:
            return f"""
Title: {clean_title}
Subtitle: Deploying custom agents for engineering operations.

Operational friction slows down teams. We found that most systems fail due to poor connector designs.

So, follow this layout to build your next integration model.

### Key Guidelines
* **Audience:** Platform Architects & Operations Managers.
* **Objective:** Streamline data pipelines between systems of record.

### Configuration Phase
* **Step 1: Register the Endpoint**
  Navigate to Settings > Integrations. Add your new API base URL.
* **Step 2: Scoping and Security**
  Set up OAuth client parameters. Restrict edit privileges to Admin groups.
* **Step 3: Verification**
  Run a test payload to verify successful authorization and data transfer.
            """.strip()
        
    elif agent_name == "Publisher":
        return "wix-item-mock-12345"
        
    return "Mock Response"

async def run_pipeline():
    print(f"Initializing Kordic Hub Content Engine (Mock Mode: {MOCK_MODE})...")

    # Load agent configurations
    product_marketer_instructions = load_system_instructions("Product Marketer")
    sme_instructions = load_system_instructions("Technical Subject Matter Expert")
    content_editor_instructions = load_system_instructions("Content Editor")
    publisher_instructions = load_system_instructions("Publisher")

    agent_hooks = [on_start, on_end, pre_turn, post_turn, pre_tool, post_tool, on_error]

    pm_config = LocalAgentConfig(
        model="gemini-3.5-flash",
        system_instructions=CustomSystemInstructions(text=product_marketer_instructions),
        capabilities=CapabilitiesConfig(enabled_tools=[]),
        mcp_servers=[],
        policies=policy.approve_scopes([]),
        hooks=agent_hooks
    )
    sme_config = LocalAgentConfig(
        model="gemini-3.5-flash",
        system_instructions=CustomSystemInstructions(text=sme_instructions),
        capabilities=CapabilitiesConfig(enabled_tools=[]),
        mcp_servers=[],
        policies=policy.approve_scopes([]),
        hooks=agent_hooks
    )
    editor_config = LocalAgentConfig(
        model="gemini-3.5-flash",
        system_instructions=CustomSystemInstructions(text=content_editor_instructions),
        capabilities=CapabilitiesConfig(enabled_tools=[BuiltinTools.GENERATE_IMAGE]),
        mcp_servers=[],
        policies=policy.approve_scopes(["generate_image"]),
        hooks=agent_hooks
    )
    publisher_config = LocalAgentConfig(
        model="gemini-3.5-flash",
        system_instructions=CustomSystemInstructions(text=publisher_instructions),
        mcp_servers=get_publisher_mcp_servers(),
        policies=policy.approve_scopes(["wix-mcp/*"]),
        hooks=agent_hooks
    )

    # 1. Product Marketer discovers topics
    log_status("⚡ RUNNING", "Phase 1: Product Marketer Topic Discovery starting...", Colors.GREEN)
    cache_file = "discovered_topics.txt"
    use_cache = False
    
    if os.path.exists(cache_file):
        import time
        file_age_days = (time.time() - os.path.getmtime(cache_file)) / (24 * 3600)
        if file_age_days < 13:
            use_cache = True
            log_status("💾 CACHE LOAD", f"Loading discovered topics from cache '{cache_file}' (Age: {file_age_days:.1f} days, < 13 days old).", Colors.GREEN)
            try:
                with open(cache_file, "r") as f:
                    pm_output = f.read()
            except Exception as e:
                log_status("⚠️ CACHE WARN", f"Failed to read local cache: {e}. Falling back to live discovery.", Colors.YELLOW)
                use_cache = False

    if not use_cache:
        log_status("🤖 PM LIVE", "Product Marketer agent is scanning live web/trends...", Colors.CYAN)
        if MOCK_MODE:
            pm_output = await get_mock_response("Product Marketer")
        else:
            async with Agent(pm_config) as pm_agent:
                pm_response = await pm_agent.chat(
                    "Scan the latest trends and provide a prioritized list of topics. "
                    "Recommend exactly 2 topics for each of the 4 core verticals. For each topic, output fields: "
                    "'- Title', 'Vertical', 'Category', 'Reference Age' (in days), 'Rationale' (a brief prioritizing reason), "
                    "and 'Source Links' (at least three validated external reference links)."
                )
                pm_output = await pm_response.text()
        
        # Save newly discovered topics to local cache
        try:
            with open(cache_file, "w") as f:
                f.write(pm_output)
            log_status("💾 CACHE SAVE", f"Saved newly discovered topics to local cache '{cache_file}'.", Colors.GREEN)
        except Exception as e:
            log_status("⚠️ CACHE WARN", f"Failed to write cache file: {e}", Colors.YELLOW)
    
    # Parse discovered topics
    discovered_topics = parse_topics(pm_output)
    
    # Human-in-the-loop topic selection
    print("\nWhich of these topics would you like to pass to the Technical SME agent for architectural detailing?")
    for idx, topic in enumerate(discovered_topics, start=1):
        extra_ctx = ""
        if topic.get("rationale"):
            extra_ctx += f"\n    Rationale: {topic['rationale']}"
        if topic.get("source_links"):
            extra_ctx += f"\n    Source Links: {topic['source_links']}"
        print(f"[{idx}] {topic['title']} ({topic['category']}) - {topic['vertical']}{extra_ctx}")
        
    try:
        import sys
        # Check if stdin is a TTY to avoid blocking in non-interactive mode
        if not sys.stdin.isatty():
            print("\nNon-interactive mode detected. Processing the first topic only to save AI credits.")
            discovered_topics = discovered_topics[:1]
        else:
            user_input = input("\nEnter the numbers of the topics to process (comma-separated, e.g., '1,3'), or press Enter to process all: ")
            if user_input.strip():
                try:
                    selected_indices = [int(i.strip()) - 1 for i in user_input.split(",") if i.strip()]
                    discovered_topics = [discovered_topics[i] for i in selected_indices if 0 <= i < len(discovered_topics)]
                except ValueError:
                    print("Invalid input. Processing all discovered topics by default.")
    except (EOFError, ImportError):
        print("\nInput not available. Processing the first topic only to save AI credits.")
        discovered_topics = discovered_topics[:1]
            
    print(f"\nProceeding with {len(discovered_topics)} selected topics. Starting verification and publishing loop...")

    # 2. Iterate through each topic
    for idx, topic in enumerate(discovered_topics, start=1):
        title = topic["title"]
        vertical = topic["vertical"]
        category = topic["category"]
        ref_age = topic["reference_age"]
        bypass_editor = False
        
        log_status("⚡ RUNNING", f"Phase 2: Technical SME detailing architecture for '{title}'...", Colors.GREEN)
        
        log_status("✅ PROCESSING", f"Processing topic '{title}'...", Colors.GREEN)

        # Step 2b: Technical SME generates draft
        try:
            if MOCK_MODE:
                sme_output = await get_mock_response("Technical Subject Matter Expert", title)
                import sys
                if sys.stdin.isatty():
                    while True:
                        print(f"\n--- CURRENT SME DRAFT FOR '{title}' ---")
                        print(sme_output)
                        print("---------------------------------------")
                        log_status("🔵 WAITING", "Enter feedback to revise content (or type 'Pass content to editor agent' or 'Pass content to publisher agent'):", Colors.YELLOW)
                        try:
                            user_feedback = input("> ").strip()
                        except (EOFError, KeyboardInterrupt):
                            log_status("⚠️ INTERRUPT", "Feedback input interrupted. Proceeding with current draft.", Colors.YELLOW)
                            break
                        if user_feedback.lower() == "pass content to editor agent":
                            log_status("📥 RECEIVED", "Transitioning content to Content Editor agent...", Colors.GREEN)
                            break
                        elif user_feedback.lower() == "pass content to publisher agent":
                            log_status("📥 RECEIVED", "Bypassing editor. Transitioning content directly to Publisher agent...", Colors.GREEN)
                            bypass_editor = True
                            break
                        log_status("📥 RECEIVED", f"Feedback: '{user_feedback}'. Processing revision...", Colors.CYAN)
                        sme_output = sme_output + f"\n\n[Mocked revision based on feedback: '{user_feedback}']"
            else:
                async with Agent(sme_config) as sme_agent:
                    sme_response = await sme_agent.chat(
                        f"Create factual content outline and implementation plan for the topic: '{title}' in vertical '{vertical}' as a '{category}'."
                    )
                    sme_output = await sme_response.text()
                    
                    import sys
                    if sys.stdin.isatty():
                        while True:
                            print(f"\n--- CURRENT SME DRAFT FOR '{title}' ---")
                            print(sme_output)
                            print("---------------------------------------")
                            log_status("🔵 WAITING", "Enter feedback to revise content (or type 'Pass content to editor agent' or 'Pass content to publisher agent'):", Colors.YELLOW)
                            try:
                                user_feedback = input("> ").strip()
                            except (EOFError, KeyboardInterrupt):
                                log_status("⚠️ INTERRUPT", "Feedback input interrupted. Proceeding with current draft.", Colors.YELLOW)
                                break
                            if user_feedback.lower() == "pass content to editor agent":
                                log_status("📥 RECEIVED", "Transitioning content to Content Editor agent...", Colors.GREEN)
                                break
                            elif user_feedback.lower() == "pass content to publisher agent":
                                log_status("📥 RECEIVED", "Bypassing editor. Transitioning content directly to Publisher agent...", Colors.GREEN)
                                bypass_editor = True
                                break
                            log_status("📥 RECEIVED", f"Feedback: '{user_feedback}'. Requesting revision from Technical SME agent...", Colors.CYAN)
                            sme_response = await sme_agent.chat(user_feedback)
                            sme_output = await sme_response.text()
            
            if not sme_output or len(sme_output.strip()) < 10:
                log_status("❌ ERROR", f"Technical SME generated empty or invalid draft for '{title}'. Skipping.", Colors.RED)
                continue
        except Exception as e:
            log_status("❌ ERROR", f"Exception during Technical SME content generation for '{title}': {e}. Skipping.", Colors.RED)
            continue

        # Step 2c: Content Editor polishes draft
        log_status("⚡ RUNNING", f"Phase 3: Content Editor polishing draft for '{title}'...", Colors.GREEN)
        try:
            if bypass_editor:
                log_status("⚠️ BYPASS", "Bypassing Content Editor as requested. Passing SME draft directly to publisher.", Colors.YELLOW)
                editor_output = sme_output
            elif MOCK_MODE:
                editor_output = await get_mock_response("Content Editor", sme_output)
                import sys
                if sys.stdin.isatty():
                    while True:
                        print(f"\n--- CURRENT EDITOR POLISHED ARTICLE FOR '{title}' ---")
                        print(editor_output)
                        print("-------------------------------------------------------")
                        log_status("🔵 WAITING", "Enter feedback to refine editorial style (or type 'Pass content to publisher agent'):", Colors.YELLOW)
                        try:
                            user_feedback = input("> ").strip()
                        except (EOFError, KeyboardInterrupt):
                            log_status("⚠️ INTERRUPT", "Feedback input interrupted. Proceeding with current polished version.", Colors.YELLOW)
                            break
                        if user_feedback.lower() == "pass content to publisher agent":
                            log_status("📥 RECEIVED", "Transitioning content to Publisher agent...", Colors.GREEN)
                            break
                        log_status("📥 RECEIVED", f"Feedback: '{user_feedback}'. Processing revision...", Colors.CYAN)
                        editor_output = editor_output + f"\n\n[Mocked editorial refinement based on feedback: '{user_feedback}']"
            else:
                async with Agent(editor_config) as editor_agent:
                    editor_response = await editor_agent.chat(
                        f"Edit and clean this draft to match Kordic's gritty tone, removing AI jargon and keeping the title to 15 words or less:\n{sme_output}"
                    )
                    editor_output = await editor_response.text()
                    
                    import sys
                    if sys.stdin.isatty():
                        while True:
                            print(f"\n--- CURRENT EDITOR POLISHED ARTICLE FOR '{title}' ---")
                            print(editor_output)
                            print("-------------------------------------------------------")
                            log_status("🔵 WAITING", "Enter feedback to refine editorial style (or type 'Pass content to publisher agent'):", Colors.YELLOW)
                            try:
                                user_feedback = input("> ").strip()
                            except (EOFError, KeyboardInterrupt):
                                log_status("⚠️ INTERRUPT", "Feedback input interrupted. Proceeding with current polished version.", Colors.YELLOW)
                                break
                            if user_feedback.lower() == "pass content to publisher agent":
                                log_status("📥 RECEIVED", "Transitioning content to Publisher agent...", Colors.GREEN)
                                break
                            log_status("📥 RECEIVED", f"Feedback: '{user_feedback}'. Requesting revision from Content Editor agent...", Colors.CYAN)
                            # Chat with the same editor agent instance to preserve context
                            editor_response = await editor_agent.chat(user_feedback)
                            editor_output = await editor_response.text()
            
            if not editor_output or len(editor_output.strip()) < 10:
                log_status("❌ ERROR", f"Content Editor generated empty or invalid output for '{title}'. Skipping.", Colors.RED)
                continue
        except Exception as e:
            log_status("❌ ERROR", f"Exception during Content Editor polishing for '{title}': {e}. Skipping.", Colors.RED)
            continue
                
        # Parse the polished title from the Editor output (usually starts with "Title: ...")
        polished_title = title
        title_match = re.search(r"Title:\s*(.*?)\n", editor_output, re.IGNORECASE)
        if title_match:
            polished_title = title_match.group(1).strip()
            

 
        # Print the content directly to the screen
        print(f"\n--------------------------------------------------")
        print(f"POLISHED ARTICLE CONTENT FOR: '{polished_title}'")
        print(f"--------------------------------------------------")
        print(editor_output)
        print(f"--------------------------------------------------\n")
            
        # Step 2d: Save to local database (Status: Draft/Unpublished)
        conn = db.get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM articles WHERE title = ?", (polished_title.strip(),))
        except Exception as e:
            log_status("⚠️ DB WARN", f"Failed to clean old record: {e}", Colors.YELLOW)
        finally:
            conn.close()

        save_res = db.save_article(polished_title, vertical, editor_output, category, ref_age)
        log_status("💾 LOCAL DB", f"Saved polished article '{polished_title}' locally.", Colors.GREEN)

        # Step 2e: Save locally to output_articles/ directory in Markdown format
        os.makedirs("output_articles", exist_ok=True)
        # Create a folder for the category inside output_articles
        category_dir = os.path.join("output_articles", category.replace(" ", "_"))
        os.makedirs(category_dir, exist_ok=True)
        
        # Clean title for filename
        clean_filename = re.sub(r'[\\/*?:"<>| ]', '_', polished_title).strip('_') + ".md"
        local_file_path = os.path.join(category_dir, clean_filename)
        
        with open(local_file_path, "w") as f:
            f.write(editor_output)
        log_status("💾 LOCAL FILE", f"Saved formatted article locally at: {local_file_path}", Colors.GREEN)

        # Step 2f: Publisher posts to Wix (or gets mock publish ID)
        log_status("⚡ RUNNING", f"Phase 4: Publisher sending '{polished_title}' to Wix CMS...", Colors.GREEN)
        if MOCK_MODE:
            wix_item_id = await get_mock_response("Publisher", polished_title)
            # Log mock progress to terminal
            print("\n--- Publisher Agent Log / Progress (MOCK MODE) ---")
            log_status("🔍 WIX CHECK", f"Checking for duplicates on Wix: '{polished_title}' -> None found.", Colors.CYAN)
            log_status("📂 WIX CATEGORY", f"Retrieving/Creating category for vertical '{vertical}' -> Done.", Colors.BLUE)
            log_status("🏷️ WIX TAGS", "Generating 3 labels/hashtags based on content -> Done.", Colors.BLUE)
            log_status("📝 RICOS CONVERT", "Formatting to Ricos richContent and creating draft post -> Success.", Colors.CYAN)
            print("--------------------------------------------------")
        else:
            try:
                # Connect the publisher agent to the Wix MCP server
                async with Agent(publisher_config) as publisher_agent:
                    prompt_text = (
                        f"Please publish the article '{polished_title}' (Category: '{category}') to the Wix Blog by performing these actions:\n"
                        f"1. Query site members using GET https://www.wixapis.com/members/v1/members?fieldsets=PUBLIC&paging.limit=1 to obtain a valid memberId.\n"
                        f"2. Retrieve the site's blog categories using GET https://www.wixapis.com/blog/v3/categories. "
                        f"If a category with the title/name '{vertical}' exists, retrieve its ID. "
                        f"If not, create a new category using POST https://www.wixapis.com/blog/v3/categories with the title and label set to '{vertical}', and get its ID.\n"
                        f"3. Convert this article's markdown content to Wix Ricos Rich Content format. Crucially, nest all text nodes inside PARAGRAPH nodes (even within list items, blockquotes, etc.), and use correct HEADING, BULLETED_LIST, or ORDERED_LIST structures. If there are external media/image URLs, download a local copy of each, convert it to base64, call the `UploadImageToWixSite` tool with `imageBase64`, `mimeType`, and `siteId` to upload it into the Media Manager, and use the returned media ID/wixstatic URL in the post instead of the external URL.\n"
                        f"4. Handle tags using the tags workflow: check if each of the 3 generated tags exists via GET https://www.wixapis.com/blog/v3/tags. If a tag is missing, create it using POST https://www.wixapis.com/blog/v3/tags by passing a raw JSON body with a top-level label field directly (e.g. `{{\"label\": \"Tag Label\"}}` - DO NOT wrap it inside a `\"tag\"` object) and retrieve its GUID id. Create the draft post using POST https://www.wixapis.com/blog/v3/draft-posts with 'publish': false, the retrieved memberId, the vertical category ID under categoryIds, the retrieved tag IDs in the 'tagIds' list, and the 3 tag labels in the 'hashtags' list.\n"
                        f"5. Print detailed verbose logs of all API calls, payloads, status codes, and any errors encountered.\n"
                        f"6. Return the created Wix draft post ID in a format like 'wix-item-<id>' or 'Wix Draft Post ID: <id>'.\n\n"
                        f"Content to publish:\n{editor_output}"
                    )
                    publisher_response = await publisher_agent.chat(prompt_text)
                    publisher_output = await publisher_response.text()
                    
                    print("\n--- Publisher Agent Log / Progress ---")
                    print(publisher_output)
                    print("--------------------------------------")
                    
                    # Try to parse Wix item/page ID from publisher output
                    wix_id_match = re.search(r"wix-(?:item|page|post|draft)-\S+", publisher_output)
                    if wix_id_match:
                        wix_item_id = wix_id_match.group(0)
                    else:
                        uuid_match = re.search(r"[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}", publisher_output)
                        wix_item_id = f"wix-item-{uuid_match.group(0)}" if uuid_match else "unknown-wix-id"
            except Exception as e:
                log_status("⚠️ WIX WARN", f"Live Wix publishing failed: {e}. Falling back to local draft registration.", Colors.YELLOW)
                wix_item_id = "wix-item-mock-failed-live"
                
        db.mark_published(polished_title, wix_item_id, local_file_path=local_file_path, status='draft')
        wix_site_id = os.getenv("WIX_SITE_ID", "your-site-id").strip()
        log_status("✅ PUBLISHED", f"Wix item created successfully as a DRAFT. ID: {wix_item_id}", Colors.GREEN)
        log_status("🔗 WIX LINK", f"View your draft post at: https://www.wix.com/dashboard/{wix_site_id}/blog/posts/drafts", Colors.BLUE)

    # Print final execution report
    print("\n==================================================")
    log_status("📊 REPORT", "Final Local Resource Hub Articles (Sorted by Freshness):", Colors.HEADER)
    for art in db.get_all_articles():
        publish_status = f"Wix ID: {art['wix_item_id']} [Status: {art['status'].upper()}]" if art['wix_item_id'] else "Local Only"
        file_info = f" | File: {art['local_file_path']}" if art['local_file_path'] else ""
        print(f"- [{art['category']}] {art['title']} | Reference Age: {art['reference_age']} days | {publish_status}{file_info}")
    print("==================================================")

async def run_scheduler():
    log_status("⏰ DAEMON", "Starting Kordic Content Engine Daemon on a 14-day schedule...", Colors.GREEN)
    while True:
        log_status("⚡ RUNNING", "Executing scheduled content automation pipeline run...", Colors.GREEN)
        try:
            await run_pipeline()
        except Exception as e:
            log_status("❌ ERROR", f"Pipeline execution failed in schedule loop: {e}", Colors.RED)
        
        log_status("⏰ SLEEP", "Sleeping for 14 days until the next scheduled topic refresh...", Colors.BLUE)
        await asyncio.sleep(14 * 24 * 3600)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] in ["--schedule", "--daemon"]:
        asyncio.run(run_scheduler())
    else:
        asyncio.run(run_pipeline())
