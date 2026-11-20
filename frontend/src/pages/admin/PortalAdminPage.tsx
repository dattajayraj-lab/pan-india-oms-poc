// Portal CMS admin: create bilingual content, submit, verify & publish; manage navbar/footer menus (TS Cl. 11.1, 11.2; FRD CMS-*).
import { useEffect, useState } from 'react'
import { api, errMsg } from '../../api/client'
import { useAuth } from '../../store/auth'
import { fmtDT, useRecentPages } from '../../store/hooks'
import SpreadsheetGrid from '../../components/common/SpreadsheetGrid'
import { Alert, Badge, Button, Card, Field, PageHeader, Tabs, cls, inputCls } from '../../components/common/ui'

export default function PortalAdminPage() {
  useRecentPages('Admin · Portal content')
  const { user } = useAuth()
  const [tab, setTab] = useState('content')
  const [rows, setRows] = useState<any[]>([])
  const [menu, setMenu] = useState<any[]>([])
  const [feedback, setFeedback] = useState<any[]>([])
  const [form, setForm] = useState({ content_type: 'NOTICE', title_en: '', title_hi: '', body_en: '', body_hi: '', acronym: '', body_format: 'TEXT' })
  const [file, setFile] = useState<File | null>(null)
  const [mform, setMform] = useState({ label_en: '', label_hi: '', target_type: 'INTERNAL', target: '', location: 'NAVBAR' })
  const [msg, setMsg] = useState<{ kind: 'success' | 'error'; text: string } | null>(null)
  const load = () => {
    api.get('/portal/content').then((r) => setRows(r.data))
    api.get('/portal/menu').then((r) => setMenu(r.data))
    if (user?.is_admin) api.get('/portal/feedback').then((r) => setFeedback(r.data))
  }
  useEffect(load, [user])
  const create = async () => {
    const fd = new FormData()
    Object.entries(form).forEach(([k, v]) => v && fd.append(k, v))
    if (file) fd.append('file', file)
    try { await api.post('/portal/content', fd); setMsg({ kind: 'success', text: 'Draft created. Submit it for verification, then an administrator publishes it.' }); load() } catch (e) { setMsg({ kind: 'error', text: errMsg(e) }) }
  }
  const tr = (id: number, action: string) => api.post(`/portal/content/${id}/transition`, { action }).then(load).catch((e) => setMsg({ kind: 'error', text: errMsg(e) }))
  return (
    <div className="space-y-4">
      <PageHeader title="Portal content management" subtitle="Notice board, flashers, pop-up banner, posts, FAQ, gallery; verify-and-publish workflow." />
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
      <Tabs active={tab} onChange={setTab} tabs={[{ key: 'content', label: 'Content' }, { key: 'menu', label: 'Menus' }, { key: 'feedback', label: 'Feedback', count: feedback.length }]} />
      {tab === 'content' && (<>
        <Card title="New content (bilingual)">
          <div className="grid gap-2 md:grid-cols-3">
            <Field label="Type"><select className={inputCls} value={form.content_type} onChange={(e) => setForm({ ...form, content_type: e.target.value })}>{['NOTICE', 'FLASHER', 'BANNER', 'POST', 'FAQ', 'GALLERY', 'HELP'].map((c) => <option key={c}>{c}</option>)}</select></Field>
            <Field label="Title (English)" required><input className={inputCls} value={form.title_en} onChange={(e) => setForm({ ...form, title_en: e.target.value })} /></Field>
            <Field label="शीर्षक (हिन्दी)"><input className={inputCls} value={form.title_hi} onChange={(e) => setForm({ ...form, title_hi: e.target.value })} /></Field>
            <Field label="Body (English)"><textarea className={cls(inputCls, 'h-20')} value={form.body_en} onChange={(e) => setForm({ ...form, body_en: e.target.value })} /></Field>
            <Field label="विवरण (हिन्दी)"><textarea className={cls(inputCls, 'h-20')} value={form.body_hi} onChange={(e) => setForm({ ...form, body_hi: e.target.value })} /></Field>
            <div className="space-y-2">
              <Field label="Acronym (posts)"><input className={inputCls} value={form.acronym} onChange={(e) => setForm({ ...form, acronym: e.target.value })} /></Field>
              <Field label="Format"><select className={inputCls} value={form.body_format} onChange={(e) => setForm({ ...form, body_format: e.target.value })}><option>TEXT</option><option>HTML</option></select></Field>
            </div>
          </div>
          <div className="mt-2 flex items-center gap-2"><input type="file" aria-label="Attachment" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /><span className="text-xs text-slate-500">Flasher: Word / PDF / Excel only</span><Button className="ml-auto" onClick={create}>Create draft</Button></div>
        </Card>
        <SpreadsheetGrid exportName="portal_content" rows={rows} columns={[
          { key: 'content_type', label: 'Type' }, { key: 'title_en', label: 'Title' }, { key: 'title_hi', label: 'शीर्षक' },
          { key: 'workflow_state', label: 'State', render: (r) => <Badge>{r.workflow_state}</Badge> },
          { key: 'created_at', label: 'Created', exportValue: (r) => fmtDT(r.created_at) },
          { key: 'act', label: 'Workflow', render: (r) => (
            <div className="flex gap-1">
              {['DRAFT', 'REJECTED'].includes(r.workflow_state) && <Button size="sm" variant="secondary" onClick={() => tr(r.id, 'SUBMIT')}>Submit</Button>}
              {r.workflow_state === 'SUBMITTED' && user?.is_admin && <><Button size="sm" variant="success" onClick={() => tr(r.id, 'PUBLISH')}>Publish</Button><Button size="sm" variant="danger" onClick={() => tr(r.id, 'REJECT')}>Reject</Button></>}
              {r.workflow_state === 'PUBLISHED' && user?.is_admin && <Button size="sm" variant="secondary" onClick={() => tr(r.id, 'UNPUBLISH')}>Unpublish</Button>}
            </div>) },
        ]} />
      </>)}
      {tab === 'menu' && (
        <Card title="Navigation menu (navbar / footer)">
          <div className="mb-3 grid gap-2 md:grid-cols-6">
            <input aria-label="Label EN" placeholder="Label (EN)" className={inputCls} value={mform.label_en} onChange={(e) => setMform({ ...mform, label_en: e.target.value })} />
            <input aria-label="Label HI" placeholder="लेबल (हिं)" className={inputCls} value={mform.label_hi} onChange={(e) => setMform({ ...mform, label_hi: e.target.value })} />
            <select aria-label="Target type" className={inputCls} value={mform.target_type} onChange={(e) => setMform({ ...mform, target_type: e.target.value })}><option>INTERNAL</option><option>POST</option><option>EXTERNAL</option></select>
            <input aria-label="Target" placeholder="/path, ACRONYM or https://…" className={inputCls} value={mform.target} onChange={(e) => setMform({ ...mform, target: e.target.value })} />
            <select aria-label="Location" className={inputCls} value={mform.location} onChange={(e) => setMform({ ...mform, location: e.target.value })}><option>NAVBAR</option><option>FOOTER</option></select>
            <Button onClick={() => api.post('/portal/menu', mform).then(load)}>Add</Button>
          </div>
          <SpreadsheetGrid exportName="menu" rows={menu} compact columns={[{ key: 'location', label: 'Location' }, { key: 'label_en', label: 'Label' }, { key: 'label_hi', label: 'लेबल' },
            { key: 'target_type', label: 'Type' }, { key: 'target', label: 'Target' },
            { key: 'x', label: '', render: (r) => <Button size="sm" variant="danger" onClick={() => api.delete(`/portal/menu/${r.id}`).then(load)}>Remove</Button> }]} />
        </Card>
      )}
      {tab === 'feedback' && <SpreadsheetGrid exportName="feedback" rows={feedback} columns={[{ key: 'created_at', label: 'Date', exportValue: (r) => fmtDT(r.created_at) }, { key: 'name', label: 'Name' }, { key: 'organisation', label: 'Organisation' }, { key: 'rating', label: 'Rating' }, { key: 'message', label: 'Message' }]} />}
    </div>
  )
}
