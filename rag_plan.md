# RAG Implementation Plan - Voice AI Pipeline

## ✅ ALL DECISIONS CONFIRMED - READY TO IMPLEMENT

### Final Confirmed Choices
1. **Use Case**: General knowledge base assistance ✅
2. **Upload Strategy**: Before conversation (optional step) ✅
3. **Vector Database**: Pinecone Free Starter Plan ✅
4. **Supported Formats**: **PDF, TXT, MD only** (no JSON) ✅
5. **Storage Strategy**: Direct to Pinecone + **minimal metadata in DB** ✅
6. **File Limits**: **1 file per user session** (replace on new upload) ✅
7. **Processing**: Synchronous with **step-by-step progress UI** ✅
8. **Chunking**: **Configurable BEFORE upload** (not retroactive) ✅
9. **Fallback**: Say "I don't have that information" ✅
10. **API Key**: Provided ✅
11. **Cost**: Not a concern (assignment) ✅

---

## Overview
**Goal**: Add document-based knowledge retrieval to voice agent for general knowledge assistance.

**Approach**: Zero-latency parallel embedding RAG with optional document upload before conversation starts.

---

## Your Decisions Summary

### ✅ Confirmed Choices
1. **Use Case**: General knowledge base assistance (flexible domain)
2. **Upload Strategy**: Option A - Before conversation (optional step)
3. **Vector Database**: Pinecone Free Starter Plan ($0/month)
4. **Supported Formats**: PDF, TXT, MD, JSON
5. **Storage Strategy**: Direct to Pinecone only (no database storage of documents)
6. **File Limits**: Max 10MB per file, 1 file at a time
7. **Processing**: Synchronous (block until indexed - user waits before starting conversation)
8. **Chunking**: Configurable via UI (user controls chunk size & overlap)
9. **Fallback**: Say "I don't have that information" when no context found

---

## Architecture

```
User uploads document (optional)
     ↓
Frontend validates (10MB, allowed types)
     ↓
Send to backend /api/documents/upload
     ↓
[BLOCKING PROCESSING - User waits]
  ├─ Extract text (PDF → text, JSON → string)
  ├─ Chunk with user-defined size/overlap
  ├─ Generate embeddings (OpenAI)
  └─ Upload to Pinecone with metadata
     ↓
Return success → Enable "Start Conversation" button
     ↓
User starts voice conversation
     ↓
RAG retrieval parallel with silence debounce
     ↓
If relevant chunks found: Use context
If not: Say "I don't have that information"
```

---

## Critical Questions I Need Answered

### 1. **Pinecone Free Plan Limits**
Pinecone Free (Starter) plan gives:
- **100k vectors** (embeddings)
- **1 index** (one knowledge base)
- **1 pod** (shared compute)

**Question**: With these limits, if chunk size = 500 tokens:
- 1 file (10MB) = ~13,000 words = ~26 chunks
- User can upload ~3,800 files before hitting 100k vector limit

**But you said "max 1 file"** - do you mean:
- **A) Only 1 file can be uploaded per user session** (delete old, upload new)?
- **B) Only 1 file at a time** (but multiple files can exist, up to 100k vectors)?
- **C) Only 1 file total for the entire application** (all users share same knowledge base)?

**Recommendation**: Go with **Option A** - one file per session, user can replace it. Simple, fits MVP.

---

### 2. **Document Persistence**
You said "don't store document, directly to Pinecone" - but questions:

**Scenario**: User uploads document, closes browser, comes back tomorrow.

**Question A**: Should previously uploaded document still be indexed?
- If YES → Need to track "which document is currently indexed" somewhere (minimal DB entry)
- If NO → Delete all vectors from Pinecone when session ends

**Question B**: Can user see what's currently indexed?
- If YES → Need to store at least filename + upload timestamp
- If NO → User has no visibility into knowledge base state

**Recommendation**: Store **minimal metadata only** in database:
```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY,
    session_id UUID,  -- Link to voice session
    filename TEXT,
    status TEXT,  -- 'indexing', 'ready', 'failed'
    chunk_count INTEGER,
    uploaded_at TIMESTAMP
);
```
This is <1KB per file, purely for UI display ("hours_policy.pdf - 23 chunks - Ready").

**Do you accept this minimal storage?** Or truly zero database entries?

---

### 3. **Chunk Configuration via UI**
You want chunk size/overlap configurable in UI. Current question:

