"""
Serializers for server APIs
"""
from rest_framework import serializers

from core.models import (
    Server,
    Tag,
    Component,
)


class ComponentSerializer(serializers.ModelSerializer):
    """Serializer for components."""

    class Meta:
        model = Component
        fields = ["id", "name"]
        read_only_fields = ["id"]


class TagSerializer(serializers.ModelSerializer):
    """Serializer for tags."""

    class Meta:
        model = Tag
        fields = ["id", "name"]
        read_only_fields = ["id"]


class ServerSerializer(serializers.ModelSerializer):
    """Serializer for servers."""

    tags = TagSerializer(many=True, required=False)
    components = ComponentSerializer(many=True, required=False)

    class Meta:
        model = Server
        fields = [
            "id",
            "title",
            "price",
            "link",
            "tags",
            "components",
        ]
        read_only_fields = ["id"]

    def _get_or_create_tags(self, tags, server):
        """Handle getting or creating tags as needed."""
        auth_user = self.context["request"].user
        for tag in tags:
            tag_obj, created = Tag.objects.get_or_create(
                user=auth_user,
                **tag,
            )
            server.tags.add(tag_obj)

    def _get_or_create_components(self, components, server):
        """Handle getting or creating components as needed."""
        auth_user = self.context["request"].user
        for component in components:
            component_obj, created = Component.objects.get_or_create(
                user=auth_user,
                **component,
            )
            server.components.add(component_obj)

    def create(self, validated_data):
        """Create a server."""
        tags = validated_data.pop("tags", [])
        components = validated_data.pop("components", [])
        server = Server.objects.create(**validated_data)
        self._get_or_create_tags(tags, server)
        self._get_or_create_components(components, server)

        return server

    def update(self, instance, validated_data):
        """Update server."""
        tags = validated_data.pop("tags", None)
        components = validated_data.pop('components', None)
        if tags is not None:
            instance.tags.clear()
            self._get_or_create_tags(tags, instance)
        if components is not None:
            instance.components.clear()
            self._get_or_create_components(components, instance)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance


class ServerDetailSerializer(ServerSerializer):
    """Serializer for server detail view."""

    class Meta(ServerSerializer.Meta):
        fields = ServerSerializer.Meta.fields + ["description", "image"]


class ServerImageSerializer(serializers.ModelSerializer):
    """Serializer for uploading images to servers."""

    class Meta:
        model = Server
        fields = ['id', 'image']
        read_only_fields = ['id']
        extra_kwargs = {'image': {'required': 'True'}}
