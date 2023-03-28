"""
URL mappings for the server app.
"""
from django.urls import (
    path,
    include,
)

from rest_framework.routers import DefaultRouter

from server import views


router = DefaultRouter()
router.register("servers", views.ServerViewSet)
router.register('tags', views.TagViewSet)
router.register('components', views.ComponentViewSet)

app_name = "server"

urlpatterns = [
    path("", include(router.urls)),
]
