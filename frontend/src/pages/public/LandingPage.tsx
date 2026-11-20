// Public portal: pop-up banner, moving flashers (click to download), notice board, real-time data tiles,
// gallery, FAQ, posts by acronym, feedback form, external-link redirection warning
// (TS Cl. 11.2(a)-(j); FRD CMS-01..14).
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api, errMsg } from '../../api/client'
import { bi, setLanguage } from '../../i18n'
import { useAuth } from '../../store/auth'
import { fmtDT } from '../../store/hooks'
import { Alert, Button, Field, Modal, cls, inputCls } from '../../components/common/ui'

interface Portal { notice?: any[]; flasher?: any[]; banner?: any[]; faq?: any[]; post?: any[]; gallery?: any[]; menu: any[]; tiles: any[] }

export function ExternalLink({ href, children, className }: { href: string; children: React.ReactNode; className?: string }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <a href={href} className={className} onClick={(e) => { e.preventDefault(); setOpen(true) }}>{children}</a>
      <Modal open={open} onClose={() => setOpen(false)} title="Leaving Grid-India OMS">
        <p className="text-sm">You are being redirected to an external website:</p>
        <p className="my-2 break-all rounded bg-slate-100 p-2 font-mono text-xs">{href}</p>
        <p className="text-xs text-slate-500">आप एक बाहरी वेबसाइट पर जा रहे हैं। Grid-India is not responsible for external content.</p>
        <div className="mt-3 flex gap-2">
          <Button onClick={() => { window.open(href, '_blank', 'noopener'); setOpen(false) }}>Continue</Button>
          <Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
        </div>
      </Modal>
    </>
  )
}

function PublicHeader({ menu }: { menu: any[] }) {
  const { t, i18n } = useTranslation()
  const { user } = useAuth()
  return (
    <header className="bg-grid-800 text-white">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-3 px-4 py-3">
        <Link to="/welcome" className="flex items-center gap-2">
          <img src="/favicon.svg" className="h-10 w-10" alt="Grid-India" />
          <div><div className="font-bold leading-tight">{t('app.title')}</div><div className="text-[11px] text-grid-100">Grid Controller of India Limited · ग्रिड कंट्रोलर ऑफ इंडिया लिमिटेड</div></div>
        </Link>
        <nav className="ml-auto flex flex-wrap items-center gap-1 text-sm" aria-label="Main">
          {menu.filter((m) => m.location === 'NAVBAR').map((m) => m.target_type === 'EXTERNAL'
            ? <ExternalLink key={m.id} href={m.target} className="rounded px-2 py-1 hover:bg-grid-700">{bi(m, 'label')}</ExternalLink>
            : <Link key={m.id} to={m.target_type === 'POST' ? `/p/${m.target}` : m.target === '/' ? '/welcome' : `/welcome${m.target}`} className="rounded px-2 py-1 hover:bg-grid-700">{bi(m, 'label')}</Link>)}
          <button className="rounded border border-white/40 px-2 py-1 text-xs" onClick={() => setLanguage(i18n.language === 'hi' ? 'en' : 'hi')}>{i18n.language === 'hi' ? 'English' : 'हिन्दी'}</button>
          {user ? <Link to="/" className="rounded bg-saffron-500 px-3 py-1 font-semibold">{t('common.home')}</Link> : (
            <>
              <Link to="/login?type=external" className="rounded bg-white px-3 py-1 font-semibold text-grid-800">{t('auth.externalLogin')}</Link>
              <Link to="/login" className="rounded bg-saffron-500 px-3 py-1 font-semibold">{t('auth.gridIndiaLogin')}</Link>
            </>
          )}
        </nav>
      </div>
    </header>
  )
}

function usePortal() {
  const [data, setData] = useState<Portal | null>(null)
  const [at, setAt] = useState<Date | null>(null)
  useEffect(() => {
    const load = () => api.get('/portal/public').then((r) => { setData(r.data); setAt(new Date()) })
    load()
    const id = setInterval(() => !document.hidden && load(), 2000)
    return () => clearInterval(id)
  }, [])
  return { data, at }
}

