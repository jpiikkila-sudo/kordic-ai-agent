import os
import asyncio
import re
from dotenv import load_dotenv
from google.antigravity import Agent, LocalAgentConfig
from google.antigravity.types import CustomSystemInstructions
import db

# Load environment variables (.env file)
load_dotenv()

# Initialize the local SQLite database
db.init_db()

# Check configuration settings
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MOCK_MODE = os.getenv("MOCK_MODE", "false").lower() == "true"

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
    """
    topics = []
    # Find all blocks matching the pattern
    blocks = re.findall(
        r"-\s*Title:\s*(.*?)\n\s*Vertical:\s*(.*?)\n\s*Category:\s*(.*?)\n\s*Reference Age:\s*(\d+)",
        marketer_output,
        re.IGNORECASE
    )
    
    for block in blocks:
        topics.append({
            "title": block[0].strip(),
            "vertical": block[1].strip(),
            "category": block[2].strip(),
            "reference_age": int(block[3].strip())
        })
        
    # Fallback if the regex doesn't match the LLM output format exactly
    if not topics:
        # Create a default list for testing if parsing fails
        print("Warning: Could not parse marketer output format. Using fallback topics.")
        topics = [
            {
                "title": "Auto-Groom Jira Backlogs",
                "vertical": "Atlassian system of work and Rovo agents",
                "category": "How-to",
                "reference_age": 4
            },
            {
                "title": "Enterprise LLM Strategy",
                "vertical": "AI Adoption Trends",
                "category": "Whitepaper",
                "reference_age": 10
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
- Title: Enterprise LLM Strategy
  Vertical: AI Adoption Trends
  Category: Whitepaper
  Reference Age: 10
- Title: Design Custom MCP Connectors
  Vertical: MCP Connectors
  Category: Guide
  Reference Age: 2
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
        
        # Enforce under-5-word limit for mock title
        clean_title = " ".join(clean_title.split()[:4])
        
        return f"""