**Question**: When user changes chunk settings, what happens to already-indexed document?
- **A) Auto re-index** with new settings (takes 10-30 seconds, blocks conversation)
- **B) Require manual re-upload** of document
- **C) Settings only apply to next upload** (current document unchanged)

**Recommendation**: **Option C** - settings apply to next upload only. Avoids complexity.

---

### 4. **Synchronous Processing UX**
You want sync processing (user waits). Timing breakdown:

For 10MB PDF (~13,000 words):
1. PDF extraction: 2-5 seconds
2. Chunking: <1 second
3. Embedding generation: 15-20 seconds (OpenAI API)
4. Pinecone upload: 2-3 seconds

**Total wait time: 20-30 seconds**

**Question**: What should UI show during this wait?
- **A) Progress bar** with steps ("Extracting text... 30%" → "Generating embeddings... 60%")
- **B) Simple spinner** ("Processing document...")
- **C) Step-by-step status** ("✓ Extracted 13,245 words" → "⏳ Generating embeddings...")

**Recommendation**: **Option C** - gives user confidence processing is working, not stuck.

---

### 5. **Multi-file Support (Future-proofing)**
You said "max 1 file" but also "max no of file 1" - I need clarity:

**Question**: Should architecture support multiple files even if MVP limits to 1?
- **A) Hard-code single file** (simpler MVP, requires refactor for multi-file later)
- **B) Build for multiple files** but UI enforces 1 file limit (future-proof, slightly more code now)

**Recommendation**: **Option B** - backend accepts array of documents, frontend enforces 1 file. Easy to lift limit later.

---

### 6. **Document Replacement Flow**
User uploads `policy_v1.pdf`, then later uploads `policy_v2.pdf`.

**Question**: What happens to old document?
- **A) Auto-delete from Pinecone** (remove old vectors, index new ones)
- **B) Keep both** (agent references both documents)
- **C) Prompt user** ("Replace existing document?")

**Recommendation**: **Option A** - auto-replace. User expects "upload new file" to use new file only.

---

### 7. **PDF Parsing Strategy**
PDFs can be complex (tables, images, multi-column layouts).

**Question**: Which PDF library should we use?
- **A) PyPDF2** (simple, fast, text-only, free)
- **B) pdfplumber** (handles tables, better layout, free)
- **C) pymupdf (fitz)** (fastest, best quality, free)

**Recommendation**: **Option C (pymupdf)** - best quality text extraction, 3x faster than PyPDF2.

---

### 8. **JSON File Handling**
You want to support JSON - but JSON structure varies widely.

**Question**: How should we extract text from JSON?
- **A) Stringify entire JSON** (loses structure but simple)
- **B) Extract specific fields** (requires user to specify keys like "content", "text")
- **C) Smart extraction** (recursively find all string values, concatenate)

**Recommendation**: **Option C** - concatenate all string values with field names as context.

Example JSON:
```json
{
  "title": "Refund Policy",
  "sections": [
    {"heading": "Returns", "content": "30-day return window"}
  ]
}
```

Extracted text:
```
Title: Refund Policy
Heading: Returns
Content: 30-day return window
```

**Do you accept this approach?**

---

### 9. **Pinecone Index Setup**
Pinecone requires creating an index before use.

**Question**: Should backend auto-create index on first upload or require manual setup?
- **A) Auto-create** on first document upload (convenient, may fail if wrong config)
- **B) Manual setup** via admin script (one-time, more control)
- **C) Check at startup**, create if missing (best of both)

**Recommendation**: **Option C** - check on app startup, create if needed.

Index config:
- **Name**: `voice-agent-kb`
- **Dimensions**: 1536 (OpenAI text-embedding-3-small)
- **Metric**: Cosine similarity
- **Pod type**: Starter (free tier)

---

### 10. **Chunking Strategy for Different File Types**

**Question**: Should chunking differ by file type?

| File Type | Current Plan | Alternative |
|-----------|--------------|-------------|
| **TXT/MD** | Token-based (500 tokens) | ✅ Keep as-is |
| **PDF** | Token-based (500 tokens) | Could preserve page boundaries |
| **JSON** | Token-based (500 tokens) | Could chunk by top-level keys |

**Recommendation**: **Keep uniform** - all files use same token-based chunking. Simpler for MVP.

**Do you agree or want file-specific strategies?**

---

## Technical Clarifications Needed

### 11. **Embedding Model Choice**
OpenAI offers multiple embedding models:

