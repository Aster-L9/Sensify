// Shapes returned by the Sensify API (docs/sprint2/design.md §8).

// insufficient: not enough reported readings to judge the segment (missing, intermittent or no neighbour).
export type SegmentStateName = 'normal' | 'anomalous' | 'low_trust' | 'insufficient';
export type RunStatus = 'active' | 'paused' | 'completed';
export type TrustStatus = 'Supported' | 'Review' | 'Contradicted' | 'Insufficient';
export type Severity = 'medium' | 'high' | 'critical';
export type AlertKind = 'anomaly' | 'low_trust';
export type EventCategory = 'control' | 'security' | 'device' | 'process' | 'analysis';
export type CheckName =
  | 'flow_balance'
  | 'pressure_gradient'
  | 'implausible_change'
  | 'range'
  | 'replay'
  | 'flatline';

export interface Segment {
  id: number;
  code: string;
  name: string;
  segment_type: string;
  order_index: number;
  lat_start: number;
  lon_start: number;
  lat_end: number;
  lon_end: number;
  length_km: number;
  diameter_mm: number;
  design_pressure_bar: number;
  equipment: string | null;
}

export interface Topology {
  segments: Segment[];
  total_length_km: number;
  segment_count: number;
}

export interface RunOut {
  id: number;
  name: string;
  description: string | null;
  status: RunStatus;
  paused_at: string | null;
  created_by: number | null;
  creator_username: string | null;
  created_at: string;
  started_at: string;
  ended_at: string | null;
  seed?: number; // admin only
  tick_seconds: number;
  duration_ticks: number;
  playback_speed: number;
  revealed_ticks: number;
  progress: number;
  scored: boolean;
  model_version: number | null;
  // Admin only: what was injected (ground truth).
  scenario_type?: string;
  method?: string | null;
  target_segment?: string | null;
  scenario_params?: Record<string, number | string | boolean | null>;
}

export interface TrustFactor {
  code: string;
  label: string;
  weight: number;
  penalty: number;
  detail: string;
}

export interface SegmentState {
  segment_id: number;
  code: string;
  name: string;
  segment_type: string;
  pressure_bar: number | null;
  flow_m3h: number | null;
  temperature_c: number | null;
  valve_open_pct: number | null;
  pump_speed_pct: number | null;
  valve_state: string | null;
  equipment_state: string | null;
  anomaly_score: number | null;
  ml_flag: boolean;
  trust_score: number | null;
  trust_status: TrustStatus | null;
  state: SegmentStateName;
  top_factor: TrustFactor | null;
  factors: TrustFactor[];
}

export interface RunState {
  run_id: number;
  status: RunStatus;
  tick: number;
  revealed_ticks: number;
  duration_ticks: number;
  timestamp: string;
  segments: SegmentState[];
  open_alerts: number;
}

export interface TelemetryPoint {
  run_id: number;
  segment_id: number;
  segment_code: string;
  tick: number;
  timestamp: string;
  pressure_bar: number;
  flow_m3h: number;
  temperature_c: number;
  valve_open_pct: number | null;
  pump_speed_pct: number | null;
  valve_state: string | null;
  equipment_state: string | null;
}

export interface RunEvent {
  id: number;
  run_id: number;
  tick: number;
  timestamp: string;
  segment_id: number | null;
  segment_code: string | null;
  source: string;
  category: EventCategory;
  event_type: string;
  authorized: 'yes' | 'no' | 'unknown' | 'n/a';
  severity: 'low' | 'medium' | 'high' | 'critical';
  details: string | null;
  origin: 'simulator' | 'analysis';
  observable: boolean;
}

export interface AlertItem {
  id: string;
  run_id: number;
  run_name: string;
  segment_id: number;
  segment_code: string;
  segment_name: string;
  start_tick: number;
  end_tick: number;
  peak_tick: number;
  peak_score: number | null;
  min_trust: number;
  kinds: AlertKind[];
  severity: Severity;
  summary: string;
  ongoing: boolean;
  start_time: string;
  incident_key?: string | null;
}

