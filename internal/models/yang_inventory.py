from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Optional


LOG = logging.getLogger(__name__)


MODULE_RE = re.compile(r"\b(module|submodule)\s+([A-Za-z0-9_.-]+)\s*\{", re.DOTALL)
NAMESPACE_RE = re.compile(r'\bnamespace\s+"([^"]+)"\s*;')
PREFIX_RE = re.compile(r"\bprefix\s+([A-Za-z0-9_.-]+)\s*;")
REVISION_RE = re.compile(r'\brevision\s+"?([0-9]{4}-[0-9]{2}-[0-9]{2})"?\s*\{')
IMPORT_RE = re.compile(r"\bimport\s+([A-Za-z0-9_.-]+)\s*\{")
INCLUDE_RE = re.compile(r"\binclude\s+([A-Za-z0-9_.-]+)\s*;")
FEATURE_RE = re.compile(r"\bfeature\s+([A-Za-z0-9_.-]+)\s*\{")
RPC_RE = re.compile(r"\brpc\s+([A-Za-z0-9_.-]+)\s*\{")
NOTIFICATION_RE = re.compile(r"\bnotification\s+([A-Za-z0-9_.-]+)\s*\{")
IDENTITY_RE = re.compile(r"\bidentity\s+([A-Za-z0-9_.-]+)\s*\{")
DEVIATION_RE = re.compile(r"\bdeviation\s+(.+?)\s*\{", re.DOTALL)
AUGMENT_RE = re.compile(r"\baugment\s+(.+?)\s*\{", re.DOTALL)


@dataclass(frozen=True)
class YangModuleRecord:
    source_name: str
    vendor: str
    repo_path: str
    file_path: str
    sha256: str
    module_type: str
    module_name: str
    namespace: Optional[str]
    prefix: Optional[str]
    revision: Optional[str]
    imports: list[str] = field(default_factory=list)
    includes: list[str] = field(default_factory=list)
    features: list[str] = field(default_factory=list)
    rpcs: list[str] = field(default_factory=list)
    notifications: list[str] = field(default_factory=list)
    identities: list[str] = field(default_factory=list)
    deviations: list[str] = field(default_factory=list)
    augments: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class InventorySource:
    name: str
    vendor: str
    repo_root: Path


class YangInventoryBuilder:
    """
    Builds a lightweight YANG module inventory from a repo checkout.
    """

    def build(self, source: InventorySource) -> list[YangModuleRecord]:
        records: list[YangModuleRecord] = []

        yang_files = list(self._iter_yang_files(source.repo_root))
        LOG.info(
            "Scanning source %s at %s, found %s yang files",
            source.name,
            source.repo_root,
            len(yang_files),
        )

        parsed = 0
        skipped = 0

        for yang_file in yang_files:
            try:
                record = self._parse_file(source, yang_file)
                if record:
                    records.append(record)
                    parsed += 1
                else:
                    skipped += 1
            except Exception as exc:
                LOG.warning("Failed to parse YANG file %s: %s", yang_file, exc)
                skipped += 1

        LOG.info(
            "Completed source %s, parsed %s modules, skipped %s files",
            source.name,
            parsed,
            skipped,
        )

        return sorted(records, key=lambda item: (item.module_name, item.file_path))

    def _iter_yang_files(self, repo_root: Path) -> Iterable[Path]:
        for path in repo_root.rglob("*.yang"):
            if path.is_file():
                yield path

    def _parse_file(
        self,
        source: InventorySource,
        path: Path,
    ) -> Optional[YangModuleRecord]:
        text = path.read_text(encoding="utf_8", errors="ignore")
        normalized = self._strip_comments(text)

        module_match = MODULE_RE.search(normalized)
        if not module_match:
            return None

        module_type = module_match.group(1)
        module_name = module_match.group(2)

        namespace = self._first_match(NAMESPACE_RE, normalized)
        prefix = self._first_match(PREFIX_RE, normalized)
        revision = self._first_match(REVISION_RE, normalized)

        imports = sorted(set(IMPORT_RE.findall(normalized)))
        includes = sorted(set(INCLUDE_RE.findall(normalized)))
        features = sorted(set(FEATURE_RE.findall(normalized)))
        rpcs = sorted(set(RPC_RE.findall(normalized)))
        notifications = sorted(set(NOTIFICATION_RE.findall(normalized)))
        identities = sorted(set(IDENTITY_RE.findall(normalized)))
        deviations = sorted({value.strip().strip('"') for value in DEVIATION_RE.findall(normalized)})
        augments = sorted({value.strip().strip('"') for value in AUGMENT_RE.findall(normalized)})

        sha256 = hashlib.sha256(text.encode("utf_8", errors="ignore")).hexdigest()

        return YangModuleRecord(
            source_name=source.name,
            vendor=source.vendor,
            repo_path=str(source.repo_root.resolve()),
            file_path=str(path.relative_to(source.repo_root)),
            sha256=sha256,
            module_type=module_type,
            module_name=module_name,
            namespace=namespace,
            prefix=prefix,
            revision=revision,
            imports=imports,
            includes=includes,
            features=features,
            rpcs=rpcs,
            notifications=notifications,
            identities=identities,
            deviations=deviations,
            augments=augments,
        )

    def _first_match(self, pattern: re.Pattern[str], text: str) -> Optional[str]:
        match = pattern.search(text)
        return match.group(1) if match else None

    def _strip_comments(self, text: str) -> str:
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
        text = re.sub(r"//.*?$", "", text, flags=re.MULTILINE)
        return text
