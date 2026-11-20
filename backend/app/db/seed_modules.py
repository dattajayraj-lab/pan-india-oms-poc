"""Module-level reference/demo data (portal content, CAS FAQ, availability category codes,
violation templates, SPS schemes, MIS charts and report templates)."""
from datetime import timedelta

from sqlalchemy.orm import Session

from app.db.base import utcnow


def seed_all(db: Session, centres: dict, ents: dict, subs: dict) -> None:
    _portal(db, centres)
    _cas(db)
    _availability_codes(db)
    _message_templates(db)
    _sps(db, centres, ents)
    try:
        from app.modules.mis_reporting.catalog import seed_mis

        seed_mis(db)
    except ImportError:  # MIS catalogue arrives in Milestone 5
        pass


def _portal(db: Session, centres: dict) -> None:
    from app.modules.portal_cms.models import MenuItem, PortalContent

    items = [
        ("NOTICE", None, "Revised procedure for First Time Charging under IEGC 2023 published",
         "आईईजीसी 2023 के अंतर्गत प्रथम चार्जिंग हेतु संशोधित प्रक्रिया प्रकाशित",
         "The detailed procedure for first time energization and integration of new or modified power system elements is available for reference.",
         "नए या संशोधित विद्युत प्रणाली तत्वों के प्रथम ऊर्जीकरण एवं एकीकरण की विस्तृत प्रक्रिया संदर्भ हेतु उपलब्ध है।"),
        ("NOTICE", "NRLDC", "OCC meeting for M+2 outage planning: requests open 26th to 5th",
         "एम+2 आउटेज योजना हेतु ओसीसी बैठक: अनुरोध 26 से 5 तारीख तक",
         "Constituents may submit OCC shutdown requests for the M+2 month in the Outage Coordination module.",
         "घटक आउटेज समन्वय मॉड्यूल में एम+2 माह हेतु ओसीसी शटडाउन अनुरोध प्रस्तुत कर सकते हैं।"),
        ("NOTICE", None, "Monthly availability review sheets generated on 1st of every month",
         "मासिक उपलब्धता समीक्षा शीट प्रत्येक माह की 1 तारीख को तैयार",
         "Transmission licensees must Accept or Object outage rows by the 5th.",
         "पारेषण लाइसेंसधारी 5 तारीख तक आउटेज पंक्तियों को स्वीकार या आपत्ति करें।"),
        ("FLASHER", None, "Grid-India OMS go-live rehearsal: user training schedule", "ग्रिड-इंडिया ओएमएस प्रशिक्षण कार्यक्रम",
         "Training schedule for NLDC and all RLDCs.", "एनएलडीसी एवं सभी आरएलडीसी हेतु प्रशिक्षण कार्यक्रम।"),
        ("FLASHER", None, "Updated SCADA point list template (Annexure A4)", "अद्यतन स्काडा पॉइंट सूची टेम्पलेट (अनुलग्नक ए4)",
         "Download the latest A4 template.", "नवीनतम ए4 टेम्पलेट डाउनलोड करें।"),
        ("BANNER", None, "Welcome to the Pan-Grid-India Operations Management System", "अखिल ग्रिड-इंडिया प्रचालन प्रबंधन प्रणाली में आपका स्वागत है",
         "Use External Login if you are a registered stakeholder; Grid-India staff use Grid-India Login.",
         "पंजीकृत हितधारक बाहरी लॉगिन का उपयोग करें; ग्रिड-इंडिया कर्मचारी ग्रिड-इंडिया लॉगिन का उपयोग करें।"),
        ("FAQ", None, "How do I reset my password?", "मैं अपना पासवर्ड कैसे रीसेट करूं?",
         "Use 'Forgot Password' on the login page; a reset OTP is sent to your registered e-mail and mobile.",
         "लॉगिन पृष्ठ पर 'पासवर्ड भूल गए' का उपयोग करें; पंजीकृत ई-मेल एवं मोबाइल पर ओटीपी भेजा जाता है।"),
        ("FAQ", None, "Why is my code request blocked?", "मेरा कोड अनुरोध अवरुद्ध क्यों है?",
         "Code requests are blocked until the actual execution time of earlier codes is entered (IEGC practice).",
         "पिछले कोड का वास्तविक निष्पादन समय दर्ज होने तक नए कोड अनुरोध अवरुद्ध रहते हैं।"),
        ("POST", None, "About OMS", "ओएमएस के बारे में",
         "<p>The OMS integrates Registration, FTC, Communication Certification, Real-time Outage, Outage Coordination, Availability, Protection, Alerts, SPS and MIS for NLDC and five RLDCs.</p>",
         "<p>ओएमएस एनएलडीसी एवं पांच आरएलडीसी हेतु सभी प्रचालन मॉड्यूल को एकीकृत करता है।</p>"),
        ("GALLERY", None, "NLDC Control Room", "एनएलडीसी नियंत्रण कक्ष", "", ""),
    ]
    for i, (ctype, cc, ten, thi, ben, bhi) in enumerate(items):
        db.add(PortalContent(content_type=ctype, centre_id=centres[cc].id if cc else None, title_en=ten, title_hi=thi,
                             body_en=ben, body_hi=bhi, body_format="HTML" if ctype == "POST" else "TEXT",
                             acronym="ABOUT" if ctype == "POST" else None, workflow_state="PUBLISHED",
                             is_published=True, sort_order=i))
    menu = [
        ("Home", "मुख्य पृष्ठ", "INTERNAL", "/", "NAVBAR"), ("Notice Board", "सूचना पट्ट", "INTERNAL", "/notices", "NAVBAR"),
        ("About OMS", "ओएमएस के बारे में", "POST", "ABOUT", "NAVBAR"), ("FAQ", "सामान्य प्रश्न", "INTERNAL", "/faq", "NAVBAR"),
        ("Feedback", "प्रतिक्रिया", "INTERNAL", "/feedback", "NAVBAR"),
        ("Grid-India Website", "ग्रिड-इंडिया वेबसाइट", "EXTERNAL", "https://grid-india.in", "FOOTER"),
        ("CERC Regulations", "सीईआरसी विनियम", "EXTERNAL", "https://cercind.gov.in", "FOOTER"),
        ("ISO/ISMS Documents", "आईएसओ/आईएसएमएस दस्तावेज़", "EXTERNAL", "https://posoco.in/notices", "FOOTER"),
    ]
    for i, (en, hi, tt, tgt, loc) in enumerate(menu):
        db.add(MenuItem(label_en=en, label_hi=hi, target_type=tt, target=tgt, location=loc, sort_order=i))


