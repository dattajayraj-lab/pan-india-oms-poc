import type { ModuleKey } from './store/auth'

export interface NavItem { path: string; en: string; hi: string; internalOnly?: boolean; level?: 1 | 2 | 3 | 4 }
export interface NavModule { key: ModuleKey; icon: string; base: string; items: NavItem[] }

// Sidebar sub-menus per module (TS Cl. 2.5 responsive sidebar; icons with text, Fig.4).
export const NAV: NavModule[] = [
  { key: 'cas', icon: '🎫', base: '/cas', items: [
    { path: '/cas', en: 'Tickets', hi: 'टिकट' },
    { path: '/cas/new', en: 'Lodge complaint', hi: 'शिकायत दर्ज करें' },
    { path: '/cas/dashboards', en: 'Dashboards (14)', hi: 'डैशबोर्ड (14)', internalOnly: true },
    { path: '/cas/reports', en: 'Reports & SLA penalty', hi: 'रिपोर्ट एवं एसएलए दंड', internalOnly: true },
    { path: '/cas/kb', en: 'FAQ / Knowledge base', hi: 'सामान्य प्रश्न' },
  ] },
  { key: 'registration', icon: '🪪', base: '/registration', items: [
    { path: '/registration', en: 'Applications', hi: 'आवेदन' },
    { path: '/registration/new', en: 'New registration', hi: 'नया पंजीकरण' },
    { path: '/registration/nsws', en: 'NSWS connectivity (CONN-4)', hi: 'एनएसडब्ल्यूएस कनेक्टिविटी' },
    { path: '/registration/workload', en: 'NLDC workload shifting', hi: 'एनएलडीसी कार्यभार स्थानांतरण', internalOnly: true },
    { path: '/registration/fnc-import', en: 'Fees & Charges import', hi: 'शुल्क एवं प्रभार आयात', internalOnly: true },
    { path: '/registration/account-requests', en: 'User-ID requests', hi: 'उपयोगकर्ता-आईडी अनुरोध', internalOnly: true },
  ] },
  { key: 'ftc', icon: '⚡', base: '/ftc', items: [
    { path: '/ftc', en: 'FTC cases', hi: 'एफटीसी मामले' },
    { path: '/ftc/new', en: 'New FTC application', hi: 'नया एफटीसी आवेदन' },
    { path: '/ftc/compliance', en: 'Post-commissioning compliance', hi: 'पश्चात-कमीशनिंग अनुपालन' },
    { path: '/ftc/startup-power', en: 'Start-up power', hi: 'स्टार्ट-अप पावर' },
    { path: '/ftc/reports', en: 'FTC reports', hi: 'एफटीसी रिपोर्ट' },
  ] },
  { key: 'comm_cert', icon: '📡', base: '/comm-cert', items: [
    { path: '/comm-cert', en: 'Certification cases', hi: 'प्रमाणन मामले' },
    { path: '/comm-cert/new', en: 'New application', hi: 'नया आवेदन' },
  ] },
  { key: 'realtime', icon: '🕹️', base: '/realtime', items: [
    { path: '/realtime', en: 'Control room', hi: 'नियंत्रण कक्ष' },
    { path: '/realtime/shift', en: 'Shift management', hi: 'शिफ्ट प्रबंधन', internalOnly: true },
    { path: '/realtime/request', en: 'Request code', hi: 'कोड अनुरोध' },
    { path: '/realtime/codes', en: 'Codebook & due lists', hi: 'कोडबुक' },
    { path: '/realtime/elements', en: 'Element list', hi: 'तत्व सूची' },
    { path: '/realtime/re-mvar', en: 'RE single window (MVAr)', hi: 'आरई एकल विंडो', internalOnly: true },
    { path: '/realtime/shift-report', en: 'Shift report', hi: 'शिफ्ट रिपोर्ट', internalOnly: true },
    { path: '/realtime/elog', en: 'E-logbook', hi: 'ई-लॉगबुक', internalOnly: true },
  ] },
  { key: 'outage_coord', icon: '🗓️', base: '/outage', items: [
    { path: '/outage', en: 'Shutdown requests', hi: 'शटडाउन अनुरोध' },
    { path: '/outage/new', en: 'New request', hi: 'नया अनुरोध' },
    { path: '/outage/d1', en: 'D-1 approval', hi: 'डी-1 अनुमोदन', internalOnly: true },
  ] },
  { key: 'availability', icon: '📊', base: '/availability', items: [
    { path: '/availability', en: 'Monthly review sheet', hi: 'मासिक समीक्षा शीट' },
    { path: '/availability/verify', en: 'Coordinator verification', hi: 'समन्वयक सत्यापन', internalOnly: true },
  ] },
  { key: 'protection', icon: '🛡️', base: '/protection', items: [
    { path: '/protection', en: 'Tripping events', hi: 'ट्रिपिंग घटनाएं' },
    { path: '/protection/psc', en: 'PSC tracker', hi: 'पीएससी ट्रैकर' },
    { path: '/protection/sopr', en: 'SOPR indices', hi: 'एसओपीआर सूचकांक' },
  ] },
  { key: 'alerts', icon: '📣', base: '/alerts', items: [
    { path: '/alerts', en: 'Send alert', hi: 'अलर्ट भेजें' },
    { path: '/alerts/contacts', en: 'Contact directory', hi: 'संपर्क निर्देशिका' },
    { path: '/alerts/history', en: 'Message history', hi: 'संदेश इतिहास' },
  ] },
  { key: 'sps', icon: '🔀', base: '/sps', items: [{ path: '/sps', en: 'SPS healthiness', hi: 'एसपीएस स्थिति' }] },
  { key: 'mis', icon: '📈', base: '/mis', items: [
    { path: '/mis', en: 'Report builder', hi: 'रिपोर्ट निर्माता' },
    { path: '/mis/graphs', en: 'Graph explorer (300)', hi: 'ग्राफ एक्सप्लोरर' },
    { path: '/mis/generation-outage', en: 'Generation outage & ENS', hi: 'उत्पादन आउटेज एवं ईएनएस' },
    { path: '/mis/bi', en: 'Power BI / Tableau views', hi: 'पावर बीआई / टेब्लो' },
  ] },
]

export const ADMIN_NAV: NavItem[] = [
  { path: '/admin/users', en: 'Users', hi: 'उपयोगकर्ता' },
  { path: '/admin/sessions', en: 'All sessions', hi: 'सभी सत्र' },
  { path: '/admin/settings', en: 'Settings & notifications', hi: 'सेटिंग्स' },
  { path: '/admin/audit', en: 'Audit trail', hi: 'ऑडिट ट्रेल' },
  { path: '/admin/master', en: 'Master registry', hi: 'मास्टर रजिस्ट्री' },
  { path: '/admin/portal', en: 'Portal content', hi: 'पोर्टल सामग्री' },
]
