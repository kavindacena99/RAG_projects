import os
from unittest.mock import patch

from django.test import SimpleTestCase

from rag.services.chroma_cleanup_service import cleanup_duplicate_chunks
from rag.services.chroma_service import _build_stable_chunk_id, add_note_chunks
from rag.services.chunking_service import (
    merge_small_chunks,
    semantic_chunk_pipeline,
    semantic_chunk_text,
    split_large_chunks,
)
from rag.services.evaluation_service import evaluate_all_cases, evaluate_single_case
from rag.services.hybrid_search_service import (
    apply_hybrid_scoring,
    normalize_keyword_scores,
    normalize_vector_scores,
    rank_hybrid_candidates,
    score_candidates_with_keywords,
)
from rag.services.llm_service import build_rag_prompt, format_chunks
from rag.services.query_analysis_service import (
    extract_comparison_terms,
    is_comparison_question,
    normalize_comparison_term_to_topic,
)
from rag.services.rag_service import (
    _normalize_chroma_results,
    ask_question,
    merge_and_diversify_chunks,
)
from rag.services.reranking_service import select_balanced_final_chunks
from rag.utils.topic_normalizer import normalize_topic, normalize_topics


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

    @patch("rag.services.evaluation_service.load_evaluation_cases")
    @patch("rag.services.evaluation_service.ask_question")
    def test_evaluate_all_cases_builds_summary(
        self,
        mock_ask_question,
        mock_load_evaluation_cases,
    ):
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
        mock_load_evaluation_cases.return_value = [
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

        result = evaluate_all_cases("rag/evaluation/test_questions.json")

        self.assertEqual(result["total_cases"], 2)
        self.assertEqual(result["cases_with_expected_topic_in_top_1"], 1)
        self.assertEqual(result["cases_with_expected_topic_in_top_3"], 1)
        self.assertEqual(result["cases_with_keyword_match"], 1)
        self.assertEqual(result["average_retrieval_score"], 1.0)
        self.assertEqual(result["average_answer_score"], 1.0)
        self.assertEqual(result["average_total_score"], 2.0)


class QueryAnalysisServiceTests(SimpleTestCase):
    def test_detects_comparison_question(self):
        self.assertTrue(
            is_comparison_question(
                "What is the difference between Machine Learning and Deep Learning?"
            )
        )
        self.assertTrue(is_comparison_question("Compare RAG vs Agentic RAG"))
        self.assertFalse(is_comparison_question("What is an embedding?"))

    def test_extracts_comparison_terms(self):
        self.assertEqual(
            extract_comparison_terms(
                "What is the relation between Software Engineering and DevOps?"
            ),
            ["Software Engineering", "DevOps"],
        )
        self.assertEqual(
            extract_comparison_terms("Compare RAG vs Agentic RAG"),
            ["RAG", "Agentic RAG"],
        )

    def test_normalizes_comparison_terms_to_topics(self):
        self.assertEqual(normalize_comparison_term_to_topic("GenAI"), "genai")
        self.assertEqual(normalize_comparison_term_to_topic("GenerativeAI"), "genai")
        self.assertEqual(normalize_comparison_term_to_topic("ML"), "machine_learning")
        self.assertEqual(
            normalize_comparison_term_to_topic("Machine Learning"),
            "machine_learning",
        )
        self.assertEqual(
            normalize_comparison_term_to_topic("Software Engineering"),
            "software_engineering",
        )
        self.assertEqual(normalize_comparison_term_to_topic("DevOps"), "devops")

    def test_topic_normalizer_normalizes_aliases_and_lists(self):
        self.assertEqual(normalize_topic("GenerativeAI"), "genai")
        self.assertEqual(normalize_topic("gen ai"), "genai")
        self.assertEqual(normalize_topic("ML"), "machine_learning")
        self.assertEqual(
            normalize_topics(["GenerativeAI", "ML", "Machine Learning"]),
            ["genai", "machine_learning"],
        )


class SemanticChunkingTests(SimpleTestCase):
    def test_semantic_chunk_text_splits_paragraphs_and_filters_tiny_chunks(self):
        text = (
            "Machine Learning learns patterns from data and helps make predictions.\n\n"
            "Tiny note.\n\n"
            "Deep Learning uses multi-layer neural networks to learn complex representations."
        )

        result = semantic_chunk_text(text)

        self.assertEqual(len(result), 2)
        self.assertIn("Machine Learning learns patterns", result[0])
        self.assertIn("Deep Learning uses multi-layer neural networks", result[1])

    def test_merge_small_chunks_combines_consecutive_short_chunks(self):
        chunks = [
            "Software Engineering focuses on design.",
            "It also covers testing and maintenance.",
            "DevOps emphasizes automation and collaboration across teams.",
        ]

        result = merge_small_chunks(chunks, min_length=70)

        self.assertEqual(len(result), 1)
        self.assertIn("Software Engineering focuses on design.", result[0])
        self.assertIn("testing and maintenance.", result[0])
        self.assertIn("DevOps emphasizes automation", result[0])

    def test_split_large_chunks_breaks_large_paragraphs_by_sentence(self):
        chunks = [
            (
                "Machine Learning learns from data. "
                "It identifies patterns and improves predictions. "
                "Deep Learning uses layered neural networks for complex tasks."
            )
        ]

        result = split_large_chunks(chunks, max_length=70)

        self.assertGreater(len(result), 1)
        self.assertTrue(all(len(chunk) <= 70 for chunk in result))

    def test_semantic_chunk_pipeline_returns_meaningful_chunks(self):
        text = (
            "Generative AI creates new text, images, and code using learned patterns for many practical workflows in education and productivity systems.\n\n"
            "Machine Learning learns patterns from data for prediction tasks and supports many adaptive software features across real-world applications.\n\n"
            "DevOps improves software delivery through automation, collaboration, monitoring, and faster release practices across development teams.\n\n"
            "Software Engineering focuses on designing, testing, maintaining, and improving reliable software systems over time."
        )

        result = semantic_chunk_pipeline(text)

        self.assertGreaterEqual(len(result), 2)
        self.assertTrue(all(len(chunk) >= 50 for chunk in result))


class RetrievalDiversificationTests(SimpleTestCase):
    def test_merge_and_diversify_chunks_deduplicates_and_prefers_topic_coverage(self):
        chunks = [
            {
                "id": "chunk-1",
                "text": "DevOps improves automation.",
                "metadata": {"topic": "devops"},
                "distance": 0.10,
                "retrieval_position": 1,
            },
            {
                "id": "chunk-2",
                "text": "DevOps improves automation.",
                "metadata": {"topic": "devops"},
                "distance": 0.11,
                "retrieval_position": 2,
            },
            {
                "id": "chunk-3",
                "text": "Software Engineering focuses on design and maintenance.",
                "metadata": {"topic": "software_engineering"},
                "distance": 0.20,
                "retrieval_position": 3,
            },
            {
                "id": "chunk-4",
                "text": "Machine Learning learns from data.",
                "metadata": {"topic": "machine_learning"},
                "distance": 0.30,
                "retrieval_position": 4,
            },
        ]

        result = merge_and_diversify_chunks(chunks, max_candidates=3)

        self.assertEqual([chunk["id"] for chunk in result], ["chunk-1", "chunk-3", "chunk-4"])

    def test_select_balanced_final_chunks_preserves_expected_topics(self):
        reranked_chunks = [
            {
                "id": "chunk-devops-1",
                "text": "DevOps connects development and operations through automation.",
                "metadata": {"topic": "devops"},
                "rerank_score": 9.8,
                "rerank_position": 1,
            },
            {
                "id": "chunk-devops-2",
                "text": "DevOps includes CI/CD and monitoring.",
                "metadata": {"topic": "devops"},
                "rerank_score": 9.6,
                "rerank_position": 2,
            },
            {
                "id": "chunk-se-1",
                "text": "Software Engineering focuses on design, testing, and maintenance.",
                "metadata": {"topic": "software_engineering"},
                "rerank_score": 8.7,
                "rerank_position": 3,
            },
        ]

        result = select_balanced_final_chunks(
            reranked_chunks,
            comparison_terms=["Software Engineering", "DevOps"],
            final_top_n=3,
        )

        self.assertTrue(result["balanced_selection_applied"])
        self.assertEqual(
            [chunk["id"] for chunk in result["selected_chunks"]],
            ["chunk-se-1", "chunk-devops-1", "chunk-devops-2"],
        )
        self.assertEqual(
            result["expected_comparison_topics"],
            ["software_engineering", "devops"],
        )

    def test_select_balanced_final_chunks_filters_noisy_candidates(self):
        reranked_chunks = [
            {
                "id": "chunk-general-1",
                "text": "machine_learning",
                "metadata": {"topic": "machine_learning", "title": "ml"},
                "rerank_score": 9.5,
                "rerank_position": 1,
            },
            {
                "id": "chunk-genai-1",
                "text": "Generative AI creates new content such as text and images.",
                "metadata": {"topic": "genai"},
                "rerank_score": 8.9,
                "rerank_position": 2,
            },
            {
                "id": "chunk-ml-1",
                "text": "Machine Learning learns patterns from data to make predictions.",
                "metadata": {"topic": "machine_learning"},
                "rerank_score": 8.7,
                "rerank_position": 3,
            },
        ]

        result = select_balanced_final_chunks(
            reranked_chunks,
            comparison_terms=["GenAI", "Machine Learning"],
            final_top_n=3,
        )

        self.assertEqual(result["filtered_out_chunk_ids"], ["chunk-general-1"])
        self.assertEqual(
            [chunk["id"] for chunk in result["selected_chunks"]],
            ["chunk-genai-1", "chunk-ml-1"],
        )

    @patch("rag.services.rag_service.generate_answer")
    @patch("rag.services.rag_service.rerank_candidate_chunks")
    @patch("rag.services.rag_service.query_similar_chunks")
    @patch("rag.services.rag_service.generate_embedding")
    def test_ask_question_uses_comparison_aware_retrieval_with_balanced_final_selection(
        self,
        mock_generate_embedding,
        mock_query_similar_chunks,
        mock_rerank_candidate_chunks,
        mock_generate_answer,
    ):
        mock_generate_embedding.side_effect = [
            [0.1, 0.2],
            [0.3, 0.4],
            [0.5, 0.6],
        ]
        mock_query_similar_chunks.side_effect = [
            {
                "ids": [["chunk-devops-1", "chunk-devops-2"]],
                "documents": [[
                    "DevOps helps teams automate delivery.",
                    "DevOps includes CI/CD and deployment automation.",
                ]],
                "metadatas": [[
                    {"topic": "devops", "source": "knowledge/devops/devops.txt"},
                    {"topic": "devops", "source": "knowledge/devops/devops.txt"},
                ]],
                "distances": [[0.12, 0.18]],
            },
            {
                "ids": [["chunk-se-1"]],
                "documents": [["Software Engineering covers design, testing, and maintenance."]],
                "metadatas": [[
                    {
                        "topic": "software_engineering",
                        "source": "knowledge/software_engineering/se.txt",
                    }
                ]],
                "distances": [[0.14]],
            },
            {
                "ids": [["chunk-devops-1"]],
                "documents": [["DevOps helps teams automate delivery."]],
                "metadatas": [[
                    {"topic": "devops", "source": "knowledge/devops/devops.txt"}
                ]],
                "distances": [[0.11]],
            },
        ]
        mock_rerank_candidate_chunks.return_value = [
            {
                "id": "chunk-devops-1",
                "text": "DevOps helps teams automate delivery.",
                "metadata": {"topic": "devops", "source": "knowledge/devops/devops.txt"},
                "rerank_score": 9.8,
                "rerank_position": 1,
            },
            {
                "id": "chunk-devops-2",
                "text": "DevOps includes CI/CD and deployment automation.",
                "metadata": {"topic": "devops", "source": "knowledge/devops/devops.txt"},
                "rerank_score": 9.6,
                "rerank_position": 2,
            },
            {
                "id": "chunk-se-1",
                "text": "Software Engineering covers design, testing, and maintenance.",
                "metadata": {
                    "topic": "software_engineering",
                    "source": "knowledge/software_engineering/se.txt",
                },
                "rerank_score": 8.8,
                "rerank_position": 3,
            },
        ]
        mock_generate_answer.return_value = "Software Engineering and DevOps are closely related."

        result = ask_question(
            "What is the relation between Software Engineering and DevOps?"
        )

        self.assertTrue(result["comparison_question_detected"])
        self.assertEqual(
            result["comparison_terms"],
            ["software_engineering", "devops"],
        )
        self.assertEqual(result["retrieval_strategy"], "comparison_aware")
        self.assertEqual(
            result["unique_topics_diversified"],
            ["devops", "software_engineering"],
        )
        self.assertTrue(result["balanced_selection_applied"])
        self.assertEqual(
            result["expected_comparison_topics"],
            ["software_engineering", "devops"],
        )
        self.assertEqual(
            [chunk["id"] for chunk in result["retrieved_chunks_final"]],
            ["chunk-se-1", "chunk-devops-1", "chunk-devops-2"],
        )

    @patch("rag.services.rag_service.generate_answer")
    @patch("rag.services.rag_service.rerank_candidate_chunks")
    @patch("rag.services.rag_service.query_similar_chunks")
    @patch("rag.services.rag_service.generate_embedding")
    def test_ask_question_normalizes_alias_topics_for_balanced_selection(
        self,
        mock_generate_embedding,
        mock_query_similar_chunks,
        mock_rerank_candidate_chunks,
        mock_generate_answer,
    ):
        mock_generate_embedding.side_effect = [
            [0.1, 0.2],
            [0.3, 0.4],
            [0.5, 0.6],
        ]
        mock_query_similar_chunks.side_effect = [
            {
                "ids": [["chunk-gen-1"]],
                "documents": [["Generative AI creates text and images from learned patterns."]],
                "metadatas": [[{"topic": "GenerativeAI", "source": "knowledge/genai/ai.txt"}]],
                "distances": [[0.10]],
            },
            {
                "ids": [["chunk-gen-1"]],
                "documents": [["Generative AI creates text and images from learned patterns."]],
                "metadatas": [[{"topic": "GenerativeAI", "source": "knowledge/genai/ai.txt"}]],
                "distances": [[0.10]],
            },
            {
                "ids": [["chunk-ml-1"]],
                "documents": [["Machine Learning learns patterns from data."]],
                "metadatas": [[{"topic": "ML", "source": "knowledge/machine_learning/ml.txt"}]],
                "distances": [[0.12]],
            },
        ]
        mock_rerank_candidate_chunks.return_value = [
            {
                "id": "chunk-gen-1",
                "text": "Generative AI creates text and images from learned patterns.",
                "metadata": {"topic": "GenerativeAI", "source": "knowledge/genai/ai.txt"},
                "rerank_score": 9.5,
                "rerank_position": 1,
            },
            {
                "id": "chunk-ml-1",
                "text": "Machine Learning learns patterns from data.",
                "metadata": {"topic": "ML", "source": "knowledge/machine_learning/ml.txt"},
                "rerank_score": 9.0,
                "rerank_position": 2,
            },
        ]
        mock_generate_answer.return_value = "Generative AI builds on machine learning."

        result = ask_question("What is the relation between GenerativeAI and ML?")

        self.assertTrue(result["hybrid_search_enabled"])
        self.assertEqual(result["comparison_terms"], ["genai", "machine_learning"])
        self.assertEqual(
            result["expected_comparison_topics"],
            ["genai", "machine_learning"],
        )
        self.assertTrue(result["balanced_selection_applied"])
        self.assertEqual(result["unique_topics_final"], ["genai", "machine_learning"])


class HybridSearchTests(SimpleTestCase):
    def test_score_candidates_with_keywords_attaches_keyword_scores(self):
        result = score_candidates_with_keywords(
            "devops automation delivery",
            [
                {
                    "id": "chunk-devops",
                    "text": "DevOps uses CI/CD automation for software delivery.",
                    "metadata": {"topic": "devops"},
                },
                {
                    "id": "chunk-ml",
                    "text": "Machine Learning learns patterns from data.",
                    "metadata": {"topic": "machine_learning"},
                },
            ],
        )

        self.assertIn("keyword_score_raw", result[0])
        self.assertGreater(result[0]["keyword_score_raw"], result[1]["keyword_score_raw"])

    def test_apply_hybrid_scoring_combines_vector_and_keyword_scores(self):
        chunks = normalize_keyword_scores(
            [
                {
                    **chunk,
                    "keyword_score_raw": score,
                }
                for chunk, score in zip(
                    normalize_vector_scores(
                        [
                            {
                                "id": "chunk-a",
                                "text": "CI/CD automates delivery in DevOps.",
                                "metadata": {"topic": "devops"},
                                "distance": 0.10,
                            },
                            {
                                "id": "chunk-b",
                                "text": "Software engineering covers design and testing.",
                                "metadata": {"topic": "software_engineering"},
                                "distance": 0.30,
                            },
                        ]
                    ),
                    [3.0, 0.5],
                )
            ]
        )

        result = apply_hybrid_scoring(chunks, vector_weight=0.7, keyword_weight=0.3)

        self.assertEqual(result[0]["id"], "chunk-a")
        self.assertGreater(result[0]["hybrid_score"], result[1]["hybrid_score"])
        self.assertEqual(result[0]["hybrid_position"], 1)

    def test_rank_hybrid_candidates_filters_noisy_candidates_and_ranks_remaining_chunks(self):
        result = rank_hybrid_candidates(
            "machine learning",
            [
                {
                    "id": "chunk-noisy",
                    "text": "machine_learning",
                    "metadata": {"topic": "machine_learning"},
                    "distance": 0.05,
                },
                {
                    "id": "chunk-ml",
                    "text": "Machine Learning learns patterns from data.",
                    "metadata": {"topic": "machine_learning"},
                    "distance": 0.20,
                },
                {
                    "id": "chunk-genai",
                    "text": "Generative AI creates content from learned patterns.",
                    "metadata": {"topic": "genai"},
                    "distance": 0.25,
                },
            ],
        )

        self.assertEqual(result["filtered_out_chunk_ids"], ["chunk-noisy"])
        self.assertEqual(result["ranked_chunks"][0]["id"], "chunk-ml")
        self.assertIn("vector_score", result["ranked_chunks"][0])
        self.assertIn("keyword_score", result["ranked_chunks"][0])
        self.assertIn("hybrid_score", result["ranked_chunks"][0])


class DuplicateHandlingTests(SimpleTestCase):
    @patch("rag.services.chroma_service.get_collection")
    @patch("rag.services.chroma_service.generate_embedding")
    def test_add_note_chunks_skips_existing_stable_ids(
        self,
        mock_generate_embedding,
        mock_get_collection,
    ):
        source = "knowledge/devops/devops.txt"
        existing_chunk_id = _build_stable_chunk_id(source, 0, "Chunk A")

        class FakeCollection:
            def __init__(self):
                self.add_calls = []

            def get(self, ids=None, include=None, limit=None):
                return {"ids": [chunk_id for chunk_id in (ids or []) if chunk_id == existing_chunk_id]}

            def add(self, ids=None, documents=None, embeddings=None, metadatas=None):
                self.add_calls.append(
                    {
                        "ids": ids or [],
                        "documents": documents or [],
                        "embeddings": embeddings or [],
                        "metadatas": metadatas or [],
                    }
                )

        fake_collection = FakeCollection()
        mock_get_collection.return_value = fake_collection
        mock_generate_embedding.return_value = [0.1, 0.2]

        result = add_note_chunks(
            title="devops",
            chunks=["Chunk A", "Chunk B"],
            topic="devops",
            source=source,
        )

        self.assertEqual(result["total_chunks_generated"], 2)
        self.assertEqual(result["new_chunks_stored"], 1)
        self.assertEqual(result["duplicate_chunks_skipped"], 1)
        self.assertEqual(result["duplicate_ids"], [existing_chunk_id])
        self.assertEqual(len(fake_collection.add_calls), 1)
        self.assertEqual(len(fake_collection.add_calls[0]["ids"]), 1)
        self.assertEqual(mock_generate_embedding.call_count, 1)

    @patch("rag.services.rag_service.add_note_chunks")
    @patch("rag.services.rag_service.semantic_chunk_pipeline")
    def test_ingest_note_uses_semantic_chunk_pipeline(
        self,
        mock_semantic_chunk_pipeline,
        mock_add_note_chunks,
    ):
        mock_semantic_chunk_pipeline.return_value = [
            "Software Engineering focuses on design and maintenance.",
            "DevOps improves delivery through automation.",
        ]
        mock_add_note_chunks.return_value = {
            "collection": "study_notes_openai_text_embedding_3_small",
            "title": "se-devops",
            "topic": "software_engineering",
            "source": "manual",
            "total_chunks_generated": 2,
            "new_chunks_stored": 2,
            "duplicate_chunks_skipped": 0,
            "ids": ["chunk-1", "chunk-2"],
            "documents": mock_semantic_chunk_pipeline.return_value,
            "metadatas": [
                {"topic": "software_engineering", "source": "manual", "chunk_index": 0},
                {"topic": "software_engineering", "source": "manual", "chunk_index": 1},
            ],
            "duplicate_ids": [],
        }

        from rag.services.rag_service import ingest_note

        result = ingest_note(
            title="se-devops",
            content="Software Engineering and DevOps content.",
            topic="software_engineering",
            source="manual",
        )

        mock_semantic_chunk_pipeline.assert_called_once()
        self.assertEqual(result["chunking_strategy"], "semantic")
        self.assertEqual(result["total_chunks_generated"], 2)

    def test_normalize_chroma_results_deduplicates_ids_and_identical_text(self):
        query_results = {
            "ids": [["chunk-1", "chunk-1", "chunk-2"]],
            "documents": [[
                "Repeated text",
                "Repeated text",
                "Repeated text",
            ]],
            "metadatas": [[
                {"topic": "devops"},
                {"topic": "devops"},
                {"topic": "software_engineering"},
            ]],
            "distances": [[0.10, 0.11, 0.12]],
        }

        result = _normalize_chroma_results(query_results)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "chunk-1")

    def test_normalize_chroma_results_normalizes_topic_aliases(self):
        query_results = {
            "ids": [["chunk-1", "chunk-2"]],
            "documents": [["GenAI content", "ML content"]],
            "metadatas": [[
                {"topic": "GenerativeAI"},
                {"topic": "ML"},
            ]],
            "distances": [[0.10, 0.12]],
        }

        result = _normalize_chroma_results(query_results)

        self.assertEqual(result[0]["metadata"]["topic"], "genai")
        self.assertEqual(result[1]["metadata"]["topic"], "machine_learning")

    @patch("rag.services.chroma_cleanup_service.get_active_collection_name")
    @patch("rag.services.chroma_cleanup_service.get_collection_records")
    def test_cleanup_duplicate_chunks_dry_run_reports_duplicates(
        self,
        mock_get_collection_records,
        mock_get_active_collection_name,
    ):
        mock_get_active_collection_name.return_value = "study_notes_openai_text_embedding_3_small"
        mock_get_collection_records.return_value = {
            "ids": ["chunk-a", "chunk-b", "chunk-c"],
            "documents": [
                "Shared duplicate text",
                "Shared duplicate text",
                "Unique text",
            ],
            "metadatas": [
                {"source": "knowledge/devops/devops.txt", "chunk_index": 1},
                {"source": "knowledge/devops/devops.txt", "chunk_index": 1},
                {"source": "knowledge/genai/ai.txt", "chunk_index": 2},
            ],
        }

        result = cleanup_duplicate_chunks(dry_run=True)

        self.assertTrue(result["dry_run"])
        self.assertEqual(result["total_chunks_seen"], 3)
        self.assertEqual(result["duplicate_groups_found"], 1)
        self.assertEqual(result["duplicate_chunks_found"], 1)
        self.assertEqual(result["ids_to_delete"], ["chunk-b"])
        self.assertEqual(result["deleted_count"], 0)

    @patch("rag.services.chroma_cleanup_service.get_active_collection_name")
    @patch("rag.services.chroma_cleanup_service.delete_chunks_by_ids")
    @patch("rag.services.chroma_cleanup_service.get_collection_records")
    def test_cleanup_duplicate_chunks_deletes_when_not_dry_run(
        self,
        mock_get_collection_records,
        mock_delete_chunks_by_ids,
        mock_get_active_collection_name,
    ):
        mock_get_active_collection_name.return_value = "study_notes_openai_text_embedding_3_small"
        mock_delete_chunks_by_ids.return_value = 2
        mock_get_collection_records.return_value = {
            "ids": ["chunk-a", "chunk-b", "chunk-c"],
            "documents": [
                "Shared duplicate text",
                "Shared duplicate text",
                "Shared duplicate text",
            ],
            "metadatas": [
                {"source": "knowledge/devops/devops.txt", "chunk_index": 1},
                {"source": "knowledge/devops/devops.txt", "chunk_index": 1},
                {"source": "knowledge/devops/devops.txt", "chunk_index": 1},
            ],
        }

        result = cleanup_duplicate_chunks(dry_run=False)

        self.assertFalse(result["dry_run"])
        self.assertEqual(result["duplicate_groups_found"], 1)
        self.assertEqual(result["duplicate_chunks_found"], 2)
        self.assertEqual(result["deleted_count"], 2)
        mock_delete_chunks_by_ids.assert_called_once_with(["chunk-b", "chunk-c"])


