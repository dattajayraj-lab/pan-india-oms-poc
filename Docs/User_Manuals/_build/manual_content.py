"""Content of the Grid-India OMS user manuals.

Each manual is a list of chapters; each chapter has sections. A section can carry:
  menu   - navigation path shown as a breadcrumb chip
  url    - the page address (relative to the app)
  text   - intro paragraph(s)
  steps  - numbered steps
  bullets- bullet points
  shot   - screenshot file name (without .png) and caption
  note   - highlighted tip / note
"""

S = '›'  # single right-pointing angle quote used in menu paths


def m(*parts):
    return f' {S} '.join(parts)


MODS = {
    'cas': 'Complaint Addressal System', 'reg': 'Registration', 'ftc': 'First Time Charging',
    'cc': 'Communication Certification', 'rt': 'Real-time Outage Management', 'oc': 'Outage Coordination',
    'av': 'Availability Inputs Verification', 'pr': 'Protection & Tripping Studies', 'al': 'Message Alerts',
    'sps': 'SPS Status', 'mis': 'MIS & Reporting',
}

DEMO_USERS = [
    ('superadmin', 'Grid-India', 'Super Administrator (all modules and Administration menu)'),
    ('nr_coord', 'Grid-India', 'NRLDC Registration / FTC / Communication coordinator'),
    ('nr_shiftic', 'Grid-India', 'NRLDC shift in-charge (control room)'),
    ('nr_operator', 'Grid-India', 'NRLDC grid operator'),
    ('nr_outage', 'Grid-India', 'Outage and availability coordinator'),
    ('nr_protection', 'Grid-India', 'Protection coordinator'),
    ('nr_alerts', 'Grid-India', 'Message alerts and SPS coordinator'),
    ('nldc_coord / nldc_head', 'Grid-India', 'NLDC coordinator / Head of NLDC'),
    ('re_dev', 'External', 'RE developer (Registration, FTC, Real-time, Complaints)'),
    ('pg_user', 'External', 'Transmission licensee (FTC, Comm., Real-time, Outage, Availability, Protection, SPS)'),
    ('tpcomm_user', 'External', 'Communication service provider (Registration, Comm. certification)'),
    ('ntpc_user / rvpn_user', 'External', 'Generator / State utility'),
]

