# Implementation Plan: Wix Blog Integration

## Plan Details

### Step 1: Codebase Exploration
- **Objective**: Find the existing implementation of the Publisher agent, database operations, and standalone scripts.
- **Task**: Inspect `main.py`, `db.py`, `publish_jira_backlog.py`, `publish_whitepaper.py`, and `test_pipeline.py` using search/view tools.
- **Verification**: Locate exact lines of code where the Publisher agent is defined, how it duplicates template pages (currently), and where the database writes occur.

### Step 2: Wix API & Member ID Exploration
- **Objective**: Determine how to authenticate and query site members and draft posts on Wix.
- **Task**: Inspect how the environment loads Wix API credentials (from `.env` or elsewhere) and how Wix tool calls or HTTP client calls are handled.
- **Verification**: Document the API call patterns and Ricos conversion rules.

### Step 3: Implement Live Publishing & Deduplication
- **Objective**: Implement draft post creation, dynamic member ID query, Ricos conversion, title duplicate checks, and SQLite database updates.
- **Task**: Modify `main.py`, `db.py`, `publish_jira_backlog.py`, and `publish_whitepaper.py` through teamwork subagents.
- **Verification**: Reviewer subagent confirms the code modifications meet all Kordic style rules and structural templates.

### Step 4: Test Suite Updates & Run
- **Objective**: Add test coverage to `test_pipeline.py` and run the entire suite.
- **Task**: Update tests to mock/verify Wix Blog API query and create draft-posts logic, and SQLite updates.
- **Verification**: Run `python3 -m unittest test_pipeline.py` and get 100% passing results.

### Step 5: Manual End-to-End Run
- **Objective**: Execute the pipeline in live mode.
- **Task**: Run `python3 main.py` using live mode to select a topic, run it, and verify that the draft post was created successfully.
- **Verification**: Inspect SQLite DB for the new post status and ID, and verify the Ricos format in the Wix Dashboard or via API query.

### Step 6: Integrity Audit Check
- **Objective**: Run a forensic audit to confirm implementation authenticity.
- **Task**: Run the teamwork_preview_auditor agent to verify code compliance.
- **Verification**: Clean verdict from the Forensic Auditor.
