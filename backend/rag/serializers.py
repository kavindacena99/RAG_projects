from rest_framework import serializers


class IngestNoteSerializer(serializers.Serializer):
    title = serializers.CharField(required=True, allow_blank=False)
    content = serializers.CharField(required=True, allow_blank=False)
    topic = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    source = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class IngestKnowledgeDirectorySerializer(serializers.Serializer):
    ingest_from_knowledge_dir = serializers.BooleanField(required=True)
    knowledge_base_dir = serializers.CharField(required=False, allow_blank=False)

    def validate_ingest_from_knowledge_dir(self, value):
        if value is not True:
            raise serializers.ValidationError(
                "Set ingest_from_knowledge_dir to true for directory ingestion mode."
            )
        return value


class NoteIngestSerializer(IngestNoteSerializer):
    pass


class AskQuestionSerializer(serializers.Serializer):
    question = serializers.CharField(required=True, allow_blank=False)