# ---------------------------------------------------------------------------------------------
GETTING_STARTED = {
    'file': 'OMS_User_Manual_01_Getting_Started.pdf',
    'title': 'Getting Started and Common Features',
    'audience': 'All users: Grid-India staff and external stakeholders',
    'chapters': [
        {'title': 'About the OMS', 'sections': [
            {'title': 'What the system does', 'text': [
                'The Pan-Grid-India Operations Management System (OMS) is one secure web application for the National '
                'Load Despatch Centre (NLDC) and the five Regional Load Despatch Centres (NRLDC, ERLDC, WRLDC, SRLDC and '
                'NERLDC). It brings registration, first time charging, real-time outage codes, outage planning, '
                'availability verification, protection analysis, alerts and MIS reporting into a single portal.',
                'The system has eleven application modules. Each user sees only the modules their role is authorised '
                'for; other modules are shown greyed out with a lock.'],
             'bullets': [f'<b>{v}</b>' for v in MODS.values()]},
            {'title': 'How this manual set is organised', 'bullets': [
                '<b>Manual 01, Getting Started</b> (this document): signing in, navigation, language, tables, exports and your profile.',
                '<b>Manual 02, Grid-India Internal Users</b>: every module as used by RLDC / NLDC coordinators, shift staff and departments.',
                '<b>Manual 03, External Stakeholders</b>: utilities, generators, RE developers and other external users.',
                '<b>Manual 04, Administrators</b>: users, sessions, settings, audit trail, master registry and portal content.'],
             'note': 'Menu paths are written as <b>Sidebar › Module › Menu item</b>. Screenshots were taken from the '
                     'proof-of-concept system with demo data, so names and numbers are examples.'},
        ]},
        {'title': 'Public portal', 'sections': [
            {'title': 'Public landing page', 'menu': 'Browser address: /welcome', 'url': '/welcome',
             'text': ['The public portal is open to everyone without signing in. It shows live grid figures, the notice '
                      'board, scrolling flash messages, FAQs, an image gallery and a feedback form.'],
             'bullets': ['<b>Grid-India Login</b> and <b>External Login</b> buttons open the sign-in page with the right login type selected.',
                         '<b>New stakeholder? Request an account</b> opens the pre-registration form.',
                         'The top menu links to Notice Board, About OMS, FAQ and Feedback. The Hindi button switches the portal language.',
                         'Links that leave the Grid-India site show a warning before opening.'],
             'shot': ('pub_landing', 'Public landing page with live figures, notice board and FAQ')},
        ]},
        {'title': 'Signing in', 'sections': [
            {'title': 'Grid-India (internal) login', 'menu': 'Public portal › Grid-India Login', 'url': '/login',
             'steps': ['Open the OMS address and click <b>Grid-India Login</b> (or go to /login).',
                       'Keep the <b>Grid-India Login</b> tab selected.',
                       'Enter your <b>Username</b> and <b>Password</b>.',
                       'Solve the arithmetic CAPTCHA shown under <b>Solve to continue</b> and type the answer. Use the refresh icon for a new question.',
                       'Click <b>Login</b>.',
                       'Enter the one-time password (OTP) sent to your registered mobile / e-mail and confirm. In the demo system the OTP is displayed on screen.'],
             'shot': ('pub_login', 'Sign-in page, Grid-India login'),
             'note': 'After five wrong passwords the account is locked for a period set by the administrator. Use '
                     '<b>Forgot password?</b> or <b>Forgot username?</b> to recover access.'},
            {'title': 'External stakeholder login', 'menu': 'Public portal › External Login', 'url': '/login?type=external',
             'text': ['Utilities, generators, RE developers, CTUIL, RPCs and other external users choose the <b>External Login</b> '
                      'tab. The remaining steps are the same as for internal users. Using the wrong tab is refused with a '
                      'message telling you which option to use.'],
             'shot': ('pub_login_external', 'Sign-in page, External login tab selected')},
            {'title': 'Requesting an account (new stakeholders)', 'menu': 'Public portal › New stakeholder? Request an account', 'url': '/signup',
             'steps': ['Choose the <b>User type</b> and enter your organisation.',
                       'Fill in first and last name, mobile, e-mail and the login name you want.',
                       'Select the RLDC you deal with and set a password that meets the policy (minimum 8 characters with upper case, lower case, digit and special character).',
                       'Enter the NSWS / CEA / F&amp;C / connectivity registration numbers where applicable.',
                       'Solve the CAPTCHA and click <b>Submit request</b>.'],
             'text': ['The request goes to the RLDC registration coordinator for approval. You receive your login once it is approved.'],
             'shot': ('pub_signup', 'Stakeholder pre-registration form')},
        ]},
        {'title': 'Home page and navigation', 'sections': [
            {'title': 'Home page (module launcher)', 'menu': 'Sidebar › Home', 'url': '/',
             'text': ['After sign-in you land on the home page. The banner shows your name, centre and how many modules you can '
                      'use, with shortcuts to recently visited pages. Below it are live tiles (grid frequency, demand met, '
                      'open complaints, cases under review, elements under outage, codes issued) and one card per module.'],
             'bullets': ['Click a module card to open it.',
                         'Modules you are not authorised for appear dashed and greyed with a lock and cannot be opened.',
                         'The <b>Last updated</b> stamp shows when the figures were refreshed; pages refresh automatically.'],
             'shot': ('int_home', 'Home page for an internal coordinator with all modules enabled')},
            {'title': 'What an external user sees', 'url': '/',
             'text': ['External users see the same layout, but only the modules granted to their organisation are active.'],
             'shot': ('ext_home', 'Home page for an RE developer: unauthorised modules are locked')},
            {'title': 'Screen layout', 'bullets': [
                '<b>Sidebar (left)</b>: Home, the module list and, for administrators, the Administration section. Click a module to expand its menu items; the current page is highlighted with an orange marker. The « button collapses the sidebar to icons.',
                '<b>Top bar</b>: system title, your centre and roles, the <b>Centre</b> switcher (users with more than one centre), the Hindi / English toggle, recent pages (clock icon), notifications (bell with unread count) and your initials for the user menu (Profile, Sign out).',
                '<b>Breadcrumbs</b> under the top bar show where you are, for example Home / Ftc / 2; click any part to go back up.',
                '<b>Footer</b> shows the organisation and your active centre.'],
             'shot': ('ftc_list', 'Typical module page: sidebar with expanded module, breadcrumbs, KPI tiles, charts and a data grid')},
            {'title': 'Switching to Hindi', 'menu': 'Top bar › Hindi toggle',
             'text': ['Click the Hindi toggle in the top bar to switch menus, labels and module names to Hindi. Click it again '
                      '(EN) to return to English. Your choice is remembered on this browser. Exports such as PDF and Excel '
                      'reports are bilingual with Hindi before English.'],
             'shot': ('int_hindi', 'Home page in Hindi')},
        ]},
        {'title': 'Working with data', 'sections': [
            {'title': 'Data grids, search and export', 'text': [
                'Every list in the OMS uses the same spreadsheet-style grid.'],
             'bullets': ['<b>PDF / CSV / Excel / Copy</b> buttons (top left of every grid) export the rows currently shown, in one click.',
                         '<b>Search</b> box (top right) filters the grid as you type.',
                         'Click a column header to sort; hold <b>Shift</b> and click more headers to sort on several columns.',
                         'Where a grid allows it, cells can be edited in place (drop-downs for fixed values).',
                         '<b>Paste from Excel</b> lets you paste copied rows; a preview is shown before anything is saved.',
                         'The line under the grid shows how many rows are shown out of the total.'],
             'shot': ('adm_master', 'Data grid with export buttons, search, sortable headers and status badges')},
            {'title': 'Case tracker (workflow flowchart)', 'text': [
                'Cases that move through a workflow (complaints, registrations, FTC, communication certification) show a '
                '<b>Status tracking</b> panel with the case ID, current status, who it is pending with, and a flowchart of '
                'every step. Green steps are completed, amber are pending, red were returned and grey are not reached. '
                'Click a step to see who acted, when and with what remarks.'],
             'shot': ('ftc_detail', 'Case page with status tracking flowchart, stage tabs and document list')},
            {'title': 'Uploading documents', 'bullets': [
                'Choose the document category from the drop-down, pick the file and click <b>Upload</b>. Files are renamed automatically to the case number and version.',
                'Uploading the same category again creates a new revision; tick <b>Show all revisions</b> to see older versions.',
                'Only permitted file types are accepted and every file is checked before it is stored.']},
        ]},
        {'title': 'Your profile and security', 'sections': [
            {'title': 'Profile, password and signature', 'menu': 'Top bar › your initials › Profile', 'url': '/profile',
             'steps': ['Open <b>Profile</b> from the user menu.',
                       'To change your password enter the current password, the new password twice and click <b>Save</b>.',
                       'Officers who sign certificates upload a signature image (PNG / JPG) and, optionally, their DSC serial number.'],
             'shot': ('int_profile', 'Profile page with password change and signature upload')},
            {'title': 'Sessions, time-outs and contact review', 'bullets': [
                'You are signed out automatically after a period of inactivity (set by the administrator).',
                'Passwords expire after 90 days and must be changed.',
                'Every three months you are asked to confirm your mobile number and e-mail with an OTP.',
                'Administrators can see all active sessions and force a logout if required.',
                'Every sign-in, change and approval is recorded in the audit trail.']},
            {'title': 'Notifications', 'text': [
                'The bell icon shows unread notifications such as cases waiting for you, consents received and SLA warnings. '
                'Click a notification to open the related page. The same events are also sent by e-mail / SMS where enabled.']},
        ]},
    ],
    'appendix': True,
}