export interface AnomalySeries {
  run_id: number;
  model_version: number | null;
  threshold: number;
  cutoff_tick: number;
  segments: { segment_id: number; code: string; scores: number[]; flags: boolean[] }[];
  windows: AlertItem[];
}

export interface TrustSeries {
  run_id: number;
  model_version: number | null;
  cutoff_tick: number;
  segments: {
    segment_id: number;
    code: string;
    trust: (number | null)[]; // null where the readings were insufficient to judge
    status: TrustStatus[];
    current: { score: number | null; status: TrustStatus; factors: TrustFactor[] } | null;
    series_factors_at_min: TrustFactor[];
    min_tick?: number;
  }[];
}

export interface CheckMessage {
  check: CheckName;
  status: 'warn' | 'fail';
  message: string;
}

export interface ConsistencySeries {
  run_id: number;
  model_version: number | null;
  cutoff_tick: number;
  segments: {
    segment_id: number;
    code: string;
    series: Partial<Record<CheckName, number[]>>;
    latest: Partial<Record<CheckName, number>>;
    messages: CheckMessage[];
  }[];
}

export interface BaselineWindow {
  segment_id: number;
  code: string;
  variable: 'pressure' | 'flow' | 'temperature';
  kind: 'high' | 'low' | 'rate';
  start_tick: number;
  end_tick: number;
}

export interface BaselineAlarms {
  run_id: number;
  model_version: number | null;
  cutoff_tick: number;
  windows: BaselineWindow[];
}

export interface GroundTruth {
  run_id: number;
  cutoff_tick: number;
  summary: {
    scenario_type: string;
    method: string | null;
    target_segment: string | null;
    event_start_tick: number | null;
    event_peak_tick: number | null;
    event_end_tick: number | null;
    expected_root_cause: string;
    manipulated_signal_or_asset: string | null;
    notes: string | null;
  } | null;
  segments: {
    segment_id: number;
    code: string;
    ticks: number[];
    phase: string[];
    process_affected: boolean[];
    reporting_compromised: boolean[];
    actual_pressure_bar: number[];
    actual_flow_m3h: number[];
    actual_temperature_c: number[];
  }[];
}

export interface DetectionRate {
  detected: number;
  total: number;
  rate: number | null;
}

export interface DetectionMetrics {
  overall: DetectionRate;
  per_type: Record<string, DetectionRate>;
  per_type_min_rate: number | null;
  time_to_detect_s: { median: number | null; p90: number | null };
  false_alarm: { tick_rate: number | null; windows_per_run: number | null };
  window_precision: number | null;
  localization_hit_rate: number | null;
  roc_auc: number | null;
}

export interface TrustMetrics {
  compromise_detection_rate: number | null;
  compromised_runs: number;
  low_trust_rate_honest: number | null;
}

export interface TargetCheck {
  value: number | null;
  target: number;
  op: '>=' | '<=';
  passed: boolean;
}

export interface ModelHeadline {
  detection_rate?: number | null;
  tick_false_alarm_rate?: number | null;
  false_windows_per_run?: number | null;
  window_precision?: number | null;
  median_time_to_detect_s?: number | null;
  targets_passed?: string;
}

export interface ModelVersion {
  id: number;
  version: number;
  algorithm: string;
  status: 'training' | 'ready' | 'failed';
  is_active: boolean;
  created_at: string;
  created_by: string | null;
  trained_seconds: number | null;
  error: string | null;
  threshold: number;
  feature_spec: string | null;
  params: Record<string, number>;
  headline: ModelHeadline;
  targets_passed: number;
  targets_total: number;
  artifact_available: boolean | null;
  has_validation: boolean;
}

