"""
Category accuracy — embedding-based category classifier vs expected category.
"""
from typing import List

from backend.evaluation.content_accuracy import embed_texts_bge, cosine_similarity_percent


def _category_query_text(category: str) -> str:
    return (
        f"professional resume for {category.replace('-', ' ').lower()} "
        f"job category {category.replace('-', ' ')} skills experience"
    )


def predict_category(resume_text: str, categories: List[str]) -> str:
    """Predict category from resume text using BGE embedding similarity."""
    if not categories:
        return ""

    texts = [resume_text] + [_category_query_text(c) for c in categories]
    embeddings = embed_texts_bge(texts)
    resume_emb = embeddings[0]

    best_category = categories[0]
    best_score = -1.0
    for idx, cat in enumerate(categories):
        score = cosine_similarity_percent(resume_emb, embeddings[idx + 1])
        if score > best_score:
            best_score = score
            best_category = cat
    return best_category.strip().upper()


def compute_category_accuracy(
    expected_category: str,
    resume_text: str,
    categories: List[str],
) -> float:
    """
    100% if predicted category matches expected, else 0%.
  For evaluate/all, use per-category calls (one category at a time = same rule).
    """
    expected = expected_category.strip().upper()
    predicted = predict_category(resume_text, categories)
    return 100.0 if predicted == expected else 0.0
