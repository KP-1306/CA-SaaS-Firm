from __future__ import annotations

import uuid
import pytest
from django.test import Client

HEADERS = {"HTTP_X_TENANT_ID": str(uuid.uuid4()), "HTTP_X_PRINCIPAL_ID": str(uuid.uuid4())}

@pytest.mark.django_db
def test_create_and_isolate_client() -> None:
    client=Client()
    response=client.post("/api/v1/clients/", data={"legal_name":"ABC Private Limited","client_type":"PRIVATE_LIMITED"}, content_type="application/json", **HEADERS)
    assert response.status_code == 201, response.content
    assert response.json()["legal_name"] == "ABC Private Limited"
    other={"HTTP_X_TENANT_ID":str(uuid.uuid4()),"HTTP_X_PRINCIPAL_ID":str(uuid.uuid4())}
    assert client.get("/api/v1/clients/", **other).json() == []

@pytest.mark.django_db
def test_headers_are_required() -> None:
    assert Client().get("/api/v1/clients/").status_code == 403
