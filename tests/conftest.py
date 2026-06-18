import pytest
import tempfile
from pathlib import Path

from crawler.database import OpportunityDatabase


@pytest.fixture
def tmp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        db = OpportunityDatabase(db_path)
        yield db