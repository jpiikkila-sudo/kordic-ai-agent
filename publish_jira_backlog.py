import os
import asyncio
import re
import json
import requests
from dotenv import load_dotenv
from google.antigravity import Agent, LocalAgentConfig
from google.antigravity.types import CustomSystemInstructions, McpStdioServer, McpStreamableHttpServer
import google.antigravity.hooks.policy as policy
import db

# Load environment variables
load_dotenv(override=True)

# Ensure local database is initialized
db.init_db()

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

from main import is_wix_duplicate

# Read the content directly from the output markdown file
md_path = "/Users/jessicapiikkila/Documents/kordic-ai-agent/output_articles/How-to/Auto-Groom_Jira_Backlogs.md"
with open(md_path, "r") as f:
    full_text = f.read()

# We need to extract the portion requested by the user, which is the entire text from line 9 onwards,
# or we can just use the exact content. Since the file starts with:
# # Auto-Groom Jira Backlogs
# **Vertical:** Atlassian system of work and Rovo agents
# **Category:** How-to
# **Reference Age:** 4 days
# ---
# Let's extract everything from "I have edited and cleaned..."
start_marker = "I have edited and cleaned the entire draft"
start_idx = full_text.find(start_marker)
if start_idx != -1:
    article_content = full_text[start_idx:]
else:
    article_content = full_text

title = "Auto-Groom Jira Backlogs"
category = "How-to"
vertical = "Atlassian system of work and Rovo agents"
ref_age = 4

print("Loaded content length:", len(article_content))
print("Start of content:", article_content[:150])

async def publish():
    print("\n--- Publishing 'Auto-Groom Jira Backlogs' via Wix Publisher Agent ---")
    

        
    # Check if we are running in MOCK mode or live
    MOCK_MODE = os.getenv("MOCK_MODE", "false").lower() == "true"
    print(f"MOCK_MODE is currently set to: {MOCK_MODE}")
    
    # Load Publisher instructions from gemini.md
    try:
        with open("gemini.md", "r") as f:
            gemini_content = f.read()
            
        start_marker = "## Agent - Publisher"
        start_idx = gemini_content.find(start_marker)
        if start_idx == -1:
            raise ValueError("Publisher agent instructions not found in gemini.md")
        next_idx = gemini_content.find("## Summary", start_idx + len(start_marker))
        if next_idx == -1:
            next_idx = len(gemini_content)
        publisher_instructions = gemini_content[start_idx:next_idx].strip()
        
        # Replace email placeholders
        creator_email = os.getenv("CREATOR_EMAIL", "jpiikkila@kordic.ai")
        publisher_instructions = re.sub(r"\[[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\]", creator_email, publisher_instructions)
        publisher_instructions = publisher_instructions.replace("[EMAIL_ADDRESS]", creator_email)
    except Exception as e:
        print(f"Failed to load system instructions: {e}")
        return

    publisher_config = LocalAgentConfig(
        model="gemini-3.5-flash",
        system_instructions=CustomSystemInstructions(text=publisher_instructions),
        mcp_servers=get_publisher_mcp_servers(),
        policies=[policy.allow_all()]
    )

    # First, let's make sure the article exists in the database
    if not db.is_duplicate(title):
        db.save_article(title, vertical, article_content, category, ref_age)
        print(f"Saved initial draft of '{title}' in local DB.")
    else:
        print(f"Article '{title}' already exists in local DB, checking status...")

    wix_item_id = None
    if MOCK_MODE:
        wix_item_id = "wix-item-mock-12345"
        print(f"Running in MOCK_MODE. Mocked Wix Item ID: {wix_item_id}")
        print("\n--- Publisher Agent Log / Progress (MOCK MODE) ---")
        print(f"Checking for duplicates on Wix: '{title}' -> None found.")
        print(f"Retrieving/Creating category for vertical '{vertical}' -> Done.")
        print("Generating 3 labels/hashtags based on content -> Done.")
        print(f"Formatting to Ricos richContent and creating draft post -> Success.")
        print("--------------------------------------------------")
    else:
        try:
            print("Connecting to live Wix MCP via Google Antigravity Agent...")
            async with Agent(publisher_config) as publisher_agent:
                prompt_text = (
                    f"Please publish the article '{title}' (Category: '{category}') to the Wix Blog by performing these actions:\n"
                    f"1. Query site members using GET https://www.wixapis.com/members/v1/members?fieldsets=PUBLIC&paging.limit=1 to obtain a valid memberId.\n"
                    f"2. Retrieve the site's blog categories using GET https://www.wixapis.com/blog/v3/categories. "
                    f"If a category with the title/name '{vertical}' exists, retrieve its ID. "
                    f"If not, create a new category using POST https://www.wixapis.com/blog/v3/categories with the title and label set to '{vertical}', and get its ID.\n"
                    f"4. Convert this article's markdown content to Wix Ricos Rich Content format. Crucially, nest all text nodes inside PARAGRAPH nodes (even within list items, blockquotes, etc.), and use correct HEADING, BULLETED_LIST, or ORDERED_LIST structures.\n"
                    f"5. Create the draft post using POST https://www.wixapis.com/blog/v3/draft-posts with 'publish': false, the retrieved memberId, "
                    f"the vertical category ID under categoryIds, and exactly 3 relevant tags/labels under the hashtags list.\n"
                    f"6. Print detailed verbose logs of all API calls, payloads, status codes, and any errors encountered.\n"
                    f"7. Return the created Wix draft post ID in a format like 'wix-item-<id>' or 'Wix Draft Post ID: <id>'.\n\n"
                    f"Content to publish:\n{article_content}"
                )
                publisher_response = await publisher_agent.chat(prompt_text)
                publisher_output = await publisher_response.text()
                print("\n--- Publisher Agent Log / Progress ---")
                print(publisher_output)
                print("--------------------------------------")
                
                # Extract Wix Page/Item ID from the publisher output
                wix_id_match = re.search(r"wix-(?:item|page|post|draft)-\S+", publisher_output)
                if wix_id_match:
                    wix_item_id = wix_id_match.group(0)
                else:
                    uuid_match = re.search(r"[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}", publisher_output)
                    wix_item_id = f"wix-item-{uuid_match.group(0)}" if uuid_match else "unknown-wix-page-id"
                print(f"Extracted Wix Page ID: {wix_item_id}")
        except Exception as e:
            print(f"Live Wix publishing failed: {e}")
            wix_item_id = "wix-item-mock-failed-live"

    # Mark as published in local DB with status 'draft'
    db.mark_published(title, wix_item_id, local_file_path=md_path, status='draft')
    wix_site_id = os.getenv("WIX_SITE_ID", "your-site-id").strip()
    print(f"Updated database. Title: '{title}', Wix ID: '{wix_item_id}', Status: 'draft'")
    print(f"You can see the draft post in your Wix Blog Dashboard > Drafts at: https://www.wix.com/dashboard/{wix_site_id}/blog/posts/drafts")

if __name__ == "__main__":
    asyncio.run(publish())
