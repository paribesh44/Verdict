from app.rag.pipeline import schema_locked_extract


def test_schema_locked_extract_preserves_structure():
    bundle = schema_locked_extract(
        "test query",
        [{"summary": "Claim text", "url": "https://example.com", "quote": "Claim text", "confidence": 0.7}],
    )
    assert bundle.query == "test query"
    assert len(bundle.claims) == 1
    assert bundle.claims[0].citations[0].source_url == "https://example.com"
