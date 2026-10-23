"""
AegisBridge-EMS Application Server Entry Point.
Runs the FastAPI application on http://127.0.0.1:8000.
"""

import uvicorn
import src.config  # noqa: F401 - Loads .env on process launch

if __name__ == "__main__":
    uvicorn.run("src.api:app", host="127.0.0.1", port=8000, reload=False)
