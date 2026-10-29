from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_pdf_is_rejected():
    response = client.post("/documents", files={"file": ("notes.pdf", b"Someting happening for good")})
    assert response.status_code == 400


def test_no_extension_is_rejected():
    response = client.post("/documents", files={"file": ("notes", b"Someting happening for good")})
    assert response.status_code == 400

def test_double_extension_is_rejected():
    response = client.post("/documents", files={"file": ("notes.pdf.exe", b"Someting happening for good")})
    assert response.status_code == 400

def test_error_message_lists_allowed_type():
    response = client.post("/documents", files={"file": ("notes.pdf", b"Someting happening for good")})
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert ".md" in detail
    assert ".txt" in detail

def test_not_a_valid_utf_content():
    response = client.post("/documents", files={"file" : ("notes.txt", b"\xff\xfe\x00\x00")})
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "UTF-8" in detail
