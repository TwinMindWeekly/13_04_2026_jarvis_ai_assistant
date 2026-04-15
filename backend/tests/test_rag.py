"""Tests for RAG components: LocalEmbeddings, VectorStore, DocumentParser, RagSearchTool."""

import asyncio
import os
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _inject_module(path: str, **attrs):
    """Inject a fake module into sys.modules with given attributes."""
    mod = types.ModuleType(path)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[path] = mod
    return mod


def _remove_module(path: str):
    sys.modules.pop(path, None)


# ---------------------------------------------------------------------------
# LocalEmbeddings
# ---------------------------------------------------------------------------


class TestLocalEmbeddings:
    """Tests for LocalEmbeddings using a mocked SentenceTransformer."""

    def _make_mock_st(self, dimension: int = 4):
        """Return a mock SentenceTransformer whose encode() returns numpy arrays."""
        import numpy as np

        mock_model = MagicMock()
        mock_model.encode = MagicMock(
            side_effect=lambda texts, **kw: np.array(
                [[float(i) / 10.0] * dimension for i in range(len(texts))]
            )
        )
        return mock_model

    def _inject_st(self, mock_model):
        """Inject mock SentenceTransformer into sys.modules."""
        mock_cls = MagicMock(return_value=mock_model)
        _inject_module("sentence_transformers", SentenceTransformer=mock_cls)
        return mock_cls

    def setup_method(self):
        """Reset singleton before each test."""
        from app.rag import embeddings as emb_mod
        emb_mod.LocalEmbeddings._instance = None

    def teardown_method(self):
        """Clean up singleton and injected modules."""
        from app.rag import embeddings as emb_mod
        emb_mod.LocalEmbeddings._instance = None
        _remove_module("sentence_transformers")

    @pytest.mark.asyncio
    async def test_embed_documents_returns_list_of_vectors(self):
        from app.rag.embeddings import LocalEmbeddings

        mock_model = self._make_mock_st(dimension=4)
        self._inject_st(mock_model)

        emb = LocalEmbeddings("test-model")
        result = await emb.embed_documents(["hello", "world"])

        assert isinstance(result, list)
        assert len(result) == 2
        assert isinstance(result[0], list)
        assert len(result[0]) == 4

    @pytest.mark.asyncio
    async def test_embed_documents_empty_returns_empty(self):
        from app.rag.embeddings import LocalEmbeddings

        emb = LocalEmbeddings()
        result = await emb.embed_documents([])
        assert result == []

    @pytest.mark.asyncio
    async def test_embed_query_returns_single_vector(self):
        from app.rag.embeddings import LocalEmbeddings

        mock_model = self._make_mock_st(dimension=4)
        self._inject_st(mock_model)

        emb = LocalEmbeddings("test-model")
        result = await emb.embed_query("search term")

        assert isinstance(result, list)
        assert len(result) == 4

    @pytest.mark.asyncio
    async def test_singleton_model_loaded_once(self):
        from app.rag.embeddings import LocalEmbeddings

        mock_model = self._make_mock_st(dimension=4)
        mock_cls = self._inject_st(mock_model)

        emb = LocalEmbeddings("test-model")
        await emb.embed_documents(["a"])
        await emb.embed_documents(["b"])

        # SentenceTransformer constructor called exactly once (singleton)
        assert mock_cls.call_count == 1


# ---------------------------------------------------------------------------
# VectorStore
# ---------------------------------------------------------------------------


