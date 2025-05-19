"""Entry point for the UAV Log Viewer application."""

import os
from dotenv import load_dotenv
import uvicorn
from pathlib import Path
from uav_log_viewer.core import create_app

# Get the directory containing run.py
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from backend/.env
load_dotenv(BASE_DIR / '.env')

# Create the application instance
app = create_app()

def main():
    """Run the application."""
    uvicorn.run(
        "run:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )

if __name__ == "__main__":
    main() 