| Model | Dimensions | Cost | Latency |
|-------|-----------|------|---------|
| `text-embedding-3-small` | 1536 | $0.02/1M tokens | 100ms |
| `text-embedding-3-large` | 3072 | $0.13/1M tokens | 120ms |
| `text-embedding-ada-002` (legacy) | 1536 | $0.10/1M tokens | 150ms |

**Question**: Use `text-embedding-3-small` (cheapest, fast)?

**Recommendation**: YES - 5x cheaper than ada-002, same quality for general knowledge.

---

### 12. **Retrieval Parameters**

**Question**: Default retrieval settings?
- **Top K**: How many chunks to retrieve? (Recommend: 3)
- **Similarity threshold**: Minimum score to include? (Recommend: 0.7)
- **Reranking**: Should we re-rank results? (Recommend: No for MVP)

**Current plan**: Retrieve top 3 chunks with score >0.7, no reranking.

**Do you want these configurable in UI or hard-coded?**

---

### 13. **Cost Estimation**

For your setup:
- **Indexing**: 10MB file (13k words) = $0.0013 per upload
- **Querying**: $0.00002 per query
- **Pinecone**: $0/month (free tier)

**Per hour** (240 turns):
- RAG queries: 240 × $0.00002 = $0.0048
- LLM context (1500 extra tokens/turn): 240 × $0.0015 = $0.36

**New hourly cost**: $4.00 → $4.36 (9% increase)

**Question**: Is 9% cost increase acceptable?

---

## UI Changes Required

### New Upload Section (Before Conversation)

**Location**: Add to existing main page, above "Start Conversation" button.

```
┌───────────────────────────────────────────┐
│  Knowledge Base (Optional)                │
├───────────────────────────────────────────┤
│  📄 No document uploaded                  │
│                                           │
│  [📤 Upload Document]                     │
│                                           │
│  Supported: PDF, TXT, MD, JSON (max 10MB)│
└───────────────────────────────────────────┘

[🎤 Start Conversation]
```

**After upload starts**:
```
┌───────────────────────────────────────────┐
│  Knowledge Base                           │
├───────────────────────────────────────────┤
│  📄 policy_document.pdf                   │
│  ⏳ Processing...                         │
│                                           │
│  ✓ Extracted 13,245 words                │
│  ⏳ Generating embeddings (60%)           │
│  • Uploading to knowledge base...        │
│                                           │
│  [Cancel]                                 │
└───────────────────────────────────────────┘

[🎤 Start Conversation] ← Disabled until complete
```

**After upload complete**:
```
┌───────────────────────────────────────────┐
│  Knowledge Base                           │
├───────────────────────────────────────────┤
│  ✅ policy_document.pdf                   │
│  23 chunks • Indexed 2 minutes ago        │
│                                           │
│  [🔄 Replace Document]  [🗑️ Delete]      │
└───────────────────────────────────────────┘

[🎤 Start Conversation] ← Now enabled
```

**Question**: Is this UI flow acceptable?

---

### Settings Panel Addition

Add to existing settings UI:

```
┌───────────────────────────────────────────┐
│  RAG Settings                             │
├───────────────────────────────────────────┤
│  Chunk Size: [500] tokens                 │
│  Chunk Overlap: [50] tokens               │
│                                           │
│  Top K Results: [3]                       │
│  Min Similarity: [0.70]                   │
│                                           │
│  ⚠️ Changes apply to next upload          │
└───────────────────────────────────────────┘
```

**Question**: Do you want all 4 settings exposed or just chunk size/overlap?

---

## File Structure (New Modules)

```
backend/
  app/
    rag/                          ← New directory
      __init__.py
      vector_store.py            ← Pinecone abstraction
      document_processor.py      ← Chunking + embedding
      retriever.py               ← Query handling
      file_parsers.py            ← PDF/JSON/TXT extraction
    
    api/                          ← New directory
      __init__.py
      documents.py               ← Upload endpoint
    
    config.py                     ← Add Pinecone env vars
    
  requirements.txt               ← Add dependencies
```

**Dependencies to add**:
```
pinecone-client==3.0.3
pymupdf==1.23.8           # PDF parsing
tiktoken==0.5.2           # Token counting
python-multipart==0.0.6   # File uploads
```

---

## Implementation Order

### Day 1: Setup & File Parsing
1. Add Pinecone API key to `.env`
2. Create index in Pinecone (manual or auto)
3. Build file parsers (PDF, TXT, MD, JSON)
4. Test text extraction locally

