import unittest
from unittest.mock import patch, MagicMock
import os
import re
import sqlite3
import requests
import db
import main

class TestContentEngine(unittest.TestCase):
    
    def setUp(self):
        # Override DB_PATH to use a temporary test database
        self.original_db_path = db.DB_PATH
        db.DB_PATH = "test_kordic.db"
        # Ensure fresh start
        if os.path.exists(db.DB_PATH):
            os.remove(db.DB_PATH)
        db.init_db()

    def tearDown(self):
        # Clean up test database
        if os.path.exists(db.DB_PATH):
            os.remove(db.DB_PATH)
        # Restore DB_PATH
        db.DB_PATH = self.original_db_path

    def test_database_operations(self):
        # Test default is not duplicate
        self.assertFalse(db.is_duplicate("Test Article Title"))
        
        # Save an article
        row_id = db.save_article(
            title="Test Article Title",
            vertical="AI Adoption Trends",
            content="Some body content",
            category="How-to",
            reference_age=5
        )
        self.assertGreater(row_id, 0)
        
        # Test duplication detection
        self.assertTrue(db.is_duplicate("Test Article Title"))
        # Test case/whitespace resilience
        self.assertTrue(db.is_duplicate("  Test Article Title  "))
        
        # Try to save duplicate (should return -1)
        dup_row_id = db.save_article(
            title="Test Article Title",
            vertical="AI Adoption Trends",
            content="Some body content",
            category="How-to",
            reference_age=5
        )
        self.assertEqual(dup_row_id, -1)
        
        # Mark published
        db.mark_published("Test Article Title", "wix-item-12345", local_file_path="output_articles/How-to/test.md", status="draft")
        
        # Verify retrieved articles
        articles = db.get_all_articles()
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["title"], "Test Article Title")
        self.assertEqual(articles[0]["wix_item_id"], "wix-item-12345")
        self.assertEqual(articles[0]["local_file_path"], "output_articles/How-to/test.md")
        self.assertEqual(articles[0]["status"], "draft")

    def test_get_all_articles_sorting(self):
        # Insert articles with different categories and reference ages
        db.save_article("A", "V1", "C1", "Whitepaper", 10)
        db.save_article("B", "V2", "C2", "How-to", 4)
        db.save_article("C", "V3", "C3", "Whitepaper", 2)
        db.save_article("D", "V4", "C4", "How-to", 8)
        
        articles = db.get_all_articles()
        self.assertEqual(len(articles), 4)
        
        # Expected order (sorted by category ASC, reference_age ASC):
        # 1. How-to (ref_age 4)
        # 2. How-to (ref_age 8)
        # 3. Whitepaper (ref_age 2)
        # 4. Whitepaper (ref_age 10)
        self.assertEqual(articles[0]["title"], "B")
        self.assertEqual(articles[1]["title"], "D")
        self.assertEqual(articles[2]["title"], "C")
        self.assertEqual(articles[3]["title"], "A")

    def test_parse_topics(self):
        sample_output = """
- Title: AI Governance Framework
  Vertical: AI Governance
  Category: Guide
  Reference Age: 12
- Title: Automating PRs
  Vertical: Atlassian system of work and Rovo agents
  Category: How-to
  Reference Age: 3
        """
        topics = main.parse_topics(sample_output)
        self.assertEqual(len(topics), 2)
        
        self.assertEqual(topics[0]["title"], "AI Governance Framework")
        self.assertEqual(topics[0]["vertical"], "AI Governance")
        self.assertEqual(topics[0]["category"], "Guide")
        self.assertEqual(topics[0]["reference_age"], 12)
        
        self.assertEqual(topics[1]["title"], "Automating PRs")
        self.assertEqual(topics[1]["vertical"], "Atlassian system of work and Rovo agents")
        self.assertEqual(topics[1]["category"], "How-to")
        self.assertEqual(topics[1]["reference_age"], 3)

    def test_parse_topics_fallback(self):
        # If output does not match pattern
        sample_bad_output = "No matches here"
        topics = main.parse_topics(sample_bad_output)
        self.assertGreater(len(topics), 0)
        self.assertIn("title", topics[0])

    def test_load_system_instructions(self):
        pm_instructions = main.load_system_instructions("Product Marketer")
        self.assertIn("Product Marketer", pm_instructions)
        self.assertIn("Agent", pm_instructions)
        
        sme_instructions = main.load_system_instructions("Technical Subject Matter Expert")
        self.assertIn("Technical Subject Matter Expert", sme_instructions)

        editor_instructions = main.load_system_instructions("Content Editor")
        self.assertIn("Content Editor", editor_instructions)
        self.assertIn("Blacklist", editor_instructions)

        with self.assertRaises(ValueError):
            main.load_system_instructions("Non Existent Agent")

    @patch('requests.post')
    @patch('main.MOCK_MODE', False)
    @patch.dict(os.environ, {"WIX_API_KEY": "fake-key"})
    def test_is_wix_duplicate_true(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "draftPosts": [{"id": "post-123", "title": "Test Title"}]
        }
        mock_post.return_value = mock_response

        res = main.is_wix_duplicate("Test Title")
        self.assertTrue(res)
        
        # Verify the API was called with correct URL and headers
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://www.wixapis.com/blog/v3/draft-posts/query")
        self.assertEqual(kwargs["json"]["query"]["filter"]["title"], "Test Title")

    @patch('requests.post')
    @patch('main.MOCK_MODE', False)
    @patch.dict(os.environ, {"WIX_API_KEY": "fake-key"})
    def test_is_wix_duplicate_false(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "draftPosts": []
        }
        mock_post.return_value = mock_response

        res = main.is_wix_duplicate("Unique Title")
        self.assertFalse(res)
        mock_post.assert_called_once()

    @patch('requests.post')
    @patch('main.MOCK_MODE', False)
    @patch.dict(os.environ, {"WIX_API_KEY": ""})
    def test_is_wix_duplicate_no_api_key(self, mock_post):
        # Should return False immediately without calling API
        res = main.is_wix_duplicate("Any Title")
        self.assertFalse(res)
        mock_post.assert_not_called()

    @patch('requests.get')
    @patch('requests.post')
    def test_wix_api_endpoints_mock(self, mock_post, mock_get):
        # Test mock behavior for GET members and POST draft-posts directly
        # To verify the structure of responses and requests
        
        # 1. Mock GET members
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {
            "members": [{"id": "member-999", "profile": {"nickname": "Kordic Author"}}]
        }
        mock_get.return_value = mock_get_response
        
        # Call member endpoint
        headers = {"Authorization": "fake-key", "wix-site-id": "fake-site"}
        response = requests.get("https://www.wixapis.com/members/v1/members?fieldsets=PUBLIC&paging.limit=1", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["members"][0]["id"], "member-999")
        
        # 2. Mock POST draft-posts
        mock_post_response = MagicMock()
        mock_post_response.status_code = 200
        mock_post_response.json.return_value = {
            "draftPost": {
                "id": "draft-post-uuid-abc-123",
                "title": "New Post Title",
                "memberId": "member-999"
            }
        }
        mock_post.return_value = mock_post_response
        
        payload = {
            "draftPost": {
                "title": "New Post Title",
                "memberId": "member-999",
                "richContent": {
                    "nodes": [
                        {
                            "type": "PARAGRAPH",
                            "nodes": [{"type": "TEXT", "textData": {"text": "Hello world", "decorations": []}}],
                            "paragraphData": {}
                        }
                    ]
                }
            },
            "publish": False
        }
        
        post_response = requests.post("https://www.wixapis.com/blog/v3/draft-posts", headers=headers, json=payload)
        self.assertEqual(post_response.status_code, 200)
        self.assertEqual(post_response.json()["draftPost"]["id"], "draft-post-uuid-abc-123")

    @patch('sqlite3.connect')
    def test_db_connections_are_closed(self, mock_connect):
        # Setup mock connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        # Test init_db closes connection
        db.init_db()
        mock_conn.close.assert_called()
        mock_conn.close.reset_mock()
        
        # Test is_duplicate closes connection
        db.is_duplicate("Some Title")
        mock_conn.close.assert_called()
        mock_conn.close.reset_mock()
        
        # Test save_article closes connection
        db.save_article("Some Title", "Vertical", "Content", "Category", 5)
        mock_conn.close.assert_called()
        mock_conn.close.reset_mock()
        
        # Test mark_published closes connection
        db.mark_published("Some Title", "wix-id")
        mock_conn.close.assert_called()
        mock_conn.close.reset_mock()
        
        # Test get_all_articles closes connection
        db.get_all_articles()
        mock_conn.close.assert_called()

    @patch('publish_whitepaper.is_wix_duplicate')
    @patch('publish_whitepaper.Agent')
    def test_publish_whitepaper_duplicate_skips(self, mock_agent, mock_is_wix_duplicate):
        mock_is_wix_duplicate.return_value = True
        import publish_whitepaper
        import asyncio
        asyncio.run(publish_whitepaper.publish())
        mock_agent.assert_not_called()

    @patch('publish_jira_backlog.is_wix_duplicate')
    @patch('publish_jira_backlog.Agent')
    def test_publish_jira_backlog_duplicate_skips(self, mock_agent, mock_is_wix_duplicate):
        mock_is_wix_duplicate.return_value = True
        import publish_jira_backlog
        import asyncio
        asyncio.run(publish_jira_backlog.publish())
        mock_agent.assert_not_called()

    @patch('main.is_wix_duplicate')
    @patch('db.is_duplicate')
    @patch('builtins.input', return_value='')
    @patch('main.MOCK_MODE', True)
    def test_run_pipeline_polished_title_duplicate_skips(self, mock_input, mock_db_is_duplicate, mock_is_wix_duplicate):
        # Return False on the original titles, and return True only for the polished title "Auto-Groom Jira Backlogs"
        def side_effect(title):
            if title == "Auto-Groom Jira Backlogs":
                return True
            return False
        
        mock_db_is_duplicate.side_effect = side_effect
        mock_is_wix_duplicate.return_value = False
        
        import asyncio
        with patch('main.db.save_article') as mock_save:
            asyncio.run(main.run_pipeline())
            # For the topics list:
            # 1. "Auto-Groom Jira Backlogs" has db.is_duplicate(polished_title)=True -> skipped before save_article
            # 2. "Enterprise LLM Strategy" (polished to "Enterprise LLM Strategy") has db.is_duplicate = False -> saved!
            # 3. "Design Custom MCP Connectors" (polished to "Design Custom MCP Connectors") has db.is_duplicate = False -> saved!
            # So save_article must be called, but not for "Auto-Groom Jira Backlogs".
            for call in mock_save.call_args_list:
                self.assertNotEqual(call[0][0], "Auto-Groom Jira Backlogs")

    @patch('sys.stdin.isatty', return_value=True)
    @patch('main.is_wix_duplicate', return_value=False)
    @patch('db.is_duplicate', return_value=False)
    @patch('main.MOCK_MODE', True)
    def test_run_pipeline_bypass_editor(self, mock_is_duplicate, mock_is_wix_duplicate, mock_isatty):
        import asyncio
        
        # We need builtins.input to return "1" to select topic 1, then "Pass content to publisher agent" to bypass editor.
        inputs = ["1", "Pass content to publisher agent"]
        def input_side_effect(*args, **kwargs):
            if inputs:
                return inputs.pop(0)
            return ""
            
        with patch('builtins.input', side_effect=input_side_effect) as mock_input, \
             patch('main.db.save_article') as mock_save, \
             patch('main.get_mock_response', side_effect=main.get_mock_response) as mock_get_mock:
            
            asyncio.run(main.run_pipeline())
            
            # Verify the editor mock response was NOT queried, but the SME mock response was queried
            called_agents = [c[0][0] for c in mock_get_mock.call_args_list]
            self.assertIn("Technical Subject Matter Expert", called_agents)
            self.assertNotIn("Content Editor", called_agents)

if __name__ == "__main__":
    unittest.main()
