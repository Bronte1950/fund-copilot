"""Citation validation and refusal detection.

Phase 3 implementation.

After the LLM generates a response:
    1. Parse [SOURCE: chunk_id] citations from the answer text.
    2. Verify each cited chunk_id exists in chunks_used.
    3. Detect REFUSED: prefix → set confidence = "refused".
    4. Assign confidence level based on citation density and chunk scores.
"""

from __future__ import annotations

# TODO Phase 3: implement parse_citations(), validate_grounding(), detect_refusal()