class TestVectorStore:
    """Tests for VectorStore with a mocked chromadb.PersistentClient."""

    def _make_mock_collection(self, doc_count: int = 3):
        """Return a mock ChromaDB collection."""
        mock_col = MagicMock()
        mock_col.count = MagicMock(return_value=doc_count)
        mock_col.upsert = MagicMock()
        mock_col.delete = MagicMock()
        mock_col.query = MagicMock(return_value={
            "documents": [["chunk A", "chunk B"]],
            "metadatas": [[{"filename": "a.txt"}, {"filename": "b.txt"}]],
            "distances": [[0.1, 0.3]],
        })
        return mock_col

    def _make_mock_client(self, collection):
        mock_client = MagicMock()
        mock_client.get_or_create_collection = MagicMock(return_value=collection)
        mock_client.get_collection = MagicMock(return_value=collection)
        mock_client.list_collections = MagicMock(return_value=[
            MagicMock(name="jarvis_default")
        ])
        mock_client.delete_collection = MagicMock()
        return mock_client

    @pytest.mark.asyncio
    async def test_add_documents_calls_upsert(self):
        from app.rag.vector_store import VectorStore

        mock_col = self._make_mock_collection()
        mock_client = self._make_mock_client(mock_col)

        mock_embeddings = AsyncMock()
        mock_embeddings.embed_documents = AsyncMock(return_value=[[0.1, 0.2], [0.3, 0.4]])

        with patch("chromadb.PersistentClient", return_value=mock_client), \
             patch("app.rag.vector_store.LocalEmbeddings", return_value=mock_embeddings):
            store = VectorStore()
            count = await store.add_documents(
                "test_collection",
                ["chunk 1", "chunk 2"],
                [{"source": "a.txt"}, {"source": "a.txt"}],
                ["id_0", "id_1"],
            )

        assert count == 2
        mock_col.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_documents_empty_returns_zero(self):
        from app.rag.vector_store import VectorStore

        mock_col = self._make_mock_collection()
        mock_client = self._make_mock_client(mock_col)

        mock_embeddings = AsyncMock()

        with patch("chromadb.PersistentClient", return_value=mock_client), \
             patch("app.rag.vector_store.LocalEmbeddings", return_value=mock_embeddings):
            store = VectorStore()
            count = await store.add_documents("test_collection", [], [], [])

        assert count == 0
        mock_col.upsert.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_returns_formatted_results(self):
        from app.rag.vector_store import VectorStore

        mock_col = self._make_mock_collection(doc_count=2)
        mock_client = self._make_mock_client(mock_col)

        mock_embeddings = AsyncMock()
        mock_embeddings.embed_query = AsyncMock(return_value=[0.1, 0.2])

        with patch("chromadb.PersistentClient", return_value=mock_client), \
             patch("app.rag.vector_store.LocalEmbeddings", return_value=mock_embeddings):
            store = VectorStore()
            results = await store.search("test_collection", "my query", top_k=2)

        assert isinstance(results, list)
        assert len(results) == 2
        assert results[0]["content"] == "chunk A"
        assert results[0]["score"] == round(1.0 - 0.1, 4)
        assert "metadata" in results[0]

    @pytest.mark.asyncio
    async def test_search_returns_empty_when_collection_missing(self):
        from app.rag.vector_store import VectorStore

        mock_client = MagicMock()
        mock_client.get_collection = MagicMock(side_effect=Exception("not found"))

        mock_embeddings = AsyncMock()

        with patch("chromadb.PersistentClient", return_value=mock_client), \
             patch("app.rag.vector_store.LocalEmbeddings", return_value=mock_embeddings):
            store = VectorStore()
            results = await store.search("missing_collection", "query")

        assert results == []

    @pytest.mark.asyncio
    async def test_search_returns_empty_when_collection_empty(self):
        from app.rag.vector_store import VectorStore

        mock_col = self._make_mock_collection(doc_count=0)
        mock_client = self._make_mock_client(mock_col)
        mock_embeddings = AsyncMock()

        with patch("chromadb.PersistentClient", return_value=mock_client), \
             patch("app.rag.vector_store.LocalEmbeddings", return_value=mock_embeddings):
            store = VectorStore()
            results = await store.search("test_collection", "query")

        assert results == []

    def test_list_collections(self):
        from app.rag.vector_store import VectorStore

        mock_col_obj = MagicMock()
        mock_col_obj.name = "jarvis_default"
        mock_client = MagicMock()
        mock_client.list_collections = MagicMock(return_value=[mock_col_obj])

        mock_embeddings = MagicMock()

        with patch("chromadb.PersistentClient", return_value=mock_client), \
             patch("app.rag.vector_store.LocalEmbeddings", return_value=mock_embeddings):
            store = VectorStore()
            names = store.list_collections()

        assert names == ["jarvis_default"]

    def test_delete_collection(self):
        from app.rag.vector_store import VectorStore

        mock_client = MagicMock()
        mock_client.delete_collection = MagicMock()
        mock_embeddings = MagicMock()

        with patch("chromadb.PersistentClient", return_value=mock_client), \
             patch("app.rag.vector_store.LocalEmbeddings", return_value=mock_embeddings):
            store = VectorStore()
            store.delete_collection("test_collection")

        mock_client.delete_collection.assert_called_once_with(name="test_collection")


# ---------------------------------------------------------------------------
# DocumentParser
# ---------------------------------------------------------------------------


