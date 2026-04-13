from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    AskQuestionSerializer,
    EvaluateRagSerializer,
    IngestKnowledgeDirectorySerializer,
    IngestNoteSerializer,
)
from .services.evaluation_service import evaluate_all_cases
from .services.file_ingestion_service import ingest_knowledge_directory
from .services.rag_service import ask_question, ingest_note


def _parse_int_query_param(raw_value, default_value):
    if raw_value is None:
        return default_value

    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return None


class HealthCheckView(APIView):
    def get(self, request):
        return Response(
            {
                "status": "ok",
                "message": "AI Study Notes RAG Assistant backend is running",
            }
        )


class NoteIngestView(APIView):
    def post(self, request):
        chunk_size = _parse_int_query_param(
            request.query_params.get("chunk_size"), 400
        )
        overlap = _parse_int_query_param(request.query_params.get("overlap"), 80)

        if chunk_size is None or chunk_size <= 0:
            return Response(
                {"detail": "chunk_size must be a positive integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if overlap is None or overlap < 0:
            return Response(
                {"detail": "overlap must be 0 or a positive integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if overlap >= chunk_size:
            return Response(
                {"detail": "overlap must be smaller than chunk_size."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if "ingest_from_knowledge_dir" in request.data:
            directory_serializer = IngestKnowledgeDirectorySerializer(data=request.data)
            directory_serializer.is_valid(raise_exception=True)
            requested_base_dir = directory_serializer.validated_data.get(
                "knowledge_base_dir"
            )

            try:
                result = ingest_knowledge_directory(
                    base_path=requested_base_dir,
                    chunk_size=chunk_size,
                    overlap=overlap,
                )
                return Response(result, status=status.HTTP_200_OK)
            except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
                return Response(
                    {"error": str(exc)},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            except RuntimeError as exc:
                return Response(
                    {"error": str(exc)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            except Exception as exc:
                return Response(
                    {"error": f"Unexpected directory ingest error: {exc}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        serializer = IngestNoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = ingest_note(
                title=serializer.validated_data["title"],
                content=serializer.validated_data["content"],
                topic=serializer.validated_data.get("topic"),
                source=serializer.validated_data.get("source"),
                chunk_size=chunk_size,
                overlap=overlap,
            )
            return Response(result, status=status.HTTP_200_OK)
        except ValueError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except RuntimeError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as exc:
            return Response(
                {"error": f"Unexpected ingest error: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class AskQuestionView(APIView):
    def post(self, request):
        serializer = AskQuestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        top_k = _parse_int_query_param(request.query_params.get("top_k"), None)
        if top_k is not None and top_k <= 0:
            return Response(
                {"detail": "top_k must be a positive integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = ask_question(
                question=serializer.validated_data["question"],
                top_k=top_k,
            )
            return Response(result, status=status.HTTP_200_OK)
        except ValueError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except RuntimeError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as exc:
            return Response(
                {"error": f"Unexpected ask error: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class EvaluationView(APIView):
    def get(self, request):
        file_path = request.query_params.get("file_path")
        return self._run_evaluation(file_path=file_path)

    def post(self, request):
        serializer = EvaluateRagSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._run_evaluation(
            file_path=serializer.validated_data.get("file_path")
        )

    def _run_evaluation(self, file_path: str | None = None):
        try:
            result = evaluate_all_cases(file_path=file_path)
            return Response(result, status=status.HTTP_200_OK)
        except (FileNotFoundError, ValueError) as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except RuntimeError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as exc:
            return Response(
                {"error": f"Unexpected evaluation error: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
