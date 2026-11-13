"""Request-independent numerical evidence; never cached requirement decisions."""
from pathlib import Path
import json

from filelock import FileLock

from app.core.errors import DomainError
from app.mission.identity import digest
from app.services.lunarsight.acquire import hashfile

VERSION = "numerical-validation-evidence-1"


class ValidationEvidenceCache:
    def __init__(self, root):
        self.root = Path(root)/"validation-evidence"

    def load(self, identity):
        if identity is None:
            return None
        directory = self.root/digest(identity)
        receipt = directory/"receipt.json"
        if not receipt.is_file():
            return None
        try:
            record = json.loads(receipt.read_text())
            path = directory/"evidence.json"
            if record["identity"] != identity or record["sha256"] != hashfile(path):
                raise ValueError("Numerical evidence checksum or source mismatch")
            return json.loads(path.read_text())
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise DomainError("VALIDATION_EVIDENCE_INTEGRITY_FAILED", 503) from error

    def save(self, identity, evidence):
        if identity is None:
            return
        from .pipeline import atomic_json
        directory = self.root/digest(identity)
        directory.mkdir(parents=True, exist_ok=True)
        with FileLock(str(directory/"publish.lock")):
            atomic_json(directory/"evidence.json", evidence)
            atomic_json(directory/"receipt.json", {"identity": identity,
                "sha256": hashfile(directory/"evidence.json")})
