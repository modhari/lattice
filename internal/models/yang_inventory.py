from __future__ import annotations

import re
from dataclasses import dataclass

MODULE_RE = re.compile(r"^\s*module\s+([A-Za-z0-9\-_]+)\s*\{", re.MULTILINE)
SUBMODULE_RE = re.compile(
    r"^\s*submodule\s+([A-Za-z0-9\-_]+)\s*\{",
    re.MULTILINE,
)
NAMESPACE_RE = re.compile(
    r'^\s*namespace\s+"([^"]+)"\s*;',
    re.MULTILINE,
)
PREFIX_RE = re.compile(r"^\s*prefix\s+([A-Za-z0-9\-_]+)\s*;", re.MULTILINE)
REVISION_RE = re.compile(
    r'^\s*revision\s+"?([0-9]{4}-[0-9]{2}-[0-9]{2})"?\s*\{?',
    re.MULTILINE,
)
IMPORT_RE = re.compile(r"^\s*import\s+([A-Za-z0-9\-_]+)\s*\{", re.MULTILINE)
INCLUDE_RE = re.compile(r"^\s*include\s+([A-Za-z0-9\-_]+)\s*;", re.MULTILINE)
FEATURE_RE = re.compile(r"^\s*feature\s+([A-Za-z0-9\-_]+)\s*\{", re.MULTILINE)
IDENTITY_RE = re.compile(
    r"^\s*identity\s+([A-Za-z0-9\-_]+)\s*\{",
    re.MULTILINE,
)
DEVIATION_RE = re.compile(
    r'^\s*deviation\s+("?[^"\n;]+?"?)\s*\{',
    re.MULTILINE,
)
AUGMENT_RE = re.compile(
    r'^\s*augment\s+("?[^"\n;]+?"?)\s*\{',
    re.MULTILINE,
)
RPC_RE = re.compile(r"^\s*rpc\s+([A-Za-z0-9\-_]+)\s*\{", re.MULTILINE)
NOTIFICATION_RE = re.compile(
    r"^\s*notification\s+([A-Za-z0-9\-_]+)\s*\{",
    re.MULTILINE,
)


@dataclass(frozen=True)
class YangModuleSummary:
    module_name: str | None
    submodule_name: str | None
    namespace: str | None
    prefix: str | None
    revisions: list[str]
    imports: list[str]
    includes: list[str]
    features: list[str]
    rpcs: list[str]
    notifications: list[str]
    identities: list[str]
    deviations: list[str]
    augments: list[str]


def summarize_yang_text(text: str) -> YangModuleSummary:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")

    module_match = MODULE_RE.search(normalized)
    submodule_match = SUBMODULE_RE.search(normalized)
    namespace_match = NAMESPACE_RE.search(normalized)
    prefix_match = PREFIX_RE.search(normalized)

    revisions = sorted(set(REVISION_RE.findall(normalized)))
    imports = sorted(set(IMPORT_RE.findall(normalized)))
    includes = sorted(set(INCLUDE_RE.findall(normalized)))
    features = sorted(set(FEATURE_RE.findall(normalized)))
    rpcs = sorted(set(RPC_RE.findall(normalized)))
    notifications = sorted(set(NOTIFICATION_RE.findall(normalized)))
    identities = sorted(set(IDENTITY_RE.findall(normalized)))
    deviations = sorted(
        {
            value.strip().strip('"')
            for value in DEVIATION_RE.findall(normalized)
        }
    )
    augments = sorted(
        {
            value.strip().strip('"')
            for value in AUGMENT_RE.findall(normalized)
        }
    )

    return YangModuleSummary(
        module_name=module_match.group(1) if module_match else None,
        submodule_name=(
            submodule_match.group(1) if submodule_match else None
        ),
        namespace=namespace_match.group(1) if namespace_match else None,
        prefix=prefix_match.group(1) if prefix_match else None,
        revisions=revisions,
        imports=imports,
        includes=includes,
        features=features,
        rpcs=rpcs,
        notifications=notifications,
        identities=identities,
        deviations=deviations,
        augments=augments,
    )
