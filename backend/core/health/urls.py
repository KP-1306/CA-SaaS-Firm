"""Health endpoint URL configuration."""

from __future__ import annotations

from django.urls import path

from .views import health

app_name = "health"

urlpatterns = [
    path("", health, name="health"),
]
