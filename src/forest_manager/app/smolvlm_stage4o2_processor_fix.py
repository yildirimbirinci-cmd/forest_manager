from __future__ import annotations

import json
import sys

from forest_manager.reference_analysis.smolvlm500m_local_backend import (
    SmolVLM500MLocalBackend,
)
from forest_manager.reference_analysis.smolvlm_processor_compat import (
    LocalProcessorMetadataError,
    ensure_smolvlm_processor_metadata,
)


def main() -> int:
    backend = SmolVLM500MLocalBackend()

    try:
        result = ensure_smolvlm_processor_metadata(
            backend.config.model_dir
        )
    except LocalProcessorMetadataError as exc:
        print("Stage 4O.2 metadata repair error:", str(exc))
        return 1

    print("Forest Manager SmolVLM Processor Metadata:")
    print(json.dumps(result, indent=2, ensure_ascii=True))

    if not result.get("verified"):
        print("Stage 4O.2 processor metadata verification failed.")
        return 2

    print("Stage 4O.2 processor metadata compatibility passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
