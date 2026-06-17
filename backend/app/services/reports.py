from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AthleteModel, AthleteReportModel, EvidenceTagModel, NoteModel
from app.schemas import (
    AthleteDevelopmentReportData,
    AthleteRead,
    ReportEvidenceReference,
    ReportNoteReference,
    ReportSection,
    TeamRead,
)


TRACEABILITY_STATEMENT = (
    "This report is generated only from coach-created evidence tags and coach notes. "
    "Every observation is tied to source evidence."
)


def generate_athlete_development_report(
    db: Session, athlete: AthleteModel, generated_by: str | None = None
) -> AthleteReportModel:
    evidence_entries = list(
        db.scalars(
            select(EvidenceTagModel)
            .where(EvidenceTagModel.athlete_id == athlete.id)
            .order_by(EvidenceTagModel.created_at.desc())
        )
    )
    notes = list(
        db.scalars(select(NoteModel).where(NoteModel.athlete_id == athlete.id).order_by(NoteModel.created_at.desc()))
    )

    generated_at = datetime.now(timezone.utc)
    title = f"{athlete.display_name} Athlete Development Report"
    report_data = AthleteDevelopmentReportData(
        athlete=AthleteRead.model_validate(athlete),
        team=TeamRead.model_validate(athlete.team),
        generated_at=generated_at,
        report_title=title,
        evidence_count=len(evidence_entries),
        note_count=len(notes),
        sections=[
            _athlete_information_section(athlete, evidence_entries, notes),
            _behavior_section(
                key="strengths",
                title="Strengths",
                entries=[entry for entry in evidence_entries if entry.evidence_type == "strength"],
                empty_summary="No strength-specific evidence tags have been marked yet.",
            ),
            _behavior_section(
                key="development_areas",
                title="Development Areas",
                entries=[entry for entry in evidence_entries if entry.evidence_type == "development_area"],
                empty_summary="No development-area evidence tags have been marked yet.",
            ),
            _coach_notes_section(notes),
            _supporting_evidence_section(evidence_entries),
        ],
        traceability_statement=TRACEABILITY_STATEMENT,
    )

    report = AthleteReportModel(
        organization_id=athlete.organization_id,
        team_id=athlete.team_id,
        athlete_id=athlete.id,
        title=title,
        report_type="athlete_development",
        status="generated",
        generated_by=generated_by,
        report_data=report_data.model_dump(mode="json"),
        evidence_tag_ids=[entry.id for entry in evidence_entries],
        note_ids=[note.id for note in notes],
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def render_report_pdf(report: AthleteReportModel) -> bytes:
    data = AthleteDevelopmentReportData.model_validate(report.report_data)
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        rightMargin=0.55 * inch,
        leftMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
        title=data.report_title,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ScoutDashTitle",
        parent=styles["Title"],
        textColor=colors.HexColor("#1f2933"),
        fontSize=20,
        leading=24,
        spaceAfter=8,
    )
    section_style = ParagraphStyle(
        "ScoutDashSection",
        parent=styles["Heading2"],
        textColor=colors.HexColor("#0f766e"),
        fontSize=13,
        leading=16,
        spaceBefore=10,
        spaceAfter=5,
    )
    body_style = ParagraphStyle("ScoutDashBody", parent=styles["BodyText"], fontSize=9.5, leading=12)
    small_style = ParagraphStyle(
        "ScoutDashSmall",
        parent=styles["BodyText"],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#475569"),
    )

    story = [
        Paragraph("ScoutDash", ParagraphStyle("Brand", parent=styles["Heading3"], textColor=colors.HexColor("#65a30d"))),
        Paragraph(_p(data.report_title), title_style),
        Paragraph(_p(data.traceability_statement), small_style),
        Spacer(1, 0.12 * inch),
        _summary_table(data),
    ]

    for section in data.sections:
        story.append(Paragraph(_p(section.title), section_style))
        story.append(Paragraph(_p(section.summary), body_style))
        if section.observations:
            story.append(
                ListFlowable(
                    [ListItem(Paragraph(_p(observation), body_style), leftIndent=8) for observation in section.observations],
                    bulletType="bullet",
                    start="circle",
                    leftIndent=14,
                )
            )
        if section.supporting_notes:
            story.append(Paragraph("Coach notes", small_style))
            story.append(
                ListFlowable(
                    [
                        ListItem(
                            Paragraph(
                                _p(f"{note.author_name or 'Coach'}: {note.body} [note {note.note_id}]"),
                                small_style,
                            ),
                            leftIndent=8,
                        )
                        for note in section.supporting_notes[:8]
                    ],
                    bulletType="bullet",
                    leftIndent=14,
                )
            )
        if section.supporting_evidence:
            story.append(Paragraph("Supporting clips", small_style))
            evidence_rows = [["Behavior", "Film", "Time", "Trace"]]
            for item in section.supporting_evidence[:12]:
                evidence_rows.append(
                    [
                        f"{item.category_name}: {item.tag_name}",
                        item.video_title,
                        _format_time(item.timestamp_seconds),
                        f"tag {item.evidence_tag_id}",
                    ]
                )
            story.append(_evidence_table(evidence_rows))
        story.append(Spacer(1, 0.08 * inch))

    document.build(story)
    return buffer.getvalue()


