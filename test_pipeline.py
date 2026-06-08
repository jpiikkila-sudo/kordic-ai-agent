import unittest
import os
import re
import sqlite3
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
        db.mark_published("Test Article Title", "wix-item-12345", status="draft")
        
        # Verify retrieved articles
        articles = db.get_all_articles()
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["title"], "Test Article Title")
        self.assertEqual(articles[0]["wix_item_id"], "wix-item-12345")
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

if __name__ == "__main__":
    unittest.main()
