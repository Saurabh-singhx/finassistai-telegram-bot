import uuid
from app.config import settings

import fitz  # pymupdf
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.documents import Document
from app.services.llm_service import embed_query, embed_text
from google import genai

client = genai.Client(api_key=settings.GOOGLE_API_KEY)

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 150


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return [c.strip() for c in chunks if c.strip()]


async def ingest_document(
    db: AsyncSession, user_id: uuid.UUID, text: str, source_type: str, filename: str | None = None
) -> int:
    """Chunk, embed, and store a document. Returns number of chunks stored."""
    chunks = chunk_text(text)
    for idx, chunk in enumerate(chunks):
        embedding = await embed_text(chunk)
        db.add(
            Document(
                user_id=user_id,
                source_type=source_type,
                filename=filename,
                chunk_index=idx,
                content=chunk,
                embedding=embedding,
            )
        )
    await db.flush()
    return len(chunks)


async def search_similar(db: AsyncSession, user_id: uuid.UUID, query: str, k: int = 4) -> list[Document]:
    query_embedding = await embed_query(query)
    result = await db.execute(
        select(Document)
        .where(Document.user_id == user_id)
        .order_by(Document.embedding.cosine_distance(query_embedding))
        .limit(k)
    )
    return list(result.scalars().all())


async def extract_image_text(
    file_bytes: bytes,
    mime_type: str = "image/jpeg",
) -> str:
    response = client.models.generate_content(
        model=settings.LLM_MODEL,
        contents=[
            {
                "inline_data": {
                    "mime_type": mime_type,
                    "data": file_bytes,
                }
            },
            "Transcribe any text visible in this image. "
            "If it's a chart or table, describe the key data points plainly."
            "reply with only the extracted text, nothing else.",
        ],
    )

    return response.text


async def transcribe_voice(
    file_bytes: bytes,
    mime_type: str = "audio/ogg",
) -> str:
    response = client.models.generate_content(
        model=settings.LLM_MODEL,
        contents=[
            {
                "inline_data": {
                    "mime_type": mime_type,
                    "data": file_bytes,
                }
            },
            "Transcribe this audio to plain text, nothing else.",
        ],
    )

    return response.text

async def extract_pdf_text(file_bytes: bytes) -> str:
    """Extracts text from a PDF. For pages with no text layer (scanned pages),
    rasterizes that page to an image and OCRs it via Gemini vision instead."""
    pages_text = []
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        for page in doc:
            text = page.get_text().strip()
            if text:
                pages_text.append(text)
            else:
                pix = page.get_pixmap(dpi=200)
                image_bytes = pix.tobytes("png")
                ocr_text = await extract_image_text(image_bytes, mime_type="image/png")
                pages_text.append(ocr_text)
    return "\n".join(pages_text)
