"""Executable first-version PDF RAG pipeline."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from paper_research_copilot.config import Settings
from paper_research_copilot.domain import (
    AcquisitionBudget,
    Answer,
    CorpusCatalog,
    IngestionSummary,
    RetrievedChunk,
)
from paper_research_copilot.ingestion import (
    AcademicAcquisitionService,
    CorpusPreparer,
    DynamicIngestionService,
    FastParserRouter,
    PageAwareChunker,
    PdfParser,
    PreparedCorpus,
    PreparedPaper,
)
from paper_research_copilot.integrations import (
    EmbeddingProvider,
    OpenAICompatibleChatProvider,
    SiliconFlowEmbeddingProvider,
)
from paper_research_copilot.integrations.scholarly import (
    ArxivSearchProvider,
    BoundedPaperDownloader,
)
from paper_research_copilot.reporting import AnswerGenerator
from paper_research_copilot.retrieval import (
    CandidateRetriever,
    DenseRetriever,
    QdrantVectorStore,
    RetrievalMode,
    RetrieverFactory,
)
from paper_research_copilot.storage import AcquisitionRepository


@dataclass(frozen=True)
class RetrievalRuntime:
    """Resources required for retrieval-only commands."""

    embeddings: EmbeddingProvider
    retrievers: RetrieverFactory
    vector_store: QdrantVectorStore

    def retriever_for(self, mode: RetrievalMode | str) -> CandidateRetriever:
        return self.retrievers.get(mode)

    def retrieve(
        self,
        question: str,
        top_k: int,
        mode: RetrievalMode | str,
    ) -> tuple[RetrievedChunk, ...]:
        return self.retrievers.retrieve(question, top_k, mode)

    def close(self) -> None:
        self.vector_store.close()


class BaseRagPipeline:
    def __init__(
        self,
        parser: PdfParser,
        chunker: PageAwareChunker,
        embeddings: EmbeddingProvider,
        vector_store: QdrantVectorStore,
        retrievers: RetrieverFactory,
        answer_generator: AnswerGenerator,
        default_top_k: int,
    ) -> None:
        self._parser = parser
        self._chunker = chunker
        self._embeddings = embeddings
        self._vector_store = vector_store
        self._retrievers = retrievers
        self._answer_generator = answer_generator
        self._default_top_k = default_top_k

    def ingest(self, pdf_paths: Sequence[Path]) -> IngestionSummary:
        document_count = 0
        page_count = 0
        chunk_count = 0

        for pdf_path in pdf_paths:
            document = self._parser.parse(pdf_path)
            chunks = self._chunker.split(document)
            if not chunks:
                raise ValueError(f"PDF produced no chunks: {pdf_path}")
            vectors = self._embeddings.embed([chunk.text for chunk in chunks])
            self._vector_store.upsert(chunks, vectors)
            document_count += 1
            page_count += document.metadata.page_count
            chunk_count += len(chunks)

        return IngestionSummary(
            document_count=document_count,
            page_count=page_count,
            chunk_count=chunk_count,
        )

    def ask(
        self,
        question: str,
        top_k: int | None = None,
        retrieval_mode: RetrievalMode | str = RetrievalMode.EVIDENCE,
    ) -> Answer:
        evidence = self._retrievers.retrieve(
            question,
            top_k or self._default_top_k,
            retrieval_mode,
        )
        if not evidence:
            raise LookupError("No evidence found. Ingest at least one PDF before asking questions.")
        return self._answer_generator.generate(question, evidence)

    def close(self) -> None:
        self._vector_store.close()


class CorpusIngestionPipeline:
    """Prepare and replace a complete versioned corpus in Qdrant."""

    def __init__(
        self,
        preparer: CorpusPreparer,
        embeddings: EmbeddingProvider,
        vector_store: QdrantVectorStore,
    ) -> None:
        self._preparer = preparer
        self._embeddings = embeddings
        self._vector_store = vector_store

    def prepare(self, catalog: CorpusCatalog) -> PreparedCorpus:
        return self._preparer.prepare(catalog)

    def ingest(
        self,
        prepared: PreparedCorpus,
        progress: Callable[[PreparedPaper, int, int], None] | None = None,
    ) -> IngestionSummary:
        total = len(prepared.papers)
        for index, paper in enumerate(prepared.papers, start=1):
            vectors = self._embeddings.embed([chunk.text for chunk in paper.chunks])
            replacement_filter: dict[str, str | int | bool] = {
                "corpus_id": prepared.catalog.spec.corpus_id,
                "corpus_version": prepared.catalog.spec.version,
                "paper_id": paper.asset.spec.paper_id,
                "chunking_version": paper.chunks[0].chunking_version,
            }
            self._vector_store.replace_by_metadata(
                paper.chunks,
                vectors,
                replacement_filter,
            )
            indexed_count = self._vector_store.count(replacement_filter)
            if indexed_count != len(paper.chunks):
                raise RuntimeError(
                    f"Qdrant count mismatch for {paper.asset.spec.paper_id}: "
                    f"expected {len(paper.chunks)}, found {indexed_count}"
                )
            if progress:
                progress(paper, index, total)

        return IngestionSummary(
            document_count=len(prepared.papers),
            page_count=sum(paper.document.metadata.page_count for paper in prepared.papers),
            chunk_count=len(prepared.chunks),
            collection_name=self._vector_store.collection_name,
            corpus_id=prepared.catalog.spec.corpus_id,
            corpus_version=prepared.catalog.spec.version,
        )

    def count(self, prepared: PreparedCorpus) -> int:
        return self._vector_store.count(
            {
                "corpus_id": prepared.catalog.spec.corpus_id,
                "corpus_version": prepared.catalog.spec.version,
                "chunking_version": prepared.chunks[0].chunking_version,
            }
        )

    def close(self) -> None:
        self._vector_store.close()


def build_pipeline(settings: Settings) -> BaseRagPipeline:
    llm_url, llm_key = settings.require_llm_credentials()
    retrieval_runtime = build_retrieval_runtime(settings)
    chat_provider = OpenAICompatibleChatProvider(
        base_url=llm_url,
        api_key=llm_key,
        model=settings.deepseek_model,
        max_tokens=settings.answer_max_tokens,
    )
    return BaseRagPipeline(
        parser=PdfParser(),
        chunker=PageAwareChunker(
            chunk_size=settings.chunk_size_chars,
            overlap=settings.chunk_overlap_chars,
            chunking_version=settings.chunking_version,
        ),
        embeddings=retrieval_runtime.embeddings,
        vector_store=retrieval_runtime.vector_store,
        retrievers=retrieval_runtime.retrievers,
        answer_generator=AnswerGenerator(chat_provider),
        default_top_k=settings.retrieval_top_k,
    )


def build_retrieval_runtime(
    settings: Settings,
    collection_name: str | None = None,
) -> RetrievalRuntime:
    embedding_url, embedding_key = settings.require_embedding_credentials()
    embeddings = SiliconFlowEmbeddingProvider(
        base_url=embedding_url,
        api_key=embedding_key,
        model=settings.siliconflow_embedding_model,
        dimension=settings.embedding_dimension,
    )
    vector_store = QdrantVectorStore(
        collection_name=collection_name or settings.qdrant_collection,
        dimension=settings.embedding_dimension,
        path=None if settings.qdrant_url else settings.resolved_qdrant_path(),
        url=settings.qdrant_url,
        api_key=(settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None),
    )
    dense_retriever = DenseRetriever(embeddings, vector_store)
    return RetrievalRuntime(
        embeddings=embeddings,
        retrievers=RetrieverFactory(dense_retriever, vector_store.list_chunks),
        vector_store=vector_store,
    )


def build_corpus_ingestion_pipeline(
    settings: Settings,
    collection_name: str | None = None,
) -> CorpusIngestionPipeline:
    runtime = build_retrieval_runtime(settings, collection_name)
    return CorpusIngestionPipeline(
        preparer=CorpusPreparer(
            parser=PdfParser(),
            chunker=PageAwareChunker(
                chunk_size=settings.chunk_size_chars,
                overlap=settings.chunk_overlap_chars,
                chunking_version=settings.chunking_version,
            ),
        ),
        embeddings=runtime.embeddings,
        vector_store=runtime.vector_store,
    )


def build_dynamic_acquisition_service(
    settings: Settings,
    repository: AcquisitionRepository,
) -> AcademicAcquisitionService:
    """Build the bounded Phase 4 pipeline without changing the curated collection."""

    embedding_url, embedding_key = settings.require_embedding_credentials()
    embeddings = SiliconFlowEmbeddingProvider(
        base_url=embedding_url,
        api_key=embedding_key,
        model=settings.siliconflow_embedding_model,
        dimension=settings.embedding_dimension,
    )
    vector_store = QdrantVectorStore(
        collection_name=settings.dynamic_qdrant_collection,
        dimension=settings.embedding_dimension,
        path=(
            None
            if settings.qdrant_url
            else settings.resolved_dynamic_qdrant_path()
        ),
        url=settings.qdrant_url,
        api_key=(
            settings.qdrant_api_key.get_secret_value()
            if settings.qdrant_api_key
            else None
        ),
    )
    search = ArxivSearchProvider(api_url=settings.arxiv_api_url)
    downloader = BoundedPaperDownloader(
        settings.resolved_dynamic_assets_path(),
        max_pdf_bytes=settings.acquisition_max_pdf_bytes,
    )
    ingestion = DynamicIngestionService(
        repository,
        downloader,
        FastParserRouter(),
        PageAwareChunker(
            chunk_size=settings.chunk_size_chars,
            overlap=settings.chunk_overlap_chars,
            chunking_version=settings.chunking_version,
        ),
        embeddings,
        vector_store,
        max_chunks=settings.acquisition_max_dynamic_chunks,
        index_version=(
            f"{settings.siliconflow_embedding_model}:{settings.chunking_version}"
        ),
    )
    return AcademicAcquisitionService(
        search,
        ingestion,
        repository,
        budget=AcquisitionBudget(
            candidates_per_query=settings.acquisition_candidates_per_query,
            max_downloads=settings.acquisition_max_downloads,
            max_pdf_bytes=settings.acquisition_max_pdf_bytes,
            max_dynamic_chunks=settings.acquisition_max_dynamic_chunks,
        ),
        close_callbacks=(search.close, downloader.close, vector_store.close),
    )
