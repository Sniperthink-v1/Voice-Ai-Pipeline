"""
Quick script to check Pinecone index statistics and list all documents.
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

# Get index stats
stats = index.describe_index_stats()

print("=" * 60)
print(f"📊 PINECONE INDEX: {index_name}")
print("=" * 60)
print(f"\n🔢 Total vectors: {stats.total_vector_count}")
print(f"📐 Dimension: {stats.dimension}")
print(f"\n📁 Namespaces: {stats.namespaces}")

# Query a few random vectors to see what documents exist
print("\n" + "=" * 60)
print("📄 SAMPLE DOCUMENTS IN INDEX:")
print("=" * 60)

try:
    # Fetch a few vectors to see metadata
    # Note: We need to query with a dummy vector since Pinecone doesn't have a "list all" API
    dummy_vector = [0.0] * stats.dimension
    results = index.query(
        vector=dummy_vector,
        top_k=10,
        include_metadata=True
    )
    
    seen_docs = set()
    for match in results.matches:
        doc_id = match.metadata.get("document_id", "unknown")
        filename = match.metadata.get("filename", "unknown")
        session = match.metadata.get("session_id", "unknown")[:8]
        
        doc_key = f"{filename}|{doc_id}"
        if doc_key not in seen_docs:
            seen_docs.add(doc_key)
            print(f"\n📄 {filename}")
            print(f"   Document ID: {doc_id}")
            print(f"   Session: {session}")
            print(f"   Text preview: {match.metadata.get('text', '')[:100]}...")
    
    print(f"\n✅ Found {len(seen_docs)} unique documents in index")
    
except Exception as e:
    print(f"\n❌ Error querying index: {e}")

print("\n" + "=" * 60)
