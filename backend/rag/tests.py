import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase

from rag.services.evaluation_service import evaluate_all_cases, evaluate_single_case


class EvaluationServiceTests(SimpleTestCase):
    @patch("rag.services.evaluation_service.ask_question")
    def test_evaluate_single_case_scores_retrieval_and_answer(self, mock_ask_question):
        mock_ask_question.return_value = {
            "provider": "gemini",
            "collection": "study_notes_gemini_text_embedding_004",
            "reranking_enabled": True,
            "reranking_fallback_used": False,
            "reranking_error": None,
            "total_retrieved_initial": 3,
            "total_retrieved_final": 2,
            "retrieved_chunks_initial": [
                {
                    "id": "chunk-1",
                    "text": "CI/CD helps automate software delivery.",
                    "metadata": {"topic": "software_engineering"},
                    "distance": 0.33,
                },
                {
                    "id": "chunk-2",
                    "text": "CI/CD stands for continuous integration and continuous deployment.",
                    "metadata": {"topic": "devops"},
                    "distance": 0.21,
                },
            ],
            "retrieved_chunks_final": [
                {
                    "id": "chunk-2",
                    "text": "CI/CD stands for continuous integration and continuous deployment.",
                    "metadata": {"topic": "devops"},
                    "distance": 0.21,
                },
                {
                    "id": "chunk-1",
                    "text": "CI/CD helps automate software delivery.",
                    "metadata": {"topic": "software_engineering"},
                    "distance": 0.33,
                },
            ],
            "answer": "CI/CD means continuous integration and continuous deployment.",
        }

        result = evaluate_single_case(
            {
                "question": "What is CI/CD?",
                "expected_topic": "devops",
                "expected_keywords": ["continuous", "integration", "deployment"],
            }
        )

        self.assertEqual(result["retrieval_score"], 2)
        self.assertEqual(result["answer_score"], 2)
        self.assertEqual(result["total_score"], 4)
        self.assertTrue(result["expected_topic_in_top_1"])
        self.assertTrue(result["top_1_chunk_changed_after_rerank"])
        self.assertTrue(result["reranking_improved_topic_placement"])
        self.assertEqual(
            result["matched_keywords"],
            ["continuous", "integration", "deployment"],
        )

    @patch("rag.services.evaluation_service.ask_question")
    def test_evaluate_all_cases_builds_summary(self, mock_ask_question):
        mock_ask_question.side_effect = [
            {
                "provider": "openai",
                "collection": "study_notes_openai_text_embedding_3_small",
                "reranking_enabled": False,
                "reranking_fallback_used": False,
                "reranking_error": None,
                "total_retrieved_initial": 2,
                "total_retrieved_final": 2,
                "retrieved_chunks_initial": [
                    {
                        "id": "chunk-a",
                        "text": "Embeddings turn text into vectors.",
                        "metadata": {"topic": "genai"},
                        "distance": 0.12,
                    }
                ],
                "retrieved_chunks_final": [
                    {
                        "id": "chunk-a",
                        "text": "Embeddings turn text into vectors.",
                        "metadata": {"topic": "genai"},
                        "distance": 0.12,
                    }
                ],
                "answer": "An embedding represents text as a vector for similarity search.",
            },
            {
                "provider": "openai",
                "collection": "study_notes_openai_text_embedding_3_small",
                "reranking_enabled": False,
                "reranking_fallback_used": False,
                "reranking_error": None,
                "total_retrieved_initial": 2,
                "total_retrieved_final": 2,
                "retrieved_chunks_initial": [
                    {
                        "id": "chunk-b",
                        "text": "Containers help package applications.",
                        "metadata": {"topic": "devops"},
                        "distance": 0.45,
                    }
                ],
                "retrieved_chunks_final": [
                    {
                        "id": "chunk-b",
                        "text": "Containers help package applications.",
                        "metadata": {"topic": "devops"},
                        "distance": 0.45,
                    }
                ],
                "answer": "Containers package applications.",
            },
        ]

        with TemporaryDirectory() as temp_dir:
            evaluation_file = Path(temp_dir) / "cases.json"
            evaluation_file.write_text(
                json.dumps(
                    [
                        {
                            "question": "What is an embedding?",
                            "expected_topic": "genai",
                            "expected_keywords": ["vector", "similarity"],
                        },
                        {
                            "question": "What is MLOps?",
                            "expected_topic": "machine_learning",
                            "expected_keywords": ["automation", "deployment"],
                        },
                    ]
                ),
                encoding="utf-8",
            )

            result = evaluate_all_cases(str(evaluation_file))

        self.assertEqual(result["total_cases"], 2)
        self.assertEqual(result["cases_with_expected_topic_in_top_1"], 1)
        self.assertEqual(result["cases_with_expected_topic_in_top_3"], 1)
        self.assertEqual(result["cases_with_keyword_match"], 1)
        self.assertEqual(result["average_retrieval_score"], 1.0)
        self.assertEqual(result["average_answer_score"], 1.0)
        self.assertEqual(result["average_total_score"], 2.0)