def _cas(db: Session) -> None:
    from app.modules.ticketing_cas.models import DowntimeEvent, KnowledgeBaseArticle

    for module, q, a in [
        ("realtime", "Code request button is disabled", "Enter pending execution times in 'Due for Outage/Charging'; the gate releases automatically."),
        ("ftc", "Cannot submit A-annexures", "A-annexures must be submitted at least 10 days before the proposed charging date."),
        ("registration", "Upload of .zip model files rejected", "Upload each model file under its category head; .zip dumps are not accepted."),
    ]:
        db.add(KnowledgeBaseArticle(module=module, question_en=q, answer_en=a))
    now = utcnow()
    db.add(DowntimeEvent(kind="MAINTENANCE", started_at=now - timedelta(days=12, hours=2), ended_at=now - timedelta(days=12),
                         reason="EIC-approved patch window"))
    db.add(DowntimeEvent(kind="DOWNTIME", started_at=now - timedelta(days=8, minutes=30), ended_at=now - timedelta(days=8),
                         reason="Application pod restart"))


CATEGORY_CODES = [
    ("C01", "Planned maintenance by licensee", True), ("C02", "Breakdown maintenance by licensee", True),
    ("C03", "Tripping due to equipment failure", True), ("C04", "Tripping due to protection mal-operation", True),
    ("C05", "Shutdown for line diversion (NHAI/Railways)", False), ("C06", "Shutdown for construction of new element", False),
    ("C07", "Outage due to kite/foreign material", False), ("C08", "Outage due to weather (storm, lightning)", False),
    ("C09", "Opened on high voltage (RLDC instruction)", False), ("C10", "Opened on low loading / system constraint", False),
    ("C11", "Outage for OPGW work", False), ("C12", "Over-fluxing trip", False), ("C13", "Grid disturbance (LNCC)", False),
    ("C14", "Spare changeover", True), ("C15", "Delay by utility other than licensee", False),
    ("C16", "Right of Way (ROW) issue", False), ("C17", "Fire in substation / switchyard", True),
    ("C18", "Tower collapse", True), ("C19", "Conductor snapping", True), ("C20", "Insulator failure", True),
    ("C21", "CT/PT failure", True), ("C22", "Breaker failure", True), ("C23", "Isolator problem", True),
    ("C24", "Auto-reclosure lockout", True), ("C25", "Transformer internal fault", True),
    ("C26", "Reactor fault", True), ("C27", "HVDC pole block (self)", True), ("C28", "HVDC pole block (others)", False),
    ("C29", "HVDC power order restriction", False), ("C30", "Generation evacuation constraint", False),
    ("C31", "SPS operation", False), ("C32", "Load management by SLDC", False), ("C33", "Flood / water logging", False),
    ("C34", "Earthquake / natural calamity", False), ("C35", "Bird / animal fault", False),
    ("C36", "Hot line maintenance", True), ("C37", "Testing and commissioning", False),
    ("C38", "Deemed available (RLDC instruction)", False), ("C39", "Others (to be specified)", False),
]


def _availability_codes(db: Session) -> None:
    from app.modules.availability_verify.models import CategoryCode

    for code, desc, owner_fault in CATEGORY_CODES:
        db.add(CategoryCode(code=code, description=desc, owner_fault=owner_fault))


