import os
import re
import json
import sqlite3
import requests
from dotenv import load_dotenv

# Load env variables
env_path = "/Users/jessicapiikkila/Documents/kordic-ai-agent/.env"
load_dotenv(env_path, override=True)

WIX_API_KEY = os.getenv("WIX_API_KEY", "").strip()
WIX_SITE_ID = os.getenv("WIX_SITE_ID", "").strip()
DB_PATH = "kordic.db"

headers = {
    "Authorization": WIX_API_KEY,
    "wix-site-id": WIX_SITE_ID,
    "Content-Type": "application/json"
}

# Image file locations in current conversation's brain directory
images_to_upload = {
    "cover": {
        "local_path": "/Users/jessicapiikkila/.gemini/antigravity/brain/98bb3c8c8da15c3e7cb9a9f443f8613e/blog_cover_tiled_1781220723686.png",
        "fileName": "blog_cover_tiled_1781220723686.png"
    },
    "diagram": {
        "local_path": "/Users/jessicapiikkila/.gemini/antigravity/brain/98bb3c8c8da15c3e7cb9a9f443f8613e/compliance_diagram_1781220733533.png",
        "fileName": "compliance_diagram_1781220733533.png"
    },
    "incontent": {
        "local_path": "/Users/jessicapiikkila/.gemini/antigravity/brain/98bb3c8c8da15c3e7cb9a9f443f8613e/in_content_audit_1781220746697.png",
        "fileName": "in_content_audit_1781220746697.png"
    }
}

def upload_images():
    uploaded_assets = {}
    for key, img_info in images_to_upload.items():
        print(f"Uploading {key}: {img_info['fileName']}...")
        
        # Step 1: Generate Upload URL
        gen_url = "https://www.wixapis.com/site-media/v1/files/generate-upload-url"
        payload = {
            "mimeType": "image/png",
            "fileName": img_info["fileName"]
        }
        
        res = requests.post(gen_url, headers=headers, json=payload)
        if res.status_code != 200:
            print(f"  Failed to generate upload URL: {res.status_code} - {res.text}")
            continue
            
        upload_data = res.json()
        upload_url = upload_data.get("uploadUrl")
        if not upload_url:
            print("  Error: No uploadUrl found in response:", upload_data)
            continue
            
        print(f"  Got upload URL. Uploading file binary...")
        
        # Step 2: Upload File Binary via PUT
        with open(img_info["local_path"], "rb") as f:
            file_bytes = f.read()
            
        put_headers = {
            "Content-Type": "image/png"
        }
        
        upload_url_with_param = f"{upload_url}&filename={img_info['fileName']}" if "?" in upload_url else f"{upload_url}?filename={img_info['fileName']}"
        
        put_res = requests.put(upload_url_with_param, headers=put_headers, data=file_bytes)
        if put_res.status_code not in (200, 201):
            print(f"  Failed to upload file bytes: {put_res.status_code} - {put_res.text}")
            continue
            
        result_data = put_res.json()
        file_info = result_data.get("file", {})
        wix_url = file_info.get("url")
        wix_id = file_info.get("id")
        
        print(f"  SUCCESS! Wix URL: {wix_url} | Wix ID: {wix_id}")
        uploaded_assets[key] = {
            "url": wix_url,
            "id": wix_id
        }
    return uploaded_assets

def get_tag_ids(tag_labels):
    tag_ids = []
    # 1. Get existing tags
    tags_url = "https://www.wixapis.com/blog/v3/tags"
    res = requests.get(tags_url, headers=headers)
    existing_tags = {}
    if res.status_code == 200:
        for t in res.json().get("tags", []):
            existing_tags[t["label"].lower()] = t["id"]
            
    for label in tag_labels:
        label_lower = label.lower()
        if label_lower in existing_tags:
            tag_ids.append(existing_tags[label_lower])
            print(f"Tag '{label}' already exists with ID: {existing_tags[label_lower]}")
        else:
            print(f"Creating missing tag '{label}'...")
            create_url = "https://www.wixapis.com/blog/v3/tags"
            create_payload = {
                "label": label
            }
            create_res = requests.post(create_url, headers=headers, json=create_payload)
            if create_res.status_code in (200, 201):
                new_tag = create_res.json().get("tag", {})
                tag_ids.append(new_tag["id"])
                print(f"  SUCCESS! Created tag '{label}' with ID: {new_tag['id']}")
            else:
                print(f"  Failed to create tag '{label}': {create_res.status_code} - {create_res.text}")
    return tag_ids

