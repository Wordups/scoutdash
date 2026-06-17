export type EvidenceType = "neutral" | "strength" | "development_area";

export interface Organization {
  id: string;
  name: string;
  sport_label: string | null;
  created_at: string;
  updated_at: string;
}

export interface Team {
  id: string;
  organization_id: string;
  name: string;
  sport: string | null;
  season: string | null;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface Athlete {
  id: string;
  organization_id: string;
  team_id: string;
  display_name: string;
  first_name: string | null;
  last_name: string | null;
  jersey_number: string | null;
  position: string | null;
  external_id: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface Event {
  id: string;
  organization_id: string;
  team_id: string;
  name: string;
  sport: string | null;
  opponent: string | null;
  event_date: string | null;
  location: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface VideoAsset {
  id: string;
  organization_id: string;
  team_id: string;
  event_id: string | null;
  title: string;
  original_filename: string | null;
  content_type: string | null;
  storage_backend: string;
  storage_key: string;
  storage_url: string | null;
  duration_seconds: number | null;
  fps: number | null;
  frame_count: number | null;
  created_at: string;
  updated_at: string;
}

export interface VideoFrame {
  id: string;
  video_id: string;
  frame_number: number;
  timestamp_seconds: number;
  storage_key: string;
  frame_url: string | null;
  width: number | null;
  height: number | null;
  created_at: string;
  updated_at: string;
}

export interface VideoProcessRead {
  video: VideoAsset;
  frames: VideoFrame[];
  frame_count_extracted: number;
}

export interface VideoReadiness {
  video_id: string;
  file_available: boolean;
  processing_ready: boolean;
  storage_persistent: boolean;
  extracted_frame_count: number;
  message: string;
}

export interface Category {
  id: string;
  organization_id: string;
  sport: string | null;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface TagDefinition {
  id: string;
  category_id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface Clip {
  id: string;
  organization_id: string;
  team_id: string;
  event_id: string | null;
  video_id: string;
  title: string | null;
  start_time_seconds: number;
  end_time_seconds: number;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface EvidenceTag {
  id: string;
  organization_id: string;
  team_id: string;
  athlete_id: string;
  event_id: string | null;
  video_id: string;
  clip_id: string | null;
  category_id: string;
  tag_id: string;
  timestamp_seconds: number;
  evidence_type: EvidenceType;
  notes: string | null;
  created_by: string | null;
  athlete_name: string;
  category_name: string;
  tag_name: string;
  video_title: string;
  clip: Clip | null;
  created_at: string;
  updated_at: string;
}

export interface Note {
  id: string;
  organization_id: string;
  team_id: string | null;
  athlete_id: string | null;
  video_id: string | null;
  clip_id: string | null;
  evidence_tag_id: string | null;
  author_name: string | null;
  body: string;
  created_at: string;
  updated_at: string;
}

export interface BehaviorFrequency {
  category_id: string;
  category_name: string;
  tag_id: string;
  tag_name: string;
  evidence_count: number;
  video_count: number;
  event_count: number;
  latest_timestamp_seconds: number | null;
}

export interface AthleteProfile {
  athlete: Athlete;
  strengths: BehaviorFrequency[];
  development_areas: BehaviorFrequency[];
  behavior_frequency: BehaviorFrequency[];
  behavior_consistency: BehaviorFrequency[];
  evidence_clips: EvidenceTag[];
  coach_notes: Note[];
}

export interface ReportEvidenceReference {
  evidence_tag_id: string;
  clip_id: string | null;
  video_id: string;
  video_title: string;
  category_name: string;
  tag_name: string;
  timestamp_seconds: number;
  clip_start_seconds: number | null;
  clip_end_seconds: number | null;
  notes: string | null;
}

export interface ReportNoteReference {
  note_id: string;
  author_name: string | null;
  body: string;
  created_at: string;
}

export interface ReportSection {
  key: string;
  title: string;
  summary: string;
  observations: string[];
  supporting_evidence: ReportEvidenceReference[];
  supporting_notes: ReportNoteReference[];
}

export interface AthleteDevelopmentReportData {
  athlete: Athlete;
  team: Team;
  generated_at: string;
  report_title: string;
  evidence_count: number;
  note_count: number;
  sections: ReportSection[];
  traceability_statement: string;
}

export interface AthleteReport {
  id: string;
  organization_id: string;
  team_id: string;
  athlete_id: string;
  title: string;
  report_type: string;
  status: string;
  generated_by: string | null;
  report_data: AthleteDevelopmentReportData;
  evidence_tag_ids: string[];
  note_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface VisionTrack {
  id: string;
  organization_id: string;
  video_id: string;
  athlete_id: string | null;
  track_label: string | null;
  source: string;
  status: string;
  frame_start: number;
  frame_end: number;
  bounding_data: Record<string, unknown>;
  segmentation_metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface TrackTimelineMoment {
  frame_id: string;
  frame_number: number;
  timestamp_seconds: number;
  frame_url: string | null;
  box: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
}

export interface VisionTrackTimeline {
  track: VisionTrack;
  athlete: Athlete | null;
  video: VideoAsset;
  moments: TrackTimelineMoment[];
}
