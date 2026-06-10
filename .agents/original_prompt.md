## 2026-06-09T17:33:51Z

Implement and integrate the live Wix Blog publishing functionality into the automated multi-agent Knowledge Hub Content Engine, replacing the template page duplication method. The pipeline must fully run end-to-end, check for duplicates against the live Wix Blog API, and create draft blog posts formatted in Ricos Rich Content format.

Working directory: /Users/jessicapiikkila/Documents/kordic-ai-agent
Integrity mode: development

## Requirements

### R1. End-to-End Wix Blog Publisher Agent
- Update the `Publisher` agent in `main.py` (and standalone scripts `publish_jira_backlog.py` and `publish_whitepaper.py`) to publish content items as draft posts using the Wix Blog API (`POST https://www.wixapis.com/blog/v3/draft-posts` with `"publish": false`).
- The agent must dynamically retrieve a valid `memberId` to assign as the post's owner by querying site members using `GET https://www.wixapis.com/members/v1/members?fieldsets=PUBLIC&paging.limit=1`.
- The agent must convert the polished markdown articles into Wix's Ricos Rich Content format (valid nesting of PARAGRAPH, HEADING, LIST_ITEM, BLOCKQUOTE, etc.).

### R2. Live Wix Blog Duplication Check
- Add functionality to query the live Wix Blog API (`POST https://www.wixapis.com/blog/v3/draft-posts/query`) to search for existing draft posts with the same title before generating/publishing.
- Skip processing or publishing any article that already exists on the Wix site.

### R3. Content Structure and Formatting compliance
- Ensure the Technical SME and Content Editor agents format and design the blog post content to meet the Kordic Brand Style Guide (titles under 5 words, no blacklisted jargon) and the specific structural templates (e.g. How-tos, Whitepapers, Solution Guides).

### R4. Database Updates
- Update the local SQLite database (`kordic.db`) with the created Wix draft post ID, local file path, and status ('draft').

## Verification Plan

### Automated Tests
- Run `python3 -m unittest test_pipeline.py` to verify all database operations, parsing, and pipeline flow test cases pass.
- Update `test_pipeline.py` to cover the new live duplication checking logic and blog post creation.

### Manual Verification
- Run `python3 main.py` in live mode, selecting a discovered topic to generate and publish.
- Check the SQLite database `articles` table to ensure the `wix_item_id` matches the returned Wix draft post ID and status is set to `'draft'`.
- Verify on the Wix Dashboard under Blog > Drafts that the post is created with correct headers, lists, and blockquotes formatted via Ricos.

## Acceptance Criteria

### API Integration & Formatting
- [ ] Successfully queries a site member to retrieve a valid `memberId` to owner-authorize the draft post.
- [ ] Creates draft blog posts on the live Wix site using the REST endpoint `https://www.wixapis.com/blog/v3/draft-posts` with `"publish": false`.
- [ ] Validates the Ricos JSON structure to ensure all text nodes are properly wrapped in PARAGRAPH nodes, preventing API parsing failures.
- [ ] Preserves formatting: headers (`HEADING`), lists (`BULLETED_LIST` or `ORDERED_LIST` with nested `LIST_ITEM` nodes), and blockquotes (`BLOCKQUOTE`).

### Deduplication
- [ ] Duplication check successfully queries the live Wix Blog API (`POST https://www.wixapis.com/blog/v3/draft-posts/query`) by title.
- [ ] Skips publishing when a match is found on the live Wix site.

### Compliance & Quality
- [ ] Titles of the generated blog posts are strictly under 5 words.
- [ ] No blacklisted AI jargon words (e.g., intersection, delve, leverage) or filler transitions appear in the published content.
- [ ] Successfully updates the SQLite database with the Wix draft post ID and marks the status as 'draft'.