def get_or_create_category(vertical_name):
    # 1. Get existing categories
    cat_url = "https://www.wixapis.com/blog/v3/categories"
    res = requests.get(cat_url, headers=headers)
    if res.status_code == 200:
        for c in res.json().get("categories", []):
            if c.get("title", "").strip().lower() == vertical_name.strip().lower():
                print(f"Category '{vertical_name}' already exists with ID: {c['id']}")
                return c["id"]
                
    # 2. Create if missing
    print(f"Creating category '{vertical_name}'...")
    create_payload = {
        "category": {
            "title": vertical_name,
            "label": vertical_name
        }
    }
    create_res = requests.post(cat_url, headers=headers, json=create_payload)
    if create_res.status_code in (200, 201):
        new_cat = create_res.json().get("category", {})
        print(f"  SUCCESS! Created category with ID: {new_cat['id']}")
        return new_cat["id"]
    else:
        print(f"  Failed to create category: {create_res.status_code} - {create_res.text}")
        return None

def publish_post(uploaded_images):
    md_path = "/Users/jessicapiikkila/Documents/kordic-ai-agent/output_articles/Whitepaper/Auditing_Autonomous_Multi-Agent_Systems_for_Compliance_and_Traceability.md"
    with open(md_path, "r") as f:
        content = f.read()
        
    # Replace the local image placeholders with uploaded wix static URLs
    wix_cover_url = uploaded_images["cover"]["url"]
    wix_diagram_url = uploaded_images["diagram"]["url"]
    wix_incontent_url = uploaded_images["incontent"]["url"]
    
    new_content = content
    new_content = new_content.replace("`blog_cover_tiled`", wix_cover_url)
    new_content = new_content.replace("compliance_diagram", wix_diagram_url)
    new_content = new_content.replace("in_content_audit", wix_incontent_url)
    
    # Save the updated markdown locally
    with open(md_path, "w") as f:
        f.write(new_content)
    print("Markdown file updated locally with Wix image URLs.")
    
    # Extract actual article body starting from title
    start_marker = "# The Black Box Mess: Auditing Multi-Agent Systems for Enterprise Compliance"
    start_idx = new_content.find(start_marker)
    if start_idx != -1:
        article_body = new_content[start_idx:]
    else:
        print("Warning: Start marker not found. Using full content.")
        article_body = new_content
        
    # Convert markdown to Ricos Document
    convert_url = "https://www.wixapis.com/ricos/v1/ricos-document/convert/to-ricos"
    payload = {
        "markdown": article_body,
        "options": {
            "plugins": ["IMAGE", "LINK", "TEXT_COLOR", "HEADING", "DIVIDER", "CODE_BLOCK"]
        }
    }
    
    print("Converting markdown to Ricos Document...")
    res = requests.post(convert_url, headers=headers, json=payload)
    if res.status_code != 200:
        print(f"Failed to convert markdown: {res.status_code} - {res.text}")
        return
        
    ricos_doc = res.json().get("document")
    print(f"Successfully converted. Number of nodes: {len(ricos_doc.get('nodes', []))}")
    
    # Wix member ID and category
    member_id = "6c8a9944-7378-45bd-a86d-6e1de87f278d"
    category_id = get_or_create_category("AI Governance")
    tag_labels = ["AI Auditing", "Multi-Agent Systems", "Compliance"]
    tag_ids = get_tag_ids(tag_labels)
    
    # Create draft post
    post_url = "https://www.wixapis.com/blog/v3/draft-posts"
    post_payload = {
        "draftPost": {
            "title": "The Black Box Mess: Auditing Multi-Agent Systems for Enterprise Compliance",
            "memberId": member_id,
            "categoryIds": [category_id] if category_id else [],
            "tagIds": tag_ids,
            "hashtags": tag_labels,
            "richContent": ricos_doc
        },
        "publish": False
    }
    
    print("Creating draft post on Wix Blog...")
    post_res = requests.post(post_url, headers=headers, json=post_payload)
    print("POST Status:", post_res.status_code)
    if post_res.status_code in (200, 201):
        draft_post = post_res.json().get("draftPost", {})
        draft_id = draft_post.get("id")
        wix_item_id = f"wix-item-{draft_id}"
        print(f"SUCCESS! Wix draft post created: {wix_item_id}")
        
        # Update local SQLite DB
        conn = sqlite3.connect(DB_PATH)
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO articles (title, vertical, content, category, reference_age, wix_item_id, local_file_path, status, published_at)
                    VALUES ('The Black Box Mess: Auditing Multi-Agent Systems for Enterprise Compliance', 'AI Governance', ?, 'Whitepaper', 11, ?, ?, 'draft', CURRENT_TIMESTAMP)
                """, (content, wix_item_id, md_path))
                print("Local SQLite database updated successfully.")
        finally:
            conn.close()
            
        print(f"\nDraft created successfully! You can see it in your Wix Blog Dashboard > Drafts at:")
        print(f"https://www.wix.com/dashboard/{WIX_SITE_ID}/blog/posts/drafts")
    else:
        print("Failed to create draft post:", post_res.text)

if __name__ == "__main__":
    uploaded = upload_images()
    if len(uploaded) == 3:
        publish_post(uploaded)
    else:
        print("Error: Not all 3 images were uploaded successfully. Aborting post creation.")
