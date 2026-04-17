from rest_framework import serializers

from chat.models import ChatSession, Message


class StartSessionSerializer(serializers.Serializer):
    pass


class SendMessageSerializer(serializers.Serializer):
    session_id = serializers.IntegerField(required=True, min_value=1)
    message = serializers.CharField(required=True, allow_blank=False)


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ("id", "role", "content", "created_at")


class ChatSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatSession
        fields = ("id", "title", "created_at", "updated_at")