/** Outcomes on the validation split, kept apart from the test metrics (handover DH-09). */
export interface ValidationOutcomes {
  split: 'validation';
  dataset: string;
  runs: number;
  normal_runs: number;
  scenario_runs: number;
  by_type: Record<string, number>;
  model_version: number;
  computed: 'at training' | 'after training';
  computed_at: string;
  note: string;
  metrics: { ml: DetectionMetrics; baseline: DetectionMetrics; trust: TrustMetrics };
}

export interface ModelDetail extends ModelVersion {
  metrics: { ml?: DetectionMetrics; baseline?: DetectionMetrics; trust?: TrustMetrics };
  validation: ValidationOutcomes | null; // null: this version never recorded validation outcomes
  targets_check: Record<string, TargetCheck>;
  targets: Record<string, { metric: string; op: '>=' | '<='; value: number; label?: string; datasets?: EvalDatasetName[] }>;
  dataset: { path?: string; runs?: number; splits?: Record<string, Record<string, number>> };
}

export interface TrustAlert {
  run_id: number;
  segment_id: number;
  code: string;
  name: string;
  trust_score: number | null;
  trust_status: TrustStatus;
  top_factor: TrustFactor | null;
}

export interface DashboardSummary {
  total_runs: number;
  active_runs: number;
  completed_runs: number;
  total_segments: number;
  segments_by_state: Partial<Record<SegmentStateName, number>>;
  system_status: 'critical' | 'warning' | 'operational' | 'idle';
  latest_run: RunOut | null;
  telemetry_points: number;
  active_run: RunOut | null;
  live: {
    run_id: number;
    run_name: string;
    tick: number;
    avg_pressure_bar: number | null;
    throughput_m3h: number | null;
    segments_by_state: Record<SegmentStateName, number>;
    trust_alerts: TrustAlert[];
  } | null;
  anomaly_count_24h: number;
  anomaly_count_total: number;
  detection: DetectionRate | null; // administrators only: it needs each run's ground truth
  runs_flagged: { flagged: number; completed: number };
  trust_alerts: TrustAlert[];
  recent_trust_alerts: AlertItem[];
  alerts_per_day: { date: string; anomaly: number; low_trust: number }[];
  incidents_by_classification: Record<Classification, number>;
  open_investigations: IncidentSummary[];
  latest_evaluation: LatestEvaluationSummary | null;
  demo_run_id: number | null;
}

export interface ScenarioMethod {
  id: string;
  label: string;
  description: string;
  allowed_targets: string[];
}

export interface ScenarioType {
  id: string;
  label: string;
  description: string;
  cyber: boolean;
  magnitude_label: string | null;
  methods: ScenarioMethod[];
}

export interface ScenarioCatalog {
  types: ScenarioType[];
  segments: { id: number; code: string; name: string; segment_type: string; equipment: string | null }[];
  playback_speeds: number[];
  defaults: Record<string, number | boolean | string>;
}

export interface ScenarioLaunch {
  scenario_type: string;
  method?: string | null;
  target_segment?: string | null;
  magnitude?: number;
  variable?: 'pressure' | 'flow';
  onset_min?: number;
  ramp_min?: number;
  active_min?: number;
  recovery?: boolean;
  duration_min?: number;
  playback_speed?: number;
  seed?: number;
  name?: string;
  description?: string;
}

// ── Sprint 3: investigation and evaluation ───────────────────────────────────
export type Classification =
  | 'normal_behaviour'
  | 'physical_anomaly'
  | 'sensor_fault'
  | 'cyber_manipulation'
  | 'reporting_inconsistency'
  | 'uncertain';
export type IncidentStatus = 'developing' | 'open' | 'investigating' | 'resolved';
export type OtLayer = 'physical_process' | 'field_device' | 'control' | 'reporting';