Title: {clean_title}
When a deployment fails at 4:45 PM on a Friday, this tool saves your sanity. We found that most teams do this manually.
So, use this automation model to route tickets:
1. Open settings.
2. Tap config.
3. Turn on auto-sync.
        """.strip()
        
    elif agent_name == "Publisher":
        return "wix-item-mock-12345"
        
    return "Mock Response"

async def run_pipeline():
    print(f"Initializing Content Automation Pipeline (Mock Mode: {MOCK_MODE})...")

    # Load agent configurations
    product_marketer_instructions = load_system_instructions("Product Marketer")
    sme_instructions = load_system_instructions("Technical Subject Matter Expert")
    content_editor_instructions = load_system_instructions("Content Editor")
    publisher_instructions = load_system_instructions("Publisher")

    pm_config = LocalAgentConfig(
        system_instructions=CustomSystemInstructions(text=product_marketer_instructions)
    )
    sme_config = LocalAgentConfig(
        system_instructions=CustomSystemInstructions(text=sme_instructions)
    )
    editor_config = LocalAgentConfig(
        system_instructions=CustomSystemInstructions(text=content_editor_instructions)
    )
    publisher_config = LocalAgentConfig(
        system_instructions=CustomSystemInstructions(text=publisher_instructions)
    )

    # 1. Product Marketer discovers topics
    print("\n--- Phase 1: Product Marketer Topic Discovery ---")
    if MOCK_MODE:
        pm_output = await get_mock_response("Product Marketer")
    else:
        async with Agent(pm_config) as pm_agent:
            pm_response = await pm_agent.chat(
                "Scan the latest trends and provide a prioritized list of topics with 'Title', 'Vertical', 'Category', and 'Reference Age' (in days) fields."
            )
            pm_output = await pm_response.text()
    
    print("Marketer identified topics:\n", pm_output)
    
    # Parse discovered topics
    discovered_topics = parse_topics(pm_output)
    
    # Human-in-the-loop topic selection
    print("\nWhich of these topics would you like to pass to the Technical SME agent for architectural detailing?")
    for idx, topic in enumerate(discovered_topics, start=1):
        print(f"[{idx}] {topic['title']} ({topic['category']}) - {topic['vertical']}")
        
    user_input = input("\nEnter the numbers of the topics to process (comma-separated, e.g., '1,3'), or press Enter to process all: ")
    if user_input.strip():
        try:
            selected_indices = [int(i.strip()) - 1 for i in user_input.split(",") if i.strip()]
            discovered_topics = [discovered_topics[i] for i in selected_indices if 0 <= i < len(discovered_topics)]
        except ValueError:
            print("Invalid input. Processing all discovered topics by default.")
            
    print(f"\nProceeding with {len(discovered_topics)} selected topics. Starting verification and publishing loop...")

    # 2. Iterate through each topic
    for idx, topic in enumerate(discovered_topics, start=1):
        title = topic["title"]
        vertical = topic["vertical"]
        category = topic["category"]
        ref_age = topic["reference_age"]
        
        print(f"\n[{idx}/{len(discovered_topics)}] Processing: '{title}' ({category})")
        
        # Step 2a: Check for duplication in the local database
        if db.is_duplicate(title):
            print(f"  [Skip] Title '{title}' already exists in the local database. Skipping to prevent duplicates.")
            continue
            
        print(f"  [Unique] Title '{title}' is not a duplicate. Generating content...")

        # Step 2b: Technical SME generates draft
        if MOCK_MODE:
            sme_output = await get_mock_response("Technical Subject Matter Expert", title)
        else:
            async with Agent(sme_config) as sme_agent:
                sme_response = await sme_agent.chat(
                    f"Create factual content outline and implementation plan for the topic: '{title}' in vertical '{vertical}' as a '{category}'."
                )
                sme_output = await sme_response.text()

        # Step 2c: Content Editor polishes draft
        if MOCK_MODE:
            editor_output = await get_mock_response("Content Editor", sme_output)
        else:
            async with Agent(editor_config) as editor_agent:
                editor_response = await editor_agent.chat(
                    f"Edit and clean this draft to match Kordic's gritty tone, removing AI jargon and keeping the title under 5 words:\n{sme_output}"
                )
                editor_output = await editor_response.text()
                
        # Parse the polished title from the Editor output (usually starts with "Title: ...")
        polished_title = title
        title_match = re.search(r"Title:\s*(.*?)\n", editor_output, re.IGNORECASE)
        if title_match:
            polished_title = title_match.group(1).strip()
            
        # Step 2d: Save to local database (Status: Draft/Unpublished)
        db.save_article(polished_title, vertical, editor_output, category, ref_age)
        print(f"  [Local DB] Saved polished article '{polished_title}' locally.")

        # Step 2e: Save locally to output_articles/ directory in Markdown format
        os.makedirs("output_articles", exist_ok=True)
        # Create a folder for the category inside output_articles
        category_dir = os.path.join("output_articles", category.replace(" ", "_"))
        os.makedirs(category_dir, exist_ok=True)
        
        # Clean title for filename
        clean_filename = re.sub(r'[\\/*?:"<>| ]', '_', polished_title).strip('_') + ".md"
        local_file_path = os.path.join(category_dir, clean_filename)
        
        with open(local_file_path, "w") as f:
            f.write(f"# {polished_title}\n\n**Vertical:** {vertical}\n**Category:** {category}\n**Reference Age:** {ref_age} days\n\n---\n\n{editor_output}")
        print(f"  [Local File] Saved formatted article locally at: {local_file_path}")

        # Step 2f: Publisher posts to Wix (or gets mock publish ID)
        print("  [Publishing] Sending to Wix CMS...")
        if MOCK_MODE:
            wix_item_id = await get_mock_response("Publisher", polished_title)
        else:
            # Connect the publisher agent to the Wix MCP server
            async with Agent(publisher_config) as publisher_agent:
                publisher_response = await publisher_agent.chat(
                    f"Query Wix to double check duplicates, then insert this article into the portfolio database as a DRAFT. Title: '{polished_title}', Content: '{editor_output}'."
                )
                publisher_output = await publisher_response.text()
                
                # Try to parse Wix item ID from publisher output
                wix_id_match = re.search(r"wix-item-\S+", publisher_output)
                wix_item_id = wix_id_match.group(0) if wix_id_match else "unknown-wix-id"
                
        db.mark_published(polished_title, wix_item_id, local_file_path=local_file_path, status='draft')
        print(f"  [Published] Wix item created successfully as a DRAFT. ID: {wix_item_id}")

    # Print final execution report
    print("\n==================================================")
    print("Final Local Resource Hub Articles (Sorted by Freshness):")
    for art in db.get_all_articles():
        publish_status = f"Wix ID: {art['wix_item_id']} [Status: {art['status'].upper()}]" if art['wix_item_id'] else "Local Only"
        file_info = f" | File: {art['local_file_path']}" if art['local_file_path'] else ""
        print(f"- [{art['category']}] {art['title']} | Reference Age: {art['reference_age']} days | {publish_status}{file_info}")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_pipeline())
