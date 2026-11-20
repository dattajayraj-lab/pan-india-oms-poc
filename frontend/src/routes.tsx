// Route registry grows milestone by milestone. Module pages are lazy-loaded for fast initial load (TS Cl. 2.10).
import { lazy, type ReactNode } from 'react'
import type { ModuleKey } from './store/auth'

export interface ModuleRoute { path: string; module: ModuleKey; element: ReactNode }
export interface PlainRoute { path: string; element: ReactNode }

const L = <T extends Record<string, any>>(loader: () => Promise<T>, name: keyof T) =>
  lazy(() => loader().then((m) => ({ default: m[name] as any })))

// Milestone 2: portal + CAS
const LandingPage = L(() => import('./pages/public/LandingPage'), 'default')
const PostPage = L(() => import('./pages/public/LandingPage'), 'PostPage')
const PortalAdminPage = L(() => import('./pages/admin/PortalAdminPage'), 'default')
const TicketsPage = L(() => import('./pages/ticketing/CasPages'), 'TicketsPage')
const NewTicketPage = L(() => import('./pages/ticketing/CasPages'), 'NewTicketPage')
const TicketDetailPage = L(() => import('./pages/ticketing/CasPages'), 'TicketDetailPage')
const CasDashboardsPage = L(() => import('./pages/ticketing/CasPages'), 'CasDashboardsPage')
const CasReportsPage = L(() => import('./pages/ticketing/CasPages'), 'CasReportsPage')
const KbPage = L(() => import('./pages/ticketing/CasPages'), 'KbPage')

// Milestone 3: master registry, registration, FTC, comm cert
const MasterPage = L(() => import('./pages/master/MasterPage'), 'default')
const RegistrationListPage = L(() => import('./pages/registration/RegistrationPages'), 'RegistrationListPage')
const NewRegistrationPage = L(() => import('./pages/registration/RegistrationPages'), 'NewRegistrationPage')
const RegistrationDetailPage = L(() => import('./pages/registration/RegistrationPages'), 'RegistrationDetailPage')
const NswsPage = L(() => import('./pages/registration/RegistrationPages'), 'NswsPage')
const WorkloadPage = L(() => import('./pages/registration/RegistrationPages'), 'WorkloadPage')
const FncImportPage = L(() => import('./pages/registration/RegistrationPages'), 'FncImportPage')
const AccountRequestsPage = L(() => import('./pages/registration/RegistrationPages'), 'AccountRequestsPage')
const SignupPage = L(() => import('./pages/registration/RegistrationPages'), 'SignupPage')
const FtcListPage = L(() => import('./pages/ftc/FtcPages'), 'FtcListPage')
const NewFtcPage = L(() => import('./pages/ftc/FtcPages'), 'NewFtcPage')
const FtcDetailPage = L(() => import('./pages/ftc/FtcPages'), 'FtcDetailPage')
const FtcCompliancePage = L(() => import('./pages/ftc/FtcPages'), 'FtcCompliancePage')
const StartupPowerPage = L(() => import('./pages/ftc/FtcPages'), 'StartupPowerPage')
const FtcReportsPage = L(() => import('./pages/ftc/FtcPages'), 'FtcReportsPage')
const CommListPage = L(() => import('./pages/comm_cert/CommCertPages'), 'CommListPage')
const CommNewPage = L(() => import('./pages/comm_cert/CommCertPages'), 'CommNewPage')
const CommDetailPage = L(() => import('./pages/comm_cert/CommCertPages'), 'CommDetailPage')

// Milestone 4: real-time, outage, availability, protection, alerts, SPS
const ControlRoomPage = L(() => import('./pages/realtime_outage/RealtimePages'), 'ControlRoomPage')
const ShiftPage = L(() => import('./pages/realtime_outage/RealtimePages'), 'ShiftPage')
const RequestCodePage = L(() => import('./pages/realtime_outage/RealtimePages'), 'RequestCodePage')
const CodebookPage = L(() => import('./pages/realtime_outage/RealtimePages'), 'CodebookPage')
const ElementListPage = L(() => import('./pages/realtime_outage/RealtimePages'), 'ElementListPage')
const ReMvarPage = L(() => import('./pages/realtime_outage/RealtimePages'), 'ReMvarPage')
const ShiftReportPage = L(() => import('./pages/realtime_outage/RealtimePages'), 'ShiftReportPage')
const ElogPage = L(() => import('./pages/realtime_outage/RealtimePages'), 'ElogPage')
const OutagePlansPage = L(() => import('./pages/outage_coord/OperationsPages'), 'OutagePlansPage')
const NewOutagePage = L(() => import('./pages/outage_coord/OperationsPages'), 'NewOutagePage')
const D1Page = L(() => import('./pages/outage_coord/OperationsPages'), 'D1Page')
const AvailabilitySheetPage = L(() => import('./pages/outage_coord/OperationsPages'), 'AvailabilitySheetPage')
const AvailabilityVerifyPage = L(() => import('./pages/outage_coord/OperationsPages'), 'AvailabilityVerifyPage')
const ProtectionEventsPage = L(() => import('./pages/outage_coord/OperationsPages'), 'ProtectionEventsPage')
const ProtectionEventPage = L(() => import('./pages/outage_coord/OperationsPages'), 'ProtectionEventPage')
const PscPage = L(() => import('./pages/outage_coord/OperationsPages'), 'PscPage')
const SoprPage = L(() => import('./pages/outage_coord/OperationsPages'), 'SoprPage')
const AlertsPage = L(() => import('./pages/outage_coord/OperationsPages'), 'AlertsPage')
const ContactsPage = L(() => import('./pages/outage_coord/OperationsPages'), 'ContactsPage')
const AlertHistoryPage = L(() => import('./pages/outage_coord/OperationsPages'), 'AlertHistoryPage')
const SpsPage = L(() => import('./pages/outage_coord/OperationsPages'), 'SpsPage')

