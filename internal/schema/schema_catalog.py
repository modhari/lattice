from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

LOG = logging.getLogger(__name__)


DOMAIN_PATTERNS: dict[str, tuple[str, ...]] = {
    "interfaces": (
        "interface",
        "interfaces",
        "if-",
        "ethernet",
        "lag",
        "port-channel",
        "subinterface",
    ),
    "bgp": (
        "bgp",
        "evpn",
        "route-reflector",
    ),
    "routing": (
        "route",
        "routing",
        "rib",
        "fib",
        "isis",
        "ospf",
        "static-route",
        "pim",
        "igmp",
    ),
    "mpls": (
        "mpls",
        "ldp",
        "segment-routing",
        "srte",
        "te",
        "rsvp",
    ),
    "system": (
        "system",
        "ntp",
        "clock",
        "dns",
        "logging",
        "syslog",
        "aaa",
        "tacacs",
        "radius",
        "snmp",
    ),
    "platform": (
        "platform",
        "component",
        "chassis",
        "linecard",
        "transceiver",
        "inventory",
        "hardware",
    ),
    "optics": (
        "optical",
        "optics",
        "transceiver",
        "laser",
        "channel-monitor",
        "dom",
        "fec",
    ),
    "qos": (
        "qos",
        "queue",
        "scheduler",
        "class-of-service",
        "classifier",
        "forwarding-class",
        "policer",
        "remark",
    ),
    "acl": (
        "acl",
        "access-list",
        "firewall",
        "filter",
    ),
    "network_instance": (
        "network-instance",
        "vrf",
        "vsi",
        "bridge-domain",
        "mac-vrf",
        "ip-vrf",
    ),
    "services": (
        "service",
        "l2vpn",
        "l3vpn",
        "vpls",
        "vpws",
        "evpn",
    ),
    "telemetry": (
        "telemetry",
        "gnmi",
        "grpc",
        "subscription",
        "sensor",
    ),
    "security": (
        "crypto",
        "keychain",
        "ipsec",
        "macsec",
        "ssh",
        "tls",
        "certificate",
    ),
}


CONFIG_TRUE_RE = re.compile(r"\bconfig\s+true\s*;")
CONFIG_FALSE_RE = re.compile(r"\bconfig\s+false\s*;")
CONTAINER_RE = re.compile(r"\bcontainer\s+([A-Za-z0-9_\.\-]+)\s*\{")
LIST_RE = re.compile(r"\blist\s+([A-Za-z0-9_\.\-]+)\s*\{")
LEAF_RE = re.compile(r"\bleaf\s+([A-Za-z0-9_\.\-]+)\s*\{")
LEAF_LIST_RE = re.compile(r"\bleaf-list\s+([A-Za-z0-9_\.\-]+)\s*\{")
CHOICE_RE = re.compile(r"\bchoice\s+([A-Za-z0-9_\.\-]+)\s*\{")
CASE_RE = re.compile(r"\bcase\s+([A-Za-z0-9_\.\-]+)\s*\{")
ANYDATA_RE = re.compile(r"\banydata\s+([A-Za-z0-9_\.\-]+)\s*;?")
ANYXML_RE = re.compile(r"\banyxml\s+([A-Za-z0-9_\.\-]+)\s*;?")
TYPE_RE = re.compile(r"\btype\s+([A-Za-z0-9_\.\-:]+)\s*;")
IDENTITYREF_RE = re.compile(r"\btype\s+identityref\b")
UNION_RE = re.compile(r"\btype\s+union\b")
ENUM_RE = re.compile(r"\benum\s+([A-Za-z0-9_\.\-]+)\s*;")
USES_RE = re.compile(r"\buses\s+([A-Za-z0-9_\.\-:]+)\s*;")
GROUPING_RE = re.compile(r"\bgrouping\s+([A-Za-z0-9_\.\-]+)\s*\{")
ACTION_RE = re.compile(r"\baction\s+([A-Za-z0-9_\.\-]+)\s*\{")
EXTENSION_RE = re.compile(r"\bextension\s+([A-Za-z0-9_\.\-]+)\s*\{")


@dataclass
class ModuleEntry:
    source_name: str
    vendor: str
    repo_path: str
    file_path: str
    sha256: str
    module_type: str
    module_name: str
    namespace: str | None
    prefix: str | None
    revision: str | None
    imports: list[str]
    includes: list[str]
    features: list[str]
    rpcs: list[str]
    notifications: list[str]
    identities: list[str]
    deviations: list[str]
    augments: list[str]


