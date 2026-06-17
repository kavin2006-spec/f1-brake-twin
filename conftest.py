"""
conftest.py — pytest configuration for the project.

This file adds the project root to sys.path so that 'from src...' imports
work from anywhere in the project (tests, notebooks, scripts).

This is a standard pytest trick: pytest automatically picks up conftest.py and runs it before any test, which makes our src/ package importable without needing to install anything.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))