def _athlete_information_section(
    athlete: AthleteModel, evidence_entries: list[EvidenceTagModel], notes: list[NoteModel]
) -> ReportSection:
    team = athlete.team
    details = [
        f"Team: {team.name}",
        f"Sport: {team.sport or 'Not specified'}",
        f"Season: {team.season or 'Not specified'}",
    ]
    if athlete.jersey_number:
        details.append(f"Jersey: #{athlete.jersey_number}")
    if athlete.position:
        details.append(f"Position: {athlete.position}")
    return ReportSection(
        key="athlete_information",
        title="Athlete Information",
        summary=(
            f"{athlete.display_name} has {len(evidence_entries)} evidence tags and {len(notes)} coach notes "
            "included in this report."
        ),
        observations=details,
    )


def _behavior_section(
    key: str, title: str, entries: list[EvidenceTagModel], empty_summary: str
) -> ReportSection:
    if not entries:
        return ReportSection(key=key, title=title, summary=empty_summary)
    buckets = _behavior_buckets(entries)
    observations = [_bucket_summary(bucket) for bucket in buckets]
    evidence = [_evidence_reference(entry) for bucket in buckets for entry in bucket["entries"]]
    return ReportSection(
        key=key,
        title=title,
        summary=f"{len(entries)} evidence tags support this section.",
        observations=observations,
        supporting_evidence=evidence,
    )


def _coach_notes_section(notes: list[NoteModel]) -> ReportSection:
    if not notes:
        return ReportSection(key="coach_notes", title="Coach Notes", summary="No coach notes have been recorded yet.")
    return ReportSection(
        key="coach_notes",
        title="Coach Notes",
        summary=f"{len(notes)} coach notes are included.",
        observations=[_shorten(note.body, 180) for note in notes[:8]],
        supporting_notes=[
            ReportNoteReference(
                note_id=note.id,
                author_name=note.author_name,
                body=note.body,
                created_at=note.created_at,
            )
            for note in notes
        ],
    )


def _supporting_evidence_section(entries: list[EvidenceTagModel]) -> ReportSection:
    if not entries:
        return ReportSection(
            key="supporting_evidence",
            title="Supporting Evidence",
            summary="No evidence tags have been recorded yet.",
        )
    buckets = _behavior_buckets(entries)
    return ReportSection(
        key="supporting_evidence",
        title="Supporting Evidence",
        summary=f"{len(entries)} total evidence tags are attached to this athlete.",
        observations=[_bucket_summary(bucket) for bucket in buckets],
        supporting_evidence=[_evidence_reference(entry) for entry in entries],
    )


def _behavior_buckets(entries: list[EvidenceTagModel]) -> list[dict]:
    grouped: dict[tuple[str, str], list[EvidenceTagModel]] = defaultdict(list)
    for entry in entries:
        grouped[(entry.category.name, entry.tag.name)].append(entry)

    buckets = []
    for (category_name, tag_name), bucket_entries in grouped.items():
        video_ids = {entry.video_id for entry in bucket_entries}
        event_ids = {entry.event_id for entry in bucket_entries if entry.event_id}
        buckets.append(
            {
                "category_name": category_name,
                "tag_name": tag_name,
                "count": len(bucket_entries),
                "video_count": len(video_ids),
                "event_count": len(event_ids),
                "entries": bucket_entries,
            }
        )
    return sorted(buckets, key=lambda bucket: bucket["count"], reverse=True)


def _bucket_summary(bucket: dict) -> str:
    films = _plural(bucket["video_count"], "film")
    events = _plural(bucket["event_count"], "event")
    return (
        f"{bucket['tag_name']} in {bucket['category_name']} was tagged "
        f"{bucket['count']} {_plural(bucket['count'], 'time')} across {films} and {events}."
    )


def _evidence_reference(entry: EvidenceTagModel) -> ReportEvidenceReference:
    clip = entry.clip
    return ReportEvidenceReference(
        evidence_tag_id=entry.id,
        clip_id=entry.clip_id,
        video_id=entry.video_id,
        video_title=entry.video.title,
        category_name=entry.category.name,
        tag_name=entry.tag.name,
        timestamp_seconds=entry.timestamp_seconds,
        clip_start_seconds=clip.start_time_seconds if clip else None,
        clip_end_seconds=clip.end_time_seconds if clip else None,
        notes=entry.notes,
    )


def _summary_table(data: AthleteDevelopmentReportData) -> Table:
    rows = [
        ["Athlete", data.athlete.display_name, "Team", data.team.name],
        ["Evidence Tags", str(data.evidence_count), "Coach Notes", str(data.note_count)],
        ["Generated", data.generated_at.strftime("%Y-%m-%d %H:%M UTC"), "Report Type", "Athlete Development"],
    ]
    table = Table(rows, colWidths=[1.1 * inch, 2.0 * inch, 1.1 * inch, 2.2 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d8dee8")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#475569")),
                ("TEXTCOLOR", (2, 0), (2, -1), colors.HexColor("#475569")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def _evidence_table(rows: list[list[str]]) -> Table:
    table = Table(rows, colWidths=[1.65 * inch, 1.65 * inch, 0.6 * inch, 1.9 * inch], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d8dee8")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def _format_time(seconds: float) -> str:
    whole = max(0, int(seconds))
    return f"{whole // 60}:{whole % 60:02d}"


def _plural(count: int, noun: str) -> str:
    suffix = "" if count == 1 else "s"
    return f"{count} {noun}{suffix}"


def _shorten(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[: limit - 3].rstrip()}..."


def _p(value: str) -> str:
    return escape(value or "")
