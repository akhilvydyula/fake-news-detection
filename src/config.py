"""Central paths and defaults for the fake-news prototype."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_INTERIM = PROJECT_ROOT / "data" / "interim"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
ARTIFACTS = PROJECT_ROOT / "artifacts"

DEFAULT_MAX_SAMPLES = 10_000
DEFAULT_RANDOM_STATE = 42
TEST_SIZE = 0.15
VAL_SIZE = 0.15  # of remaining after test split

# HF dataset ids (permissive research use; verify license for production)
HF_FAKE_NEWS = "GonzaloA/fake_news"
HF_AG_NEWS = "ag_news"
