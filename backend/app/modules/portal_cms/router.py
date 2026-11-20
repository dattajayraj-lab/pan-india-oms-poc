"""Common web portal: public content, verify-and-publish CMS, menus, feedback, search, home tiles
(TS Cl. 11.1, 11.2(a)-(j); FRD CMS-01..14, CMN-02, CMN-03, CMN-05)."""
from datetime import timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.rbac import can_access, get_current_user, is_admin, require_admin, role_codes
from app.core.security import verify_captcha
from app.db.base import utcnow
from app.db.session import get_db
from app.integrations import scada_adapter
from app.modules.dms_files.models import Document
from app.modules.dms_files.service import store_upload
from app.modules.portal_cms.models import Feedback, MenuItem, PortalContent
from app.utils.exports import export

router = APIRouter(prefix="/api/v1/portal", tags=["portal"])


def content_out(c: PortalContent) -> dict:
    return {"id": c.id, "content_type": c.content_type, "acronym": c.acronym, "title_en": c.title_en,
            "title_hi": c.title_hi, "body_en": c.body_en, "body_hi": c.body_hi, "body_format": c.body_format,
            "attachment_doc_id": c.attachment_doc_id, "link_url": c.link_url, "workflow_state": c.workflow_state,
            "is_published": c.is_published, "audience": c.audience, "centre_id": c.centre_id,
            "created_at": c.created_at, "sort_order": c.sort_order}


@router.get("/public")
def public_portal(db: Session = Depends(get_db)):
    """Everything the public landing page needs, without login (Public User, TS Cl. 2.1)."""
    rows = db.scalars(select(PortalContent).where(PortalContent.is_published, PortalContent.audience == "PUBLIC")
                      .order_by(PortalContent.sort_order, PortalContent.created_at.desc())).all()
    grouped: dict[str, list] = {}
    for c in rows:
        if c.valid_until and c.valid_until < utcnow():
            continue
        grouped.setdefault(c.content_type.lower(), []).append(content_out(c))
    menu = db.scalars(select(MenuItem).where(MenuItem.is_active).order_by(MenuItem.location, MenuItem.sort_order)).all()
    return {**grouped, "menu": [_menu_out(m) for m in menu], "tiles": scada_adapter.grid_tiles("NLDC")}


@router.get("/public/file/{doc_id}")
def public_file(doc_id: int, db: Session = Depends(get_db)):
    """Flasher click downloads the attached file (TS 11.2(a))."""
    from fastapi.responses import FileResponse

    linked = db.scalar(select(PortalContent).where(PortalContent.attachment_doc_id == doc_id, PortalContent.is_published))
    d = db.get(Document, doc_id)
    if linked is None or d is None:
        raise HTTPException(404)
    return FileResponse(d.storage_path, filename=d.auto_filename)


@router.get("/post/{acronym}")
def post_by_acronym(acronym: str, db: Session = Depends(get_db)):
    c = db.scalar(select(PortalContent).where(PortalContent.acronym == acronym.upper(), PortalContent.is_published))
    if c is None:
        raise HTTPException(404, "Post not found")
    return content_out(c)


def _menu_out(m: MenuItem) -> dict:
    return {"id": m.id, "parent_id": m.parent_id, "label_en": m.label_en, "label_hi": m.label_hi, "icon": m.icon,
            "target_type": m.target_type, "target": m.target, "location": m.location, "sort_order": m.sort_order}


