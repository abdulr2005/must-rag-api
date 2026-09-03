# main.py
import os
import uvicorn
from rag_api import app   # pulls in the FastAPI instance you already have

if __name__ == "__main__":
    # Railway provides the port number in the $PORT env var.
    # Fallback to 8000 when you run it locally.
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
