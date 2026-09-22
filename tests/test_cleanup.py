import os
import time
from app.config import settings
from app.utils.file_utils import create_job_workspace
from app.utils.cleanup import cleanup_expired_jobs


def test_cleanup_expired_jobs(tmp_path, monkeypatch):
    # Set TEMP_DIR to temporary directory for isolated test
    test_temp = tmp_path / "temp"
    test_temp.mkdir()
    monkeypatch.setattr(settings, "TEMP_DIR", test_temp)

    # 1. Create job folder that looks 60 minutes old
    old_job_id, _, _, _ = create_job_workspace("old_job_123")
    old_job_dir = test_temp / "old_job_123"
    assert old_job_dir.exists()
    
    # Backdate modification time by 60 minutes
    old_time = time.time() - 3600
    os.utime(old_job_dir, (old_time, old_time))

    # 2. Create fresh job folder
    fresh_job_id, _, _, _ = create_job_workspace("fresh_job_456")
    fresh_job_dir = test_temp / "fresh_job_456"
    assert fresh_job_dir.exists()

    # 3. Run cleanup with 30-minute TTL
    purged = cleanup_expired_jobs(ttl_minutes=30)
    assert purged == 1

    # Old job should be removed, fresh job should remain
    assert not old_job_dir.exists()
    assert fresh_job_dir.exists()