export default function LandingPage() {
  const { t, i18n } = useTranslation()
  const { data, at } = usePortal()
  const { section } = useParams()
  const [banner, setBanner] = useState(true)
  if (!data) return <div className="p-10 text-center">Loading…</div>
  const flashers = data.flasher ?? []
  return (
    <div className="min-h-screen bg-slate-50">
      <PublicHeader menu={data.menu} />
      {flashers.length > 0 && (
        <div className="overflow-hidden whitespace-nowrap bg-saffron-500/10 py-1.5 text-sm" aria-label="Flash news">
          <div className="inline-block animate-marquee">
            {flashers.map((f) => (
              <a key={f.id} className="mx-8 font-medium text-grid-800 underline-offset-2 hover:underline"
                href={f.attachment_doc_id ? `/api/v1/portal/public/file/${f.attachment_doc_id}` : '#'}>🔔 {bi(f, 'title')}</a>
            ))}
          </div>
        </div>
      )}
      {!section && (
        <section className="relative overflow-hidden bg-gradient-to-br from-grid-800 via-grid-900 to-grid-950 pb-24 pt-12 text-white">
          <svg className="absolute inset-0 h-full w-full opacity-[0.06]" aria-hidden><defs><pattern id="lgrid" width="48" height="48" patternUnits="userSpaceOnUse"><path d="M48 0H0V48" fill="none" stroke="white" strokeWidth="1" /></pattern></defs><rect width="100%" height="100%" fill="url(#lgrid)" /></svg>
          <div className="relative mx-auto max-w-7xl px-4">
            <div className="text-xs font-semibold uppercase tracking-widest text-saffron-400">NLDC · NRLDC · ERLDC · WRLDC · SRLDC · NERLDC</div>
            <h1 className="mt-3 max-w-3xl text-3xl font-bold leading-tight tracking-tight sm:text-4xl">{t('app.title')}</h1>
            <p className="mt-3 max-w-2xl text-grid-200">{i18n.language === 'hi' ? 'राष्ट्रीय एवं क्षेत्रीय भार प्रेषण केंद्रों हेतु एकीकृत प्रचालन मंच।' : 'An integrated, secure platform for the operations of the National and Regional Load Despatch Centres.'}</p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link to="/login" className="rounded-lg bg-saffron-500 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-saffron-500/20 hover:bg-saffron-600">{t('auth.gridIndiaLogin')}</Link>
              <Link to="/login?type=external" className="rounded-lg bg-white/10 px-5 py-2.5 text-sm font-semibold text-white ring-1 ring-white/25 hover:bg-white/20">{t('auth.externalLogin')}</Link>
              <Link to="/signup" className="px-2 py-2.5 text-sm font-medium text-grid-200 hover:text-white">{t('auth.signUp')} →</Link>
            </div>
          </div>
        </section>
      )}
      {section && <nav aria-label="Breadcrumb" className="mx-auto max-w-7xl px-4 pt-3 text-xs text-slate-500"><Link to="/welcome">{t('common.home')}</Link> / {section}</nav>}
      <main className={cls('relative mx-auto grid max-w-7xl gap-5 px-4 py-4 lg:grid-cols-3', !section && '-mt-24')}>
        <section className="lg:col-span-3">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {data.tiles.map((tile) => (
              <div key={tile.key} className="rounded-xl bg-white/95 p-4 shadow-lift ring-1 ring-slate-200/60">
                <div className="text-xs text-slate-500">{i18n.language === 'hi' ? tile.label_hi : tile.label_en}</div>
                <div className="mt-1 text-2xl font-bold tabular-nums text-grid-800">{tile.value}</div>
                {tile.sub && <div className="text-[11px] text-slate-500">{tile.sub}</div>}
              </div>
            ))}
          </div>
          <div className={cls('mt-2 text-right text-[11px]', section ? 'text-slate-500' : 'text-slate-500')}>{t('common.lastUpdated')}: {at ? fmtDT(at) : ''}</div>
        </section>
        {(!section || section === 'notices') && (
          <section className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-card lg:col-span-2" aria-labelledby="nb">
            <h2 id="nb" className="mb-2 font-semibold text-grid-800">📋 {i18n.language === 'hi' ? 'सूचना पट्ट' : 'Notice Board'}</h2>
            <ul className="divide-y">
              {(data.notice ?? []).map((n) => (
                <li key={n.id} className="py-2">
                  <div className="font-medium">{bi(n, 'title')}</div>
                  <div className="text-sm text-slate-600">{bi(n, 'body')}</div>
                  <div className="text-[11px] text-slate-400">{fmtDT(n.created_at)}</div>
                </li>
              ))}
            </ul>
          </section>
        )}
        {(!section || section === 'faq') && (
          <section className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-card" aria-labelledby="faq">
            <h2 id="faq" className="mb-2 font-semibold text-grid-800">❓ FAQ</h2>
            {(data.faq ?? []).map((f) => (
              <details key={f.id} className="border-b py-1.5 text-sm"><summary className="cursor-pointer font-medium">{bi(f, 'title')}</summary><p className="mt-1 text-slate-600">{bi(f, 'body')}</p></details>
            ))}
          </section>
        )}
        {!section && (
          <section className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-card lg:col-span-2">
            <h2 className="mb-2 font-semibold text-grid-800">🖼️ {i18n.language === 'hi' ? 'छवि दीर्घा' : 'Image gallery'}</h2>
            <div className="grid grid-cols-3 gap-2">
              {['NLDC control room', 'NRLDC video wall', 'SCADA EMS'].map((g, i) => (
                <div key={g} className="flex aspect-video items-end rounded bg-gradient-to-br from-grid-600 to-grid-900 p-2 text-xs text-white" style={{ opacity: 1 - i * 0.15 }}>{g}</div>
              ))}
            </div>
          </section>
        )}
        {(!section || section === 'feedback') && <FeedbackForm />}
      </main>
      <footer className="border-t bg-grid-900 py-4 text-center text-xs text-grid-100">
        <div className="mb-1 flex flex-wrap justify-center gap-3">
          {data.menu.filter((m) => m.location === 'FOOTER').map((m) => <ExternalLink key={m.id} href={m.target} className="hover:underline">{bi(m, 'label')}</ExternalLink>)}
        </div>
        © Grid Controller of India Limited · GIGW-compliant layout · {t('app.tagline')}
      </footer>
      {banner && (data.banner ?? []).length > 0 && (
        <Modal open onClose={() => setBanner(false)} title={bi(data.banner![0], 'title')}>
          <p className="text-sm">{bi(data.banner![0], 'body')}</p>
        </Modal>
      )}
    </div>
  )
}