class SharedPromptTests(SimpleTestCase):
    def test_format_chunks_includes_chunk_indices_and_topics(self):
        formatted = format_chunks(
            [
                {
                    "text": "Machine Learning learns patterns from data.",
                    "metadata": {"topic": "machine_learning"},
                },
                {
                    "text": "Deep Learning uses neural networks.",
                    "metadata": {"topic": "deep_learning"},
                },
            ]
        )

        self.assertIn("[CHUNK 1 | Topic: machine_learning]", formatted)
        self.assertIn("[CHUNK 2 | Topic: deep_learning]", formatted)
        self.assertIn("Machine Learning learns patterns from data.", formatted)
        self.assertIn("Deep Learning uses neural networks.", formatted)

    def test_build_rag_prompt_includes_role_context_instructions_and_question(self):
        prompt = build_rag_prompt(
            "What is the relation between Software Engineering and DevOps?",
            [
                {
                    "text": "Software Engineering focuses on designing and maintaining software.",
                    "metadata": {
                        "topic": "software_engineering",
                        "title": "se",
                        "source": "knowledge/software_engineering/se.txt",
                    },
                },
                {
                    "text": "DevOps improves collaboration between development and operations.",
                    "metadata": {
                        "topic": "devops",
                        "title": "devops",
                        "source": "knowledge/devops/devops.txt",
                    },
                },
            ],
            is_comparison=True,
        )

        self.assertIn("ROLE:", prompt)
        self.assertIn("CONTEXT:", prompt)
        self.assertIn("INSTRUCTIONS:", prompt)
        self.assertIn("QUESTION:", prompt)
        self.assertIn("Software Engineering", prompt)
        self.assertIn("DevOps", prompt)
        self.assertIn("use all provided chunks", prompt.lower())
        self.assertIn("this is a comparison question", prompt.lower())
        self.assertIn("both concepts are covered with balanced attention", prompt.lower())
        self.assertIn("**Explanation:**", prompt)
        self.assertIn("**Key Points:**", prompt)


