import io
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root_endpoint():
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert "Private Document Converter" in data["message"]
    assert "health" in data


def test_health_endpoint():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "services" in data
    assert "dependencies" in data
    assert data["services"]["pdf"] is True
    assert data["services"]["image"] is True


def test_conversions_registry():
    res = client.get("/api/conversions")
    assert res.status_code == 200
    data = res.json()
    assert "categories" in data
    assert "pdf" in data["categories"]
    assert "word" in data["categories"]
    assert "spreadsheets" in data["categories"]
    assert "images" in data["categories"]
    assert "pdf" in data["supported_inputs"]


def test_convert_txt_to_pdf_flow():
    txt_content = b"Sample document text for test conversion.\nSecond line of content."
    files = {
        "file": ("test.txt", txt_content, "text/plain")
    }
    data = {
        "target_format": "pdf",
        "conversion_type": "convert",
        "options": "{}"
    }

    # Execute conversion
    res = client.post("/api/convert", files=files, data=data)
    assert res.status_code == 200
    result = res.json()
    job_id = result["job_id"]
    assert result["status"] == "completed"
    assert result["target_format"] == "pdf"
    assert result["output_filename"].endswith(".pdf")

    # Check job status
    job_res = client.get(f"/api/jobs/{job_id}")
    assert job_res.status_code == 200
    job_data = job_res.json()
    assert job_data["status"] == "completed"

    # Download output
    download_res = client.get(f"/api/jobs/{job_id}/download")
    assert download_res.status_code == 200
    assert len(download_res.content) > 0
    assert download_res.content.startswith(b"%PDF")

    # Delete job
    del_res = client.delete(f"/api/jobs/{job_id}")
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True