// Milestone 5: MIS
const ReportBuilderPage = L(() => import('./pages/mis/MisPages'), 'ReportBuilderPage')
const GraphExplorerPage = L(() => import('./pages/mis/MisPages'), 'GraphExplorerPage')
const GenerationOutagePage = L(() => import('./pages/mis/MisPages'), 'GenerationOutagePage')
const BiViewsPage = L(() => import('./pages/mis/MisPages'), 'BiViewsPage')

export const PUBLIC_ROUTES: PlainRoute[] = [
  { path: '/welcome', element: <LandingPage /> },
  { path: '/welcome/:section', element: <LandingPage /> },
  { path: '/p/:acronym', element: <PostPage /> },
  { path: '/signup', element: <SignupPage /> },
]

export const ADMIN_ROUTES: PlainRoute[] = [
  { path: '/admin/portal', element: <PortalAdminPage /> },
  { path: '/admin/master', element: <MasterPage /> },
]

export const MODULE_ROUTES: ModuleRoute[] = [
  { path: '/cas', module: 'cas', element: <TicketsPage /> },
  { path: '/cas/new', module: 'cas', element: <NewTicketPage /> },
  { path: '/cas/dashboards', module: 'cas', element: <CasDashboardsPage /> },
  { path: '/cas/reports', module: 'cas', element: <CasReportsPage /> },
  { path: '/cas/kb', module: 'cas', element: <KbPage /> },
  { path: '/cas/:id', module: 'cas', element: <TicketDetailPage /> },
  { path: '/registration', module: 'registration', element: <RegistrationListPage /> },
  { path: '/registration/new', module: 'registration', element: <NewRegistrationPage /> },
  { path: '/registration/nsws', module: 'registration', element: <NswsPage /> },
  { path: '/registration/workload', module: 'registration', element: <WorkloadPage /> },
  { path: '/registration/fnc-import', module: 'registration', element: <FncImportPage /> },
  { path: '/registration/account-requests', module: 'registration', element: <AccountRequestsPage /> },
  { path: '/registration/:id', module: 'registration', element: <RegistrationDetailPage /> },
  { path: '/ftc', module: 'ftc', element: <FtcListPage /> },
  { path: '/ftc/new', module: 'ftc', element: <NewFtcPage /> },
  { path: '/ftc/compliance', module: 'ftc', element: <FtcCompliancePage /> },
  { path: '/ftc/startup-power', module: 'ftc', element: <StartupPowerPage /> },
  { path: '/ftc/reports', module: 'ftc', element: <FtcReportsPage /> },
  { path: '/ftc/:id', module: 'ftc', element: <FtcDetailPage /> },
  { path: '/comm-cert', module: 'comm_cert', element: <CommListPage /> },
  { path: '/comm-cert/new', module: 'comm_cert', element: <CommNewPage /> },
  { path: '/comm-cert/:id', module: 'comm_cert', element: <CommDetailPage /> },
  { path: '/realtime', module: 'realtime', element: <ControlRoomPage /> },
  { path: '/realtime/shift', module: 'realtime', element: <ShiftPage /> },
  { path: '/realtime/request', module: 'realtime', element: <RequestCodePage /> },
  { path: '/realtime/codes', module: 'realtime', element: <CodebookPage /> },
  { path: '/realtime/elements', module: 'realtime', element: <ElementListPage /> },
  { path: '/realtime/re-mvar', module: 'realtime', element: <ReMvarPage /> },
  { path: '/realtime/shift-report', module: 'realtime', element: <ShiftReportPage /> },
  { path: '/realtime/elog', module: 'realtime', element: <ElogPage /> },
  { path: '/outage', module: 'outage_coord', element: <OutagePlansPage /> },
  { path: '/outage/new', module: 'outage_coord', element: <NewOutagePage /> },
  { path: '/outage/d1', module: 'outage_coord', element: <D1Page /> },
  { path: '/availability', module: 'availability', element: <AvailabilitySheetPage /> },
  { path: '/availability/verify', module: 'availability', element: <AvailabilityVerifyPage /> },
  { path: '/protection', module: 'protection', element: <ProtectionEventsPage /> },
  { path: '/protection/psc', module: 'protection', element: <PscPage /> },
  { path: '/protection/sopr', module: 'protection', element: <SoprPage /> },
  { path: '/protection/:id', module: 'protection', element: <ProtectionEventPage /> },
  { path: '/alerts', module: 'alerts', element: <AlertsPage /> },
  { path: '/alerts/contacts', module: 'alerts', element: <ContactsPage /> },
  { path: '/alerts/history', module: 'alerts', element: <AlertHistoryPage /> },
  { path: '/sps', module: 'sps', element: <SpsPage /> },
  { path: '/mis', module: 'mis', element: <ReportBuilderPage /> },
  { path: '/mis/graphs', module: 'mis', element: <GraphExplorerPage /> },
  { path: '/mis/generation-outage', module: 'mis', element: <GenerationOutagePage /> },
  { path: '/mis/bi', module: 'mis', element: <BiViewsPage /> },
]