# --------------------------------------------------------------------- CMS (verify & publish)
@router.get("/content")
def list_content(content_type: str | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    stmt = select(PortalContent).order_by(PortalContent.created_at.desc())
    if content_type:
        stmt = stmt.where(PortalContent.content_type == content_type)
    return [content_out(c) for c in db.scalars(stmt)]


@router.post("/content")
def create_content(content_type: str = Form(...), title_en: str = Form(...), title_hi: str = Form(""),
                   body_en: str = Form(""), body_hi: str = Form(""), body_format: str = Form("TEXT"),
                   acronym: str | None = Form(None), audience: str = Form("PUBLIC"), link_url: str = Form(""),
                   file: UploadFile | None = File(None), db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not (is_admin(user) or any(c.endswith("COORDINATOR") for c in role_codes(user))):
        raise HTTPException(403, "Only authenticated coordinators/admins can create portal content")
    c = PortalContent(content_type=content_type.upper(), title_en=title_en, title_hi=title_hi, body_en=body_en,
                      body_hi=body_hi, body_format=body_format, acronym=acronym.upper() if acronym else None,
                      audience=audience, link_url=link_url, created_by=user.id, workflow_state="DRAFT")
    db.add(c)
    db.flush()
    if file is not None and file.filename:
        if content_type.upper() == "FLASHER":
            allowed = {".pdf", ".docx", ".doc", ".xlsx", ".xls"}
        else:
            allowed = None
        d = store_upload(db, file=file, module="portal", doc_category=content_type.upper(), owner_ref=f"content:{c.id}",
                         user=user, allowed=allowed)
        c.attachment_doc_id = d.id
    audit(db, user, "portal", "CONTENT_CREATED", "content", c.id, new={"title": title_en, "type": content_type})
    db.commit()
    return content_out(c)


class TransitionIn(BaseModel):
    action: str = Field(pattern="^(SUBMIT|PUBLISH|REJECT|UNPUBLISH)$")
    remarks: str = ""


@router.post("/content/{cid}/transition")
def transition(cid: int, body: TransitionIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """DRAFT -> SUBMITTED -> PUBLISHED; publish only by administrator (TS 11.1 'Verify & Publish'; Fig.12)."""
    c = db.get(PortalContent, cid)
    if c is None:
        raise HTTPException(404)
    old = c.workflow_state
    if body.action == "SUBMIT":
        if c.workflow_state not in ("DRAFT", "REJECTED"):
            raise HTTPException(409, "Only drafts can be submitted")
        c.workflow_state = "SUBMITTED"
    else:
        if not is_admin(user):
            raise HTTPException(403, "Only the administrator verifies and publishes content")
        if body.action == "PUBLISH":
            if c.workflow_state != "SUBMITTED":
                raise HTTPException(409, "Content must be submitted before publishing")
            c.workflow_state, c.is_published, c.approved_by = "PUBLISHED", True, user.id
        elif body.action == "REJECT":
            c.workflow_state, c.is_published = "REJECTED", False
        else:
            c.workflow_state, c.is_published = "DRAFT", False
    audit(db, user, "portal", f"CONTENT_{body.action}", "content", c.id, old={"state": old}, new={"state": c.workflow_state})
    db.commit()
    return content_out(c)


@router.delete("/content/{cid}")
def delete_content(cid: int, db: Session = Depends(get_db), user=Depends(require_admin)):
    c = db.get(PortalContent, cid)
    if c:
        db.delete(c)
        audit(db, user, "portal", "CONTENT_DELETED", "content", cid)
        db.commit()
    return {"ok": True}


# --------------------------------------------------------------------- menus
@router.get("/menu")
def get_menu(db: Session = Depends(get_db)):
    return [_menu_out(m) for m in db.scalars(select(MenuItem).order_by(MenuItem.location, MenuItem.sort_order))]


class MenuIn(BaseModel):
    parent_id: int | None = None
    label_en: str
    label_hi: str = ""
    icon: str = ""
    target_type: str = Field("INTERNAL", pattern="^(INTERNAL|POST|EXTERNAL)$")
    target: str = ""
    location: str = Field("NAVBAR", pattern="^(NAVBAR|FOOTER)$")
    sort_order: int = 0


@router.post("/menu")
def add_menu(body: MenuIn, db: Session = Depends(get_db), user=Depends(require_admin)):
    m = MenuItem(**body.model_dump())
    db.add(m)
    audit(db, user, "portal", "MENU_ADDED", "menu", body.label_en)
    db.commit()
    return _menu_out(m)


@router.delete("/menu/{mid}")
def del_menu(mid: int, db: Session = Depends(get_db), user=Depends(require_admin)):
    m = db.get(MenuItem, mid)
    if m:
        db.delete(m)
        db.commit()
    return {"ok": True}


# --------------------------------------------------------------------- feedback
class FeedbackIn(BaseModel):
    name: str = Field(min_length=2)
    email: str = ""
    organisation: str = ""
    category: str = "SUGGESTION"
    rating: int | None = Field(None, ge=1, le=5)
    message: str = Field(min_length=5, max_length=4000)
    captcha_token: str | None = None
    captcha_answer: str | None = None


@router.post("/feedback")
def submit_feedback(body: FeedbackIn, db: Session = Depends(get_db)):
    if not verify_captcha(body.captcha_token, body.captcha_answer):
        raise HTTPException(400, "CAPTCHA verification failed")
    f = Feedback(**body.model_dump(exclude={"captcha_token", "captcha_answer"}))
    db.add(f)
    db.commit()
    return {"ok": True, "id": f.id}


@router.get("/feedback")
def list_feedback(fmt: str | None = None, db: Session = Depends(get_db), user=Depends(require_admin)):
    rows = [{"id": f.id, "name": f.name, "email": f.email, "organisation": f.organisation, "category": f.category,
             "rating": f.rating, "message": f.message, "created_at": f.created_at}
            for f in db.scalars(select(Feedback).order_by(Feedback.created_at.desc()))]
    if fmt:
        cols = [("created_at", "Date", "दिनांक"), ("name", "Name", "नाम"), ("organisation", "Organisation", "संगठन"),
                ("category", "Category", "श्रेणी"), ("rating", "Rating", "रेटिंग"), ("message", "Message", "संदेश")]
        return export(fmt, "Customer Feedback & Suggestions", "ग्राहक प्रतिक्रिया एवं सुझाव", cols, rows, "feedback")
    return rows


# --------------------------------------------------------------------- search & home
@router.get("/search")
def search(q: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    like = f"%{q}%"
    content = db.scalars(select(PortalContent).where(PortalContent.is_published, or_(
        PortalContent.title_en.ilike(like), PortalContent.title_hi.ilike(like), PortalContent.body_en.ilike(like))).limit(30)).all()
    docs = db.scalars(select(Document).where(Document.is_latest, Document.is_confidential.is_(False), or_(
        Document.auto_filename.ilike(like), Document.original_filename.ilike(like))).limit(30)).all()
    return {"content": [content_out(c) for c in content],
            "documents": [{"id": d.id, "auto_filename": d.auto_filename, "module": d.module} for d in docs]}


@router.get("/home-stats")
def home_stats(centre: str | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Graphical home page tiles (TS Cl. 2.5 Fig.5) - only for modules the user may access."""
    from app.modules.ticketing_cas.models import Ticket

    tiles = list(scada_adapter.grid_tiles(centre or (user.centre.code if user.centre else "NLDC")))[:2]
    open_q = select(func.count()).select_from(Ticket).where(Ticket.status.notin_(["CLOSED", "RESOLVED"]))
    if user.user_category != "GRID_INDIA":
        open_q = open_q.where(Ticket.complainant_user_id == user.id)
    tiles.append({"key": "tickets", "label_en": "Open complaints", "label_hi": "खुली शिकायतें", "value": db.scalar(open_q), "tone": "amber"})
    try:
        from app.modules.workflow_engine.models import WorkflowCase

        if can_access(user, "ftc") or can_access(user, "registration"):
            q = select(func.count()).select_from(WorkflowCase).where(WorkflowCase.status.in_(["SUBMITTED", "UNDER_REVIEW"]))
            if user.user_category != "GRID_INDIA":
                q = q.where(WorkflowCase.applicant_user_id == user.id)
            tiles.append({"key": "cases", "label_en": "Cases under review", "label_hi": "समीक्षाधीन मामले", "value": db.scalar(q), "tone": "grid"})
        from app.modules.master_registry.models import GridElement

        if can_access(user, "realtime"):
            q = select(func.count()).select_from(GridElement).where(GridElement.status.in_(["OUTAGE", "TRIPPED"]))
            tiles.append({"key": "outage", "label_en": "Elements under outage", "label_hi": "आउटेज में तत्व", "value": db.scalar(q), "tone": "red"})
        from app.modules.realtime_outage.models import OutageCode

        if can_access(user, "realtime"):
            since = utcnow() - timedelta(hours=24)
            q = select(func.count()).select_from(OutageCode).where(OutageCode.issued_at >= since)
            tiles.append({"key": "codes", "label_en": "Codes issued (24 h)", "label_hi": "जारी कोड (24 घंटे)", "value": db.scalar(q), "tone": "green"})
    except ImportError:
        pass
    return {"tiles": tiles}
