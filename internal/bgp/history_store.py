from __future__ import annotations

import json
import logging
from pathlib import Path

from internal.bgp.anomaly_detector import BgpAnomaly
from internal.bgp.models import (
    BgpPeerRouteSummary,
    BgpRouteEvent,
    BgpRouteRecord,
)
from internal.bgp.storage_models import (
    BgpAnomalyRow,
    BgpPeerRouteSummaryRow,
    BgpRouteEventRow,
    BgpRouteSnapshotRow,
)

LOG = logging.getLogger(__name__)


class BgpHistoryStore:
    """
    In memory history store with JSON artifact export.

    This gives you the logical storage contract now.
    Later the same interface can be backed by ClickHouse.
    """

    def __init__(self) -> None:
        self.route_snapshots: list[BgpRouteSnapshotRow] = []
        self.peer_summaries: list[BgpPeerRouteSummaryRow] = []
        self.route_events: list[BgpRouteEventRow] = []
        self.anomalies: list[BgpAnomalyRow] = []

    def store_route_snapshot_rows(
        self,
        routes: list[BgpRouteRecord],
    ) -> None:
        for route in routes:
            self.route_snapshots.append(
                BgpRouteSnapshotRow(
                    ts=route.timestamp_ms,
                    device=route.device,
                    network_instance=route.network_instance,
                    peer=route.peer,
                    direction=route.direction,
                    afi_safi=route.afi_safi,
                    prefix=route.prefix,
                    next_hop=route.next_hop,
                    as_path=route.as_path,
                    local_pref=route.local_pref,
                    med=route.med,
                    communities=route.communities,
                    origin=route.origin,
                    best_path=route.best_path,
                    validation_state=route.validation_state,
                    region=route.region,
                    pop=route.pop,
                    fabric=route.fabric,
                )
            )

        LOG.info("Stored %s route snapshot rows", len(routes))

    def store_peer_summary_rows(
        self,
        summaries: list[BgpPeerRouteSummary],
    ) -> None:
        for summary in summaries:
            self.peer_summaries.append(
                BgpPeerRouteSummaryRow(
                    ts=summary.timestamp_ms,
                    device=summary.device,
                    network_instance=summary.network_instance,
                    peer=summary.peer,
                    afi_safi=summary.afi_safi,
                    received_prefix_count=summary.received_prefix_count,
                    advertised_prefix_count=summary.advertised_prefix_count,
                    region=summary.region,
                    pop=summary.pop,
                    fabric=summary.fabric,
                )
            )

        LOG.info("Stored %s peer summary rows", len(summaries))

    def store_route_event_rows(
        self,
        events: list[BgpRouteEvent],
    ) -> None:
        for event in events:
            self.route_events.append(
                BgpRouteEventRow(
                    ts=event.timestamp_ms,
                    device=event.device,
                    network_instance=event.network_instance,
                    peer=event.peer,
                    direction=event.direction,
                    afi_safi=event.afi_safi,
                    prefix=event.prefix,
                    event_type=event.event_type,
                    details=event.details,
                )
            )

        LOG.info("Stored %s route event rows", len(events))

    def store_anomaly_rows(
        self,
        anomalies: list[BgpAnomaly],
    ) -> None:
        for anomaly in anomalies:
            self.anomalies.append(
                BgpAnomalyRow(
                    ts=anomaly.timestamp_ms,
                    device=anomaly.device,
                    network_instance=anomaly.network_instance,
                    peer=anomaly.peer,
                    afi_safi=anomaly.afi_safi,
                    anomaly_type=anomaly.anomaly_type,
                    severity=anomaly.severity,
                    blast_radius=anomaly.blast_radius,
                    details=anomaly.details,
                )
            )

        LOG.info("Stored %s anomaly rows", len(anomalies))

    def routes_at_or_before(
        self,
        timestamp_ms: int,
        peer: str | None = None,
        direction: str | None = None,
        afi_safi: str | None = None,
    ) -> list[BgpRouteSnapshotRow]:
        candidate_timestamps = [
            row.ts
            for row in self.route_snapshots
            if row.ts <= timestamp_ms
        ]
        if not candidate_timestamps:
            return []

        snapshot_ts = max(candidate_timestamps)

        rows: list[BgpRouteSnapshotRow] = []
        for row in self.route_snapshots:
            if row.ts != snapshot_ts:
                continue
            if peer and row.peer != peer:
                continue
            if direction and row.direction != direction:
                continue
            if afi_safi and row.afi_safi != afi_safi:
                continue
            rows.append(row)

        return sorted(
            rows,
            key=lambda row: (
                row.device,
                row.network_instance,
                row.peer,
                row.direction,
                row.afi_safi,
                row.prefix,
            ),
        )    

    def route_events_between(
        self,
        start_ts: int,
        end_ts: int,
        peer: str | None = None,
        direction: str | None = None,
        afi_safi: str | None = None,
        event_type: str | None = None,
    ) -> list[BgpRouteEventRow]:
        rows: list[BgpRouteEventRow] = []

        for row in self.route_events:
            if row.ts < start_ts or row.ts > end_ts:
                continue
            if peer and row.peer != peer:
                continue
            if direction and row.direction != direction:
                continue
            if afi_safi and row.afi_safi != afi_safi:
                continue
            if event_type and row.event_type != event_type:
                continue
            rows.append(row)

        return sorted(
            rows,
            key=lambda row: (
                row.ts,
                row.device,
                row.peer,
                row.direction,
                row.prefix,
            ),
        )

    def peer_summaries_at_or_before(
        self,
        timestamp_ms: int,
        peer: str | None = None,
        afi_safi: str | None = None,
    ) -> list[BgpPeerRouteSummaryRow]:
        latest_by_key: dict[str, BgpPeerRouteSummaryRow] = {}

        for row in self.peer_summaries:
            if row.ts > timestamp_ms:
                continue
            if peer and row.peer != peer:
                continue
            if afi_safi and row.afi_safi != afi_safi:
                continue

            key = row.peer_key()
            existing = latest_by_key.get(key)
            if existing is None or row.ts > existing.ts:
                latest_by_key[key] = row

        return sorted(
            latest_by_key.values(),
            key=lambda row: (
                row.device,
                row.network_instance,
                row.peer,
                row.afi_safi,
            ),
        )

    def anomalies_between(
        self,
        start_ts: int,
        end_ts: int,
        peer: str | None = None,
        anomaly_type: str | None = None,
    ) -> list[BgpAnomalyRow]:
        rows: list[BgpAnomalyRow] = []

        for row in self.anomalies:
            if row.ts < start_ts or row.ts > end_ts:
                continue
            if peer and row.peer != peer:
                continue
            if anomaly_type and row.anomaly_type != anomaly_type:
                continue
            rows.append(row)

        return sorted(
            rows,
            key=lambda row: (
                row.ts,
                row.device,
                row.peer,
                row.anomaly_type,
            ),
        )

    def write_json_artifacts(self, output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)

        artifacts = {
            "bgp_route_snapshots.json": [row.to_dict() for row in self.route_snapshots],
            "bgp_peer_summaries.json": [row.to_dict() for row in self.peer_summaries],
            "bgp_route_events.json": [row.to_dict() for row in self.route_events],
            "bgp_anomalies.json": [row.to_dict() for row in self.anomalies],
        }

        for filename, payload in artifacts.items():
            path = output_dir / filename
            path.write_text(json.dumps(payload, indent=2), encoding="utf_8")
            LOG.info("Wrote artifact to %s", path)
