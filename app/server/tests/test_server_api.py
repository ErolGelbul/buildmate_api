"""
Tests for server APIs.
"""
from decimal import Decimal
import tempfile
import os

from PIL import Image

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from core.models import (
    Server,
    Tag,
    Component,
)

from server.serializers import (
    ServerSerializer,
    ServerDetailSerializer,
)

SERVERS_URL = reverse("server:server-list")


def detail_url(server_id):
    """Create and return a server detail URL."""
    return reverse("server:server-detail", args=[server_id])


def image_upload_url(server_id):
    """Create and return an image upload URL."""
    return reverse("server:server-upload-image", args=[server_id])


def create_server(user, **params):
    """Create and return a sample server."""
    defaults = {
        "title": "Sample server title",
        "price": Decimal("5.25"),
        "description": "Sample description",
        "link": "http://example.com/server.pdf",
    }
    defaults.update(params)

    server = Server.objects.create(user=user, **defaults)
    return server


def create_user(**params):
    """Create and return a new user."""
    return get_user_model().objects.create_user(**params)


class PublicServerAPITests(TestCase):
    """Test unauthenticated API requests."""

    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        """Test auth is required to call API."""
        res = self.client.get(SERVERS_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateServerApiTests(TestCase):
    """Test authenticated API requests."""

    def setUp(self):
        self.client = APIClient()
        self.user = create_user(email="user@example.com", password="test123")
        self.client.force_authenticate(self.user)

    def test_retrieve_servers(self):
        """Test retrieving a list of servers."""
        create_server(user=self.user)
        create_server(user=self.user)

        res = self.client.get(SERVERS_URL)
        servers = Server.objects.all().order_by("-id")
        serializer = ServerSerializer(servers, many=True)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_server_list_limited_to_user(self):
        """Test list of servers is limited to authenticated user."""
        other_user = create_user(email="other@example.com", password="test123")
        create_server(user=other_user)
        create_server(user=self.user)

        res = self.client.get(SERVERS_URL)

        servers = Server.objects.filter(user=self.user)
        serializer = ServerSerializer(servers, many=True)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_get_server_detail(self):
        """Test get server detail."""
        server = create_server(user=self.user)

        url = detail_url(server.id)
        res = self.client.get(url)

        serializer = ServerDetailSerializer(server)
        self.assertEqual(res.data, serializer.data)

    def test_create_server(self):
        """Test creating a server."""
        payload = {
            "title": "Sample server",
            "price": Decimal("5.99"),
        }
        res = self.client.post(SERVERS_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        server = Server.objects.get(id=res.data["id"])
        for k, v in payload.items():
            self.assertEqual(getattr(server, k), v)
        self.assertEqual(server.user, self.user)

    def test_partial_update(self):
        """Test partial update of a server."""
        original_link = "https://example.com/server.pdf"
        server = create_server(
            user=self.user,
            title="Sample serer title",
            link=original_link,
        )

        payload = {"title": "New server title"}
        url = detail_url(server.id)
        res = self.client.patch(url, payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        server.refresh_from_db()
        self.assertEqual(server.title, payload["title"])
        self.assertEqual(server.link, original_link)
        self.assertEqual(server.user, self.user)

    def test_full_update(self):
        """Test full update of server."""
        server = create_server(
            user=self.user,
            title="Sample server title",
            link="https://exmaple.com/server.pdf",
            description="Sample server description.",
        )

        payload = {
            "title": "New server title",
            "link": "https://example.com/new-server.pdf",
            "description": "New server description",
            "price": Decimal("2.50"),
        }
        url = detail_url(server.id)
        res = self.client.put(url, payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        server.refresh_from_db()
        for k, v in payload.items():
            self.assertEqual(getattr(server, k), v)
        self.assertEqual(server.user, self.user)

    def test_update_user_returns_error(self):
        """Test changing the server user results in an error."""
        new_user = create_user(email="user2@example.com", password="test123")
        server = create_server(user=self.user)

        payload = {"user": new_user.id}
        url = detail_url(server.id)
        self.client.patch(url, payload)

        server.refresh_from_db()
        self.assertEqual(server.user, self.user)

    def test_delete_server(self):
        """Test deleting a server successful."""
        server = create_server(user=self.user)

        url = detail_url(server.id)
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Server.objects.filter(id=server.id).exists())

    def test_server_other_users_server_error(self):
        """Test trying to delete another users server gives error."""
        new_user = create_user(email="user2@example.com", password="test123")
        server = create_server(user=new_user)

        url = detail_url(server.id)
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Server.objects.filter(id=server.id).exists())

    def test_create_server_with_new_tags(self):
        """Test creating a server with new tags."""
        payload = {
            "title": "Thai Prawn Curry",
            "price": Decimal("2.50"),
            "tags": [{"name": "Thai"}, {"name": "Dinner"}],
        }
        res = self.client.post(SERVERS_URL, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        servers = Server.objects.filter(user=self.user)
        self.assertEqual(servers.count(), 1)
        server = servers[0]
        self.assertEqual(server.tags.count(), 2)
        for tag in payload["tags"]:
            exists = server.tags.filter(
                name=tag["name"],
                user=self.user,
            ).exists()
            self.assertTrue(exists)

    def test_create_server_with_existing_tags(self):
        """Test creating a server with existing tag."""
        tag_indian = Tag.objects.create(user=self.user, name="Indian")
        payload = {
            "title": "Pongal",
            "time_minutes": 60,
            "price": Decimal("4.50"),
            "tags": [{"name": "Indian"}, {"name": "Breakfast"}],
        }
        res = self.client.post(SERVERS_URL, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        servers = Server.objects.filter(user=self.user)
        self.assertEqual(servers.count(), 1)
        server = servers[0]
        self.assertEqual(server.tags.count(), 2)
        self.assertIn(tag_indian, server.tags.all())
        for tag in payload["tags"]:
            exists = server.tags.filter(
                name=tag["name"],
                user=self.user,
            ).exists()
            self.assertTrue(exists)

    def test_create_tag_on_update(self):
        """Test create tag when updating a server."""
        server = create_server(user=self.user)

        payload = {"tags": [{"name": "Lunch"}]}
        url = detail_url(server.id)
        res = self.client.patch(url, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        new_tag = Tag.objects.get(user=self.user, name="Lunch")
        self.assertIn(new_tag, server.tags.all())

    def test_update_server_assign_tag(self):
        """Test assigning an existing tag when updating a server."""
        tag_breakfast = Tag.objects.create(user=self.user, name="Breakfast")
        server = create_server(user=self.user)
        server.tags.add(tag_breakfast)

        tag_lunch = Tag.objects.create(user=self.user, name="Lunch")
        payload = {"tags": [{"name": "Lunch"}]}
        url = detail_url(server.id)
        res = self.client.patch(url, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn(tag_lunch, server.tags.all())
        self.assertNotIn(tag_breakfast, server.tags.all())

    def test_clear_server_tags(self):
        """Test clearing a servers tags."""
        tag = Tag.objects.create(user=self.user, name="Dessert")
        server = create_server(user=self.user)
        server.tags.add(tag)

        payload = {"tags": []}
        url = detail_url(server.id)
        res = self.client.patch(url, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(server.tags.count(), 0)

    def test_create_server_with_new_components(self):
        """Test creating a server with new components."""
        payload = {
            "title": "Video Editing Server",
            "price": Decimal("4.30"),
            "components": [{"name": "Nvidia Titan X"}, {"name": "AMD Ryzen 9 5950X"}],
        }
        res = self.client.post(SERVERS_URL, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        servers = Server.objects.filter(user=self.user)
        self.assertEqual(servers.count(), 1)
        server = servers[0]
        self.assertEqual(server.components.count(), 2)
        for component in payload["components"]:
            exists = server.components.filter(
                name=component["name"],
                user=self.user,
            ).exists()
            self.assertTrue(exists)

    def test_create_server_with_existing_component(self):
        """Test creating a new server with existing component."""
        component = Component.objects.create(user=self.user, name="Nvidia Titan X")
        payload = {
            "title": "Machine Learning Server",
            "price": "2.55",
            "components": [{"name": "Nvidia Titan X"}, {"name": "AMD Ryzen 9 5950X"}],
        }
        res = self.client.post(SERVERS_URL, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        servers = Server.objects.filter(user=self.user)
        self.assertEqual(servers.count(), 1)
        server = servers[0]
        self.assertEqual(server.components.count(), 2)
        self.assertIn(component, server.components.all())
        for component in payload["components"]:
            exists = server.components.filter(
                name=component["name"],
                user=self.user,
            ).exists()
            self.assertTrue(exists)

    def test_create_component_on_update(self):
        """Test creating an component when updating a server."""
        server = create_server(user=self.user)

        payload = {"components": [{"name": "Nvidia Titan X"}]}
        url = detail_url(server.id)
        res = self.client.patch(url, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        new_component = Component.objects.get(user=self.user, name="Nvidia Titan X")
        self.assertIn(new_component, server.components.all())

    def test_update_server_assign_component(self):
        """Test assigning an existing component when updating a server."""
        component1 = Component.objects.create(user=self.user, name="Nvidia Titan X")
        server = create_server(user=self.user)
        server.components.add(component1)

        component2 = Component.objects.create(user=self.user, name="AMD Ryzen 9 5950X")
        payload = {"components": [{"name": "AMD Ryzen 9 5950X"}]}
        url = detail_url(server.id)
        res = self.client.patch(url, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn(component2, server.components.all())
        self.assertNotIn(component1, server.components.all())

    def test_clear_server_components(self):
        """Test clearing a servers components."""
        component = Component.objects.create(
            user=self.user, name="Nvidia GeForce RTX 3090"
        )
        server = create_server(user=self.user)
        server.components.add(component)

        payload = {"components": []}
        url = detail_url(server.id)
        res = self.client.patch(url, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(server.components.count(), 0)

    def test_filter_by_tags(self):
        """Test filtering servers by tags."""
        s1 = create_server(user=self.user, title="Video Editing Server")
        s2 = create_server(user=self.user, title="Machine Learning Server")
        tag1 = Tag.objects.create(user=self.user, name="Fast")
        tag2 = Tag.objects.create(user=self.user, name="Storage")
        s1.tags.add(tag1)
        s2.tags.add(tag2)
        s3 = create_server(user=self.user, title="Gaming Server")

        params = {"tags": f"{tag1.id},{tag2.id}"}
        res = self.client.get(SERVERS_URL, params)

        s1 = ServerSerializer(s1)
        s2 = ServerSerializer(s2)
        s3 = ServerSerializer(s3)
        self.assertIn(s1.data, res.data)
        self.assertIn(s2.data, res.data)
        self.assertNotIn(s3.data, res.data)

    def test_filter_by_components(self):
        """Test filtering servers by components."""
        s1 = create_server(user=self.user, title="Video Editing Server")
        s2 = create_server(user=self.user, title="Machine Learning Server")
        comp1 = Component.objects.create(user=self.user, name="Nvidia Titan X")
        comp2 = Component.objects.create(user=self.user, name="AMD Ryzen 9 5950X")
        s1.components.add(comp1)
        s2.components.add(comp2)
        s3 = create_server(user=self.user, title="Gaming Server")

        params = {"components": f"{comp1.id},{comp2.id}"}
        res = self.client.get(SERVERS_URL, params)

        x1 = ServerSerializer(s1)
        x2 = ServerSerializer(s2)
        x3 = ServerSerializer(s3)
        self.assertIn(x1.data, res.data)
        self.assertIn(x2.data, res.data)
        self.assertNotIn(x3.data, res.data)


class ImageUploadTests(TestCase):
    """Tests for the image upload API."""

    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            "user@example.com",
            "password123",
        )
        self.client.force_authenticate(self.user)
        self.server = create_server(user=self.user)

    def tearDown(self):
        self.server.image.delete()

    def test_upload_image(self):
        """Test uploading an image to a server."""
        url = image_upload_url(self.server.id)
        with tempfile.NamedTemporaryFile(suffix=".jpg") as image_file:
            img = Image.new("RGB", (10, 10))
            img.save(image_file, format="JPEG")
            image_file.seek(0)
            payload = {"image": image_file}
            res = self.client.post(url, payload, format="multipart")

        self.server.refresh_from_db()
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("image", res.data)
        self.assertTrue(os.path.exists(self.server.image.path))

    def test_upload_image_bad_request(self):
        """Test uploading an invalid image."""
        url = image_upload_url(self.server.id)
        payload = {"image": "notanimage"}
        res = self.client.post(url, payload, format="multipart")

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
