"use client";

import {
  Activity,
  AlertTriangle,
  Calendar,
  ClipboardList,
  Crosshair,
  Download,
  Eye,
  FileText,
  LayoutDashboard,
  Layers3,
  ListChecks,
  Menu,
  Plus,
  RefreshCw,
  Save,
  Search,
  Settings,
  Tags,
  Upload,
  UserRound,
  Users,
  Video,
  X
} from "lucide-react";
import type { ChangeEvent, FormEvent, MouseEvent, ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";

import { apiGet, apiPost, apiUpload, apiUrl, mediaUrl } from "@/lib/api";
import type {
  Athlete,
  AthleteProfile,
  AthleteReport,
  Category,
  Event,
  EvidenceTag,
  EvidenceType,
  Organization,
  TagDefinition,
  Team,
  TrackTimelineMoment,
  VideoAsset,
  VideoFrame,
  VideoProcessRead,
  VideoReadiness,
  VisionTrack,
  ReportEvidenceReference,
  VisionTrackTimeline
} from "@/types/scoutdash";

type Tab = "dashboard" | "review" | "directory" | "taxonomy" | "reports";
type Notice = { kind: "idle" | "loading" | "success" | "error"; message: string };

const initialNotice: Notice = { kind: "idle", message: "" };
const workflowSteps = ["Upload Film", "Break Down Film", "Review Findings", "Review Players", "Generate Reports"] as const;

export function ScoutDashApp() {
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const [tab, setTab] = useState<Tab>("dashboard");
  const [isTabletNavOpen, setIsTabletNavOpen] = useState(false);
  const [notice, setNotice] = useState<Notice>(initialNotice);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [athletes, setAthletes] = useState<Athlete[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [videos, setVideos] = useState<VideoAsset[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [tags, setTags] = useState<TagDefinition[]>([]);
  const [evidence, setEvidence] = useState<EvidenceTag[]>([]);
  const [profile, setProfile] = useState<AthleteProfile | null>(null);
  const [reports, setReports] = useState<AthleteReport[]>([]);
  const [activeReport, setActiveReport] = useState<AthleteReport | null>(null);
  const [isGeneratingReport, setIsGeneratingReport] = useState(false);
  const [tracks, setTracks] = useState<VisionTrack[]>([]);
  const [frames, setFrames] = useState<VideoFrame[]>([]);
  const [selectedFrameId, setSelectedFrameId] = useState("");
  const [selectedPoint, setSelectedPoint] = useState<{ x: number; y: number } | null>(null);
  const [trackTimeline, setTrackTimeline] = useState<VisionTrackTimeline | null>(null);
  const [isProcessingVideo, setIsProcessingVideo] = useState(false);
  const [isCreatingTrack, setIsCreatingTrack] = useState(false);
  const [videoReadiness, setVideoReadiness] = useState<VideoReadiness | null>(null);
  const [isUploadingVideo, setIsUploadingVideo] = useState(false);
  const [isImportingVideo, setIsImportingVideo] = useState(false);

  const [selectedOrgId, setSelectedOrgId] = useState("");
  const [selectedTeamId, setSelectedTeamId] = useState("");
  const [selectedAthleteId, setSelectedAthleteId] = useState("");
  const [selectedEventId, setSelectedEventId] = useState("");
  const [selectedVideoId, setSelectedVideoId] = useState("");
  const [currentTime, setCurrentTime] = useState(0);

  const [organizationForm, setOrganizationForm] = useState({ name: "", sport_label: "" });
  const [teamForm, setTeamForm] = useState({ name: "", sport: "", season: "" });
  const [athleteForm, setAthleteForm] = useState({ display_name: "", jersey_number: "", position: "" });
  const [eventForm, setEventForm] = useState({ name: "", opponent: "", event_date: "", location: "" });
  const [categoryForm, setCategoryForm] = useState({ name: "", sport: "", description: "" });
  const [tagDefinitionForm, setTagDefinitionForm] = useState({ category_id: "", name: "", description: "" });
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [urlImportForm, setUrlImportForm] = useState({ title: "", source_url: "" });
  const [tagForm, setTagForm] = useState({
    athlete_id: "",
    category_id: "",
    tag_id: "",
    timestamp_seconds: "0.00",
    clip_start_seconds: "",
    clip_end_seconds: "",
    evidence_type: "neutral" as EvidenceType,
    notes: ""
  });
  const [noteForm, setNoteForm] = useState({ author_name: "", body: "" });

  const selectedOrganization = organizations.find((item) => item.id === selectedOrgId) ?? null;
  const selectedTeam = teams.find((item) => item.id === selectedTeamId) ?? null;
  const selectedAthlete = athletes.find((item) => item.id === selectedAthleteId) ?? null;
  const selectedVideo = videos.find((item) => item.id === selectedVideoId) ?? null;
  const selectedFrame = useMemo(
    () => frames.find((item) => item.id === selectedFrameId) ?? frames[0] ?? null,
    [frames, selectedFrameId]
  );
  const tagsForCategory = useMemo(
    () => tags.filter((item) => item.category_id === tagForm.category_id),
    [tagForm.category_id, tags]
  );
  const filteredEvidence = useMemo(() => {
    return evidence.filter((item) => {
      if (selectedAthleteId && item.athlete_id !== selectedAthleteId) return false;
      if (selectedVideoId && item.video_id !== selectedVideoId) return false;
      return true;
    });
  }, [evidence, selectedAthleteId, selectedVideoId]);
  const currentWorkflowStep = useMemo(() => {
    if (!selectedVideoId) return "Upload Film";
    if (!frames.length && !trackTimeline) return "Break Down Film";
    if (!filteredEvidence.length) return "Review Findings";
    if (!selectedAthleteId || !profile) return "Review Players";
    return "Generate Reports";
  }, [filteredEvidence.length, frames.length, profile, selectedAthleteId, selectedVideoId, trackTimeline]);
  const navigationItems: Array<{ id: Tab; label: string; icon: ReactNode }> = [
    { id: "dashboard", label: "Dashboard", icon: <LayoutDashboard size={19} /> },
    { id: "review", label: "Film Room", icon: <Video size={19} /> },
    { id: "directory", label: "Setup", icon: <Settings size={19} /> },
    { id: "taxonomy", label: "Tag Library", icon: <Tags size={19} /> },
    { id: "reports", label: "Reports", icon: <FileText size={19} /> }
  ];
  const activeSectionLabel = navigationItems.find((item) => item.id === tab)?.label ?? "Dashboard";

  function navigateTo(nextTab: Tab) {
    setTab(nextTab);
    setIsTabletNavOpen(false);
  }

  useEffect(() => {
    void loadOrganizations();
  }, []);

  useEffect(() => {
    if (!selectedOrgId) return;
    void loadOrganizationScope(selectedOrgId);
  }, [selectedOrgId]);

  useEffect(() => {
    if (!selectedTeamId) return;
    void loadTeamScope(selectedTeamId);
  }, [selectedTeamId]);

  useEffect(() => {
    if (!selectedAthleteId) {
      setProfile(null);
      setReports([]);
      setActiveReport(null);
      return;
    }
    setTagForm((value) => ({ ...value, athlete_id: selectedAthleteId }));
    void loadAthleteProfile(selectedAthleteId);
    void loadReports(selectedAthleteId);
  }, [selectedAthleteId]);

  useEffect(() => {
    if (!selectedVideoId) {
      setFrames([]);
      setSelectedFrameId("");
      setSelectedPoint(null);
      setTracks([]);
      setTrackTimeline(null);
      setVideoReadiness(null);
      return;
    }
    void loadEvidence();
    void loadFrames(selectedVideoId);
    void loadTracks(selectedVideoId);
    void loadVideoReadiness(selectedVideoId);
  }, [selectedVideoId]);

  useEffect(() => {
    if (!tagForm.category_id && categories.length > 0) {
      setTagForm((value) => ({ ...value, category_id: categories[0].id }));
      setTagDefinitionForm((value) => ({ ...value, category_id: categories[0].id }));
    }
  }, [categories, tagForm.category_id]);

  useEffect(() => {
    if (tagsForCategory.length === 0) {
      setTagForm((value) => ({ ...value, tag_id: "" }));
      return;
    }
    if (!tagsForCategory.some((item) => item.id === tagForm.tag_id)) {
      setTagForm((value) => ({ ...value, tag_id: tagsForCategory[0].id }));
    }
  }, [tagForm.tag_id, tagsForCategory]);

  async function loadOrganizations() {
    try {
      setNotice({ kind: "loading", message: "Loading workspace" });
      const data = await apiGet<Organization[]>("/organizations");
      setOrganizations(data);
      if (!selectedOrgId && data[0]) setSelectedOrgId(data[0].id);
      setNotice(initialNotice);
    } catch (error) {
      showError(error);
    }
  }

  async function loadOrganizationScope(organizationId: string) {
    try {
      const [teamData, categoryData, tagData] = await Promise.all([
        apiGet<Team[]>(`/teams?organization_id=${organizationId}`),
        apiGet<Category[]>(`/categories?organization_id=${organizationId}`),
        apiGet<TagDefinition[]>(`/tags?organization_id=${organizationId}`)
      ]);
      setTeams(teamData);
      setCategories(categoryData);
      setTags(tagData);
      if (!teamData.some((item) => item.id === selectedTeamId)) {
        setSelectedTeamId(teamData[0]?.id ?? "");
      }
      if (!categoryData.some((item) => item.id === tagDefinitionForm.category_id)) {
        setTagDefinitionForm((value) => ({ ...value, category_id: categoryData[0]?.id ?? "" }));
      }
    } catch (error) {
      showError(error);
    }
  }

  async function loadTeamScope(teamId: string) {
    try {
      const [athleteData, eventData, videoData] = await Promise.all([
        apiGet<Athlete[]>(`/athletes?team_id=${teamId}`),
        apiGet<Event[]>(`/events?team_id=${teamId}`),
        apiGet<VideoAsset[]>(`/videos?team_id=${teamId}`)
      ]);
      setAthletes(athleteData);
      setEvents(eventData);
      setVideos(videoData);
      if (!athleteData.some((item) => item.id === selectedAthleteId)) {
        setSelectedAthleteId(athleteData[0]?.id ?? "");
      }
      if (!eventData.some((item) => item.id === selectedEventId)) {
        setSelectedEventId(eventData[0]?.id ?? "");
      }
      if (!videoData.some((item) => item.id === selectedVideoId)) {
        setSelectedVideoId(videoData[0]?.id ?? "");
      }
      await loadEvidence(teamId);
    } catch (error) {
      showError(error);
    }
  }

  async function loadEvidence(teamId = selectedTeamId) {
    if (!teamId) return;
    try {
      const data = await apiGet<EvidenceTag[]>(`/evidence-tags?team_id=${teamId}`);
      setEvidence(data);
    } catch (error) {
      showError(error);
    }
  }

  async function loadAthleteProfile(athleteId: string) {
    try {
      const data = await apiGet<AthleteProfile>(`/athletes/${athleteId}/profile`);
      setProfile(data);
    } catch (error) {
      showError(error);
    }
  }

  async function loadReports(athleteId: string) {
    try {
      const data = await apiGet<AthleteReport[]>(`/athletes/${athleteId}/reports`);
      setReports(data);
      setActiveReport(data[0] ?? null);
    } catch (error) {
      showError(error);
    }
  }

  async function loadFrames(videoId = selectedVideoId) {
    if (!videoId) return;
    try {
      const data = await apiGet<VideoFrame[]>(`/videos/${videoId}/frames`);
      setFrames(data);
      setSelectedFrameId((current) => (data.some((item) => item.id === current) ? current : data[0]?.id ?? ""));
      if (!data.length) {
        setSelectedPoint(null);
        setTrackTimeline(null);
      }
    } catch (error) {
      showError(error);
    }
  }

  async function loadVideoReadiness(videoId = selectedVideoId) {
    if (!videoId) return;
    try {
      setVideoReadiness(await apiGet<VideoReadiness>(`/videos/${videoId}/readiness`));
    } catch (error) {
      setVideoReadiness(null);
      showError(error);
    }
  }

  async function loadTrackTimeline(trackId: string) {
    try {
      const data = await apiGet<VisionTrackTimeline>(`/vision/tracks/${trackId}/timeline`);
      setTrackTimeline(data);
    } catch (error) {
      showError(error);
    }
  }

  async function loadTracks(videoId = selectedVideoId) {
    if (!videoId) return;
    try {
      const data = await apiGet<VisionTrack[]>(`/vision/tracks?video_id=${videoId}`);
      setTracks(data);
      const activeTrackId =
        trackTimeline?.video.id === videoId && data.some((item) => item.id === trackTimeline.track.id)
          ? trackTimeline.track.id
          : data[0]?.id;
      if (activeTrackId) {
        await loadTrackTimeline(activeTrackId);
      } else {
        setTrackTimeline(null);
      }
    } catch (error) {
      showError(error);
    }
  }

  async function createOrganization(event: FormEvent) {
    event.preventDefault();
    try {
      const created = await apiPost<Organization>("/organizations", cleanPayload(organizationForm));
      setOrganizations((items) => [created, ...items]);
      setSelectedOrgId(created.id);
      setOrganizationForm({ name: "", sport_label: "" });
      showSuccess("Organization saved");
    } catch (error) {
      showError(error);
    }
  }

  async function createTeam(event: FormEvent) {
    event.preventDefault();
    if (!selectedOrgId) return;
    try {
      const created = await apiPost<Team>("/teams", cleanPayload({ ...teamForm, organization_id: selectedOrgId }));
      setTeams((items) => [created, ...items]);
      setSelectedTeamId(created.id);
      setTeamForm({ name: "", sport: "", season: "" });
      showSuccess("Team saved");
    } catch (error) {
      showError(error);
    }
  }

  async function createAthlete(event: FormEvent) {
    event.preventDefault();
    if (!selectedOrgId || !selectedTeamId) return;
    try {
      const created = await apiPost<Athlete>(
        "/athletes",
        cleanPayload({ ...athleteForm, organization_id: selectedOrgId, team_id: selectedTeamId, status: "active" })
      );
      setAthletes((items) => [...items, created].sort((a, b) => a.display_name.localeCompare(b.display_name)));
      setSelectedAthleteId(created.id);
      setAthleteForm({ display_name: "", jersey_number: "", position: "" });
      showSuccess("Athlete saved");
    } catch (error) {
      showError(error);
    }
  }

  async function createEvent(event: FormEvent) {
    event.preventDefault();
    if (!selectedOrgId || !selectedTeamId) return;
    try {
      const created = await apiPost<Event>(
        "/events",
        cleanPayload({
          ...eventForm,
          organization_id: selectedOrgId,
          team_id: selectedTeamId,
          sport: selectedTeam?.sport ?? null
        })
      );
      setEvents((items) => [created, ...items]);
      setSelectedEventId(created.id);
      setEventForm({ name: "", opponent: "", event_date: "", location: "" });
      showSuccess("Event saved");
    } catch (error) {
      showError(error);
    }
  }

  async function createCategory(event: FormEvent) {
    event.preventDefault();
    if (!selectedOrgId) return;
    try {
      const created = await apiPost<Category>(
        "/categories",
        cleanPayload({
          ...categoryForm,
          sport: categoryForm.sport || selectedTeam?.sport || selectedOrganization?.sport_label || null,
          organization_id: selectedOrgId
        })
      );
      setCategories((items) => [...items, created].sort((a, b) => a.name.localeCompare(b.name)));
      setTagDefinitionForm((value) => ({ ...value, category_id: created.id }));
      setTagForm((value) => ({ ...value, category_id: created.id }));
      setCategoryForm({ name: "", sport: "", description: "" });
      showSuccess("Category saved");
    } catch (error) {
      showError(error);
    }
  }

  async function createTagDefinition(event: FormEvent) {
    event.preventDefault();
    if (!tagDefinitionForm.category_id) return;
    try {
      const created = await apiPost<TagDefinition>("/tags", cleanPayload(tagDefinitionForm));
      setTags((items) => [...items, created].sort((a, b) => a.name.localeCompare(b.name)));
      setTagForm((value) => ({ ...value, category_id: created.category_id, tag_id: created.id }));
      setTagDefinitionForm((value) => ({ ...value, name: "", description: "" }));
      showSuccess("Tag saved");
    } catch (error) {
      showError(error);
    }
  }

  async function uploadVideo(event: FormEvent) {
    event.preventDefault();
    if (!selectedOrgId || !selectedTeamId || !uploadFile) return;
    try {
      setIsUploadingVideo(true);
      const body = new FormData();
      body.append("organization_id", selectedOrgId);
      body.append("team_id", selectedTeamId);
      if (selectedEventId) body.append("event_id", selectedEventId);
      body.append("title", uploadTitle || uploadFile.name);
      body.append("file", uploadFile);
      const created = await apiUpload<VideoAsset>("/videos/upload", body);
      setVideos((items) => [created, ...items]);
      setSelectedVideoId(created.id);
      setUploadTitle("");
      setUploadFile(null);
      showSuccess("Film uploaded");
    } catch (error) {
      showError(error);
    } finally {
      setIsUploadingVideo(false);
    }
  }

  async function importVideoUrl(event: FormEvent) {
    event.preventDefault();
    if (!selectedOrgId || !selectedTeamId || !urlImportForm.source_url) return;
    try {
      setIsImportingVideo(true);
      const created = await apiPost<VideoAsset>(
        "/videos/from-url",
        cleanPayload({
          organization_id: selectedOrgId,
          team_id: selectedTeamId,
          event_id: selectedEventId || null,
          title: urlImportForm.title || "Imported film",
          source_url: urlImportForm.source_url
        })
      );
      setVideos((items) => [created, ...items]);
      setSelectedVideoId(created.id);
      setUrlImportForm({ title: "", source_url: "" });
      showSuccess("Film imported");
    } catch (error) {
      showError(error);
    } finally {
      setIsImportingVideo(false);
    }
  }

  async function processSelectedVideo() {
    if (!selectedVideoId) return;
    try {
      setIsProcessingVideo(true);
      const processed = await apiPost<VideoProcessRead>(`/videos/${selectedVideoId}/process`, {
        sample_fps: 1,
        max_frames: 240
      });
      setVideos((items) => items.map((item) => (item.id === processed.video.id ? processed.video : item)));
      setFrames(processed.frames);
      setSelectedFrameId(processed.frames[0]?.id ?? "");
      setSelectedPoint(null);
      setTrackTimeline(null);
      await loadVideoReadiness(processed.video.id);
      showSuccess(`${processed.frame_count_extracted} review moments ready`);
    } catch (error) {
      showError(error);
    } finally {
      setIsProcessingVideo(false);
    }
  }

  async function saveEvidence(event: FormEvent) {
    event.preventDefault();
    if (!selectedOrgId || !selectedTeamId || !selectedVideoId) return;
    const athleteId = tagForm.athlete_id || selectedAthleteId;
    if (!athleteId || !tagForm.category_id || !tagForm.tag_id) return;
    try {
      const created = await apiPost<EvidenceTag>(
        "/evidence-tags",
        cleanPayload({
          organization_id: selectedOrgId,
          team_id: selectedTeamId,
          athlete_id: athleteId,
          event_id: selectedEventId || selectedVideo?.event_id || null,
          video_id: selectedVideoId,
          category_id: tagForm.category_id,
          tag_id: tagForm.tag_id,
          timestamp_seconds: numeric(tagForm.timestamp_seconds, currentTime),
          clip_start_seconds: optionalNumber(tagForm.clip_start_seconds),
          clip_end_seconds: optionalNumber(tagForm.clip_end_seconds),
          evidence_type: tagForm.evidence_type,
          notes: tagForm.notes
        })
      );
      setEvidence((items) => [created, ...items]);
      setTagForm((value) => ({ ...value, notes: "", clip_start_seconds: "", clip_end_seconds: "" }));
      if (athleteId) await loadAthleteProfile(athleteId);
      showSuccess("Evidence saved");
    } catch (error) {
      showError(error);
    }
  }

  async function saveCoachNote(event: FormEvent) {
    event.preventDefault();
    if (!selectedOrgId || !selectedAthleteId || !noteForm.body) return;
    try {
      await apiPost("/notes", cleanPayload({ ...noteForm, organization_id: selectedOrgId, athlete_id: selectedAthleteId }));
      setNoteForm({ author_name: "", body: "" });
      await loadAthleteProfile(selectedAthleteId);
      showSuccess("Note saved");
    } catch (error) {
      showError(error);
    }
  }

  async function generateReport() {
    if (!selectedAthleteId) return;
    try {
      setIsGeneratingReport(true);
      const created = await apiPost<AthleteReport>(`/athletes/${selectedAthleteId}/reports`, {
        generated_by: "Coach"
      });
      setReports((items) => [created, ...items]);
      setActiveReport(created);
      showSuccess("Development report generated");
    } catch (error) {
      showError(error);
    } finally {
      setIsGeneratingReport(false);
    }
  }

  function downloadReport(reportId: string) {
    window.open(apiUrl(`/reports/${reportId}/pdf`), "_blank", "noopener,noreferrer");
  }

  async function createTrackSeed() {
    if (!selectedVideoId || !selectedFrame || !selectedPoint) return;
    try {
      setIsCreatingTrack(true);
      const timeline = await apiPost<VisionTrackTimeline>(
        "/vision/track-seeds",
        cleanPayload({
          video_id: selectedVideoId,
          athlete_id: selectedAthleteId || null,
          frame_id: selectedFrame.id,
          x_ratio: selectedPoint.x,
          y_ratio: selectedPoint.y,
          track_label: selectedAthlete ? athleteLabel(selectedAthlete) : "Coach-selected player"
        })
      );
      setTrackTimeline(timeline);
      setTracks((items) => [timeline.track, ...items.filter((item) => item.id !== timeline.track.id)]);
      showSuccess("Athlete view saved");
    } catch (error) {
      showError(error);
    } finally {
      setIsCreatingTrack(false);
    }
  }

  function selectFramePoint(frame: VideoFrame, event: MouseEvent<HTMLButtonElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
    const y = Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height));
    setSelectedFrameId(frame.id);
    setSelectedPoint({ x, y });
  }

  function useTimelineMomentForTag(moment: TrackTimelineMoment) {
    const clipStart = Math.max(0, moment.timestamp_seconds - 3);
    const clipEnd = moment.timestamp_seconds + 3;
    setCurrentTime(moment.timestamp_seconds);
    setTagForm((value) => ({
      ...value,
      athlete_id: trackTimeline?.track.athlete_id ?? selectedAthleteId,
      timestamp_seconds: moment.timestamp_seconds.toFixed(2),
      clip_start_seconds: clipStart.toFixed(2),
      clip_end_seconds: clipEnd.toFixed(2)
    }));
    setTab("review");
    showSuccess("Timeline moment ready for evidence tagging");
  }

  function jumpTo(seconds: number) {
    if (!videoRef.current) return;
    videoRef.current.currentTime = seconds;
    void videoRef.current.play();
  }

  function captureTimestamp() {
    const seconds = videoRef.current?.currentTime ?? currentTime;
    setCurrentTime(seconds);
    setTagForm((value) => ({ ...value, timestamp_seconds: seconds.toFixed(2) }));
  }

  function onUploadFileChange(event: ChangeEvent<HTMLInputElement>) {
    setUploadFile(event.target.files?.[0] ?? null);
  }

  function showSuccess(message: string) {
    setNotice({ kind: "success", message });
    window.setTimeout(() => setNotice(initialNotice), 2200);
  }

  function showError(error: unknown) {
    const rawMessage = error instanceof Error ? error.message : "";
    const message =
      rawMessage === "Failed to fetch"
        ? "ScoutDash could not load saved team data. Check the connection and refresh."
        : rawMessage === "Video file not found on local storage" || rawMessage.includes("stored video file is missing")
          ? "This film file is missing. Upload the original film again, then select the new copy."
        : rawMessage || "Something went wrong";
    setNotice({ kind: "error", message });
  }

  return (
    <div className="min-h-screen text-ink">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-60 flex-col border-r border-white/10 bg-slate-950 px-3 py-4 text-white lg:flex">
        <BrandMark />
        <nav aria-label="Primary navigation" className="mt-8 space-y-1">
          {navigationItems.map((item) => (
            <SidebarNavButton active={tab === item.id} icon={item.icon} key={item.id} label={item.label} onClick={() => navigateTo(item.id)} />
          ))}
        </nav>
        <div className="mt-auto rounded-md border border-white/10 bg-white/5 p-3 text-sm">
          <div className="font-semibold">{selectedTeam?.name || "Select a team"}</div>
          <div className="mt-1 text-xs text-slate-400">{selectedOrganization?.name || "Program setup"}</div>
        </div>
      </aside>

      {isTabletNavOpen ? (
        <button aria-label="Close navigation" className="fixed inset-0 z-40 hidden bg-slate-950/30 md:block lg:hidden" onClick={() => setIsTabletNavOpen(false)} type="button" />
      ) : null}
      <aside className={`fixed inset-y-0 left-0 z-50 hidden w-72 flex-col bg-slate-950 px-4 py-4 text-white shadow-2xl transition-transform md:flex lg:hidden ${isTabletNavOpen ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="flex items-center justify-between">
          <BrandMark />
          <button aria-label="Close navigation" className="flex h-11 w-11 items-center justify-center rounded-md text-slate-300 hover:bg-white/10 hover:text-white" onClick={() => setIsTabletNavOpen(false)} type="button">
            <X size={20} />
          </button>
        </div>
        <nav aria-label="Tablet navigation" className="mt-8 space-y-1">
          {navigationItems.map((item) => (
            <SidebarNavButton active={tab === item.id} icon={item.icon} key={item.id} label={item.label} onClick={() => navigateTo(item.id)} />
          ))}
        </nav>
      </aside>

      <div className="min-h-screen pb-24 lg:pl-60 lg:pb-0">
        <header className="z-30 border-b border-line bg-white/95 backdrop-blur md:sticky md:top-0">
          <div className="mx-auto flex max-w-[1480px] flex-col gap-3 px-4 py-3 sm:px-6 xl:px-8">
            <div className="flex items-center justify-between gap-3">
              <div className="flex min-w-0 items-center gap-3">
                <button aria-label="Open navigation" className="hidden h-11 w-11 shrink-0 items-center justify-center rounded-md border border-line bg-white md:flex lg:hidden" onClick={() => setIsTabletNavOpen(true)} type="button">
                  <Menu size={20} />
                </button>
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-field text-white lg:hidden">
                  <Activity aria-hidden="true" size={21} />
                </div>
                <div className="min-w-0">
                  <div className="truncate text-lg font-semibold lg:text-xl">{activeSectionLabel}</div>
                  <div className="truncate text-xs text-slate-500 sm:text-sm">{tab === "dashboard" ? "Your coaching workspace" : "ScoutDash"}</div>
                </div>
              </div>
              <button
                aria-label="Refresh workspace"
                className="inline-flex h-11 items-center justify-center gap-2 rounded-md border border-line bg-white px-3 text-sm font-medium hover:border-review"
                onClick={() => {
                  void loadOrganizations();
                  if (selectedOrgId) void loadOrganizationScope(selectedOrgId);
                  if (selectedTeamId) void loadTeamScope(selectedTeamId);
                }}
                title="Refresh workspace"
                type="button"
              >
                <RefreshCw aria-hidden="true" size={17} />
                <span className="hidden sm:inline">Refresh</span>
              </button>
            </div>
            <div className="grid gap-2 sm:grid-cols-3">
          <SelectBox
            label="Program"
            value={selectedOrgId}
            onChange={setSelectedOrgId}
            options={organizations.map((item) => ({ value: item.id, label: item.name }))}
            icon={<Users size={16} />}
          />
          <SelectBox
            label="Team"
            value={selectedTeamId}
            onChange={setSelectedTeamId}
            options={teams.map((item) => ({
              value: item.id,
              label: [item.name, item.season].filter(Boolean).join(" · ")
            }))}
            icon={<ClipboardList size={16} />}
          />
          <SelectBox
            label="Athlete"
            value={selectedAthleteId}
            onChange={setSelectedAthleteId}
            options={athletes.map((item) => ({ value: item.id, label: athleteLabel(item) }))}
            icon={<UserRound size={16} />}
          />
            </div>
          </div>
        </header>

        <main className="mx-auto max-w-[1480px] px-4 py-4 sm:px-6 xl:px-8">
          {notice.message ? (
            <div className={`mb-4 flex items-start gap-2 rounded-md border px-3 py-2 text-sm ${notice.kind === "error" ? "border-red-200 bg-red-50 text-red-800" : "border-emerald-200 bg-emerald-50 text-emerald-800"}`}>
              {notice.kind === "error" ? <AlertTriangle className="mt-0.5 shrink-0" size={16} /> : <ListChecks className="mt-0.5 shrink-0" size={16} />}
              {notice.message}
            </div>
          ) : null}
          {tab === "dashboard" ? renderDashboard() : null}
          {tab === "review" ? renderReview() : null}
          {tab === "directory" ? renderDirectory() : null}
          {tab === "taxonomy" ? renderTaxonomy() : null}
          {tab === "reports" ? renderReports() : null}
        </main>
      </div>

      <nav aria-label="Mobile navigation" className="fixed inset-x-0 bottom-0 z-50 grid grid-cols-5 border-t border-line bg-white px-1 pb-[max(0.35rem,env(safe-area-inset-bottom))] pt-1 shadow-[0_-8px_24px_rgba(31,41,51,0.08)] md:hidden">
        {navigationItems.map((item) => (
          <button
            aria-current={tab === item.id ? "page" : undefined}
            className={`flex min-h-14 min-w-0 flex-col items-center justify-center gap-1 rounded-md px-1 text-[11px] font-semibold ${tab === item.id ? "bg-teal-50 text-field" : "text-slate-500"}`}
            key={item.id}
            onClick={() => navigateTo(item.id)}
            type="button"
          >
            {item.icon}
            <span className="w-full truncate">{item.label}</span>
          </button>
        ))}
      </nav>
    </div>
  );

  function renderDashboard() {
    return (
      <div className="space-y-4">
        <CoachWorkflow currentStep={currentWorkflowStep} />
        <div className="grid gap-4 md:grid-cols-2">
          <section className="rounded-md border border-line bg-white p-4 shadow-panel">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-xs font-semibold uppercase text-slate-500">Continue coaching</div>
                <h2 className="mt-1 text-lg font-semibold">{selectedVideo?.title || "Choose your next film"}</h2>
                <p className="mt-1 text-sm text-slate-600">Next step: {currentWorkflowStep}</p>
              </div>
              <Video className="shrink-0 text-field" size={22} />
            </div>
            <button className="mt-5 inline-flex h-11 w-full items-center justify-center gap-2 rounded-md bg-field px-4 text-sm font-semibold text-white hover:bg-teal-800" onClick={() => navigateTo("review")} type="button">
              <Video size={17} /> Open Film Room
            </button>
          </section>

          <section className="rounded-md border border-line bg-white p-4 shadow-panel">
            <div className="text-xs font-semibold uppercase text-slate-500">Team workspace</div>
            <h2 className="mt-1 text-lg font-semibold">{selectedTeam?.name || "No team selected"}</h2>
            <div className="mt-4 grid grid-cols-2 gap-2">
              <Metric label="Athletes" value={athletes.length.toLocaleString()} />
              <Metric label="Films" value={videos.length.toLocaleString()} />
              <Metric label="Evidence" value={evidence.length.toLocaleString()} />
              <Metric label="Reports" value={reports.length.toLocaleString()} />
            </div>
          </section>

          <section className="rounded-md border border-line bg-white p-4 shadow-panel">
            <div className="mb-3 flex items-center justify-between gap-3">
              <h2 className="flex items-center gap-2 text-base font-semibold"><ListChecks size={18} /> Recent Evidence</h2>
              <button className="text-sm font-semibold text-review" onClick={() => navigateTo("review")} type="button">Review film</button>
            </div>
            <div className="space-y-2">
              {filteredEvidence.length ? filteredEvidence.slice(0, 4).map((item) => (
                <div className="flex items-center justify-between gap-3 rounded-md border border-line px-3 py-2 text-sm" key={item.id}>
                  <div className="min-w-0">
                    <div className="truncate font-semibold">{item.tag_name}</div>
                    <div className="truncate text-xs text-slate-500">{item.athlete_name}</div>
                  </div>
                  <span className="shrink-0 text-xs font-semibold text-slate-600">{formatTime(item.timestamp_seconds)}</span>
                </div>
              )) : <EmptyState label="Evidence from film review will appear here." />}
            </div>
          </section>

          <section className="rounded-md border border-line bg-white p-4 shadow-panel">
            <div className="mb-3 flex items-center justify-between gap-3">
              <h2 className="flex items-center gap-2 text-base font-semibold"><FileText size={18} /> Athlete Reports</h2>
              <button className="text-sm font-semibold text-review" onClick={() => navigateTo("reports")} type="button">Open reports</button>
            </div>
            {activeReport ? (
              <div className="rounded-md border border-line bg-slate-50 p-3">
                <div className="font-semibold">{activeReport.title}</div>
                <div className="mt-1 text-sm text-slate-600">Built from {activeReport.report_data.evidence_count} saved evidence clips.</div>
              </div>
            ) : <EmptyState label="Generate a report after reviewing film evidence." />}
          </section>
        </div>
      </div>
    );
  }

  function renderReview() {
    return (
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.45fr)_minmax(360px,0.95fr)]">
        <div className="space-y-4">
          <section className="rounded-md border border-field/30 bg-white p-4 shadow-panel">
            <div className="mb-3 flex items-start gap-3">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-field text-sm font-semibold text-white">1</span>
              <div>
                <h2 className="text-base font-semibold">Upload Film</h2>
                <p className="text-sm text-slate-600">Add the game film you want to review with your team.</p>
              </div>
            </div>
            <form className="grid gap-3 lg:grid-cols-[minmax(180px,0.8fr)_minmax(240px,1.2fr)_auto]" onSubmit={uploadVideo}>
              <input className="h-11 rounded-md border border-line px-3 text-sm outline-none focus:border-field" onChange={(event) => setUploadTitle(event.target.value)} placeholder="Film title" value={uploadTitle} />
              <input className="h-11 min-w-0 rounded-md border border-line px-3 text-sm file:mr-3 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-1.5" onChange={onUploadFileChange} type="file" accept="video/*" />
              <button className="inline-flex h-11 items-center justify-center gap-2 rounded-md bg-field px-5 text-sm font-semibold text-white shadow-sm hover:bg-teal-800 disabled:bg-slate-300" disabled={!selectedOrgId || !selectedTeamId || !uploadFile || isUploadingVideo} type="submit">
                <Upload aria-hidden="true" size={17} /> {isUploadingVideo ? "Uploading Film…" : "Upload Film"}
              </button>
            </form>
            <details className="mt-3 rounded-md border border-line bg-slate-50">
              <summary className="flex min-h-11 cursor-pointer list-none items-center gap-2 px-3 text-sm font-semibold text-slate-700">
                <Plus size={16} /> Add a direct film URL instead
              </summary>
              <form className="grid gap-3 border-t border-line p-3 lg:grid-cols-[minmax(180px,0.8fr)_minmax(240px,1.2fr)_auto]" onSubmit={importVideoUrl}>
                <input className="h-11 rounded-md border border-line bg-white px-3 text-sm outline-none focus:border-field" onChange={(event) => setUrlImportForm((value) => ({ ...value, title: event.target.value }))} placeholder="Film title" value={urlImportForm.title} />
                <input className="h-11 rounded-md border border-line bg-white px-3 text-sm outline-none focus:border-field" onChange={(event) => setUrlImportForm((value) => ({ ...value, source_url: event.target.value }))} placeholder="Paste direct video URL" type="url" value={urlImportForm.source_url} />
                <button className="inline-flex h-11 items-center justify-center gap-2 rounded-md border border-line bg-white px-4 text-sm font-semibold hover:border-field disabled:text-slate-400" disabled={!selectedOrgId || !selectedTeamId || !urlImportForm.source_url || isImportingVideo} type="submit">
                  <Plus size={16} /> {isImportingVideo ? "Adding Film…" : "Add Film URL"}
                </button>
              </form>
            </details>
          </section>

          <section className="rounded-md border border-line bg-white p-4 shadow-panel">
            <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <div className="flex-1">
                <SelectBox label="Film to review" value={selectedVideoId} onChange={setSelectedVideoId} options={videos.map((item) => ({ value: item.id, label: item.title }))} icon={<Video size={16} />} />
              </div>
              {selectedVideo ? (
                <span className={`inline-flex min-h-10 items-center rounded-md px-3 text-sm font-semibold ${videoReadiness?.file_available === false ? "bg-red-50 text-red-700" : "bg-emerald-50 text-emerald-700"}`}>
                  {videoReadiness?.message || "Checking film readiness…"}
                </span>
              ) : null}
            </div>
            {selectedVideo?.storage_url ? (
              <video
                className="aspect-video w-full rounded-md"
                controls
                onPause={captureTimestamp}
                onTimeUpdate={(event) => setCurrentTime(event.currentTarget.currentTime)}
                ref={videoRef}
                src={mediaUrl(selectedVideo.storage_url)}
              />
            ) : (
              <div className="field-empty flex aspect-video w-full items-center justify-center rounded-md border border-line">
                <div className="rounded-md bg-white px-4 py-3 text-sm font-medium text-slate-600 shadow-panel">
                  No film selected
                </div>
              </div>
            )}
            <div className="mt-4">
              <h2 className="mb-2 text-sm font-semibold">Film Details</h2>
              <div className="grid grid-cols-2 gap-2 text-sm text-slate-700 sm:grid-cols-3">
                <Metric label="File" value={selectedVideo?.original_filename || "No film selected"} />
                <Metric label="Format" value={formatContentType(selectedVideo?.content_type)} />
                <Metric label="Duration" value={selectedVideo?.duration_seconds != null ? formatTime(selectedVideo.duration_seconds) : "Pending"} />
                <Metric label="Frame Rate" value={selectedVideo?.fps != null ? `${selectedVideo.fps.toFixed(2)} fps` : "Pending"} />
                <Metric label="Source Frames" value={selectedVideo?.frame_count != null ? selectedVideo.frame_count.toLocaleString() : "Pending"} />
                <Metric label="Review Moments" value={(videoReadiness?.extracted_frame_count ?? frames.length).toLocaleString()} />
              </div>
            </div>
            {videoReadiness?.file_available === false ? (
              <div className="mt-3 flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
                <AlertTriangle className="mt-0.5 shrink-0" size={17} />
                <div><span className="font-semibold">Film file missing.</span> Upload the original film again above, then select the new copy.</div>
              </div>
            ) : null}
            {selectedVideo && videoReadiness && !videoReadiness.storage_persistent ? (
              <div className="mt-3 flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                <AlertTriangle className="mt-0.5 shrink-0" size={17} />
                <div><span className="font-semibold">Permanent film storage is not connected.</span> This film may need to be uploaded again after a server update.</div>
              </div>
            ) : null}
            <div className="mt-4 rounded-md border border-field/30 bg-teal-50 p-4">
              <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div>
                  <div className="mb-1 text-xs font-semibold uppercase text-teal-700">Step 2</div>
                  <h2 className="flex items-center gap-2 text-base font-semibold">
                    <Eye aria-hidden="true" size={16} />
                    Break Down Film
                  </h2>
                  <p className="mt-1 text-sm text-slate-600">Create review moments for manual player selection and evidence tagging.</p>
                  <div className="mt-2 grid grid-cols-2 gap-2 text-sm text-slate-700">
                    <Metric label="Film Moments" value={frames.length.toLocaleString()} />
                    <Metric label="Player Views" value={tracks.length.toLocaleString()} />
                  </div>
                </div>
                <button
                  className="inline-flex h-12 min-w-48 items-center justify-center gap-2 rounded-md bg-field px-5 text-sm font-semibold text-white shadow-sm hover:bg-teal-800 disabled:bg-slate-300"
                  disabled={!selectedVideoId || isProcessingVideo || videoReadiness?.processing_ready === false}
                  onClick={processSelectedVideo}
                  type="button"
                >
                  <RefreshCw aria-hidden="true" size={16} />
                  {isProcessingVideo ? "Preparing review moments…" : frames.length ? "Rebuild Film Moments" : "Break Down Film"}
                </button>
              </div>
              {frames.length ? (
                <div className="mt-3 grid gap-3 lg:grid-cols-[minmax(0,1fr)_220px]">
                  <div className="grid max-h-52 grid-cols-2 gap-2 overflow-y-auto pr-1 sm:grid-cols-4">
                    {frames.slice(0, 12).map((frame) => (
                      <button
                        className={`relative aspect-video overflow-hidden rounded-md border bg-white text-left ${
                          selectedFrame?.id === frame.id ? "border-review ring-2 ring-blue-100" : "border-line hover:border-review"
                        }`}
                        key={frame.id}
                        onClick={(event) => selectFramePoint(frame, event)}
                        type="button"
                      >
                        {frame.frame_url ? <img alt="" className="h-full w-full object-cover" src={mediaUrl(frame.frame_url)} /> : null}
                        <span className="absolute bottom-1 left-1 rounded bg-white/90 px-1.5 py-0.5 text-[10px] font-semibold text-ink">
                          {formatTime(frame.timestamp_seconds)}
                        </span>
                        {selectedFrame?.id === frame.id && selectedPoint ? (
                          <span
                            className="absolute h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-review shadow"
                            style={{ left: `${selectedPoint.x * 100}%`, top: `${selectedPoint.y * 100}%` }}
                          />
                        ) : null}
                      </button>
                    ))}
                  </div>
                  <div className="space-y-2">
                    <Metric
                      label="Selected Player"
                      value={selectedPoint ? `${Math.round(selectedPoint.x * 100)}%, ${Math.round(selectedPoint.y * 100)}%` : "None"}
                    />
                    <button
                      className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-review px-4 text-sm font-semibold text-white hover:bg-blue-700 disabled:bg-slate-300"
                      disabled={!selectedVideoId || !selectedFrame || !selectedPoint || isCreatingTrack}
                      onClick={createTrackSeed}
                      type="button"
                    >
                      <Save aria-hidden="true" size={16} />
                      {isCreatingTrack ? "Saving" : "Save Player View"}
                    </button>
                  </div>
                </div>
              ) : null}
            </div>
          </section>

          <section className="rounded-md border border-line bg-white p-4 shadow-panel">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="flex items-center gap-2 text-base font-semibold">
                <Crosshair aria-hidden="true" size={18} />
                Tag What You See
              </h2>
              <button
                className="inline-flex h-9 items-center gap-2 rounded-md border border-line px-3 text-sm font-medium hover:border-review"
                onClick={captureTimestamp}
                type="button"
              >
                <Search aria-hidden="true" size={15} />
                Use {formatTime(currentTime)}
              </button>
            </div>
            <form className="grid gap-3" onSubmit={saveEvidence}>
              <div className="grid gap-3 md:grid-cols-3">
                <FieldLabel label="Athlete">
                  <select
                    className="h-10 w-full rounded-md border border-line px-3 text-sm outline-none focus:border-review"
                    onChange={(event) => {
                      setSelectedAthleteId(event.target.value);
                      setTagForm((value) => ({ ...value, athlete_id: event.target.value }));
                    }}
                    value={tagForm.athlete_id || selectedAthleteId}
                  >
                    <option value="">Choose athlete</option>
                    {athletes.map((item) => (
                      <option key={item.id} value={item.id}>
                        {athleteLabel(item)}
                      </option>
                    ))}
                  </select>
                </FieldLabel>
                <FieldLabel label="Focus Area">
                  <select
                    className="h-10 w-full rounded-md border border-line px-3 text-sm outline-none focus:border-review"
                    onChange={(event) => setTagForm((value) => ({ ...value, category_id: event.target.value }))}
                    value={tagForm.category_id}
                  >
                    <option value="">Choose focus area</option>
                    {categories.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                  </select>
                </FieldLabel>
                <FieldLabel label="Behavior">
                  <select
                    className="h-10 w-full rounded-md border border-line px-3 text-sm outline-none focus:border-review"
                    onChange={(event) => setTagForm((value) => ({ ...value, tag_id: event.target.value }))}
                    value={tagForm.tag_id}
                  >
                    <option value="">Choose behavior</option>
                    {tagsForCategory.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                  </select>
                </FieldLabel>
              </div>

              <div className="grid gap-3 md:grid-cols-[120px_120px_120px_1fr]">
                <TextInput
                  label="Timestamp"
                  onChange={(value) => setTagForm((item) => ({ ...item, timestamp_seconds: value }))}
                  value={tagForm.timestamp_seconds}
                />
                <TextInput
                  label="Clip Starts"
                  onChange={(value) => setTagForm((item) => ({ ...item, clip_start_seconds: value }))}
                  value={tagForm.clip_start_seconds}
                />
                <TextInput
                  label="Clip Ends"
                  onChange={(value) => setTagForm((item) => ({ ...item, clip_end_seconds: value }))}
                  value={tagForm.clip_end_seconds}
                />
                <FieldLabel label="How should this be used?">
                  <div className="flex h-10 rounded-md border border-line bg-slate-50 p-1">
                    {(["neutral", "strength", "development_area"] as EvidenceType[]).map((value) => (
                      <button
                        className={`flex-1 rounded px-2 text-sm font-medium ${
                          tagForm.evidence_type === value ? "bg-white text-review shadow-sm" : "text-slate-600"
                        }`}
                        key={value}
                        onClick={() => setTagForm((item) => ({ ...item, evidence_type: value }))}
                        type="button"
                      >
                        {value === "development_area" ? "Development" : value === "neutral" ? "Evidence" : "Strength"}
                      </button>
                    ))}
                  </div>
                </FieldLabel>
              </div>

              <textarea
                className="min-h-24 w-full rounded-md border border-line px-3 py-2 text-sm outline-none focus:border-review"
                onChange={(event) => setTagForm((value) => ({ ...value, notes: event.target.value }))}
                placeholder="What happened? What should the athlete remember?"
                value={tagForm.notes}
              />
              <button
                className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-md bg-review px-4 text-sm font-semibold text-white hover:bg-blue-700 disabled:bg-slate-300 sm:w-fit"
                disabled={!selectedVideoId || !tagForm.tag_id || !(tagForm.athlete_id || selectedAthleteId)}
                type="submit"
              >
                <Save aria-hidden="true" size={16} />
                Save to Athlete Profile
              </button>
            </form>
          </section>
        </div>

        <aside className="space-y-4">
          <ProfilePanel
            isGeneratingReport={isGeneratingReport}
            onGenerateReport={generateReport}
            profile={profile}
            selectedAthlete={selectedAthlete}
          />
          <ReportPanel
            activeReport={activeReport}
            onDownloadReport={downloadReport}
            onSelectReport={setActiveReport}
            reports={reports}
          />
          <section className="rounded-md border border-line bg-white p-4 shadow-panel">
            <h2 className="mb-3 flex items-center gap-2 text-base font-semibold">
              <ListChecks aria-hidden="true" size={18} />
              Evidence Library
            </h2>
            <div className="space-y-2">
              {filteredEvidence.length ? (
                filteredEvidence.map((item) => (
                  <EvidenceRow evidence={item} key={item.id} onJump={jumpTo} />
                ))
              ) : (
                <EmptyState label="Pause the film, tag a behavior, and evidence will appear here." />
              )}
            </div>
          </section>
          <section className="rounded-md border border-line bg-white p-4 shadow-panel">
            <h2 className="mb-3 flex items-center gap-2 text-base font-semibold">
              <ClipboardList aria-hidden="true" size={18} />
              Coach Notes
            </h2>
            <form className="space-y-2" onSubmit={saveCoachNote}>
              <input
                className="h-10 w-full rounded-md border border-line px-3 text-sm outline-none focus:border-review"
                onChange={(event) => setNoteForm((value) => ({ ...value, author_name: event.target.value }))}
                placeholder="Author"
                value={noteForm.author_name}
              />
              <textarea
                className="min-h-20 w-full rounded-md border border-line px-3 py-2 text-sm outline-none focus:border-review"
                onChange={(event) => setNoteForm((value) => ({ ...value, body: event.target.value }))}
                placeholder="Note"
                value={noteForm.body}
              />
              <button
                className="inline-flex h-9 items-center gap-2 rounded-md bg-court px-3 text-sm font-semibold text-white hover:bg-amber-700 disabled:bg-slate-300"
                disabled={!selectedAthleteId || !noteForm.body}
                type="submit"
              >
                <Plus aria-hidden="true" size={15} />
                Add Note
              </button>
            </form>
            <div className="mt-3 space-y-2">
              {profile?.coach_notes.length ? (
                profile.coach_notes.map((item) => (
                  <div className="rounded-md border border-line p-3 text-sm" key={item.id}>
                    <div className="font-medium">{item.author_name || "Coach"}</div>
                    <p className="mt-1 text-slate-700">{item.body}</p>
                  </div>
                ))
              ) : (
                <EmptyState label="No notes" />
              )}
            </div>
          </section>
        </aside>
      </div>
    );
  }

  function renderReports() {
    return (
      <div className="grid gap-4 lg:grid-cols-[minmax(360px,0.8fr)_minmax(0,1.2fr)]">
        <div className="space-y-4">
          <ProfilePanel
            isGeneratingReport={isGeneratingReport}
            onGenerateReport={generateReport}
            profile={profile}
            selectedAthlete={selectedAthlete}
          />
          <section className="rounded-md border border-line bg-white p-4 shadow-panel">
            <h2 className="mb-3 flex items-center gap-2 text-base font-semibold">
              <ListChecks aria-hidden="true" size={18} />
              Evidence Used for Reports
            </h2>
            <div className="space-y-2">
              {filteredEvidence.length ? (
                filteredEvidence.map((item) => <EvidenceRow evidence={item} key={item.id} onJump={jumpTo} />)
              ) : (
                <EmptyState label="Break down film and save evidence before generating reports." />
              )}
            </div>
          </section>
        </div>
        <ReportPanel
          activeReport={activeReport}
          onDownloadReport={downloadReport}
          onSelectReport={setActiveReport}
          reports={reports}
        />
      </div>
    );
  }

  function renderDirectory() {
    return (
      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-md border border-line bg-white p-4 shadow-panel">
          <h2 className="mb-3 flex items-center gap-2 text-base font-semibold">
            <Users aria-hidden="true" size={18} />
            Program
          </h2>
          <form className="grid gap-3 md:grid-cols-2" onSubmit={createOrganization}>
            <TextInput label="Name" onChange={(value) => setOrganizationForm((item) => ({ ...item, name: value }))} value={organizationForm.name} />
            <TextInput
              label="Primary Sport"
              onChange={(value) => setOrganizationForm((item) => ({ ...item, sport_label: value }))}
              value={organizationForm.sport_label}
            />
            <button className="inline-flex h-10 w-fit items-center gap-2 rounded-md bg-field px-4 text-sm font-semibold text-white" type="submit">
              <Plus size={16} />
              Save Program
            </button>
          </form>
        </section>

        <section className="rounded-md border border-line bg-white p-4 shadow-panel">
          <h2 className="mb-3 flex items-center gap-2 text-base font-semibold">
            <ClipboardList aria-hidden="true" size={18} />
            Team Setup
          </h2>
          <form className="grid gap-3 md:grid-cols-3" onSubmit={createTeam}>
            <TextInput label="Name" onChange={(value) => setTeamForm((item) => ({ ...item, name: value }))} value={teamForm.name} />
            <TextInput label="Sport" onChange={(value) => setTeamForm((item) => ({ ...item, sport: value }))} value={teamForm.sport} />
            <TextInput label="Season" onChange={(value) => setTeamForm((item) => ({ ...item, season: value }))} value={teamForm.season} />
            <button className="inline-flex h-10 w-fit items-center gap-2 rounded-md bg-field px-4 text-sm font-semibold text-white" type="submit">
              <Plus size={16} />
              Save Team
            </button>
          </form>
        </section>

        <section className="rounded-md border border-line bg-white p-4 shadow-panel">
          <h2 className="mb-3 flex items-center gap-2 text-base font-semibold">
            <UserRound aria-hidden="true" size={18} />
            Roster
          </h2>
          <form className="grid gap-3 md:grid-cols-3" onSubmit={createAthlete}>
            <TextInput
              label="Display Name"
              onChange={(value) => setAthleteForm((item) => ({ ...item, display_name: value }))}
              value={athleteForm.display_name}
            />
            <TextInput
              label="Jersey"
              onChange={(value) => setAthleteForm((item) => ({ ...item, jersey_number: value }))}
              value={athleteForm.jersey_number}
            />
            <TextInput
              label="Position"
              onChange={(value) => setAthleteForm((item) => ({ ...item, position: value }))}
              value={athleteForm.position}
            />
            <button className="inline-flex h-10 w-fit items-center gap-2 rounded-md bg-review px-4 text-sm font-semibold text-white" type="submit">
              <Plus size={16} />
              Add Athlete
            </button>
          </form>
          <ListBlock items={athletes.map((item) => [athleteLabel(item), item.position || "Active"])} />
        </section>

        <section className="rounded-md border border-line bg-white p-4 shadow-panel">
          <h2 className="mb-3 flex items-center gap-2 text-base font-semibold">
            <Calendar aria-hidden="true" size={18} />
            Games and Practices
          </h2>
          <form className="grid gap-3 md:grid-cols-2" onSubmit={createEvent}>
            <TextInput label="Name" onChange={(value) => setEventForm((item) => ({ ...item, name: value }))} value={eventForm.name} />
            <TextInput
              label="Opponent"
              onChange={(value) => setEventForm((item) => ({ ...item, opponent: value }))}
              value={eventForm.opponent}
            />
            <TextInput
              label="Date"
              onChange={(value) => setEventForm((item) => ({ ...item, event_date: value }))}
              type="date"
              value={eventForm.event_date}
            />
            <TextInput
              label="Location"
              onChange={(value) => setEventForm((item) => ({ ...item, location: value }))}
              value={eventForm.location}
            />
            <button className="inline-flex h-10 w-fit items-center gap-2 rounded-md bg-court px-4 text-sm font-semibold text-white" type="submit">
              <Plus size={16} />
              Save Event
            </button>
          </form>
          <ListBlock items={events.map((item) => [item.name, [item.opponent, item.event_date].filter(Boolean).join(" · ")])} />
        </section>
      </div>
    );
  }

  function renderTaxonomy() {
    return (
      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-md border border-line bg-white p-4 shadow-panel">
          <h2 className="mb-3 flex items-center gap-2 text-base font-semibold">
            <Layers3 aria-hidden="true" size={18} />
            Focus Areas
          </h2>
          <form className="grid gap-3 md:grid-cols-2" onSubmit={createCategory}>
            <TextInput
              label="Name"
              onChange={(value) => setCategoryForm((item) => ({ ...item, name: value }))}
              value={categoryForm.name}
            />
            <TextInput
              label="Sport"
              onChange={(value) => setCategoryForm((item) => ({ ...item, sport: value }))}
              value={categoryForm.sport}
            />
            <textarea
              className="min-h-20 rounded-md border border-line px-3 py-2 text-sm outline-none focus:border-review md:col-span-2"
              onChange={(event) => setCategoryForm((item) => ({ ...item, description: event.target.value }))}
              placeholder="Description"
              value={categoryForm.description}
            />
            <button className="inline-flex h-10 w-fit items-center gap-2 rounded-md bg-field px-4 text-sm font-semibold text-white" type="submit">
              <Plus size={16} />
              Save Focus Area
            </button>
          </form>
          <ListBlock items={categories.map((item) => [item.name, item.sport || "All sports"])} />
        </section>

        <section className="rounded-md border border-line bg-white p-4 shadow-panel">
          <h2 className="mb-3 flex items-center gap-2 text-base font-semibold">
            <Tags aria-hidden="true" size={18} />
            Behaviors
          </h2>
          <form className="grid gap-3 md:grid-cols-2" onSubmit={createTagDefinition}>
            <FieldLabel label="Focus Area">
              <select
                className="h-10 w-full rounded-md border border-line px-3 text-sm outline-none focus:border-review"
                onChange={(event) => setTagDefinitionForm((item) => ({ ...item, category_id: event.target.value }))}
                value={tagDefinitionForm.category_id}
              >
                <option value="">Choose focus area</option>
                {categories.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </FieldLabel>
            <TextInput
              label="Name"
              onChange={(value) => setTagDefinitionForm((item) => ({ ...item, name: value }))}
              value={tagDefinitionForm.name}
            />
            <textarea
              className="min-h-20 rounded-md border border-line px-3 py-2 text-sm outline-none focus:border-review md:col-span-2"
              onChange={(event) => setTagDefinitionForm((item) => ({ ...item, description: event.target.value }))}
              placeholder="Description"
              value={tagDefinitionForm.description}
            />
            <button className="inline-flex h-10 w-fit items-center gap-2 rounded-md bg-review px-4 text-sm font-semibold text-white" type="submit">
              <Plus size={16} />
              Save Behavior
            </button>
          </form>
          <ListBlock
            items={tags.map((item) => [
              item.name,
              categories.find((category) => category.id === item.category_id)?.name ?? "Category"
            ])}
          />
        </section>
      </div>
    );
  }

  function renderVision() {
    const selectedFrameUrl = selectedFrame?.frame_url ? mediaUrl(selectedFrame.frame_url) : "";
    const activeTrackStatus = trackTimeline?.track.segmentation_metadata.status;

    return (
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(360px,0.75fr)]">
        <section className="rounded-md border border-line bg-white p-4 shadow-panel">
          <div className="mb-3 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <SelectBox
              label="Film"
              value={selectedVideoId}
              onChange={setSelectedVideoId}
              options={videos.map((item) => ({ value: item.id, label: item.title }))}
              icon={<Video size={16} />}
            />
            <button
              className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-field px-4 text-sm font-semibold text-white hover:bg-teal-800 disabled:bg-slate-300"
              disabled={!selectedVideoId || isProcessingVideo}
              onClick={processSelectedVideo}
              type="button"
            >
              <RefreshCw aria-hidden="true" size={16} />
              {isProcessingVideo ? "Breaking down film" : "Break Down Film"}
            </button>
          </div>
          <div className="mb-4 grid gap-2 text-sm text-slate-700 sm:grid-cols-4">
            <Metric label="Film Moments" value={frames.length.toLocaleString()} />
            <Metric label="Player Focus" value={selectedAthlete ? athleteLabel(selectedAthlete) : "Choose player"} />
            <Metric label="Selected Moment" value={selectedFrame ? formatTime(selectedFrame.timestamp_seconds) : "None"} />
            <Metric label="Player Views" value={tracks.length.toLocaleString()} />
          </div>

          {selectedFrame ? (
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_220px]">
              <button
                className="relative aspect-video overflow-hidden rounded-md border border-line bg-slate-100 text-left"
                onClick={(event) => selectFramePoint(selectedFrame, event)}
                type="button"
              >
                {selectedFrameUrl ? (
                  <img alt="" className="h-full w-full object-contain" src={selectedFrameUrl} />
                ) : (
                  <div className="flex h-full items-center justify-center text-sm text-slate-500">Moment unavailable</div>
                )}
                {selectedPoint ? (
                  <span
                    className="absolute h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-review shadow"
                    style={{ left: `${selectedPoint.x * 100}%`, top: `${selectedPoint.y * 100}%` }}
                  />
                ) : null}
              </button>
              <div className="grid max-h-[420px] grid-cols-2 gap-2 overflow-y-auto pr-1">
                {frames.map((frame) => (
                  <button
                    className={`relative aspect-video overflow-hidden rounded-md border bg-slate-100 text-left ${
                      selectedFrame?.id === frame.id ? "border-review ring-2 ring-blue-100" : "border-line hover:border-review"
                    }`}
                    key={frame.id}
                    onClick={(event) => selectFramePoint(frame, event)}
                    type="button"
                  >
                    {frame.frame_url ? <img alt="" className="h-full w-full object-cover" src={mediaUrl(frame.frame_url)} /> : null}
                    <span className="absolute bottom-1 left-1 rounded bg-white/90 px-1.5 py-0.5 text-[10px] font-semibold text-ink">
                      {formatTime(frame.timestamp_seconds)}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <EmptyState label={selectedVideoId ? "Break down the film, then click a player in one clear moment." : "Choose film to start breakdown."} />
          )}

          <div className="mt-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div className="grid gap-2 text-sm text-slate-700 sm:grid-cols-2 md:min-w-[420px]">
              <Metric
                label="Selected Player"
                value={selectedPoint ? `${Math.round(selectedPoint.x * 100)}%, ${Math.round(selectedPoint.y * 100)}%` : "None"}
              />
              <Metric label="Player View" value={activeTrackStatus ? String(activeTrackStatus) : "Not saved"} />
            </div>
            <button
              className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-review px-4 text-sm font-semibold text-white hover:bg-blue-700 disabled:bg-slate-300"
              disabled={!selectedVideoId || !selectedFrame || !selectedPoint || isCreatingTrack}
              onClick={createTrackSeed}
              type="button"
            >
              <Save aria-hidden="true" size={16} />
              {isCreatingTrack ? "Saving" : "Save Player View"}
            </button>
          </div>
        </section>

        <section className="rounded-md border border-line bg-white p-4 shadow-panel">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 className="flex items-center gap-2 text-base font-semibold">
              <Activity aria-hidden="true" size={18} />
              Breakdown Findings
            </h2>
            <span className="rounded bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">
              {trackTimeline ? `${trackTimeline.moments.length} moments` : "No moments"}
            </span>
          </div>

          {trackTimeline ? (
            <div className="space-y-3">
              <div className="rounded-md border border-line bg-slate-50 p-3 text-sm">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-semibold">{trackTimeline.track.track_label || "Coach-selected player"}</div>
                    <div className="mt-1 text-xs text-slate-600">
                      {trackTimeline.athlete ? athleteLabel(trackTimeline.athlete) : "Unassigned athlete"}
                    </div>
                  </div>
                  <span className="rounded bg-white px-2 py-1 text-xs font-medium text-slate-700">{trackTimeline.track.status}</span>
                </div>
              </div>

              <div className="max-h-[520px] space-y-2 overflow-y-auto pr-1">
                {trackTimeline.moments.map((moment) => (
                  <div className="rounded-md border border-line p-2 text-sm" key={moment.frame_id}>
                    <div className="grid gap-2 sm:grid-cols-[120px_1fr]">
                      <div className="relative aspect-video overflow-hidden rounded bg-slate-100">
                        {moment.frame_url ? <img alt="" className="h-full w-full object-cover" src={mediaUrl(moment.frame_url)} /> : null}
                        <span
                          className="absolute border-2 border-review"
                          style={{
                            left: `${moment.box.x * 100}%`,
                            top: `${moment.box.y * 100}%`,
                            width: `${moment.box.width * 100}%`,
                            height: `${moment.box.height * 100}%`
                          }}
                        />
                      </div>
                      <div className="flex min-w-0 items-center justify-between gap-2">
                        <div>
                          <div className="font-semibold">{formatTime(moment.timestamp_seconds)}</div>
                          <div className="text-xs text-slate-600">Moment {moment.frame_number}</div>
                        </div>
                        <button
                          className="inline-flex h-8 items-center gap-1.5 rounded-md border border-line px-2.5 text-xs font-semibold hover:border-review"
                          onClick={() => useTimelineMomentForTag(moment)}
                          type="button"
                        >
                          <Tags aria-hidden="true" size={13} />
                          Tag Evidence
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <EmptyState label="Click a player in the film to organize moments for tagging." />
          )}

          <div className="mt-4 space-y-2">
            <div className="text-xs font-semibold uppercase text-slate-500">Player Views in This Film</div>
            {tracks.length ? (
              tracks.slice(0, 6).map((track) => (
                <button
                  className={`w-full rounded-md border px-3 py-2 text-left text-sm ${
                    trackTimeline?.track.id === track.id ? "border-review bg-blue-50" : "border-line hover:border-review"
                  }`}
                  key={track.id}
                  onClick={() => loadTrackTimeline(track.id)}
                  type="button"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold">{track.track_label || "Coach-selected player"}</span>
                    <span className="rounded bg-white px-2 py-1 text-xs font-medium text-slate-700">{track.status}</span>
                  </div>
                </button>
              ))
            ) : (
              <EmptyState label="No player views saved yet" />
            )}
          </div>
        </section>
      </div>
    );
  }
}

function CoachWorkflow({ currentStep }: { currentStep: (typeof workflowSteps)[number] }) {
  return (
    <section className="rounded-md border border-line bg-white p-3 shadow-panel">
      <div className="mb-2 flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold text-ink">Coach workflow</h2>
          <p className="text-xs text-slate-600">Break down film first. Player evidence and reports come from that work.</p>
        </div>
        <span className="hidden text-xs font-semibold uppercase text-slate-500 md:inline">Current step: {currentStep}</span>
      </div>
      <div className="flex items-center gap-3 rounded-md border border-review bg-blue-50 px-3 py-3 text-sm text-review md:hidden">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-review text-xs font-semibold text-white">
          {workflowSteps.indexOf(currentStep) + 1}
        </span>
        <div>
          <div className="text-xs font-semibold uppercase text-blue-600">Do this next</div>
          <div className="font-semibold">{currentStep}</div>
        </div>
      </div>
      <div className="hidden gap-2 md:grid md:grid-cols-5">
        {workflowSteps.map((step, index) => {
          const active = step === currentStep;
          return (
            <div
              className={`flex min-h-14 items-center gap-2 rounded-md border px-3 py-2 text-sm ${
                active ? "border-review bg-blue-50 text-review" : "border-line bg-slate-50 text-slate-700"
              }`}
              key={step}
            >
              <span
                className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                  active ? "bg-review text-white" : "bg-white text-slate-600"
                }`}
              >
                {index + 1}
              </span>
              <span className="font-semibold">{step}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function ProfilePanel({
  isGeneratingReport,
  onGenerateReport,
  profile,
  selectedAthlete
}: {
  isGeneratingReport: boolean;
  onGenerateReport: () => void;
  profile: AthleteProfile | null;
  selectedAthlete: Athlete | null;
}) {
  return (
    <section className="rounded-md border border-line bg-white p-4 shadow-panel">
      <div className="mb-3 flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-center">
        <h2 className="flex items-center gap-2 text-base font-semibold">
          <UserRound aria-hidden="true" size={18} />
          Athlete Development Profile
        </h2>
        <button
          className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-md bg-ink px-3 text-sm font-semibold text-white hover:bg-slate-700 disabled:bg-slate-300 sm:h-9 sm:w-auto"
          disabled={!profile || isGeneratingReport}
          onClick={onGenerateReport}
          type="button"
        >
          <FileText aria-hidden="true" size={15} />
          {isGeneratingReport ? "Generating" : "Generate Report"}
        </button>
      </div>
      {profile ? (
        <div className="space-y-4">
          <div>
            <div className="text-xl font-semibold">{profile.athlete.display_name}</div>
            <div className="text-sm text-slate-600">
              {[profile.athlete.jersey_number ? `#${profile.athlete.jersey_number}` : null, profile.athlete.position]
                .filter(Boolean)
                .join(" · ")}
            </div>
          </div>
          <ProfileSection label="Strengths" items={profile.strengths} />
          <ProfileSection label="Development Areas" items={profile.development_areas} />
          <ProfileSection label="Most Seen Behaviors" items={profile.behavior_frequency} />
          <ProfileSection label="Shows Up Across Film" items={profile.behavior_consistency} />
        </div>
      ) : (
        <EmptyState label={selectedAthlete ? "Profile loading" : "No athlete selected"} />
      )}
    </section>
  );
}

function ReportPanel({
  activeReport,
  onDownloadReport,
  onSelectReport,
  reports
}: {
  activeReport: AthleteReport | null;
  onDownloadReport: (reportId: string) => void;
  onSelectReport: (report: AthleteReport) => void;
  reports: AthleteReport[];
}) {
  return (
    <section className="rounded-md border border-line bg-white p-4 shadow-panel">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-base font-semibold">
          <FileText aria-hidden="true" size={18} />
          Reports
        </h2>
        <button
          className="inline-flex h-11 shrink-0 items-center gap-2 rounded-md border border-line px-3 text-sm font-medium hover:border-review disabled:text-slate-400 sm:h-9"
          disabled={!activeReport}
          onClick={() => activeReport && onDownloadReport(activeReport.id)}
          type="button"
        >
          <Download aria-hidden="true" size={15} />
          PDF
        </button>
      </div>
      {reports.length > 1 ? (
        <div className="mb-3 flex flex-wrap gap-2">
          {reports.slice(0, 4).map((report) => (
            <button
              className={`rounded-md border px-2.5 py-1.5 text-xs font-medium ${
                activeReport?.id === report.id
                  ? "border-review bg-blue-50 text-review"
                  : "border-line text-slate-600 hover:border-review"
              }`}
              key={report.id}
              onClick={() => onSelectReport(report)}
              type="button"
            >
              {new Date(report.created_at).toLocaleDateString()}
            </button>
          ))}
        </div>
      ) : null}
      {activeReport ? (
        <div className="space-y-4">
          <div className="rounded-md border border-line bg-slate-50 p-3 text-sm">
            <div className="font-semibold">{activeReport.title}</div>
            <div className="mt-1 text-xs text-slate-600">
              {activeReport.report_data.evidence_count} saved evidence clips - {activeReport.report_data.note_count} coach notes
            </div>
            <p className="mt-2 text-xs text-slate-600">{activeReport.report_data.traceability_statement}</p>
          </div>
          {activeReport.report_data.sections.map((section) => (
            <div className="rounded-md border border-line p-3" key={section.key}>
              <div className="text-sm font-semibold">{section.title}</div>
              <p className="mt-1 text-sm text-slate-700">{section.summary}</p>
              {section.observations.length ? (
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">
                  {section.observations.slice(0, 4).map((observation) => (
                    <li key={observation}>{observation}</li>
                  ))}
                </ul>
              ) : null}
              {section.supporting_notes.length ? (
                <div className="mt-3 space-y-2">
                  <div className="text-xs font-semibold uppercase text-slate-500">Coach Notes</div>
                  {section.supporting_notes.slice(0, 3).map((note) => (
                    <div className="rounded border border-line bg-slate-50 px-2 py-1.5 text-xs text-slate-700" key={note.note_id}>
                      {note.author_name || "Coach"}: {note.body}
                    </div>
                  ))}
                </div>
              ) : null}
              {section.supporting_evidence.length ? (
                <div className="mt-3">
                  <div className="mb-2 text-xs font-semibold uppercase text-slate-500">Supporting Clips</div>
                  <div className="space-y-1.5">
                    {section.supporting_evidence.slice(0, 5).map((item) => (
                      <ReportEvidenceChip evidence={item} key={`${section.key}-${item.evidence_tag_id}`} />
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      ) : (
        <EmptyState label="Generate reports after film has been broken down and evidence is saved." />
      )}
    </section>
  );
}

function ReportEvidenceChip({ evidence }: { evidence: ReportEvidenceReference }) {
  const clipWindow =
    evidence.clip_start_seconds !== null && evidence.clip_end_seconds !== null
      ? `${formatTime(evidence.clip_start_seconds)}-${formatTime(evidence.clip_end_seconds)}`
      : formatTime(evidence.timestamp_seconds);
  return (
    <div className="rounded-md border border-line bg-slate-50 px-2 py-2 text-xs">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="font-semibold text-ink">{evidence.tag_name}</div>
          <div className="text-slate-600">{evidence.category_name}</div>
        </div>
        <span className="rounded bg-white px-2 py-1 font-medium text-slate-700">{clipWindow}</span>
      </div>
      <div className="mt-1 text-slate-600">{evidence.video_title}</div>
      {evidence.notes ? <div className="mt-1 text-slate-700">{evidence.notes}</div> : null}
    </div>
  );
}

function ProfileSection({ label, items }: { label: string; items: AthleteProfile["behavior_frequency"] }) {
  return (
    <div>
      <h3 className="mb-2 text-sm font-semibold text-slate-700">{label}</h3>
      <div className="space-y-2">
        {items.length ? (
          items.slice(0, 5).map((item) => (
            <div className="rounded-md border border-line p-3" key={`${label}-${item.category_id}-${item.tag_id}`}>
              <div className="flex items-center justify-between gap-2">
                <div>
                  <div className="text-sm font-semibold">{item.tag_name}</div>
                  <div className="text-xs text-slate-600">{item.category_name}</div>
                </div>
                <div className="text-right text-sm font-semibold text-review">{item.evidence_count}</div>
              </div>
              <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-slate-600">
                <span>{item.video_count} films</span>
                <span>{item.event_count} events</span>
              </div>
            </div>
          ))
        ) : (
          <EmptyState label="No evidence saved for this section yet" />
        )}
      </div>
    </div>
  );
}

function EvidenceRow({ evidence, onJump }: { evidence: EvidenceTag; onJump: (seconds: number) => void }) {
  return (
    <button
      className="w-full rounded-md border border-line p-3 text-left text-sm hover:border-review hover:bg-blue-50"
      onClick={() => onJump(evidence.timestamp_seconds)}
      type="button"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-semibold">{evidence.tag_name}</div>
          <div className="text-xs text-slate-600">
            {evidence.athlete_name} · {evidence.category_name}
          </div>
        </div>
        <span className="rounded bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700">
          {formatTime(evidence.timestamp_seconds)}
        </span>
      </div>
      {evidence.notes ? <p className="mt-2 text-slate-700">{evidence.notes}</p> : null}
    </button>
  );
}

function SelectBox({
  label,
  value,
  onChange,
  options,
  icon
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  icon: ReactNode;
}) {
  return (
    <label className="block text-xs font-semibold uppercase text-slate-500">
      <span className="mb-1 flex items-center gap-1.5">
        {icon}
        {label}
      </span>
      <select
        className="h-10 w-full rounded-md border border-line bg-white px-3 text-sm font-medium normal-case text-ink outline-none focus:border-review"
        onChange={(event) => onChange(event.target.value)}
        value={value}
      >
        <option value="">Select</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function BrandMark() {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-field text-white">
        <Activity aria-hidden="true" size={21} />
      </div>
      <div>
        <div className="text-lg font-semibold">ScoutDash</div>
        <div className="text-xs text-slate-400">Film breakdown for coaches</div>
      </div>
    </div>
  );
}

function SidebarNavButton({
  active,
  icon,
  label,
  onClick
}: {
  active: boolean;
  icon: ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      aria-current={active ? "page" : undefined}
      className={`flex h-11 w-full items-center gap-3 rounded-md px-3 text-sm font-semibold ${
        active ? "bg-field text-white" : "text-slate-300 hover:bg-white/10 hover:text-white"
      }`}
      onClick={onClick}
      type="button"
    >
      {icon}
      {label}
    </button>
  );
}

function TextInput({
  label,
  value,
  onChange,
  type = "text"
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
}) {
  return (
    <FieldLabel label={label}>
      <input
        className="h-10 w-full rounded-md border border-line px-3 text-sm outline-none focus:border-review"
        onChange={(event) => onChange(event.target.value)}
        type={type}
        value={value}
      />
    </FieldLabel>
  );
}

function FieldLabel({ children, label }: { children: ReactNode; label: string }) {
  return (
    <label className="block text-xs font-semibold uppercase text-slate-500">
      <span className="mb-1 block">{label}</span>
      {children}
    </label>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-line bg-slate-50 px-3 py-2">
      <div className="text-xs font-semibold uppercase text-slate-500">{label}</div>
      <div className="mt-0.5 font-semibold text-ink">{value}</div>
    </div>
  );
}

function ListBlock({ items }: { items: string[][] }) {
  return (
    <div className="mt-4 space-y-2">
      {items.length ? (
        items.map(([title, detail], index) => (
          <div className="flex items-center justify-between gap-3 rounded-md border border-line px-3 py-2 text-sm" key={`${title}-${index}`}>
            <span className="font-medium">{title}</span>
            <span className="text-slate-600">{detail}</span>
          </div>
        ))
      ) : (
        <EmptyState label="Nothing saved yet" />
      )}
    </div>
  );
}

function EmptyState({ label }: { label: string }) {
  return <div className="rounded-md border border-dashed border-line px-3 py-6 text-center text-sm text-slate-500">{label}</div>;
}

function athleteLabel(athlete: Athlete): string {
  return [athlete.jersey_number ? `#${athlete.jersey_number}` : null, athlete.display_name].filter(Boolean).join(" ");
}

function formatTime(value: number): string {
  const seconds = Number.isFinite(value) ? Math.max(0, Math.floor(value)) : 0;
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  return `${minutes}:${remaining.toString().padStart(2, "0")}`;
}

function formatContentType(value: string | null | undefined): string {
  if (!value) return "Pending";
  const subtype = value.split("/", 2)[1] || value;
  return subtype.replace("x-", "").toUpperCase();
}

function numeric(value: string, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function optionalNumber(value: string): number | null {
  if (!value.trim()) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function cleanPayload<T extends object>(payload: T): Record<string, unknown> {
  return Object.fromEntries(Object.entries(payload).map(([key, value]) => [key, value === "" ? null : value]));
}