VIOLATION_TEMPLATES = [
    ("FLASH_ADD", "Add flash message to latest updates", "MISC", "ALERT", "{message}"),
    ("FLASH_DISABLE", "Disable flash message of latest updates", "MISC", "ALERT", "Flash message withdrawn: {message}"),
    ("SCADA_TELEMETRY", "SCADA telemetry violation", "STATE", "ALERT",
     "{utility}: Telemetry of {points} not available at {centre} since {since}. Restore immediately as per IEGC."),
    ("FREQ_DEVIATION", "Frequency & deviation violation", "STATE", "EMERGENCY",
     "{utility}: Freq {frequency} Hz. Schedule {schedule} MW, actual {actual} MW, ACE {ace} MW. Reduce overdrawal now."),
    ("DEVIATION", "Deviation violation", "STATE", "ALERT",
     "{utility}: Deviation {actual} MW vs schedule {schedule} MW at {time}. Correct as per IEGC 2023."),
    ("DEV_PR_WARNING", "Deviation physical regulation warning", "STATE", "EMERGENCY",
     "{utility}: Persistent deviation. Physical regulation will be implemented if not corrected within {minutes} min."),
    ("DEV_PR_IMPL", "Deviation physical regulation implementation", "STATE", "EXTREME",
     "{utility}: Physical regulation implemented on feeders {feeders} due to persistent deviation."),
    ("HIGH_VOLTAGE", "High voltage violation", "STATE", "ALERT",
     "{utility}: Voltage at {station} is {voltage} kV. Absorb MVAr / take reactors in service."),
    ("LOW_VOLTAGE", "Low voltage violation", "STATE", "ALERT",
     "{utility}: Voltage at {station} is {voltage} kV. Inject MVAr / reduce load."),
    ("LV_PR_WARNING", "Low voltage physical regulation warning", "STATE", "EMERGENCY",
     "{utility}: Low voltage persists at {station}. Physical regulation will be implemented."),
    ("LV_PR_IMPL", "Low voltage physical regulation implementation", "STATE", "EXTREME",
     "{utility}: Physical regulation implemented at {station} due to low voltage."),
    ("CORRIDOR_LOADING", "Transmission element / corridor loading violation", "STATE", "ALERT",
     "{utility}: {element} loading {loading} MW exceeds limit {limit} MW. Take corrective action."),
    ("NONCOMP_LOADING", "Non-compliance loading violation", "STATE", "EMERGENCY",
     "{utility}: Non-compliance of earlier loading instruction on {element}."),
    ("ICT_LOADING", "ICT loading violation", "STATE", "ALERT",
     "{utility}: {element} loading {loading} MVA exceeds {limit} MVA."),
    ("RE_DEVIATION", "RE generator deviation violation", "RE_GEN", "ALERT",
     "{generator} at {pooling_station}: actual {actual} MW vs schedule {schedule} MW. Freq {frequency} Hz."),
    ("RE_CURTAIL", "RE curtailment instruction", "RE_GEN", "EMERGENCY",
     "{generator} at {pooling_station}: curtail generation to {schedule} MW due to {reason}."),
]


def _message_templates(db: Session) -> None:
    import re

    from app.modules.message_alerts.models import MessageTemplate

    for code, name, cat, sev, tpl in VIOLATION_TEMPLATES:
        keys = list(dict.fromkeys(re.findall(r"{(\w+)}", tpl)))
        db.add(MessageTemplate(code=code, name_en=name, category=cat, severity=sev, sms_template=tpl,
                               email_subject=f"[Grid-India] {name}",
                               email_template="Dear Sir/Madam,\n\n" + tpl + "\n\nShift In-charge, {centre}",
                               fields_json=[{"key": k, "label": k.replace("_", " ").title(), "type": "text"} for k in keys]))


def _sps(db: Session, centres: dict, ents: dict) -> None:
    from app.modules.sps_status.models import SpsScheme, SpsStatusLog

    now = utcnow()
    schemes = [
        ("NR-SPS-001", "Bikaner-Bhadla corridor SPS (RE backdown)", "NRLDC", "PG", "ON"),
        ("NR-SPS-002", "765 kV Agra-Gwalior inter-regional SPS", "NRLDC", "PG", "ON"),
        ("NR-SPS-003", "Dadri ICT overload load-shedding SPS", "NRLDC", "NTPC", "OFF"),
        ("NR-SPS-004", "Fatehgarh-II RE evacuation SPS", "NRLDC", "PG", "DEGRADED"),
        ("WR-SPS-001", "Indore 765 kV ICT SPS", "WRLDC", "PG", "ON"),
    ]
    for sid, name, cc, ek, status in schemes:
        s = SpsScheme(sps_id=sid, sps_name=name, centre_id=centres[cc].id, owner_entity_id=ents[ek].id,
                      logic_description="Trip/back-down logic as per RPC approved scheme", current_status=status,
                      template_fields_json={"trigger": "Line loading > 90%", "action": "Back down 300 MW RE"})
        db.add(s)
        db.flush()
        for d, st in [(9, "ON"), (5, "OFF"), (3, "ON"), (1, status)]:
            db.add(SpsStatusLog(sps_scheme_id=s.id, status=st, source="SCADA" if d % 2 else "USER",
                                updated_at=now - timedelta(days=d)))