@dataclass
class ModuleCatalogRecord:
    module_name: str
    module_type: str
    vendor: str
    source_name: str
    file_path: str
    revision: str | None
    namespace: str | None
    prefix: str | None
    semantic_domains: list[str]
    config_nodes: int
    state_nodes: int
    containers: int
    lists: int
    leaves: int
    leaf_lists: int
    choices: int
    cases: int
    anydata_nodes: int
    anyxml_nodes: int
    groupings: int
    uses_statements: int
    actions: int
    rpcs: int
    notifications: int
    identities: int
    features: int
    enums: int
    union_types: int
    identityrefs: int
    augments: list[str]
    deviations: list[str]
    imports: list[str]
    includes: list[str]
    imported_by: list[str] = field(default_factory=list)
    included_by: list[str] = field(default_factory=list)
    augmented_by: list[str] = field(default_factory=list)
    deviated_by: list[str] = field(default_factory=list)


@dataclass
class DomainSummary:
    domain: str
    module_count: int = 0
    modules: list[str] = field(default_factory=list)


@dataclass
class SourceSummary:
    source_name: str
    vendor: str
    module_count: int = 0
    domains: dict[str, int] = field(default_factory=dict)


@dataclass
class SchemaCatalog:
    generated_from: str
    total_sources: int
    total_modules: int
    total_unique_modules: int
    modules: list[ModuleCatalogRecord]
    import_graph: dict[str, list[str]]
    reverse_import_graph: dict[str, list[str]]
    include_graph: dict[str, list[str]]
    reverse_include_graph: dict[str, list[str]]
    augment_index: dict[str, list[str]]
    deviation_index: dict[str, list[str]]
    domain_summary: dict[str, DomainSummary]
    source_summary: dict[str, SourceSummary]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_from": self.generated_from,
            "total_sources": self.total_sources,
            "total_modules": self.total_modules,
            "total_unique_modules": self.total_unique_modules,
            "modules": [asdict(module) for module in self.modules],
            "import_graph": self.import_graph,
            "reverse_import_graph": self.reverse_import_graph,
            "include_graph": self.include_graph,
            "reverse_include_graph": self.reverse_include_graph,
            "augment_index": self.augment_index,
            "deviation_index": self.deviation_index,
            "domain_summary": {
                key: asdict(value) for key, value in self.domain_summary.items()
            },
            "source_summary": {
                key: asdict(value) for key, value in self.source_summary.items()
            },
        }