# ---------------------------------------------------------------------------------------------
INTERNAL = {
    'file': 'OMS_User_Manual_02_Grid-India_Internal_Users.pdf',
    'title': 'Grid-India Internal Users',
    'audience': 'NLDC / RLDC coordinators, shift staff, departments, HoDs and heads',
    'chapters': [
        {'title': MODS['cas'], 'sections': [
            {'title': 'Ticket list', 'menu': m('Sidebar', MODS['cas'], 'Tickets'), 'url': '/cas',
             'text': ['Lists complaints for your centre with ticket ID, subject, module, channel, priority, severity, escalation '
                      'level, status and SLA. Use the <b>Active / Completed / All</b> tabs to filter. Click a ticket ID to open it. '
                      'Helpdesk staff can log a complaint received by phone, e-mail or walk-in with <b>+ Lodge complaint</b>.'],
             'shot': ('cas_tickets', 'Complaint list for NRLDC')},
            {'title': 'Assessing and resolving a ticket', 'menu': m('Tickets', 'click a ticket ID'),
             'steps': ['Open the ticket. The progress tracker shows Logged, Assessed, In progress, Resolved and Closed.',
                       'In <b>Assess (helpdesk / RLDC)</b> the AMC sets <b>Priority</b> and tags, and the RLDC / NLDC sets <b>Severity</b> (S1 to S4). Click <b>Save assessment</b>.',
                       'Use the actions panel to comment, request input, transfer to another team or resolve.',
                       'Tickets that breach the SLA are escalated automatically from Level 0 to Level 3; the level badge is shown next to the ID.',
                       'The complainant can give feedback or re-open a resolved ticket. <b>Ticket report (PDF)</b> prints the full history.'],
             'shot': ('cas_detail', 'Ticket detail with progress tracker, complaint details and assessment panel')},
            {'title': 'Dashboards', 'menu': m('Sidebar', MODS['cas'], 'Dashboards (14)'), 'url': '/cas/dashboards',
             'text': ['Fourteen role-based dashboards with totals, pending, resolved, average resolution time and SLA breaches, '
                      'trend, status, module and severity charts. Choose the dashboard from the drop-down at the top right. Each '
                      'chart can be downloaded as PNG or CSV.'],
             'shot': ('cas_dashboards', 'Complaint dashboards')},
            {'title': 'Reports and SLA penalty', 'menu': m('Sidebar', MODS['cas'], 'Reports & SLA penalty'), 'url': '/cas/reports',
             'steps': ['Under <b>Standard reports</b> pick a report and the date range, then <b>Preview</b> or export as PDF, XLSX or CSV.',
                       'Under <b>Quarterly SLA &amp; AMC penalty</b> choose the quarter start month, enter the quarterly AMC value and click <b>Calculate</b>; export as PDF or Excel.'],
             'shot': ('cas_reports', 'Complaint reports and quarterly SLA penalty calculation')},
            {'title': 'FAQ / Knowledge base', 'menu': m('Sidebar', MODS['cas'], 'FAQ / Knowledge base'), 'url': '/cas/kb',
             'text': ['Answers built from resolved tickets. Staff add articles with <b>+ Add FAQ</b>; drafts are published after review.'],
             'shot': ('cas_kb', 'Knowledge base')},
        ]},
        {'title': MODS['reg'], 'sections': [
            {'title': 'Applications', 'menu': m('Sidebar', MODS['reg'], 'Applications'), 'url': '/registration',
             'text': ['All registration cases (NSWS / CONN-4 connectivity, Fees &amp; Charges registration and communication '
                      'registration) with charts by status, RLDC and category. Use the tabs to filter by type and click a case ID to open it.'],
             'shot': ('reg_list', 'Registration applications')},
            {'title': 'Processing a registration case', 'menu': m('Applications', 'click a case ID'),
             'steps': ['Review the applicant data and documents.',
                       'Forward for departmental consents. SO-1, SO-2, Market Operation, SCADA and MIS give their comments in parallel; the consent panel shows each status.',
                       'Return the case to the applicant for corrections if required; the tracker shows the step in red.',
                       'After all consents, approve. The registration letter is generated and the case is locked.'],
             'shot': ('reg_detail', 'Registration case with tracker and departmental consent status')},
            {'title': 'NSWS connectivity (CONN-4)', 'menu': m('Sidebar', MODS['reg'], 'NSWS connectivity (CONN-4)'), 'url': '/registration/nsws',
             'text': ['Connectivity applications fetched from the National Single Window System. CTUIL and the RLDC add joint comments before CONN-4 is issued.'],
             'shot': ('reg_nsws', 'NSWS connectivity applications')},
            {'title': 'NLDC workload shifting', 'menu': m('Sidebar', MODS['reg'], 'NLDC workload shifting'), 'url': '/registration/workload',
             'text': ['NLDC views pending RE applications per RLDC and shifts unstarted applications from a heavily loaded RLDC '
                      'to a lightly loaded one: select the target RLDC, add a comment and click <b>Shift to</b>. Applications return '
                      'automatically after model validation.'],
             'shot': ('reg_workload', 'Workload across RLDCs')},
            {'title': 'Fees & Charges import', 'menu': m('Sidebar', MODS['reg'], 'Fees & Charges import'), 'url': '/registration/fnc-import',
             'steps': ['Click <b>Download template</b> and fill it from the RLDC Fees &amp; Charges software.',
                       'Choose the file. A preview with row errors is shown.',
                       'Commit to create the entities and login IDs (default password, forced change at first login).'],
             'shot': ('reg_fnc', 'Fees and Charges import')},
            {'title': 'User-ID requests', 'menu': m('Sidebar', MODS['reg'], 'User-ID requests'), 'url': '/registration/account-requests',
             'text': ['Pre-registration requests from the public sign-up page. Approve with the right roles (several permissions can be assigned to one login) or reject with a reason.'],
             'shot': ('reg_accounts', 'Pre-registration / user-ID requests')},
        ]},
        {'title': MODS['ftc'], 'sections': [
            {'title': 'FTC cases', 'menu': m('Sidebar', MODS['ftc'], 'FTC cases'), 'url': '/ftc',
             'text': ['First time charging under the IEGC 2023 procedure. Tiles show FTC cases, departmental acceptances, returns and '
                      'average clearance days; charts show cases by stage and rejection causes. The grid lists each case with '
                      'stage, stage status and who it is pending with.'],
             'shot': ('ftc_list', 'FTC case list')},
            {'title': 'Working on an FTC case', 'menu': m('FTC cases', 'click a case ID'), 'url': '/ftc/2',
             'text': ['An FTC case moves through five stages, shown as tabs at the top of the case:'],
             'bullets': ['<b>1. Intimation</b> (A-annexures)', '<b>2. Request and trial-run notice</b> (B-annexures)',
                         '<b>3. Trial-run completion</b> (C-annexures)', '<b>4. Certificate of successful trial run</b>',
                         '<b>5. DOCO letter</b>'],
             'steps': ['Open the stage tab to review the applicant’s annexures in the document list.',
                       'Forward for departmental consent. SCADA, Protection and Metering give general consent in parallel, followed by their HoDs, then the Sub-Head SO, Head of System Operation and Head of RLDC in sequence.',
                       'Each consent and return appears in the status tracking log with date and time.',
                       'After the trial run, the certificate is generated automatically and released once the Head of RLDC signs it digitally.',
                       'When the DOCO letter is uploaded and accepted, the case closes and post-commissioning compliance tracking starts.'],
             'shot': ('ftc_detail', 'FTC case at Stage 5 with consent log and documents')},
            {'title': 'Post-commissioning compliance', 'menu': m('Sidebar', MODS['ftc'], 'Post-commissioning compliance'), 'url': '/ftc/compliance',
             'text': ['Tracks items due after commissioning (as-built model, final SLD, annual power quality report, periodic tests) with due dates, days left and status. Tiles show expired, expiring in 30 days and accepted items.'],
             'shot': ('ftc_compliance', 'Compliance monitoring')},
            {'title': 'Start-up power', 'menu': m('Sidebar', MODS['ftc'], 'Start-up power'), 'url': '/ftc/startup-power',
             'text': ['Applications for drawal of start-up power (2014 procedure): application, departmental consents, RLDC grant (copy to RPC) and weekly / monthly updates.'],
             'shot': ('ftc_startup', 'Start-up power applications')},
            {'title': 'FTC reports', 'menu': m('Sidebar', MODS['ftc'], 'FTC reports'), 'url': '/ftc/reports',
             'text': ['Choose a report (for example first-time charged elements), set the date range and export as XLSX or PDF.'],
             'shot': ('ftc_reports', 'FTC reports')},
        ]},
        {'title': MODS['cc'], 'sections': [
            {'title': 'Certification cases', 'menu': m('Sidebar', MODS['cc'], 'Certification cases'), 'url': '/comm-cert',
             'text': ['OPGW, FOTE, auxiliary power and State CSP certification: CA-annexures lead to the Stage-1 certificate, then CB-annexures to Format III.'],
             'shot': ('cc_list', 'Communication certification cases')},
            {'title': 'Processing a certification case', 'menu': m('Certification cases', 'click a case ID'),
             'steps': ['Review the annexures in the document panel (CB1 to CB4, SAT report, Format II).',
                       'Obtain third-party consent where the route needs it (route A, B or C).',
                       'Forward for SCADA and HoD approval; the tracker shows each step.',
                       'The signed certificate is generated and issued to the applicant.'],
             'shot': ('cc_detail', 'Communication certification case with tracker and documents')},
        ]},
        {'title': MODS['rt'], 'sections': [
            {'title': 'Control room', 'menu': m('Sidebar', MODS['rt'], 'Control room'), 'url': '/realtime',
             'text': ['The 24×7 control-room view. The dark shift bar at the top shows the centre, the current shift and who is '
                      'in charge, with quick buttons for Request code, Issue / due codes, Report tripping and Shift handover. Tiles '
                      'show grid frequency, demand, RE generation, units under outage, trippings, codes issued and pending consents; '
                      'charts show frequency, pending requests and cumulative availability.'],
             'shot': ('rt_control', 'Real-time control room')},
            {'title': 'Shift management', 'menu': m('Sidebar', MODS['rt'], 'Shift management'), 'url': '/realtime/shift',
             'steps': ['The shift in-charge starts the shift (Morning, Evening or Night) and assigns operators.',
                       'At the end of the shift, hand over with remarks; operators of the previous shift are logged out automatically.'],
             'shot': ('rt_shift', 'Shift management')},
            {'title': 'Requesting a code', 'menu': m('Sidebar', MODS['rt'], 'Request code'), 'url': '/realtime/request',
             'steps': ['Choose the request type tab: planned (approved list), forced, emergency, tripping, FTC, anti-theft, AR, suo-moto, HV/LV and others.',
                       'Select the element, the action (opening / shutdown or closing), the planned time and the availability head.',
                       'Add the reason and remarks and click <b>Submit request</b>. It is routed automatically to all stakeholders for consent; no code is issued without consent.'],
             'shot': ('rt_request', 'Code request form')},
            {'title': 'Codebook and due lists', 'menu': m('Sidebar', MODS['rt'], 'Codebook & due lists'), 'url': '/realtime/codes',
             'bullets': ['Tabs: Requested codes, Due for charging, Due for outage, Issued (24 h), Tripped elements.',
                         'For each request the grid shows category, action, element, requester, status, consents, weather and the RLDC action buttons.',
                         'An issued code is valid for one hour and is revoked automatically if not executed. Record execution times from both ends to close it.'],
             'shot': ('rt_codes', 'Codebook')},
            {'title': 'Element list', 'menu': m('Sidebar', MODS['rt'], 'Element list'), 'url': '/realtime/elements',
             'text': ['Voltage-level lists of elements with live status (in service, under outage, tripped), owners and operator notes. Notes are append-only.'],
             'shot': ('rt_elements', 'Element list')},
            {'title': 'RE single window (MVAr)', 'menu': m('Sidebar', MODS['rt'], 'RE single window (MVAr)'), 'url': '/realtime/re-mvar',
             'text': ['Issue MVAr / Vref / PF codes to several RE plants at once: choose the mode, tick the plants, enter the values and click <b>Issue code</b>.'],
             'shot': ('rt_remvar', 'RE single window')},
            {'title': 'Shift report and e-logbook', 'menu': m('Sidebar', MODS['rt'], 'Shift report / E-logbook'), 'url': '/realtime/shift-report',
             'text': ['The shift report is compiled automatically from the shift’s events and moves from Draft to Final when the '
                      'shift in-charge approves it. The e-logbook records grid events, operations messages, curtailment, technical orders and STOA entries.'],
             'shot': ('rt_elog', 'Control-room e-logbook')},
        ]},
        {'title': MODS['oc'], 'sections': [
            {'title': 'Shutdown requests', 'menu': m('Sidebar', MODS['oc'], 'Shutdown requests'), 'url': '/outage',
             'text': ['All shutdown requests with route (OCC M+2, D-3, D-2, emergency, non-auto), element, owner, dates and status. '
                      'Use the tabs to filter by route and <b>Utility-wise sheets</b> for per-utility lists.'],
             'shot': ('oc_list', 'Outage coordination requests')},
            {'title': 'New request', 'menu': m('Sidebar', MODS['oc'], 'New request'), 'url': '/outage/new',
             'steps': ['Select the element, the from and to date-times, daily or continuous, and the request type (maintenance, construction and so on).',
                       'Enter the reason, the availability head and any comments.',
                       'Tick <b>Non-auto mode</b> only for requests that should be excluded from availability.',
                       'Click <b>Submit</b>. The route (OCC, D-3 or D-2) is chosen from ownership and voltage.'],
             'shot': ('oc_new', 'New shutdown request')},
            {'title': 'D-1 approval', 'menu': m('Sidebar', MODS['oc'], 'D-1 approval'), 'url': '/outage/d1',
             'text': ['Final day-ahead decision using the study file and the weather check. Approved shutdowns flow to the control room; the D-1 list can be printed as PDF.'],
             'shot': ('oc_d1', 'D-1 approval')},
        ]},
        {'title': MODS['av'], 'sections': [
            {'title': 'Monthly outage review sheet', 'menu': m('Sidebar', MODS['av'], 'Monthly review sheet'), 'url': '/availability',
             'text': ['Generated on the 1st of each month. Licensees accept or object by the 5th, after which the sheet is published. Choose the month at the top right and export with <b>Excel</b>.'],
             'shot': ('av_sheet', 'Monthly availability review sheet')},
            {'title': 'Coordinator verification', 'menu': m('Sidebar', MODS['av'], 'Coordinator verification'), 'url': '/availability/verify',
             'steps': ['Select the outage rows.',
                       'Send to protection for review where needed, then mark <b>Verify</b> or <b>Not verify</b>.',
                       'Forward to the RPC. Outages are bifurcated between heads where required.'],
             'shot': ('av_verify', 'Availability coordinator verification')},
        ]},
        {'title': MODS['pr'], 'sections': [
            {'title': 'Tripping events', 'menu': m('Sidebar', MODS['pr'], 'Tripping events'), 'url': '/protection',
             'text': ['Events created from OMS outage records. Tiles show events and pending files. Click <b>+ Create event from trippings</b> to group trippings into a GD / GI event.'],
             'shot': ('pr_events', 'Protection tripping events')},
            {'title': 'Event details and reports', 'menu': m('Tripping events', 'click an event'),
             'bullets': ['Due dates are shown for the flash report (8 h), DR/EL (24 h) and the detailed report (7 days).',
                         'Each end (End-1 / End-2) fills the FIR and uploads DR, EL and TR files.',
                         '<b>Download all files (zip)</b> collects every file for analysis.'],
             'shot': ('pr_detail', 'Tripping event with due dates and FIR form')},
            {'title': 'PSC tracker and SOPR indices', 'menu': m('Sidebar', MODS['pr'], 'PSC tracker / SOPR indices'), 'url': '/protection/psc',
             'text': ['The PSC tracker records Protection Sub-Committee recommendations, the utility’s action and compliance status. SOPR shows the monthly D, S and R indices by utility.'],
             'shot': ('pr_psc', 'Protection Sub-Committee tracker')},
        ]},
        {'title': f"{MODS['al']} and {MODS['sps']}", 'sections': [
            {'title': 'Sending an alert', 'menu': m('Sidebar', MODS['al'], 'Send alert'), 'url': '/alerts',
             'steps': ['Pick a violation template on the left (frequency deviation, voltage, loading, SCADA telemetry and others).',
                       'Fill the values; the message text updates automatically.',
                       'Tick the recipient states / utilities, click <b>Preview</b>, then <b>Send SMS + e-mail</b>.'],
             'shot': ('al_send', 'Message alert templates')},
            {'title': 'Contact directory and history', 'menu': m('Sidebar', MODS['al'], 'Contact directory / Message history'), 'url': '/alerts/contacts',
             'text': ['The contact directory holds recipients per organisation, with SMS and e-mail flags for alert, emergency and extreme messages. Message history shows what was sent to each constituent.'],
             'shot': ('al_contacts', 'Alert contact directory')},
            {'title': 'SPS healthiness', 'menu': m('Sidebar', MODS['sps'], 'SPS healthiness'), 'url': '/sps',
             'text': ['Live ON / OFF / Degraded status of each System Protection Scheme with its timeline. Users and SCADA update the status; export with <b>Excel</b>.'],
             'shot': ('sps_status', 'SPS healthiness')},
        ]},
        {'title': MODS['mis'], 'sections': [
            {'title': 'Report builder', 'menu': m('Sidebar', MODS['mis'], 'Report builder'), 'url': '/mis',
             'steps': ['<b>Run a report</b>: choose a template and dates, then Preview or export as PDF, XLSX or CSV (bilingual, Hindi before English). Reports can also be e-mailed on a schedule.',
                       '<b>Ad-hoc report</b>: choose a data source, group-by fields, a measure and a function, then <b>Run</b>. Click <b>Save as template</b> to reuse it.'],
             'shot': ('mis_builder', 'MIS report builder')},
            {'title': 'Graph explorer', 'menu': m('Sidebar', MODS['mis'], 'Graph explorer (300)'), 'url': '/mis/graphs',
             'text': ['Three hundred interactive graphs, thirty per module. Choose the module tab and the graph group; each graph refreshes automatically and can be downloaded as PNG or CSV.'],
             'shot': ('mis_graphs', 'Graph explorer')},
            {'title': 'Generation outage and ENS', 'menu': m('Sidebar', MODS['mis'], 'Generation outage & ENS'), 'url': '/mis/generation-outage',
             'text': ['Outage duration and energy not served by unit, plant, owner, fuel or location, plus the NPMC daily Excel.'],
             'shot': ('mis_genout', 'Generation outage and ENS')},
            {'title': 'Power BI / Tableau views', 'menu': m('Sidebar', MODS['mis'], 'Power BI / Tableau views'), 'url': '/mis/bi',
             'text': ['Read-only SQL views for Grid-India’s BI tools, with a live preview of each view and a link to the GraphQL explorer.'],
             'shot': ('mis_bi', 'BI data views')},
        ]},
    ],
}