function FeedbackForm() {
  const [form, setForm] = useState({ name: '', email: '', organisation: '', message: '', rating: 5 })
  const [cap, setCap] = useState<{ captcha_token: string; question: string } | null>(null)
  const [ans, setAns] = useState('')
  const [msg, setMsg] = useState<{ kind: 'success' | 'error'; text: string } | null>(null)
  const loadCap = () => api.get('/auth/captcha').then((r) => setCap(r.data))
  useEffect(() => { loadCap() }, [])
  const submit = async () => {
    try {
      await api.post('/portal/feedback', { ...form, captcha_token: cap?.captcha_token, captcha_answer: ans })
      setMsg({ kind: 'success', text: 'Thank you for your feedback.' })
      setForm({ name: '', email: '', organisation: '', message: '', rating: 5 })
    } catch (e) { setMsg({ kind: 'error', text: errMsg(e) }) }
    loadCap(); setAns('')
  }
  return (
    <section className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-card" aria-labelledby="fb">
      <h2 id="fb" className="mb-2 font-semibold text-grid-800">💬 Feedback & Suggestions / प्रतिक्रिया एवं सुझाव</h2>
      {msg && <div className="mb-2"><Alert kind={msg.kind}>{msg.text}</Alert></div>}
      <div className="space-y-2">
        <Field label="Name" required><input className={inputCls} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
        <div className="grid grid-cols-2 gap-2">
          <Field label="E-mail"><input className={inputCls} value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
          <Field label="Organisation"><input className={inputCls} value={form.organisation} onChange={(e) => setForm({ ...form, organisation: e.target.value })} /></Field>
        </div>
        <Field label="Rating"><select className={inputCls} value={form.rating} onChange={(e) => setForm({ ...form, rating: Number(e.target.value) })}>{[5, 4, 3, 2, 1].map((r) => <option key={r} value={r}>{'★'.repeat(r)}</option>)}</select></Field>
        <Field label="Message" required><textarea className={cls(inputCls, 'h-20')} value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} /></Field>
        <div className="flex items-center gap-2"><span className="rounded bg-slate-800 px-2 py-1 font-mono text-xs text-amber-200">{cap?.question}</span><input aria-label="captcha answer" className={cls(inputCls, 'w-20')} value={ans} onChange={(e) => setAns(e.target.value)} /></div>
        <Button onClick={submit}>Submit</Button>
      </div>
    </section>
  )
}

export function PostPage() {
  const { acronym } = useParams()
  const [post, setPost] = useState<any>(null)
  const [menu, setMenu] = useState<any[]>([])
  const nav = useNavigate()
  useEffect(() => {
    api.get(`/portal/post/${acronym}`).then((r) => setPost(r.data)).catch(() => nav('/welcome'))
    api.get('/portal/menu').then((r) => setMenu(r.data))
  }, [acronym, nav])
  return (
    <div className="min-h-screen bg-slate-50">
      <PublicHeader menu={menu} />
      <article className="mx-auto max-w-3xl p-6">
        {post && (<>
          <h1 className="mb-3 text-2xl font-bold text-grid-800">{bi(post, 'title')}</h1>
          {/* Content is admin-authored and published via verify-and-publish workflow */}
          <div className="prose text-slate-700" dangerouslySetInnerHTML={{ __html: post.body_format === 'HTML' ? bi(post, 'body') : bi(post, 'body').replace(/</g, '&lt;') }} />
        </>)}
      </article>
    </div>
  )
}