class TestDocumentParser:
    """Tests for DocumentParser with real temp files (txt/md) and mocked heavy libs."""

    @pytest.mark.asyncio
    async def test_parse_txt_file(self):
        from app.rag.document_parser import DocumentParser

        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w",
                                         encoding="utf-8", delete=False) as f:
            f.write("Hello world. This is a test document.\n" * 5)
            tmp_path = f.name

        try:
            parser = DocumentParser()
            chunks = await parser.parse_file(tmp_path)
            assert isinstance(chunks, list)
            assert len(chunks) >= 1
            assert "content" in chunks[0]
            assert "metadata" in chunks[0]
            assert isinstance(chunks[0]["content"], str)
            assert len(chunks[0]["content"]) > 0
        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    async def test_parse_md_file(self):
        from app.rag.document_parser import DocumentParser

        with tempfile.NamedTemporaryFile(suffix=".md", mode="w",
                                         encoding="utf-8", delete=False) as f:
            f.write("# Title\n\nSome markdown content.\n\n## Section\n\nMore text here.\n")
            tmp_path = f.name

        try:
            parser = DocumentParser()
            chunks = await parser.parse_file(tmp_path)
            assert len(chunks) >= 1
            all_content = " ".join(c["content"] for c in chunks)
            assert "Title" in all_content or "markdown" in all_content
        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    async def test_parse_empty_txt_returns_empty(self):
        from app.rag.document_parser import DocumentParser

        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w",
                                         encoding="utf-8", delete=False) as f:
            f.write("   \n  \n  ")
            tmp_path = f.name

        try:
            parser = DocumentParser()
            chunks = await parser.parse_file(tmp_path)
            assert chunks == []
        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    async def test_parse_unsupported_falls_back_to_text(self):
        """Unknown extensions should be read as plain text without error."""
        from app.rag.document_parser import DocumentParser

        with tempfile.NamedTemporaryFile(suffix=".log", mode="w",
                                         encoding="utf-8", delete=False) as f:
            f.write("Some log content here.\n")
            tmp_path = f.name

        try:
            parser = DocumentParser()
            chunks = await parser.parse_file(tmp_path)
            assert len(chunks) >= 1
        finally:
            os.unlink(tmp_path)

    def test_chunk_elements_splits_long_text(self):
        from app.rag.document_parser import DocumentParser

        parser = DocumentParser()
        long_text = "word " * 300  # ~1500 chars, exceeds 1000-char limit
        elements = [{"text": long_text, "page_number": 1, "element_type": "NarrativeText"}]
        chunks = parser._chunk_elements(elements, max_chars=1000)
        assert len(chunks) >= 2
        for chunk in chunks:
            assert len(chunk["content"]) <= 1000

    def test_chunk_elements_assigns_chunk_index(self):
        from app.rag.document_parser import DocumentParser

        parser = DocumentParser()
        elements = [
            {"text": "First element.", "page_number": 1, "element_type": "NarrativeText"},
            {"text": "Second element.", "page_number": 2, "element_type": "NarrativeText"},
        ]
        chunks = parser._chunk_elements(elements)
        for i, chunk in enumerate(chunks):
            assert chunk["metadata"]["chunk_index"] == i

    def test_supported_extensions_set(self):
        from app.rag.document_parser import DocumentParser

        assert ".pdf" in DocumentParser.SUPPORTED_EXTENSIONS
        assert ".docx" in DocumentParser.SUPPORTED_EXTENSIONS
        assert ".txt" in DocumentParser.SUPPORTED_EXTENSIONS
        assert ".md" in DocumentParser.SUPPORTED_EXTENSIONS
        assert ".pptx" in DocumentParser.SUPPORTED_EXTENSIONS
        assert ".xlsx" in DocumentParser.SUPPORTED_EXTENSIONS


# ---------------------------------------------------------------------------
# RagSearchTool
# ---------------------------------------------------------------------------


class TestRagSearchTool:
    """Tests for RagSearchTool with a mocked VectorStore."""

    @pytest.mark.asyncio
    async def test_execute_returns_results(self):
        from app.tools.rag_search import RagSearchTool

        mock_results = [
            {"content": "relevant chunk", "metadata": {"filename": "doc.txt"}, "score": 0.95},
        ]
        mock_store = AsyncMock()
        mock_store.search = AsyncMock(return_value=mock_results)

        # VectorStore is imported lazily inside execute(); patch at its definition site
        with patch("app.rag.vector_store.VectorStore", return_value=mock_store):
            tool = RagSearchTool()
            result = await tool.execute(query="test query", top_k=3)

        assert result.success is True
        assert result.data == mock_results
        assert result.metadata["count"] == 1
        assert result.metadata["query"] == "test query"

    @pytest.mark.asyncio
    async def test_execute_no_results_returns_message(self):
        from app.tools.rag_search import RagSearchTool

        mock_store = AsyncMock()
        mock_store.search = AsyncMock(return_value=[])

        with patch("app.rag.vector_store.VectorStore", return_value=mock_store):
            tool = RagSearchTool()
            result = await tool.execute(query="unknown topic")

        assert result.success is True
        assert result.data == "No matching documents found."
        assert result.metadata["count"] == 0

    @pytest.mark.asyncio
    async def test_execute_handles_exception(self):
        from app.tools.rag_search import RagSearchTool

        # Patch chromadb so VectorStore instantiation itself raises
        with patch("chromadb.PersistentClient", side_effect=RuntimeError("db error")):
            tool = RagSearchTool()
            result = await tool.execute(query="something")

        assert result.success is False
        assert "db error" in result.error

    def test_tool_attributes(self):
        from app.tools.rag_search import RagSearchTool

        tool = RagSearchTool()
        assert tool.name == "rag_search"
        assert isinstance(tool.description, str)
        assert len(tool.description) > 0
        assert "properties" in tool.parameters
        assert "query" in tool.parameters["properties"]
        assert tool.DEFAULT_COLLECTION == "jarvis_default"
