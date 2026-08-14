from pathlib import Path
import sys
import os

# Ensure project root is on sys.path and working directory
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))
os.chdir(str(project_root))

from app.main import app
import uvicorn

if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=8000)
