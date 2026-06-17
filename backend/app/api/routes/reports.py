from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import AthleteModel, AthleteReportModel
from app.schemas import AthleteReportRead, ReportGenerateRequest
from app.services.reports import generate_athlete_development_report, render_report_pdf


router = APIRouter(tags=["reports"])


@router.get("/athletes/{athlete_id}/reports", response_model=list[AthleteReportRead])
def list_athlete_reports(athlete_id: str, db: Session = Depends(get_db)) -> list[AthleteReportModel]:
    if db.get(AthleteModel, athlete_id) is None:
        raise HTTPException(status_code=404, detail="Athlete not found")
    return list(
        db.scalars(
            select(AthleteReportModel)
            .where(AthleteReportModel.athlete_id == athlete_id)
            .order_by(AthleteReportModel.created_at.desc())
        )
    )


@router.post("/athletes/{athlete_id}/reports", response_model=AthleteReportRead, status_code=201)
def create_athlete_report(
    athlete_id: str, payload: ReportGenerateRequest | None = None, db: Session = Depends(get_db)
) -> AthleteReportModel:
    athlete = db.get(AthleteModel, athlete_id)
    if athlete is None:
        raise HTTPException(status_code=404, detail="Athlete not found")
    generated_by = payload.generated_by if payload else None
    return generate_athlete_development_report(db, athlete, generated_by=generated_by)


@router.get("/reports/{report_id}", response_model=AthleteReportRead)
def get_report(report_id: str, db: Session = Depends(get_db)) -> AthleteReportModel:
    report = db.get(AthleteReportModel, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.get("/reports/{report_id}/pdf")
def get_report_pdf(report_id: str, db: Session = Depends(get_db)) -> Response:
    report = db.get(AthleteReportModel, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    pdf_bytes = render_report_pdf(report)
    filename = f"{_safe_filename(report.title)}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _safe_filename(value: str) -> str:
    keep = [char.lower() if char.isalnum() else "-" for char in value]
    return "-".join("".join(keep).split("-"))[:120] or "athlete-development-report"