class SchemaCatalogBuilder:
    def __init__(self, registry_path: Path) -> None:
        self.registry_path = registry_path

    def build(self) -> SchemaCatalog:
        payload = json.loads(self.registry_path.read_text(encoding="utf_8"))
        source_entries = payload["sources"]

        module_entries: list[ModuleEntry] = []
        for source in source_entries:
            for module in source["modules"]:
                module_entries.append(ModuleEntry(**module))

        LOG.info("Loaded %s module entries from registry", len(module_entries))

        import_graph: dict[str, list[str]] = {}
        reverse_import_graph: dict[str, list[str]] = defaultdict(list)
        include_graph: dict[str, list[str]] = {}
        reverse_include_graph: dict[str, list[str]] = defaultdict(list)
        augment_index: dict[str, list[str]] = defaultdict(list)
        deviation_index: dict[str, list[str]] = defaultdict(list)

        modules: list[ModuleCatalogRecord] = []
        domain_summary: dict[str, DomainSummary] = {}
        source_summary: dict[str, SourceSummary] = {}

        unique_module_names = {entry.module_name for entry in module_entries}

        for entry in module_entries:
            raw_text = self._read_module_text(entry)
            domains = self._classify_domains(entry, raw_text)

            config_nodes = len(CONFIG_TRUE_RE.findall(raw_text))
            state_nodes = len(CONFIG_FALSE_RE.findall(raw_text))
            containers = len(CONTAINER_RE.findall(raw_text))
            lists = len(LIST_RE.findall(raw_text))
            leaves = len(LEAF_RE.findall(raw_text))
            leaf_lists = len(LEAF_LIST_RE.findall(raw_text))
            choices = len(CHOICE_RE.findall(raw_text))
            cases = len(CASE_RE.findall(raw_text))
            anydata_nodes = len(ANYDATA_RE.findall(raw_text))
            anyxml_nodes = len(ANYXML_RE.findall(raw_text))
            groupings = len(GROUPING_RE.findall(raw_text))
            uses_statements = len(USES_RE.findall(raw_text))
            actions = len(ACTION_RE.findall(raw_text))
            enums = len(ENUM_RE.findall(raw_text))
            union_types = len(UNION_RE.findall(raw_text))
            identityrefs = len(IDENTITYREF_RE.findall(raw_text))

            record = ModuleCatalogRecord(
                module_name=entry.module_name,
                module_type=entry.module_type,
                vendor=entry.vendor,
                source_name=entry.source_name,
                file_path=entry.file_path,
                revision=entry.revision,
                namespace=entry.namespace,
                prefix=entry.prefix,
                semantic_domains=domains,
                config_nodes=config_nodes,
                state_nodes=state_nodes,
                containers=containers,
                lists=lists,
                leaves=leaves,
                leaf_lists=leaf_lists,
                choices=choices,
                cases=cases,
                anydata_nodes=anydata_nodes,
                anyxml_nodes=anyxml_nodes,
                groupings=groupings,
                uses_statements=uses_statements,
                actions=actions,
                rpcs=len(entry.rpcs),
                notifications=len(entry.notifications),
                identities=len(entry.identities),
                features=len(entry.features),
                enums=enums,
                union_types=union_types,
                identityrefs=identityrefs,
                augments=entry.augments,
                deviations=entry.deviations,
                imports=entry.imports,
                includes=entry.includes,
            )
            modules.append(record)

            import_graph[entry.module_name] = sorted(set(entry.imports))
            include_graph[entry.module_name] = sorted(set(entry.includes))

            for imported in entry.imports:
                reverse_import_graph[imported].append(entry.module_name)

            for included in entry.includes:
                reverse_include_graph[included].append(entry.module_name)

            for augment_target in entry.augments:
                augment_index[augment_target].append(entry.module_name)

            for deviation_target in entry.deviations:
                deviation_index[deviation_target].append(entry.module_name)

            for domain in domains:
                if domain not in domain_summary:
                    domain_summary[domain] = DomainSummary(domain=domain)
                domain_summary[domain].module_count += 1
                domain_summary[domain].modules.append(entry.module_name)

            if entry.source_name not in source_summary:
                source_summary[entry.source_name] = SourceSummary(
                    source_name=entry.source_name,
                    vendor=entry.vendor,
                    module_count=0,
                    domains={},
                )
            source_summary[entry.source_name].module_count += 1
            for domain in domains:
                source_summary[entry.source_name].domains[domain] = (
                    source_summary[entry.source_name].domains.get(domain, 0) + 1
                )

        module_name_to_records: dict[str, list[ModuleCatalogRecord]] = defaultdict(list)
        for module in modules:
            module_name_to_records[module.module_name].append(module)

        for module in modules:
            module.imported_by = sorted(
                set(reverse_import_graph.get(module.module_name, []))
            )
            module.included_by = sorted(
                set(reverse_include_graph.get(module.module_name, []))
            )
            module.augmented_by = sorted(
                set(augment_index.get(f"/{module.module_name}", []))
            )
            module.deviated_by = sorted(
                set(deviation_index.get(f"/{module.module_name}", []))
            )

        for summary in domain_summary.values():
            summary.modules = sorted(set(summary.modules))

        for summary in source_summary.values():
            summary.domains = dict(sorted(summary.domains.items()))

        modules.sort(key=lambda item: (item.module_name, item.source_name, item.file_path))

        return SchemaCatalog(
            generated_from=str(self.registry_path),
            total_sources=len(source_entries),
            total_modules=len(modules),
            total_unique_modules=len(unique_module_names),
            modules=modules,
            import_graph={
                key: sorted(set(value)) for key, value in sorted(import_graph.items())
            },
            reverse_import_graph={
                key: sorted(set(value))
                for key, value in sorted(reverse_import_graph.items())
            },
            include_graph={
                key: sorted(set(value)) for key, value in sorted(include_graph.items())
            },
            reverse_include_graph={
                key: sorted(set(value))
                for key, value in sorted(reverse_include_graph.items())
            },
            augment_index={
                key: sorted(set(value)) for key, value in sorted(augment_index.items())
            },
            deviation_index={
                key: sorted(set(value)) for key, value in sorted(deviation_index.items())
            },
            domain_summary=dict(sorted(domain_summary.items())),
            source_summary=dict(sorted(source_summary.items())),
        )

    def _read_module_text(self, entry: ModuleEntry) -> str:
        full_path = Path(entry.repo_path) / entry.file_path
        return full_path.read_text(encoding="utf_8", errors="ignore")

    def _classify_domains(self, entry: ModuleEntry, raw_text: str) -> list[str]:
        candidates = " ".join(
            [
                entry.module_name.lower(),
                entry.file_path.lower(),
                entry.namespace.lower() if entry.namespace else "",
                " ".join(entry.imports).lower(),
                " ".join(entry.includes).lower(),
                " ".join(entry.features).lower(),
                " ".join(entry.rpcs).lower(),
                " ".join(entry.notifications).lower(),
                raw_text[:20000].lower(),
            ]
        )

        matched_domains: list[str] = []
        for domain, patterns in DOMAIN_PATTERNS.items():
            if any(pattern in candidates for pattern in patterns):
                matched_domains.append(domain)

        if not matched_domains:
            matched_domains.append("misc")

        return sorted(set(matched_domains))


def write_schema_catalog(
    catalog: SchemaCatalog,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(catalog.to_dict(), indent=2),
        encoding="utf_8",
    )
    LOG.info("Wrote schema catalog to %s", output_path)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    repo_root = Path(__file__).resolve().parents[2]
    registry_path = repo_root / "data" / "generated" / "schema" / "model_registry.json"
    output_path = repo_root / "data" / "generated" / "schema" / "schema_catalog.json"

    builder = SchemaCatalogBuilder(registry_path=registry_path)
    catalog = builder.build()
    write_schema_catalog(catalog, output_path)


if __name__ == "__main__":
    main()
