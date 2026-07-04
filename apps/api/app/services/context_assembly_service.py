from __future__ import annotations

from apps.api.app.domain.retrieval import AssembledContext, Citation, RetrievedChunk


class ContextAssemblyService:
    def assemble(
        self,
        *,
        chunks: list[RetrievedChunk],
        citations: list[Citation],
        max_context_characters: int = 6000,
    ) -> AssembledContext:
        if not chunks:
            return AssembledContext(
                text="",
                citations=[],
                chunk_count=0,
                truncated=False,
            )

        seen_chunk_ids: set[str] = set()
        sections: list[str] = []
        accumulated_length = 0
        truncated = False

        for chunk in chunks:
            if chunk.chunk_id in seen_chunk_ids:
                continue
            seen_chunk_ids.add(chunk.chunk_id)

            title = chunk.document_title or chunk.document_id
            page_suffix = f" | page={chunk.page_number}" if chunk.page_number is not None else ""
            section = (
                f"[SOURCE document_id={chunk.document_id} title={title} chunk_id={chunk.chunk_id}"
                f"{page_suffix} score={chunk.score:.4f}]\n"
                f"{chunk.text}"
            )

            if sections and accumulated_length + len(section) + 2 > max_context_characters:
                truncated = True
                break

            sections.append(section)
            accumulated_length += len(section) + 2

        selected_citations = [citation for citation in citations if citation.chunk_id in seen_chunk_ids]

        return AssembledContext(
            text="\n\n".join(sections),
            citations=selected_citations,
            chunk_count=len(sections),
            truncated=truncated,
        )
