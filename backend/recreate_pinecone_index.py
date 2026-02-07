"""
Script to recreate Pinecone index with new dimensions for local embeddings.

WARNING: This will DELETE the old index and all documents!
Run this once when switching from OpenAI (1536) to local embeddings (384).
"""

import os
from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec
import time

# Load environment
load_dotenv()

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
OLD_INDEX_NAME = "voice-agent-kb"  # 1536 dimensions
NEW_INDEX_NAME = "voice-agent-kb-local"  # 384 dimensions
ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT", "us-east-1")
NEW_DIMENSION = 384  # all-MiniLM-L6-v2 dimensions

def main():
    print(f"Connecting to Pinecone...")
    pc = Pinecone(api_key=PINECONE_API_KEY)
    
    # List existing indexes
    existing_indexes = [idx.name for idx in pc.list_indexes()]
    print(f"\nExisting indexes: {existing_indexes}")
    
    # Delete old index if exists
    if OLD_INDEX_NAME in existing_indexes:
        print(f"\n⚠️  WARNING: About to DELETE index '{OLD_INDEX_NAME}' with ALL documents!")
        confirm = input("Type 'DELETE' to confirm: ")
        if confirm != "DELETE":
            print("Aborted.")
            return
        
        print(f"Deleting old index: {OLD_INDEX_NAME}")
        pc.delete_index(OLD_INDEX_NAME)
        print(f"✅ Deleted old index")
        time.sleep(5)  # Wait for deletion to complete
    
    # Create new index with 384 dimensions
    if NEW_INDEX_NAME in existing_indexes:
        print(f"\n⚠️  Index '{NEW_INDEX_NAME}' already exists!")
        confirm = input("Delete and recreate? Type 'YES': ")
        if confirm == "YES":
            pc.delete_index(NEW_INDEX_NAME)
            print(f"Deleted existing index")
            time.sleep(5)
        else:
            print("Keeping existing index")
            return
    
    print(f"\nCreating new index: {NEW_INDEX_NAME}")
    print(f"  Dimension: {NEW_DIMENSION}")
    print(f"  Metric: cosine")
    print(f"  Environment: {ENVIRONMENT}")
    
    pc.create_index(
        name=NEW_INDEX_NAME,
        dimension=NEW_DIMENSION,
        metric="cosine",
        spec=ServerlessSpec(
            cloud="aws",
            region=ENVIRONMENT
        )
    )
    
    # Wait for index to be ready
    print("Waiting for index to be ready...")
    while not pc.describe_index(NEW_INDEX_NAME).status['ready']:
        time.sleep(1)
    
    print(f"\n✅ Successfully created index: {NEW_INDEX_NAME}")
    print(f"\n📋 Next steps:")
    print(f"1. Update .env: PINECONE_INDEX_NAME={NEW_INDEX_NAME}")
    print(f"2. Update .env: PINECONE_DIMENSION={NEW_DIMENSION}")
    print(f"3. Update .env: RAG_USE_LOCAL_EMBEDDINGS=true")
    print(f"4. Restart backend server")
    print(f"5. Re-upload all documents via /api/documents/upload")
    print(f"\n🚀 You'll now have 10x faster embeddings with local model!")

if __name__ == "__main__":
    main()