class ProviderAnswerFlowTests(SimpleTestCase):
    @patch("rag.services.openai_service._get_openai_client")
    def test_openai_generate_answer_uses_shared_topic_extractor(self, mock_get_openai_client):
        mock_client = mock_get_openai_client.return_value
        mock_client.responses.create.return_value.output_text = "CI/CD means continuous integration and continuous deployment."

        from rag.services.openai_service import generate_answer

        result = generate_answer(
            "What is CI/CD?",
            [
                {
                    "text": "Continuous Integration means code is merged and tested frequently.",
                    "metadata": {"topic": "devops"},
                }
            ],
        )

        self.assertIn("continuous integration", result.lower())

    @patch("rag.services.rag_service.generate_answer")
    @patch("rag.services.rag_service.rerank_candidate_chunks")
    @patch("rag.services.rag_service.query_similar_chunks")
    @patch("rag.services.rag_service.generate_embedding")
    def test_ask_question_passes_is_comparison_flag_to_answer_generation(
        self,
        mock_generate_embedding,
        mock_query_similar_chunks,
        mock_rerank_candidate_chunks,
        mock_generate_answer,
    ):
        mock_generate_embedding.side_effect = [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
        mock_query_similar_chunks.side_effect = [
            {
                "ids": [["chunk-genai-1"]],
                "documents": [["GenAI can generate text, images, and other content."]],
                "metadatas": [[{"topic": "genai", "source": "knowledge/genai/ai.txt"}]],
                "distances": [[0.12]],
            },
            {
                "ids": [["chunk-genai-1"]],
                "documents": [["GenAI can generate text, images, and other content."]],
                "metadatas": [[{"topic": "genai", "source": "knowledge/genai/ai.txt"}]],
                "distances": [[0.12]],
            },
            {
                "ids": [["chunk-ml-1"]],
                "documents": [["Machine Learning learns patterns from data."]],
                "metadatas": [[{"topic": "machine_learning", "source": "knowledge/machine_learning/ml.txt"}]],
                "distances": [[0.14]],
            },
        ]
        mock_rerank_candidate_chunks.return_value = [
            {
                "id": "chunk-genai-1",
                "text": "GenAI can generate text, images, and other content.",
                "metadata": {"topic": "genai", "source": "knowledge/genai/ai.txt"},
                "rerank_score": 9.8,
                "rerank_position": 1,
            },
            {
                "id": "chunk-ml-1",
                "text": "Machine Learning learns patterns from data.",
                "metadata": {
                    "topic": "machine_learning",
                    "source": "knowledge/machine_learning/ml.txt",
                },
                "rerank_score": 9.0,
                "rerank_position": 2,
            },
        ]
        mock_generate_answer.return_value = "GenAI builds on machine learning methods."

        ask_question("What is the relation between GenAI and Machine Learning?")

        mock_generate_answer.assert_called_once()
        _, kwargs = mock_generate_answer.call_args
        self.assertTrue(kwargs["is_comparison"])

    @patch.dict(
        os.environ,
        {
            "RAG_ENABLE_HYBRID_SEARCH": "true",
            "RAG_HYBRID_VECTOR_WEIGHT": "0.7",
            "RAG_HYBRID_KEYWORD_WEIGHT": "0.3",
            "RAG_HYBRID_CANDIDATE_K": "8",
        },
        clear=False,
    )
    @patch("rag.services.rag_service.generate_answer")
    @patch("rag.services.rag_service.rerank_candidate_chunks")
    @patch("rag.services.rag_service.rank_hybrid_candidates")
    @patch("rag.services.rag_service.query_similar_chunks")
    @patch("rag.services.rag_service.generate_embedding")
    def test_ask_question_exposes_hybrid_scoring_fields(
        self,
        mock_generate_embedding,
        mock_query_similar_chunks,
        mock_rank_hybrid_candidates,
        mock_rerank_candidate_chunks,
        mock_generate_answer,
    ):
        mock_generate_embedding.return_value = [0.1, 0.2]
        mock_query_similar_chunks.return_value = {
            "ids": [["chunk-1", "chunk-2"]],
            "documents": [[
                "CI/CD automates builds and deployments in DevOps.",
                "Machine Learning learns from data.",
            ]],
            "metadatas": [[
                {"topic": "devops", "source": "knowledge/devops/devops.txt"},
                {"topic": "machine_learning", "source": "knowledge/machine_learning/ml.txt"},
            ]],
            "distances": [[0.11, 0.24]],
        }
        mock_rank_hybrid_candidates.return_value = {
            "ranked_chunks": [
                {
                    "id": "chunk-1",
                    "text": "CI/CD automates builds and deployments in DevOps.",
                    "metadata": {"topic": "devops"},
                    "distance": 0.11,
                    "vector_score": 1.0,
                    "keyword_score": 1.0,
                    "hybrid_score": 1.0,
                    "hybrid_position": 1,
                },
                {
                    "id": "chunk-2",
                    "text": "Machine Learning learns from data.",
                    "metadata": {"topic": "machine_learning"},
                    "distance": 0.24,
                    "vector_score": 0.0,
                    "keyword_score": 0.0,
                    "hybrid_score": 0.0,
                    "hybrid_position": 2,
                },
            ],
            "filtered_out_chunk_ids": [],
        }
        mock_rerank_candidate_chunks.return_value = mock_rank_hybrid_candidates.return_value[
            "ranked_chunks"
        ]
        mock_generate_answer.return_value = "CI/CD is a DevOps practice."

        result = ask_question("What is CI/CD?")

        self.assertTrue(result["hybrid_search_enabled"])
        self.assertFalse(result["hybrid_search_fallback_used"])
        self.assertEqual(result["hybrid_vector_weight"], 0.7)
        self.assertEqual(result["hybrid_keyword_weight"], 0.3)
        self.assertEqual(result["hybrid_candidate_count"], 2)
        self.assertEqual(result["retrieved_chunks_hybrid_ranked"][0]["id"], "chunk-1")
        self.assertEqual(result["retrieved_chunks_hybrid_ranked"][0]["hybrid_score"], 1.0)
