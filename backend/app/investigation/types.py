from dataclasses import asdict, dataclass, field

CATEGORIES = ["physical_anomaly", "sensor_fault", "cyber_manipulation", "reporting_inconsistency", "normal_behaviour"]
UNCERTAIN = "uncertain"

CATEGORY_LABELS = {
    "normal_behaviour": "Normal behaviour",
    "physical_anomaly": "Possible physical/process anomaly",
    "sensor_fault": "Sensor/device fault",
    "cyber_manipulation": "Possible cyber manipulation",
    "reporting_inconsistency": "Possible physical/process anomaly with reporting inconsistency",
    "uncertain": "Uncertain",
}
OT_LAYER_LABELS = {
    "physical_process": "Physical process",
    "field_device": "Field device",
    "control": "Control",
    "reporting": "Reporting and telemetry",
}


@dataclass
class EvidenceItem:
    id: str
    kind: str
    tick: int
    end_tick: int
    segment: str | None
    observation: str
    interpretation: str
    supports: dict[str, float]
    link: dict


@dataclass
class Hypothesis:
    category: str
    score: float
    evidence_ids: list[str]


@dataclass
class Localisation:
    segment: str | None
    ot_layers: list[str]
    note: str


@dataclass
class ChainStage:
    stage: str
    label: str
    tick: int
    segment: str | None
    evidence_ids: list[str]


@dataclass
class Technique:
    technique_id: str
    name: str
    tactic: str
    reason: str
    evidence_ids: list[str]


@dataclass
class TimelineEntry:
    tick: int
    segment: str | None
    kind: str
    observation: str
    interpretation: str
    evidence_id: str


@dataclass
class Incident:
    start_tick: int
    end_tick: int
    detected_tick: int
    segments: list[str]
    classification: str
    confidence: float
    confidence_label: str
    hypotheses: list[Hypothesis]
    localisation: Localisation
    severity: str
    summary: str
    evidence: list[EvidenceItem]
    timeline: list[TimelineEntry]
    chain: list[ChainStage]
    mitre: list[Technique]
    actions: list[str]
    uncertainty: dict | None
    windows: list[tuple[str, int, int]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def summary_row(self) -> dict:
        return {
            "start_tick": self.start_tick, "end_tick": self.end_tick, "detected_tick": self.detected_tick,
            "classification": self.classification, "confidence": self.confidence,
            "segment_code": self.localisation.segment, "ot_layers": self.localisation.ot_layers,
            "evidence_count": len(self.evidence), "severity": self.severity,
        }