# ---------------------------------------------------------------------------------------------
EXTERNAL = {
    'file': 'OMS_User_Manual_03_External_Stakeholders.pdf',
    'title': 'External Stakeholders',
    'audience': 'Utilities, generators, RE developers, transmission licensees, CTUIL, RPCs and service providers',
    'chapters': [
        {'title': 'Before you start', 'sections': [
            {'title': 'Getting access', 'bullets': [
                'Request an account from the public portal (<b>New stakeholder? Request an account</b>) or ask your RLDC; see Manual 01.',
                'Sign in with the <b>External Login</b> tab, the CAPTCHA and the OTP.',
                'Your home page shows only the modules granted to your organisation; others are locked.'],
             'shot': ('ext_home', 'Home page for an external user')},
        ]},
        {'title': 'Complaints and help', 'sections': [
            {'title': 'Lodging a complaint', 'menu': m('Sidebar', MODS['cas'], 'Lodge complaint'), 'url': '/cas/new',
             'steps': ['Your name, e-mail and mobile are filled from your login.',
                       'Select the module (only your authorised modules can be chosen) and the complaint type.',
                       'Choose the priority you request and the centre to escalate to.',
                       'Link an earlier complaint if this is related, enter the subject and details, attach a screenshot if helpful.',
                       'Click <b>Submit complaint</b>. You get a ticket number by e-mail / SMS.'],
             'shot': ('ext_cas_new', 'Lodge a complaint')},
            {'title': 'Tracking your complaints', 'menu': m('Sidebar', MODS['cas'], 'Tickets'), 'url': '/cas',
             'text': ['Lists your tickets with status, level and SLA. Open a ticket to follow the progress tracker, add comments or '
                      'files, and give feedback or re-open it after resolution.'],
             'shot': ('ext_cas_detail', 'Your ticket with progress tracker and actions')},
            {'title': 'FAQ', 'menu': m('Sidebar', MODS['cas'], 'FAQ / Knowledge base'),
             'text': ['Check the FAQ before lodging a complaint; many common questions are answered there.']},
        ]},
        {'title': MODS['reg'], 'sections': [
            {'title': 'New registration', 'menu': m('Sidebar', MODS['reg'], 'New registration'), 'url': '/registration/new',
             'steps': ['Choose the category and sub-category (for example RE generating station, Solar).',
                       'Enter the station name, installed capacity, pooling substation, state and connectivity registration number.',
                       'Tick <b>Modified element</b> if this is a change to an existing element (fewer consents needed).',
                       'Click <b>Save draft &amp; continue to documents</b>, then upload each document in the checklist and submit.'],
             'shot': ('ext_reg_new', 'New registration form')},
            {'title': 'Your applications', 'menu': m('Sidebar', MODS['reg'], 'Applications'), 'url': '/registration',
             'text': ['Shows your applications and their status. If an application is returned, open it, correct the data or documents and resubmit. The registration letter can be downloaded once approved.'],
             'shot': ('ext_reg_list', 'Registration applications')},
        ]},
        {'title': MODS['ftc'], 'sections': [
            {'title': 'Starting an FTC application', 'menu': m('Sidebar', MODS['ftc'], 'New FTC application'), 'url': '/ftc/new',
             'steps': ['Choose the category (RE plant, transmission element, thermal unit and so on).',
                       'Enter the proposed charging date. A-annexures must be submitted at least 10 days before this date.',
                       'Give a short title and click <b>Create FTC case</b>. A unique FTC case ID is generated.',
                       'Fill the A-annexures online and upload the supporting documents.'],
             'shot': ('ext_ftc_new', 'New FTC application')},
            {'title': 'Following your FTC cases', 'menu': m('Sidebar', MODS['ftc'], 'FTC cases'), 'url': '/ftc',
             'bullets': ['Each case moves through five stages: Intimation (A), Request and trial-run notice (B), Trial-run completion (C), Certificate and DOCO.',
                         'Upload the B and C annexures when each stage opens. Format TR must be given at least 7 working days before the trial run.',
                         'When a department returns the case, the reason is shown in the tracker; correct and resubmit.',
                         'Download the trial-run certificate once signed, then upload the DOCO letter.',
                         'After DOCO, follow the items under <b>Post-commissioning compliance</b>.'],
             'shot': ('ext_ftc_list', 'Your FTC cases')},
        ]},
        {'title': MODS['cc'], 'sections': [
            {'title': 'Applying for communication certification', 'menu': m('Sidebar', MODS['cc'], 'New application'), 'url': '/comm-cert/new',
             'steps': ['Select the communication element (OPGW, FOTE and so on) and the scope (inter-state / intra-regional).',
                       'Enter the anticipated SAT / integration date (not less than 7 days ahead).',
                       'Click <b>Create</b> and upload the CA-annexures, then the CB-annexures after the Stage-1 certificate.'],
             'shot': ('ext_cc_new', 'Intimation of anticipated commissioning')},
        ]},
        {'title': 'Real-time operation and outages', 'sections': [
            {'title': 'Requesting a real-time code', 'menu': m('Sidebar', MODS['rt'], 'Request code'), 'url': '/realtime/request',
             'steps': ['Choose the request type tab (planned, forced, emergency, report tripping and so on).',
                       'Select the element and the action, the planned time and the availability head.',
                       'Click <b>Submit request</b>. The RLDC issues the code after all consents; you are notified and see it in the codebook.',
                       'Report the execution time from your end once the operation is done.'],
             'shot': ('ext_rt_request', 'Code request')},
            {'title': 'Planned shutdown requests', 'menu': m('Sidebar', MODS['oc'], 'Shutdown requests / New request'), 'url': '/outage',
             'text': ['Submit shutdown requests for the OCC (M+2), D-3 or D-2 windows using <b>+ New request</b>. The list shows the route, status and approvals of each of your requests.'],
             'shot': ('ext_oc_list', 'Your shutdown requests')},
            {'title': 'Monthly availability review', 'menu': m('Sidebar', MODS['av'], 'Monthly review sheet'), 'url': '/availability',
             'text': ['Each month review the outages of your elements. Accept them or raise an objection with remarks before the 5th; after that the sheet is published.'],
             'shot': ('ext_av', 'Monthly review sheet for a transmission licensee')},
            {'title': 'Protection reports and SPS status', 'menu': m('Sidebar', MODS['pr'], 'Tripping events'), 'url': '/protection',
             'bullets': ['For each tripping of your element, fill the FIR and upload DR, EL and TR files within the due times (8 h, 24 h, 7 days).',
                         'Update the action taken on PSC recommendations in the PSC tracker.',
                         'Under <b>SPS Status</b> update the healthiness of the schemes you own.'],
             'shot': ('ext_sps', 'SPS healthiness')},
        ]},
    ],
}

