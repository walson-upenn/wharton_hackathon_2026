
from __future__ import annotations

import ast
import math
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

import numpy as np
import pandas as pd
from openai import OpenAI
from pydantic import BaseModel, Field


# ----------------------------
# Text helpers
# ----------------------------

_SENTENCE_SPLIT_REGEX = re.compile(r"(?<=[.!?。！？])\s+|\n+")


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def humanize_amenity_name(text: str) -> str:
    text = str(text).strip()
    if not text:
        return text
    text = text.replace("_", " ").replace("-", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_for_match(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[_\-]+", " ", text)
    text = re.sub(r"[^a-z0-9\s/]", " ", text)
    return normalize_whitespace(text)


def is_missing(value) -> bool:
    return value is None or pd.isna(value)


def parse_listlike(value) -> list[str]:
    if is_missing(value):
        return []
    if isinstance(value, list):
        return [normalize_whitespace(str(v)) for v in value if normalize_whitespace(str(v))]
    raw = str(value).strip()
    if not raw:
        return []
    try:
        parsed = ast.literal_eval(raw)
        if isinstance(parsed, list):
            return [normalize_whitespace(str(v)) for v in parsed if normalize_whitespace(str(v))]
    except Exception:
        pass
    return [normalize_whitespace(raw)]


def split_review_into_chunks(title: str | None, review_text: str | None, max_chars: int = 320) -> list[str]:
    """
    Lightweight multilingual-ish sentence splitter using punctuation and newlines.
    Keeps chunks short to reduce retrieval drift and verifier cost.
    """
    pieces: list[str] = []

    if not is_missing(title) and str(title).strip():
        pieces.append(normalize_whitespace(str(title)))

    if not is_missing(review_text) and str(review_text).strip():
        raw_sentences = [
            normalize_whitespace(s)
            for s in _SENTENCE_SPLIT_REGEX.split(str(review_text))
            if normalize_whitespace(s)
        ]
        current = ""
        for sentence in raw_sentences:
            candidate = sentence if not current else f"{current} {sentence}"
            if len(candidate) <= max_chars:
                current = candidate
            else:
                if current:
                    pieces.append(current)
                if len(sentence) <= max_chars:
                    current = sentence
                else:
                    # Fall back to crude fixed-width chunking for very long runs.
                    for i in range(0, len(sentence), max_chars):
                        pieces.append(sentence[i : i + max_chars])
                    current = ""
        if current:
            pieces.append(current)

    seen: set[str] = set()
    out: list[str] = []
    for piece in pieces:
        key = piece.lower()
        if key not in seen:
            out.append(piece)
            seen.add(key)
    return out


# ----------------------------
# Amenity catalog
# ----------------------------

AMENITY_LIST_COLUMNS = ["popular_amenities_list"]
AMENITY_PREFIX = "property_amenity_"


@dataclass
class AmenityRecord:
    amenity_id: str
    eg_property_id: str
    source_column: str
    amenity_category: str
    raw_amenity_value: str
    amenity_name: str
    amenity_embedding_text: str


def amenity_columns(description_df: pd.DataFrame) -> list[str]:
    return [
        c
        for c in description_df.columns
        if c in AMENITY_LIST_COLUMNS or c.startswith(AMENITY_PREFIX)
    ]


def build_amenity_catalog(description_df: pd.DataFrame) -> pd.DataFrame:
    records: list[dict] = []
    cols = amenity_columns(description_df)

    for _, row in description_df.iterrows():
        property_id = str(row["eg_property_id"])
        for col in cols:
            category = "popular amenities" if col == "popular_amenities_list" else humanize_amenity_name(
                col.replace(AMENITY_PREFIX, "")
            )
            for idx, raw_item in enumerate(parse_listlike(row[col])):
                amenity_name = humanize_amenity_name(raw_item)
                amenity_id = f"{property_id}::{col}::{idx}"
                amenity_embedding_text = (
                    f"Hotel amenity mention candidate. "
                    f"Category: {category}. "
                    f"Amenity name: {amenity_name}. "
                    f"Raw source text: {raw_item}."
                )
                records.append(
                    {
                        "amenity_id": amenity_id,
                        "eg_property_id": property_id,
                        "source_column": col,
                        "amenity_category": category,
                        "raw_amenity_value": raw_item,
                        "amenity_name": amenity_name,
                        "amenity_embedding_text": amenity_embedding_text,
                    }
                )

    catalog = pd.DataFrame.from_records(records)
    if catalog.empty:
        raise ValueError("No amenity records were extracted from the description file.")
    return catalog


# ----------------------------
# OpenAI helpers
# ----------------------------

def get_client(api_key: str | None = None) -> OpenAI:
    api_key = api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")
    return OpenAI(api_key=api_key)


def _iter_text_batches(
    texts: list[str],
    max_items_per_batch: int = 128,
    max_total_chars_per_batch: int = 120_000,
) -> Iterable[list[str]]:
    batch: list[str] = []
    chars = 0
    for text in texts:
        text = text or ""
        if not text.strip():
            continue
        if batch and (len(batch) >= max_items_per_batch or chars + len(text) > max_total_chars_per_batch):
            yield batch
            batch = []
            chars = 0
        batch.append(text)
        chars += len(text)
    if batch:
        yield batch


def embed_texts(
    client: OpenAI,
    texts: list[str],
    model: str = "text-embedding-3-small",
    sleep_between_batches: float = 0.0,
) -> np.ndarray:
    """
    Batches embeddings calls. Returns float32 array [n_texts, dim].
    Empty strings are not allowed by the embeddings API, so this expects pre-cleaned input.
    """
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)

    vectors: list[list[float]] = []
    for batch in _iter_text_batches(texts):
        response = client.embeddings.create(model=model, input=batch)
        vectors.extend(item.embedding for item in response.data)
        if sleep_between_batches:
            time.sleep(sleep_between_batches)

    return np.asarray(vectors, dtype=np.float32)


def l2_normalize(matrix: np.ndarray) -> np.ndarray:
    if matrix.size == 0:
        return matrix
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.clip(norms, 1e-12, None)
    return matrix / norms


# ----------------------------
# Candidate retrieval
# ----------------------------

def build_hotel_amenity_index(
    amenity_catalog_df: pd.DataFrame,
    amenity_embeddings: np.ndarray,
) -> dict[str, dict]:
    if len(amenity_catalog_df) != len(amenity_embeddings):
        raise ValueError("Amenity catalog row count does not match amenity embedding count.")

    amenity_embeddings = l2_normalize(amenity_embeddings)
    hotel_index: dict[str, dict] = {}

    for property_id, group in amenity_catalog_df.groupby("eg_property_id", sort=False):
        row_idx = group.index.to_numpy()
        hotel_index[str(property_id)] = {
            "amenity_df": group.reset_index(drop=True),
            "embedding_matrix": amenity_embeddings[row_idx],
        }
    return hotel_index


def retrieve_top_amenity_candidates(
    hotel_index: dict[str, dict],
    property_id: str,
    chunk_texts: list[str],
    chunk_embeddings: np.ndarray,
    top_k: int = 3,
    min_similarity: float = 0.18,
) -> pd.DataFrame:
    if property_id not in hotel_index:
        return pd.DataFrame()

    chunk_embeddings = l2_normalize(chunk_embeddings)
    amenity_df = hotel_index[property_id]["amenity_df"]
    amenity_matrix = hotel_index[property_id]["embedding_matrix"]

    scores = chunk_embeddings @ amenity_matrix.T
    candidate_rows: list[dict] = []

    for chunk_idx in range(scores.shape[0]):
        row_scores = scores[chunk_idx]
        if row_scores.size == 0:
            continue
        top_positions = np.argsort(-row_scores)[:top_k]
        for pos in top_positions:
            score = float(row_scores[pos])
            if score < min_similarity:
                continue
            amenity_row = amenity_df.iloc[int(pos)]
            candidate_rows.append(
                {
                    "chunk_id": chunk_idx,
                    "chunk_text": chunk_texts[chunk_idx],
                    "amenity_id": amenity_row["amenity_id"],
                    "amenity_name": amenity_row["amenity_name"],
                    "amenity_category": amenity_row["amenity_category"],
                    "raw_amenity_value": amenity_row["raw_amenity_value"],
                    "retrieval_score": score,
                }
            )

    return pd.DataFrame(candidate_rows)


# ----------------------------
# Verifier
# ----------------------------

class AmenityVerification(BaseModel):
    amenity_id: str = Field(description="The amenity_id passed into the prompt.")
    mentioned: bool = Field(description="Whether the chunk discusses this hotel amenity.")
    explicitness: Literal["explicit", "implicit", "not_mentioned"]
    sentiment: Literal["positive", "negative", "mixed", "neutral", "unknown"]
    evidence: str = Field(description="Shortest evidence span copied from the review chunk.")
    rationale_short: str = Field(description="One short sentence explaining the decision.")


def verify_candidate_with_model(
    client: OpenAI,
    chunk_text: str,
    amenity_id: str,
    amenity_name: str,
    amenity_category: str,
    raw_amenity_value: str,
    model: str = "gpt-5.4-nano",
) -> AmenityVerification:
    system_prompt = (
        "You are verifying whether a hotel review chunk really discusses a specific hotel amenity. "
        "Be strict. A chunk should be marked mentioned=true only if the chunk directly or clearly implicitly "
        "talks about this amenity at the hotel. Mere topical relatedness is not enough.\n\n"
        "Examples:\n"
        "- 'Parking was expensive' => parking mentioned=true\n"
        "- 'The front desk called us a taxi' => parking mentioned=false unless the text discusses hotel parking or valet\n"
        "- 'Wifi in the room kept dropping' => internet/wifi mentioned=true\n"
        "- 'The neighborhood had lots of restaurants' => hotel restaurant amenity mentioned=false unless it is clearly on-property\n"
        "Keep evidence very short and copied from the chunk."
    )

    user_prompt = (
        f"chunk_text: {chunk_text}\n"
        f"amenity_id: {amenity_id}\n"
        f"amenity_name: {amenity_name}\n"
        f"amenity_category: {amenity_category}\n"
        f"raw_amenity_value: {raw_amenity_value}\n"
    )

    response = client.responses.parse(
        model=model,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        text_format=AmenityVerification,
    )
    return response.output_parsed


def verify_candidates_dataframe(
    client: OpenAI,
    candidates_df: pd.DataFrame,
    model: str = "gpt-5.4-nano",
    max_candidates: int | None = None,
) -> pd.DataFrame:
    if candidates_df.empty:
        return pd.DataFrame()

    rows: list[dict] = []
    work_df = candidates_df.head(max_candidates) if max_candidates else candidates_df

    for _, row in work_df.iterrows():
        result = verify_candidate_with_model(
            client=client,
            chunk_text=row["chunk_text"],
            amenity_id=row["amenity_id"],
            amenity_name=row["amenity_name"],
            amenity_category=row["amenity_category"],
            raw_amenity_value=row["raw_amenity_value"],
            model=model,
        )
        merged = row.to_dict()
        merged.update(result.model_dump())
        rows.append(merged)

    return pd.DataFrame(rows)


# ----------------------------
# Review-level orchestration
# ----------------------------

def build_review_chunk_table(reviews_df: pd.DataFrame, max_chars: int = 320) -> pd.DataFrame:
    records: list[dict] = []
    for review_idx, row in reviews_df.reset_index(drop=True).iterrows():
        chunks = split_review_into_chunks(row.get("review_title"), row.get("review_text"), max_chars=max_chars)
        for chunk_id, chunk_text in enumerate(chunks):
            records.append(
                {
                    "review_id": review_idx,
                    "eg_property_id": str(row["eg_property_id"]),
                    "acquisition_date": row.get("acquisition_date"),
                    "lob": row.get("lob"),
                    "rating": row.get("rating"),
                    "chunk_id": chunk_id,
                    "chunk_text": chunk_text,
                }
            )
    return pd.DataFrame(records)


def process_reviews(
    client: OpenAI,
    description_df: pd.DataFrame,
    reviews_df: pd.DataFrame,
    embedding_model: str = "text-embedding-3-small",
    verifier_model: str = "gpt-5.4-nano",
    top_k: int = 3,
    min_similarity: float = 0.18,
    verify: bool = True,
    max_verifications_per_review: int = 12,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    amenity_catalog = build_amenity_catalog(description_df)
    amenity_embeddings = embed_texts(client, amenity_catalog["amenity_embedding_text"].tolist(), model=embedding_model)
    hotel_index = build_hotel_amenity_index(amenity_catalog, amenity_embeddings)

    chunk_df = build_review_chunk_table(reviews_df)
    if chunk_df.empty:
        return amenity_catalog, pd.DataFrame(), pd.DataFrame()

    all_candidate_frames: list[pd.DataFrame] = []

    for review_id, review_chunks in chunk_df.groupby("review_id", sort=False):
        property_id = str(review_chunks["eg_property_id"].iloc[0])
        chunk_texts = review_chunks["chunk_text"].tolist()
        chunk_embeddings = embed_texts(client, chunk_texts, model=embedding_model)
        candidates = retrieve_top_amenity_candidates(
            hotel_index=hotel_index,
            property_id=property_id,
            chunk_texts=chunk_texts,
            chunk_embeddings=chunk_embeddings,
            top_k=top_k,
            min_similarity=min_similarity,
        )
        if candidates.empty:
            continue

        review_metadata = {
            "review_id": review_id,
            "eg_property_id": property_id,
            "acquisition_date": review_chunks["acquisition_date"].iloc[0],
            "lob": review_chunks["lob"].iloc[0],
            "rating": review_chunks["rating"].iloc[0],
        }
        for col, value in review_metadata.items():
            candidates[col] = value

        if verify:
            # Keep the best retrieved rows first so verification spend is bounded.
            candidates = candidates.sort_values(["retrieval_score"], ascending=False).head(max_verifications_per_review)
            verified = verify_candidates_dataframe(client, candidates, model=verifier_model)
            if not verified.empty:
                all_candidate_frames.append(verified)
        else:
            all_candidate_frames.append(candidates)

    all_mentions = pd.concat(all_candidate_frames, ignore_index=True) if all_candidate_frames else pd.DataFrame()
    summary = summarize_mentions(all_mentions)
    return amenity_catalog, all_mentions, summary


def summarize_mentions(mentions_df: pd.DataFrame) -> pd.DataFrame:
    if mentions_df.empty:
        return pd.DataFrame()

    work = mentions_df.copy()

    if "mentioned" in work.columns:
        work = work[work["mentioned"] == True]  # noqa: E712

    if work.empty:
        return pd.DataFrame()

    agg = (
        work.sort_values("retrieval_score", ascending=False)
        .groupby(["review_id", "amenity_id", "amenity_name", "amenity_category"], as_index=False)
        .agg(
            eg_property_id=("eg_property_id", "first"),
            best_retrieval_score=("retrieval_score", "max"),
            mention_count=("chunk_id", "nunique"),
            sample_evidence=("evidence", "first") if "evidence" in work.columns else ("chunk_text", "first"),
            sentiment=("sentiment", "first") if "sentiment" in work.columns else ("amenity_name", lambda x: "unknown"),
        )
    )
    return agg.sort_values(["review_id", "best_retrieval_score"], ascending=[True, False]).reset_index(drop=True)


# ----------------------------
# I/O helpers
# ----------------------------

def load_input_data(description_csv_path: str | os.PathLike, reviews_csv_path: str | os.PathLike) -> tuple[pd.DataFrame, pd.DataFrame]:
    description_df = pd.read_csv(description_csv_path)
    reviews_df = pd.read_csv(reviews_csv_path)
    return description_df, reviews_df


def write_outputs(
    output_dir: str | os.PathLike,
    amenity_catalog_df: pd.DataFrame,
    mentions_df: pd.DataFrame,
    summary_df: pd.DataFrame,
) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    amenity_catalog_df.to_csv(output_dir / "amenity_catalog.csv", index=False)
    mentions_df.to_csv(output_dir / "review_chunk_mentions.csv", index=False)
    summary_df.to_csv(output_dir / "review_amenity_summary.csv", index=False)