### Day 2: Document Processing
1. Build chunking logic (configurable size/overlap)
2. Integrate OpenAI embeddings
3. Upload to Pinecone with metadata
4. Test end-to-end indexing

### Day 3: Backend API
1. Create `/api/documents/upload` endpoint
2. Add WebSocket status messages
3. Implement replace/delete logic
4. Test with 10MB file

### Day 4: RAG Retrieval
1. Build retriever (query embedding + search)
2. Integrate into `TurnController` (parallel execution)
3. Implement timeout + fallback
4. Test retrieval accuracy

### Day 5: Frontend UI
1. Add upload section to main page
2. Progress tracking during processing
3. Display indexed document status
4. Wire up settings panel

### Day 6: Integration Testing
1. Test full flow (upload → conversation → retrieval)
2. Test interruption during SPECULATIVE state
3. Test "no context found" fallback
4. Measure latency (must be <400ms)

### Day 7: Polish & Edge Cases
1. Error handling (corrupt PDF, timeout)
2. File size validation
3. Source citation in responses
4. Telemetry for RAG metrics

---

## Questions You Must Answer Before I Start Coding

### Critical (Must Answer):
1. **Max files**: 1 file per session (replace on new upload)? Or keep multiple?
2. **Metadata storage**: Accept minimal DB entry (filename, status) or truly zero storage?
3. **Chunk config**: Settings apply only to next upload (not retroactive)?
4. **Progress UI**: Show step-by-step status or simple spinner?
5. **JSON parsing**: Auto-extract all string values acceptable?

### Important (Should Answer):
6. **Pinecone index**: Auto-create on startup or manual setup?
7. **Retrieval config**: Hard-code top K=3, threshold=0.7, or UI-configurable?
8. **Cost increase**: 9% hourly cost increase ($4 → $4.36) acceptable?

### Optional (Can Decide Later):
9. **Multi-file architecture**: Build extensible even if MVP limits to 1 file?
10. **File type strategies**: Uniform chunking or file-specific?

---

## Risks & Open Questions

### Risk 1: Pinecone Free Tier Stability
**Concern**: Free tier may have rate limits or downtime.

**Question**: Do you have a Pinecone account already? Can you verify free tier works?

**Mitigation**: Test with sample upload before full implementation.

---

### Risk 2: PDF Extraction Quality
**Concern**: Complex PDFs (scanned images, tables) may extract poorly.

**Question**: Do you have sample PDFs to test extraction quality?

**Mitigation**: Start with pymupdf, fall back to OCR (pytesseract) if text extraction fails (not MVP scope).

---

### Risk 3: Synchronous Processing Blocks UI
**Concern**: 20-30 second wait may feel too long.

**Question**: Should we add "Skip and start conversation" button during processing?

**Mitigation**: Show detailed progress so user knows it's working.

---

### Risk 4: Single File Limitation
**Concern**: Users may want multiple documents (company policy + product docs).

**Question**: Is 1 file truly enough for "general knowledge assistance"?

**Recommendation**: Consider 3-5 files even for MVP - not much more complex.

---

## Next Steps

### What I Need From You:
1. **Answer all Critical questions** (5 questions above)
2. **Confirm Pinecone account access** (API key ready?)
3. **Provide sample files** (1 PDF, 1 JSON to test parsing)
4. **Approve cost increase** (9% more per hour)

### What I'll Deliver After Your Answers:
1. ✅ Complete implementation code (all 7 modules)
2. ✅ Database migration (minimal metadata table)
3. ✅ Environment variables setup
4. ✅ Frontend components (upload UI + status)
5. ✅ Test cases (unit + integration)
6. ✅ Deployment guide (Pinecone setup)

---

## Summary: What Makes This "Simple MVP"

### ✅ Simplified Decisions:
- No database storage (direct to Pinecone) ← **Still need metadata answer**
- No Redis cache (in-memory only)
- No PDF OCR (text PDFs only)
- No multi-user permissions (everyone sees same docs)
- No reranking or query expansion
- Synchronous processing (user waits)

### ⚠️ Not Simple Yet (Need Answers):
- Max files: 1 or multiple?
- Metadata: Zero DB or minimal entries?
- Progress UI: Spinner or detailed?
- Chunk config: Retroactive or future-only?

**Once you answer these 4 critical questions, we have true simplicity and I can start implementation.**

---

## Ready to Proceed?

**Reply with**:
1. Answers to Critical questions (1-5)
2. Confirmation you have Pinecone API key
3. Any other constraints I should know

Then I'll start building! 🚀