export interface IncidentSummary {
  key: string;
  run_id: number;
  run_name: string;
  status: IncidentStatus;
  developing: boolean;
  classification: Classification;
  classification_label: string;
  confidence: number;
  confidence_label: string;
  segment_code: string | null;
  segment_name: string | null;
  ot_layers: OtLayer[];
  ot_layer_labels: string[];
  localisation_note: string;
  severity: Severity;
  start_tick: number;
  end_tick: number;
  detected_tick: number;
  detected_time: string;
  summary: string;
  evidence_count: number;
  status_note: string | null;
  resolved_by: number | null;
  resolved_at: string | null;
}

export interface EvidenceLink {
  type: 'run' | 'event';
  tick: number;
  segment: string | null;
  [k: string]: unknown;
}

export interface EvidenceItem {
  id: string;
  kind: string;
  tick: number;
  end_tick: number;
  segment: string | null;
  observation: string;
  interpretation: string;
  supports: Partial<Record<Classification, number>>;
  link: EvidenceLink;
}

export interface Hypothesis {
  category: Classification;
  score: number;
  evidence_ids: string[];
}

export interface ChainStage {
  stage: string;
  label: string;
  tick: number;
  segment: string | null;
  evidence_ids: string[];
}

export interface Technique {
  technique_id: string;
  name: string;
  tactic: string;
  reason: string;
  evidence_ids: string[];
}

export interface TimelineEntry {
  tick: number;
  segment: string | null;
  kind: string;
  observation: string;
  interpretation: string;
  evidence_id: string;
}

export interface IncidentDetail extends IncidentSummary {
  hypotheses: Hypothesis[];
  evidence: EvidenceItem[];
  timeline: TimelineEntry[];
  chain: ChainStage[];
  mitre: Technique[];
  actions: string[];
  uncertainty: Record<string, unknown> | null;
  windows: [string, number, number][];
}

export interface IncidentFilters {
  runId?: number;
  classification?: Classification;
  status?: IncidentStatus;
  severity?: Severity;
  segment?: string;
  sort?: string;
  order?: 'asc' | 'desc';
  limit?: number;
}

export type EvalSystem = 'A' | 'B' | 'C';
export type EvalDatasetName = 'development' | 'heldout';

export interface InvestigationMetrics {
  incident_detection: DetectionRate | null;
  classification_accuracy: DetectionRate | null;
  decision_coverage: DetectionRate | null;
  ambiguity_handled: DetectionRate | null;
  segment_localisation: DetectionRate | null;
  ot_layer_accuracy: DetectionRate | null;
  incidents_per_normal_run: number | null;
  unexplained_per_normal_run: number | null;
  incidents_outside_event: number;
  confusion: Record<string, Record<string, number>>;
}

export interface EvaluationDataset {
  runs: number;
  trust: TrustMetrics;
  systems: Record<EvalSystem, { detection: DetectionMetrics; investigation: InvestigationMetrics }>;
}

export interface EvaluationResults {
  engine_version: string;
  model_version: number | string | null;
  created_at: string;
  datasets: Record<EvalDatasetName, EvaluationDataset>;
  targets: Record<string, { metric: string; op: '>=' | '<='; value: number; label?: string; datasets?: EvalDatasetName[] }>;
  targets_check: Record<EvalDatasetName, Record<string, TargetCheck>>;
}

export interface EvaluationRunOut {
  id: number;
  version: number;
  status: 'running' | 'ready' | 'failed';
  created_at: string;
  created_by?: string | null;
  model_version: number | null;
  engine_version: string | null;
  seconds: number | null;
  error: string | null;
  shipped: boolean;
}

export interface EvaluationDetail extends EvaluationRunOut {
  results: EvaluationResults | null;
}

export interface EvaluationHeadline {
  detection_rate: number | null;
  incidents_per_normal_run: number | null;
  classification_accuracy: number | null;
}

export interface LatestEvaluationSummary {
  id: number;
  version: number;
  created_at: string;
  development: Record<EvalSystem, EvaluationHeadline>;
  heldout: Record<EvalSystem, EvaluationHeadline>;
}

export interface DemoState {
  run_id: number | null;
  [k: string]: unknown;
}
