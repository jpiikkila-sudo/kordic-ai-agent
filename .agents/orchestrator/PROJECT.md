# Project: Wix Blog Publishing Integration

## Architecture
The Knowledge Hub Content Engine runs a pipeline where:
1. Topics are discovered or prioritized.
2. The Technical SME agent drafts technical content (Solution Guides, How-tos, Whitepapers).
3. The Content Editor agent styles the content according to the Kordic Brand Style Guide.
4. The Publisher agent retrieves a member ID from the live Wix Blog API, performs a title duplication check against the live Wix Blog API, converts the formatted markdown into Ricos Rich Content JSON format, and creates a draft blog post on Wix via the REST endpoint.
5. SQLite Database `kordic.db` is updated with the returned Wix draft post ID, file path, and status ('draft').

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Exploration | Analyze current codebase, database schemas, Wix API integration patterns, and how Wix APIs are currently called. | None | DONE |
| 2 | Implementation | Update `main.py`, standalone scripts, and `db.py` to fetch memberId, convert markdown to Ricos, query existing posts by title, skip duplicate posts, and store the draft post ID. | M1 | DONE |
| 3 | Testing | Update unit tests in `test_pipeline.py`, ensure all tests pass, and perform a manual end-to-end verification run on Wix. | M2 | DONE |
| 4 | Integrity Audit | Run a forensic audit to verify there are no integrity violations (cheating, hardcoding, etc.). | M3 | IN_PROGRESS (Auditor Conv ID: c5a5abfb-5775-4285-907d-d0b327da0c20) |

## Interface Contracts
- Wix Blog API:
  - GET `/members/v1/members?fieldsets=PUBLIC&paging.limit=1`
  - POST `/blog/v3/draft-posts/query` (with body query filters for titles)
  - POST `/blog/v3/draft-posts` (with JSON body including draftPost and publish: false)
- Ricos Rich Content format:
  - Wrapped nodes with types `PARAGRAPH`, `HEADING`, `LIST_ITEM`, `BULLETED_LIST`, `ORDERED_LIST`, `BLOCKQUOTE`. All text nodes must reside inside `PARAGRAPH` type nodes.

## Code Layout
- `main.py` - Coordinates the multi-agent execution pipeline.
- `db.py` - SQLite helper functions to update and query articles.
- `test_pipeline.py` - Unit testing suite.
- `publish_jira_backlog.py` - Standalone backlog publisher.
- `publish_whitepaper.py` - Standalone whitepaper publisher.
- `gemini.md` - System instructions / Brand rules.
