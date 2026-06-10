import os
import sys
import asyncio
from unittest.mock import patch

# Load dotenv to get current configurations
from dotenv import load_dotenv
load_dotenv(override=True)

import main
import db

async def main_run():
    MOCK_MODE = os.getenv("MOCK_MODE", "false").lower() == "true"
    print(f"Running pipeline for 'Operationalizing the EU AI Act Risk Mitigation Strategy' (Mock Mode: {MOCK_MODE})")

    # Automatically feed inputs to the interactive prompts:
    # 1. Select the first topic in the list (the filtered EU AI Act topic)
    # 2. Transition SME draft to the Content Editor agent
    # 3. Transition Editor draft to the Publisher agent
    inputs = [
        "1", 
        "Pass content to editor agent", 
        "Pass content to publisher agent"
    ]
    
    def mock_input(*args, **kwargs):
        if inputs:
            val = inputs.pop(0)
            print(f"[Auto-Input] {val}")
            return val
        return ""

    # Load from discovered topics cache
    cache_file = "discovered_topics.txt"
    if not os.path.exists(cache_file):
        print(f"Error: Cache file '{cache_file}' not found.")
        return
        
    with open(cache_file, "r") as f:
        pm_output = f.read()
    
    all_topics = main.parse_topics(pm_output)
    eu_ai_act_topic = [t for t in all_topics if "EU AI Act" in t["title"]]
    
    if not eu_ai_act_topic:
        print("Error: Could not find 'EU AI Act' topic in discovered_topics.txt")
        return
        
    print(f"Found target topic: '{eu_ai_act_topic[0]['title']}'")

    # Patch stdin and input to simulate interactive execution for only the targeted topic
    with patch('sys.stdin.isatty', return_value=True), \
         patch('builtins.input', side_effect=mock_input), \
         patch('main.parse_topics', return_value=eu_ai_act_topic):
         
         await main.run_pipeline()

if __name__ == "__main__":
    db.init_db()
    asyncio.run(main_run())