# ---------------------------------------------------------------------------------------------
ADMIN = {
    'file': 'OMS_User_Manual_04_Administrators.pdf',
    'title': 'Administrators',
    'audience': 'Super administrators and module administrators',
    'chapters': [
        {'title': 'Administration menu', 'sections': [
            {'title': 'Where to find it', 'menu': 'Sidebar › Administration', 'url': '/',
             'text': ['Users with the Super Admin role see an <b>Administration</b> section at the bottom of the sidebar with Users, '
                      'All sessions, Settings &amp; notifications, Audit trail, Master registry and Portal content. The centre '
                      'switcher includes <b>All centres</b>.'],
             'shot': ('adm_home', 'Home page for the super administrator')},
        ]},
        {'title': 'Users and sessions', 'sections': [
            {'title': 'User management', 'menu': m('Sidebar', 'Administration', 'Users'), 'url': '/admin/users',
             'steps': ['Click <b>+ New user</b> to create a login: name, category (Grid-India / External), centre, contact details and roles.',
                       'Click <b>Edit</b> on a row to change roles, deactivate a user, toggle two-factor authentication or allow multiple sessions.',
                       'Several roles can be assigned to one login; module access follows the roles.'],
             'shot': ('adm_users', 'User management')},
            {'title': 'All active sessions', 'menu': m('Sidebar', 'Administration', 'All sessions'), 'url': '/admin/sessions',
             'text': ['Lists every signed-in session with IP address, login time and last activity. Click <b>Force logout</b> to end a session immediately.'],
             'shot': ('adm_sessions', 'Active sessions')},
        ]},
        {'title': 'Settings and audit', 'sections': [
            {'title': 'Runtime settings', 'menu': m('Sidebar', 'Administration', 'Settings & notifications'), 'url': '/admin/settings',
             'bullets': ['System parameters: refresh interval, idle logout, code validity, escalation timers, D-3 windows, FTC minimum days, trial-run notice days, protection report deadlines and more. Click <b>Save</b>.',
                         'E-mail / SMS per workflow step: enable or disable notifications for each step of each module.'],
             'shot': ('adm_settings', 'Runtime settings')},
            {'title': 'Audit trail', 'menu': m('Sidebar', 'Administration', 'Audit trail'), 'url': '/admin/audit',
             'text': ['Immutable log of every create, update, approval and login event with time, user, module, action, entity and details. Filter by module and export for audits.'],
             'shot': ('adm_audit', 'Audit trail')},
        ]},
        {'title': 'Master data and portal content', 'sections': [
            {'title': 'Master registry', 'menu': m('Sidebar', 'Administration', 'Master registry'), 'url': '/admin/master',
             'steps': ['Use the tabs for Grid elements, Entities, Substations and Ownership changes.',
                       'To add an element, enter the name, type, centre, voltage and from / to substations and click <b>Add</b>. A Unique Element ID is generated automatically.',
                       'Ownership changes are recorded with history; notes on elements are append-only.'],
             'shot': ('adm_master', 'Master registry')},
            {'title': 'Portal content management', 'menu': m('Sidebar', 'Administration', 'Portal content'), 'url': '/admin/portal',
             'steps': ['On the <b>Content</b> tab choose the type (notice, flasher, post, FAQ, gallery), enter English and Hindi titles and body, attach a file if needed and click <b>Create draft</b>.',
                       'A second user verifies and publishes the draft; published items can be unpublished.',
                       'Use the <b>Menus</b> tab to manage portal menus and <b>Feedback</b> to read visitor feedback.'],
             'shot': ('adm_portal', 'Portal content management')},
        ]},
    ],
}

MANUALS = [GETTING_STARTED, INTERNAL, EXTERNAL, ADMIN]
