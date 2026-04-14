from django.urls import path

from .views import (
    AskQuestionView,
    ChromaCleanupDuplicatesView,
    EvaluationView,
    HealthCheckView,
    NoteIngestView,
)

urlpatterns = [
    path("health", HealthCheckView.as_view(), name="health-check"),
    path("notes/ingest", NoteIngestView.as_view(), name="notes-ingest"),
    path("ask", AskQuestionView.as_view(), name="ask-question"),
    path("evaluate", EvaluationView.as_view(), name="evaluate-rag"),
    path(
        "maintenance/chroma/cleanup-duplicates",
        ChromaCleanupDuplicatesView.as_view(),
        name="cleanup-chroma-duplicates",
    ),
]
