"""
Precompute pipeline results for known-good 2026 sessions.

Run once locally before pushing to deploy. Pickles are committed to the
repo so the dashboard can load them instantly on Streamlit Cloud (which
has no persistent cache between cold starts).

Usage:
    python scripts/precompute_sessions.py
"""
import pickle
from pathlib import Path

# Make src/ importable when run from project root
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

import fastf1
from src.analysis.pipeline import run_session


OUTPUT_DIR = Path('data/precomputed')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

fastf1.Cache.enable_cache('data/raw')

SESSIONS = [
    (2026, 'Australia', 'Q'),
    (2026, 'China',     'Q'),
    (2026, 'Japan',     'Q'),
    (2026, 'Miami',     'Q'),
    (2026, 'Monaco',    'Q'),
    (2026, 'Canada',    'Q'),
]


def pkl_path(year: int, gp: str, sess: str) -> Path:
    return OUTPUT_DIR / f"{year}_{gp.replace(' ', '_')}_{sess}.pkl"


def main():
    for year, gp, sess in SESSIONS:
        path = pkl_path(year, gp, sess)
        if path.exists():
            print(f"Skipping {year} {gp} {sess} (already at {path})")
            continue

        print(f"\n=== {year} {gp} {sess} ===")
        try:
            result = run_session(year, gp, sess, verbose=True)
        except Exception as e:
            print(f"  FAILED: {type(e).__name__}: {e}")
            continue

        with open(path, 'wb') as f:
            pickle.dump(result, f)
        print(f"  Saved: {path} ({path.stat().st_size / 1024:.1f} KB)")

    print("\nDone.")


if __name__ == '__main__':
    main()