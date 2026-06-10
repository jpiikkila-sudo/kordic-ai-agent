# Progress Tracking — 2026-06-09T17:55:50-05:00

Last visited: 2026-06-09T17:55:50-05:00

## Tasks
- [x] Investigate existing files (`db.py`, `main.py`, `publish_whitepaper.py`, `publish_jira_backlog.py`, `test_pipeline.py`) <!-- id: 0 -->
- [x] Fix db.py Unclosed Connections <!-- id: 1 -->
- [x] Fix main.py Polished Title Duplicate Bypass <!-- id: 2 -->
- [x] Fix publish_whitepaper.py Style and Content Defect <!-- id: 3 -->
- [x] Add Programmatic Duplication Checks to Standalone Scripts <!-- id: 4 -->
- [x] Fix em-dash in metadata report <!-- id: 5 -->
- [x] Update test_pipeline.py and Verify <!-- id: 6 -->

## Step-by-Step Plan
1. **Fix `db.py` unclosed connections**: Replace current sqlite3 connection usage with context managers and `try...finally` blocks to guarantee that connection closing is executed under all circumstances. (Done)
2. **Fix `main.py` duplicate bypass logic**:
   - Locate the Content Editor title polishing section.
   - Insert checks for `db.is_duplicate(polished_title)` and `is_wix_duplicate(polished_title)`.
   - Update `db.save_article` call to handle a `-1` return value, printing a skip message and executing `continue` to proceed to the next topic. (Done)
3. **Fix `publish_whitepaper.py` style and path**:
   - Change `title` to `"Enterprise LLM Strategy"`.
   - Point `md_path` to `/Users/jessicapiikkila/Documents/kordic-ai-agent/output_articles/Whitepaper/Enterprise_LLM_Strategy.md`. (Done)
4. **Add programmatic duplication check to `publish_whitepaper.py` and `publish_jira_backlog.py`**:
   - Define or import `is_wix_duplicate` and call it on `title`. Exit early if a duplicate is found on Wix. (Done)
5. **Fix em-dash in metadata report markdown**:
   - Edit the metadata report markdown file at line 18 to replace `—` with clean punctuation/parentheses. (Done)
6. **Update `test_pipeline.py`**:
   - Add tests checking connection context manager logic and the new duplicate bypass paths.
   - Verify everything passes via `python3 -m unittest test_pipeline.py`. (Done)
