"""
Tests for the components API.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import TestCase

from rest_framework import status
from rest_framework.test import APIClient

from core.models import (
    Component,
    Server,
)

from server.serializers import ComponentSerializer


COMPONENTS_URL = reverse("server:component-list")


def detail_url(component_id):
    """Create and return an component detail URL."""
    return reverse("server:component-detail", args=[component_id])


def create_user(email="user@example.com", password="testpass123"):
    """Create and return user."""
    return get_user_model().objects.create_user(email=email, password=password)


class PublicComponentsApiTests(TestCase):
    """Test unauthenticated API requests."""

    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        """Test auth is required for retrieving components."""
        res = self.client.get(COMPONENTS_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateComponentsApiTests(TestCase):
    """Test authenticated API requests."""

    def setUp(self):
        self.user = create_user()
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_retrieve_components(self):
        """Test retrieving a list of components."""
        Component.objects.create(user=self.user, name="Nvidia GTX 1080")
        Component.objects.create(user=self.user, name="Intel i7-8700k")

        res = self.client.get(COMPONENTS_URL)

        components = Component.objects.all().order_by("-name")
        serializer = ComponentSerializer(components, many=True)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_components_limited_to_user(self):
        """Test list of components is limited to authenticated user."""
        user2 = create_user(email="user2@example.com")
        Component.objects.create(user=user2, name="Nvidia GTX 1080")
        component = Component.objects.create(user=self.user, name="Intel i7-8700k")

        res = self.client.get(COMPONENTS_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["name"], component.name)
        self.assertEqual(res.data[0]["id"], component.id)

    def test_update_component(self):
        """Test updating an component."""
        component = Component.objects.create(user=self.user, name="Nvidia Titan X")

        payload = {"name": "Nvidia Titan Xp"}
        url = detail_url(component.id)
        res = self.client.patch(url, payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        component.refresh_from_db()
        self.assertEqual(component.name, payload["name"])

    def test_delete_component(self):
        """Test deleting an component."""
        component = Component.objects.create(user=self.user, name="Lettuce")

        url = detail_url(component.id)
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        components = Component.objects.filter(user=self.user)
        self.assertFalse(components.exists())

    def test_filter_components_assigned_to_servers(self):
        """Test listing components to those assigned to servers."""
        comp1 = Component.objects.create(user=self.user, name='Nvidia GTX 1080')
        comp2 = Component.objects.create(user=self.user, name='Intel i7-8700k')
        server = Server.objects.create(
            title='Gaming Server',
            price=Decimal('4.50'),
            user=self.user,
        )
        server.components.add(comp1)

        res = self.client.get(COMPONENTS_URL, {'assigned_only': 1})

        x1 = ComponentSerializer(comp1)
        x2 = ComponentSerializer(comp2)
        self.assertIn(x1.data, res.data)
        self.assertNotIn(x2.data, res.data)

    def test_filtered_components_unique(self):
        """Test filtered components returns a unique list."""
        comp = Component.objects.create(user=self.user, name='Nvidia GTX 1080')
        Component.objects.create(user=self.user, name='Intel i7-8700k')
        server1 = Server.objects.create(
            title='Gaming Server',
            price=Decimal('7.00'),
            user=self.user,
        )
        server2 = Server.objects.create(
            title='Video Editing Server',
            price=Decimal('4.00'),
            user=self.user,
        )
        server1.components.add(comp)
        server2.components.add(comp)

        res = self.client.get(COMPONENTS_URL, {'assigned_only': 1})

        self.assertEqual(len(res.data), 1)
