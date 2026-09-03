import json
import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
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

SECONDS_BETWEEN_REQUESTS = 0.7
MAX_RETRIES_ON_RATE_LIMIT = 3

with open("chunks.json", "r", encoding="utf-8") as f:
    chunks = [json.loads(line) for line in f if line.strip()]

print(f"Loaded {len(chunks)} chunks")

failed_chunks = []

for i, chunk in enumerate(chunks, start=1):
    text = chunk["chunk_text"]
    chunk_id = chunk.get("chunk_id")

    for attempt in range(1, MAX_RETRIES_ON_RATE_LIMIT + 1):
        try:
            result = gemini.models.embed_content(
                model="gemini-embedding-001",
                contents=text,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT",  # matches RETRIEVAL_QUERY used at search time
                    output_dimensionality=1024,
                ),
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
                **chunk.get("metadata", {}),
            }

            row = {
                "chunk_id": chunk_id,       # real column now, used as the upsert key
                "content": text,
                "metadata": metadata,
                "embedding": embedding,
            }

            # upsert instead of insert: re-running this script updates
            # existing rows by chunk_id instead of creating duplicates
            supabase.table("documents").upsert(row, on_conflict="chunk_id").execute()

            print(f"[{i}/{len(chunks)}] upserted: {chunk_id}")
            break

        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                wait_time = 45
                print(f"[{i}/{len(chunks)}] rate limited (attempt {attempt}/{MAX_RETRIES_ON_RATE_LIMIT}), waiting {wait_time}s...")
                time.sleep(wait_time)
                continue
            else:
                print(f"[{i}/{len(chunks)}] FAILED: {chunk_id} - {error_str}")
                failed_chunks.append(chunk_id)
                break
    else:
        print(f"[{i}/{len(chunks)}] FAILED after {MAX_RETRIES_ON_RATE_LIMIT} retries: {chunk_id}")
        failed_chunks.append(chunk_id)

    time.sleep(SECONDS_BETWEEN_REQUESTS)

print()
print(f"DONE - {len(chunks) - len(failed_chunks)}/{len(chunks)} chunks embedded and stored in Supabase")
if failed_chunks:
    print(f"FAILED chunks ({len(failed_chunks)}): {failed_chunks}")
    print("Safe to just re-run this script - upsert means it will only retry these, not duplicate the successful ones.")
