"use client";

import {
  Activity,
  AlertTriangle,
  Calendar,
  ClipboardList,
  Crosshair,
  Eye,
  Layers3,
  ListChecks,
  Plus,
  RefreshCw,
  Save,
  Search,
  Tags,
  Upload,
  UserRound,
  Users,
  Video
} from "lucide-react";
import type { ChangeEvent, FormEvent, ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";

import { apiGet, apiPost, apiUpload, mediaUrl } from "@/lib/api";
import type {
  Athlete,
  AthleteProfile,
  Category,
  Event,
  EvidenceTag,
  EvidenceType,
  Organization,
  TagDefinition,
  Team,
  VideoAsset,
  VisionTrack
} from "@/types/scoutdash";

type Tab = "review" | "directory" | "taxonomy" | "vision";
type Notice = { kind: "idle" | "loading" | "success" | "error"; message: string };

const initialNotice: Notice = { kind: "idle", message: "" };

export function ScoutDashApp() {
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const [tab, setTab] = useState<Tab>("review");
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
  const [tracks, setTracks] = useState<VisionTrack[]>([]);

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
  const [trackForm, setTrackForm] = useState({ track_label: "", frame_start: "0", frame_end: "0" });

  const selectedOrganization = organizations.find((item) => item.id === selectedOrgId) ?? null;
  const selectedTeam = teams.find((item) => item.id === selectedTeamId) ?? null;
  const selectedAthlete = athletes.find((item) => item.id === selectedAthleteId) ?? null;
  const selectedVideo = videos.find((item) => item.id === selectedVideoId) ?? null;
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
      return;
    }
    setTagForm((value) => ({ ...value, athlete_id: selectedAthleteId }));
    void loadAthleteProfile(selectedAthleteId);
  }, [selectedAthleteId]);

  useEffect(() => {
    if (!selectedVideoId) return;
    void loadEvidence();
    void loadTracks();
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

  async function loadTracks() {
    if (!selectedVideoId) return;
    try {
      const data = await apiGet<VisionTrack[]>(`/vision/tracks?video_id=${selectedVideoId}`);
      setTracks(data);
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

  async function saveTrack(event: FormEvent) {
    event.preventDefault();
    if (!selectedOrgId || !selectedVideoId) return;
    const frameStart = Math.max(0, Math.floor(numeric(trackForm.frame_start, 0)));
    const frameEnd = Math.max(frameStart, Math.floor(numeric(trackForm.frame_end, frameStart)));
    try {
      const created = await apiPost<VisionTrack>(
        "/vision/tracks",
        cleanPayload({
          organization_id: selectedOrgId,
          video_id: selectedVideoId,
          athlete_id: selectedAthleteId || null,
          track_label: trackForm.track_label,
          frame_start: frameStart,
          frame_end: frameEnd,
          source: "manual_sam3",
          status: "draft",
          bounding_data: { manual_time_seconds: currentTime, frames: [] },
          segmentation_metadata: { model: "sam3", status: "pending_manual_segmentation" }
        })
      );
      setTracks((items) => [created, ...items]);
      setTrackForm({ track_label: "", frame_start: "0", frame_end: "0" });
      showSuccess("Track saved");
    } catch (error) {
      showError(error);
    }
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
    setNotice({ kind: "error", message: error instanceof Error ? error.message : "Something went wrong" });
  }

  return (
    <main className="min-h-screen px-4 py-4 text-ink sm:px-6 lg:px-8">
      <header className="mx-auto flex max-w-7xl flex-col gap-4 border-b border-line pb-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-md bg-field text-white">
              <Activity aria-hidden="true" size={22} />
            </div>
            <div>
              <h1 className="text-2xl font-semibold">ScoutDash</h1>
              <p className="text-sm text-slate-600">Film evidence library</p>
            </div>
          </div>
        </div>
        <div className="grid gap-2 sm:grid-cols-3 lg:w-[720px]">
          <SelectBox
            label="Organization"
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
      </header>

      <section className="mx-auto mt-4 max-w-7xl">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex rounded-md border border-line bg-white p-1 shadow-panel">
            <TabButton active={tab === "review"} icon={<Video size={16} />} label="Review" onClick={() => setTab("review")} />
            <TabButton
              active={tab === "directory"}
              icon={<Users size={16} />}
              label="Directory"
              onClick={() => setTab("directory")}
            />
            <TabButton
              active={tab === "taxonomy"}
              icon={<Tags size={16} />}
              label="Taxonomy"
              onClick={() => setTab("taxonomy")}
            />
            <TabButton active={tab === "vision"} icon={<Eye size={16} />} label="Vision" onClick={() => setTab("vision")} />
          </div>
          <button
            className="inline-flex h-10 items-center gap-2 rounded-md border border-line bg-white px-3 text-sm font-medium shadow-panel hover:border-review"
            onClick={() => {
              void loadOrganizations();
              if (selectedOrgId) void loadOrganizationScope(selectedOrgId);
              if (selectedTeamId) void loadTeamScope(selectedTeamId);
            }}
            type="button"
          >
            <RefreshCw aria-hidden="true" size={16} />
            Refresh
          </button>
        </div>

        {notice.message ? (
          <div
            className={`mt-3 flex items-center gap-2 rounded-md border px-3 py-2 text-sm ${
              notice.kind === "error"
                ? "border-red-200 bg-red-50 text-red-800"
                : "border-emerald-200 bg-emerald-50 text-emerald-800"
            }`}
          >
            {notice.kind === "error" ? <AlertTriangle size={16} /> : <ListChecks size={16} />}
            {notice.message}
          </div>
        ) : null}
      </section>

      <section className="mx-auto mt-4 max-w-7xl">
        {tab === "review" ? renderReview() : null}
        {tab === "directory" ? renderDirectory() : null}
        {tab === "taxonomy" ? renderTaxonomy() : null}
        {tab === "vision" ? renderVision() : null}
      </section>
    </main>
  );

  function renderReview() {
    return (
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.45fr)_minmax(360px,0.95fr)]">
        <div className="space-y-4">
          <section className="rounded-md border border-line bg-white p-4 shadow-panel">
            <div className="mb-3 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
              <SelectBox
                label="Film"
                value={selectedVideoId}
                onChange={setSelectedVideoId}
                options={videos.map((item) => ({ value: item.id, label: item.title }))}
                icon={<Video size={16} />}
              />
              <form className="grid gap-2 md:grid-cols-[minmax(160px,1fr)_minmax(180px,1fr)_auto]" onSubmit={uploadVideo}>
                <input
                  className="h-10 rounded-md border border-line px-3 text-sm outline-none focus:border-review"
                  onChange={(event) => setUploadTitle(event.target.value)}
                  placeholder="Film title"
                  value={uploadTitle}
                />
                <input
                  className="h-10 rounded-md border border-line px-3 text-sm file:mr-3 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-1.5"
                  onChange={onUploadFileChange}
                  type="file"
                  accept="video/*"
                />
                <button
                  className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-field px-3 text-sm font-semibold text-white hover:bg-teal-800 disabled:bg-slate-300"
                  disabled={!selectedOrgId || !selectedTeamId || !uploadFile}
                  type="submit"
                >
                  <Upload aria-hidden="true" size={16} />
                  Upload
                </button>
              </form>
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
            <div className="mt-3 grid gap-2 text-sm text-slate-700 sm:grid-cols-4">
              <Metric label="Time" value={formatTime(currentTime)} />
              <Metric label="Duration" value={formatTime(selectedVideo?.duration_seconds ?? 0)} />
              <Metric label="FPS" value={selectedVideo?.fps ? selectedVideo.fps.toFixed(2) : "Pending"} />
              <Metric label="Frames" value={selectedVideo?.frame_count?.toLocaleString() ?? "Pending"} />
            </div>
          </section>

          <section className="rounded-md border border-line bg-white p-4 shadow-panel">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="flex items-center gap-2 text-base font-semibold">
                <Crosshair aria-hidden="true" size={18} />
                Timestamp Tag
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
                    <option value="">Select</option>
                    {athletes.map((item) => (
                      <option key={item.id} value={item.id}>
                        {athleteLabel(item)}
                      </option>
                    ))}
                  </select>
                </FieldLabel>
                <FieldLabel label="Category">
                  <select
                    className="h-10 w-full rounded-md border border-line px-3 text-sm outline-none focus:border-review"
                    onChange={(event) => setTagForm((value) => ({ ...value, category_id: event.target.value }))}
                    value={tagForm.category_id}
                  >
                    <option value="">Select</option>
                    {categories.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                  </select>
                </FieldLabel>
                <FieldLabel label="Tag">
                  <select
                    className="h-10 w-full rounded-md border border-line px-3 text-sm outline-none focus:border-review"
                    onChange={(event) => setTagForm((value) => ({ ...value, tag_id: event.target.value }))}
                    value={tagForm.tag_id}
                  >
                    <option value="">Select</option>
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
                  label="Clip Start"
                  onChange={(value) => setTagForm((item) => ({ ...item, clip_start_seconds: value }))}
                  value={tagForm.clip_start_seconds}
                />
                <TextInput
                  label="Clip End"
                  onChange={(value) => setTagForm((item) => ({ ...item, clip_end_seconds: value }))}
                  value={tagForm.clip_end_seconds}
                />
                <FieldLabel label="Evidence Type">
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
                placeholder="Coach notes"
                value={tagForm.notes}
              />
              <button
                className="inline-flex h-10 w-fit items-center gap-2 rounded-md bg-review px-4 text-sm font-semibold text-white hover:bg-blue-700 disabled:bg-slate-300"
                disabled={!selectedVideoId || !tagForm.tag_id || !(tagForm.athlete_id || selectedAthleteId)}
                type="submit"
              >
                <Save aria-hidden="true" size={16} />
                Save Evidence
              </button>
            </form>
          </section>
        </div>

        <aside className="space-y-4">
          <ProfilePanel profile={profile} selectedAthlete={selectedAthlete} />
          <section className="rounded-md border border-line bg-white p-4 shadow-panel">
            <h2 className="mb-3 flex items-center gap-2 text-base font-semibold">
              <ListChecks aria-hidden="true" size={18} />
              Evidence Clips
            </h2>
            <div className="space-y-2">
              {filteredEvidence.length ? (
                filteredEvidence.map((item) => (
                  <EvidenceRow evidence={item} key={item.id} onJump={jumpTo} />
                ))
              ) : (
                <EmptyState label="No evidence yet" />
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

  function renderDirectory() {
    return (
      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-md border border-line bg-white p-4 shadow-panel">
          <h2 className="mb-3 flex items-center gap-2 text-base font-semibold">
            <Users aria-hidden="true" size={18} />
            Organization
          </h2>
          <form className="grid gap-3 md:grid-cols-2" onSubmit={createOrganization}>
            <TextInput label="Name" onChange={(value) => setOrganizationForm((item) => ({ ...item, name: value }))} value={organizationForm.name} />
            <TextInput
              label="Sport Label"
              onChange={(value) => setOrganizationForm((item) => ({ ...item, sport_label: value }))}
              value={organizationForm.sport_label}
            />
            <button className="inline-flex h-10 w-fit items-center gap-2 rounded-md bg-field px-4 text-sm font-semibold text-white" type="submit">
              <Plus size={16} />
              Save
            </button>
          </form>
        </section>

        <section className="rounded-md border border-line bg-white p-4 shadow-panel">
          <h2 className="mb-3 flex items-center gap-2 text-base font-semibold">
            <ClipboardList aria-hidden="true" size={18} />
            Team
          </h2>
          <form className="grid gap-3 md:grid-cols-3" onSubmit={createTeam}>
            <TextInput label="Name" onChange={(value) => setTeamForm((item) => ({ ...item, name: value }))} value={teamForm.name} />
            <TextInput label="Sport" onChange={(value) => setTeamForm((item) => ({ ...item, sport: value }))} value={teamForm.sport} />
            <TextInput label="Season" onChange={(value) => setTeamForm((item) => ({ ...item, season: value }))} value={teamForm.season} />
            <button className="inline-flex h-10 w-fit items-center gap-2 rounded-md bg-field px-4 text-sm font-semibold text-white" type="submit">
              <Plus size={16} />
              Save
            </button>
          </form>
        </section>

        <section className="rounded-md border border-line bg-white p-4 shadow-panel">
          <h2 className="mb-3 flex items-center gap-2 text-base font-semibold">
            <UserRound aria-hidden="true" size={18} />
            Athletes
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
              Save
            </button>
          </form>
          <ListBlock items={athletes.map((item) => [athleteLabel(item), item.position || "Active"])} />
        </section>

        <section className="rounded-md border border-line bg-white p-4 shadow-panel">
          <h2 className="mb-3 flex items-center gap-2 text-base font-semibold">
            <Calendar aria-hidden="true" size={18} />
            Events
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
              Save
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
            Categories
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
              Save
            </button>
          </form>
          <ListBlock items={categories.map((item) => [item.name, item.sport || "All sports"])} />
        </section>

        <section className="rounded-md border border-line bg-white p-4 shadow-panel">
          <h2 className="mb-3 flex items-center gap-2 text-base font-semibold">
            <Tags aria-hidden="true" size={18} />
            Tags
          </h2>
          <form className="grid gap-3 md:grid-cols-2" onSubmit={createTagDefinition}>
            <FieldLabel label="Category">
              <select
                className="h-10 w-full rounded-md border border-line px-3 text-sm outline-none focus:border-review"
                onChange={(event) => setTagDefinitionForm((item) => ({ ...item, category_id: event.target.value }))}
                value={tagDefinitionForm.category_id}
              >
                <option value="">Select</option>
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
              Save
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
    return (
      <div className="grid gap-4 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
        <section className="rounded-md border border-line bg-white p-4 shadow-panel">
          <h2 className="mb-3 flex items-center gap-2 text-base font-semibold">
            <Eye aria-hidden="true" size={18} />
            Athlete Tracks
          </h2>
          <form className="grid gap-3" onSubmit={saveTrack}>
            <TextInput
              label="Track Label"
              onChange={(value) => setTrackForm((item) => ({ ...item, track_label: value }))}
              value={trackForm.track_label}
            />
            <div className="grid gap-3 sm:grid-cols-2">
              <TextInput
                label="Frame Start"
                onChange={(value) => setTrackForm((item) => ({ ...item, frame_start: value }))}
                value={trackForm.frame_start}
              />
              <TextInput
                label="Frame End"
                onChange={(value) => setTrackForm((item) => ({ ...item, frame_end: value }))}
                value={trackForm.frame_end}
              />
            </div>
            <button
              className="inline-flex h-10 w-fit items-center gap-2 rounded-md bg-field px-4 text-sm font-semibold text-white disabled:bg-slate-300"
              disabled={!selectedVideoId}
              type="submit"
            >
              <Save size={16} />
              Save Track
            </button>
          </form>
        </section>
        <section className="rounded-md border border-line bg-white p-4 shadow-panel">
          <h2 className="mb-3 flex items-center gap-2 text-base font-semibold">
            <Activity aria-hidden="true" size={18} />
            Stored Tracks
          </h2>
          <div className="space-y-2">
            {tracks.length ? (
              tracks.map((track) => (
                <div className="rounded-md border border-line p-3 text-sm" key={track.id}>
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-semibold">{track.track_label || "Manual track"}</div>
                    <span className="rounded bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700">{track.status}</span>
                  </div>
                  <div className="mt-2 grid gap-2 text-slate-700 sm:grid-cols-3">
                    <Metric label="Source" value={track.source} />
                    <Metric label="Start" value={String(track.frame_start)} />
                    <Metric label="End" value={String(track.frame_end)} />
                  </div>
                </div>
              ))
            ) : (
              <EmptyState label="No tracks stored" />
            )}
          </div>
        </section>
      </div>
    );
  }
}

function ProfilePanel({ profile, selectedAthlete }: { profile: AthleteProfile | null; selectedAthlete: Athlete | null }) {
  return (
    <section className="rounded-md border border-line bg-white p-4 shadow-panel">
      <h2 className="mb-3 flex items-center gap-2 text-base font-semibold">
        <UserRound aria-hidden="true" size={18} />
        Athlete Profile
      </h2>
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
          <ProfileSection label="Behavior Frequency" items={profile.behavior_frequency} />
          <ProfileSection label="Behavior Consistency" items={profile.behavior_consistency} />
        </div>
      ) : (
        <EmptyState label={selectedAthlete ? "Profile loading" : "No athlete selected"} />
      )}
    </section>
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
          <EmptyState label="No entries" />
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

function TabButton({
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
      className={`inline-flex h-9 items-center gap-2 rounded px-3 text-sm font-semibold ${
        active ? "bg-ink text-white" : "text-slate-600 hover:bg-slate-100"
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
        <EmptyState label="No records" />
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
