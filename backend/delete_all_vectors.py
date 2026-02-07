"""
Delete all vectors from Pinecone index to start fresh.
"""
import os
from dotenv import load_dotenv
from pinecone import Pinecone

# Load environment variables
load_dotenv()

# Initialize Pinecone
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index_name = os.getenv("PINECONE_INDEX_NAME")
index = pc.Index(index_name)

print("=" * 60)
print(f"🗑️  DELETE ALL VECTORS FROM: {index_name}")
print("=" * 60)

# Get current stats
stats = index.describe_index_stats()
print(f"\n📊 Current vector count: {stats.total_vector_count}")

if stats.total_vector_count == 0:
    print("\n✅ Index already empty!")
else:
    confirm = input(f"\n⚠️  Delete ALL {stats.total_vector_count} vectors? Type 'DELETE ALL' to confirm: ")
    
    if confirm == "DELETE ALL":
        print("\n🗑️  Deleting all vectors...")
        index.delete(delete_all=True)
        print("✅ All vectors deleted!")
        
        # Verify
        stats = index.describe_index_stats()
        print(f"📊 New vector count: {stats.total_vector_count}")
    else:
        print("\n❌ Deletion cancelled")

print("\n" + "=" * 60)
print("Next steps:")
print("1. Re-upload your documents via the frontend")
print("2. Query: 'Tell me about OmniDimension'")
print("3. Expected score: 0.55-0.75 (not 0.28!)")
print("=" * 60)
