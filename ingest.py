import json
import os
from dotenv import load_dotenv
from google import genai
from supabase import create_client

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not GEMINI_API_KEY:
    raise ValueError("Missing GEMINI_API_KEY")

if not SUPABASE_URL:
    raise ValueError("Missing SUPABASE_URL")

if not SUPABASE_KEY:
    raise ValueError("Missing SUPABASE_KEY")

gemini = genai.Client(api_key=GEMINI_API_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

with open("chunks.json", "r", encoding="utf-8") as f:
    chunks = [
        json.loads(line)
        for line in f
        if line.strip()
    ]

print(f"Loaded {len(chunks)} chunks")

for i, chunk in enumerate(chunks, start=1):

    text = chunk["chunk_text"]

    result = gemini.models.embed_content(
        model="gemini-embedding-001",
        contents=text,
        config={
            "output_dimensionality": 1024
        }
    )

    embedding = result.embeddings[0].values

    metadata = {
        "chunk_id": chunk.get("chunk_id"),
        "parent_doc_id": chunk.get("parent_doc_id"),
        "doc_type": chunk.get("doc_type"),
        "major": chunk.get("major"),
        "semester": chunk.get("semester"),
        "language": chunk.get("language"),
        "source_type": chunk.get("source_type"),
        "confidence": chunk.get("confidence"),
        **chunk.get("metadata", {})
    }

    row = {
        "content": text,
        "metadata": metadata,
        "embedding": embedding
    }

    supabase.table("documents").insert(row).execute()

    print(f"[{i}/{len(chunks)}] inserted: {chunk.get('chunk_id')}")

print("DONE - all chunks embedded and stored in Supabase")