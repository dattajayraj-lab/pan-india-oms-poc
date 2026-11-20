// Admin: user management, all sessions with force-logout, runtime settings, notification toggles, audit trail
// (TS Cl. 2.1, 2.3, 2.4, Table 1 note; FRD UM-02, UM-08..11, NOT-02, UI-04, UI-06).
import { useEffect, useState } from 'react'
import { api, errMsg } from '../../api/client'
import { useAutoRefresh, fmtDT, useRecentPages } from '../../store/hooks'
import SpreadsheetGrid from '../../components/common/SpreadsheetGrid'
import { Alert, Badge, Button, Card, Field, LastUpdated, Modal, PageHeader, inputCls } from '../../components/common/ui'

export function UsersPage() {
  useRecentPages('Admin · Users')
  const [rows, setRows] = useState<any[]>([])
  const [roles, setRoles] = useState<any[]>([])
  const [edit, setEdit] = useState<any | null>(null)
  const [create, setCreate] = useState(false)
  const [msg, setMsg] = useState('')
  const load = () => api.get('/admin/users').then((r) => setRows(r.data))
  useEffect(() => { load(); api.get('/admin/roles').then((r) => setRoles(r.data)) }, [])
  return (
    <div>
      <PageHeader title="User management" subtitle="Create, modify, deactivate users; assign roles; toggle 2FA and multi-session." actions={<Button onClick={() => setCreate(true)}>+ New user</Button>} />
      {msg && <div className="mb-3"><Alert kind="success">{msg}</Alert></div>}
      <SpreadsheetGrid exportName="users" rows={rows} columns={[
        { key: 'username', label: 'Username' }, { key: 'full_name', label: 'Name' },
        { key: 'user_category', label: 'Category' }, { key: 'centre', label: 'Centre', exportValue: (r) => r.centre?.code ?? '' },
        { key: 'roles', label: 'Roles', exportValue: (r) => r.roles.join(', ') },
        { key: 'is_2fa_enabled', label: '2FA', render: (r) => <Badge color={r.is_2fa_enabled ? 'green' : 'red'}>{r.is_2fa_enabled ? 'ON' : 'OFF'}</Badge> },
        { key: 'allow_multi_session', label: 'Multi-session', render: (r) => (r.allow_multi_session ? 'Yes' : 'No') },
        { key: 'is_active', label: 'Status', render: (r) => <Badge color={r.is_active ? 'green' : 'red'}>{r.is_active ? 'ACTIVE' : 'INACTIVE'}</Badge> },
        { key: 'act', label: 'Actions', render: (r) => <Button size="sm" variant="secondary" onClick={() => setEdit(r)}>Edit</Button> },
      ]} />
      {edit && <EditUser user={edit} roles={roles} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); load() }} />}
      {create && <CreateUser roles={roles} onClose={() => setCreate(false)} onSaved={(m) => { setCreate(false); setMsg(m); load() }} />}
    </div>
  )
}

function RolePicker({ roles, value, onChange }: { roles: any[]; value: string[]; onChange: (v: string[]) => void }) {
  return (
    <div className="grid max-h-48 grid-cols-2 gap-1 overflow-y-auto rounded border p-2 text-xs">
      {roles.map((r) => (
        <label key={r.code} className="flex items-center gap-1">
          <input type="checkbox" checked={value.includes(r.code)} onChange={(e) => onChange(e.target.checked ? [...value, r.code] : value.filter((x) => x !== r.code))} />
          {r.name}
        </label>
      ))}
    </div>
  )
}

function EditUser({ user, roles, onClose, onSaved }: { user: any; roles: any[]; onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState({ full_name: user.full_name, email: user.email, mobile: user.mobile, is_active: user.is_active, is_2fa_enabled: user.is_2fa_enabled, allow_multi_session: user.allow_multi_session, roles: user.roles as string[] })
  const [err, setErr] = useState('')
  const save = async (extra: object = {}) => {
    try { await api.patch(`/admin/users/${user.id}`, { ...form, ...extra }); onSaved() } catch (e) { setErr(errMsg(e)) }
  }
  return (
    <Modal open onClose={onClose} title={`Edit ${user.username}`}>
      <div className="space-y-3">
        {err && <Alert kind="error">{err}</Alert>}
        <Field label="Name"><input className={inputCls} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></Field>
        <div className="grid grid-cols-2 gap-2">
          <Field label="E-mail"><input className={inputCls} value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
          <Field label="Mobile"><input className={inputCls} value={form.mobile} onChange={(e) => setForm({ ...form, mobile: e.target.value })} /></Field>
        </div>
        <div className="flex flex-wrap gap-4 text-sm">
          {(['is_active', 'is_2fa_enabled', 'allow_multi_session'] as const).map((k) => (
            <label key={k} className="flex items-center gap-1"><input type="checkbox" checked={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.checked })} />{k.replace(/_/g, ' ')}</label>
          ))}
        </div>
        <Field label="Roles"><RolePicker roles={roles} value={form.roles} onChange={(v) => setForm({ ...form, roles: v })} /></Field>
        <div className="flex gap-2">
          <Button onClick={() => save()}>Save</Button>
          <Button variant="secondary" onClick={() => save({ unlock: true })}>Save & unlock account</Button>
          <Button variant="danger" onClick={() => api.delete(`/admin/users/${user.id}`).then(onSaved)}>Deactivate</Button>
        </div>
      </div>
    </Modal>
  )
}

function CreateUser({ roles, onClose, onSaved }: { roles: any[]; onClose: () => void; onSaved: (m: string) => void }) {
  const [form, setForm] = useState({ username: '', full_name: '', email: '', mobile: '', user_category: 'GRID_INDIA', department: '', centre_code: 'NRLDC', roles: [] as string[], is_2fa_enabled: true })
  const [err, setErr] = useState('')
  const save = async () => {
    try {
      const { data } = await api.post('/admin/users', form)
      onSaved(`${data.message} (POC: activation OTP ${data.activation?.dev_otp ?? 'sent'})`)
    } catch (e) { setErr(errMsg(e)) }
  }
  return (
    <Modal open onClose={onClose} title="Create user">
      <div className="space-y-3">
        {err && <Alert kind="error">{err}</Alert>}
        <div className="grid grid-cols-2 gap-2">
          <Field label="Username" required><input className={inputCls} value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} /></Field>
          <Field label="Name" required><input className={inputCls} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></Field>
          <Field label="E-mail" required><input className={inputCls} value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
          <Field label="Mobile" required><input className={inputCls} value={form.mobile} onChange={(e) => setForm({ ...form, mobile: e.target.value })} /></Field>
          <Field label="Category"><select className={inputCls} value={form.user_category} onChange={(e) => setForm({ ...form, user_category: e.target.value })}>{['GRID_INDIA', 'EXTERNAL', 'CTU', 'RPC', 'PUBLIC'].map((c) => <option key={c}>{c}</option>)}</select></Field>
          <Field label="Centre"><select className={inputCls} value={form.centre_code} onChange={(e) => setForm({ ...form, centre_code: e.target.value })}>{['NLDC', 'NRLDC', 'ERLDC', 'WRLDC', 'SRLDC', 'NERLDC'].map((c) => <option key={c}>{c}</option>)}</select></Field>
          <Field label="Department"><input className={inputCls} value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} /></Field>
        </div>
        <Field label="Roles"><RolePicker roles={roles} value={form.roles} onChange={(v) => setForm({ ...form, roles: v })} /></Field>
        <Button onClick={save}>Create & send activation link</Button>
      </div>
    </Modal>
  )
}

export function SessionsPage() {
  useRecentPages('Admin · Sessions')
  const { data, updatedAt, reload } = useAutoRefresh<any[]>('/admin/sessions')
  return (
    <div>
      <PageHeader title="All active sessions" subtitle="Force logout of any selected session." actions={<LastUpdated at={updatedAt} />} />
      <SpreadsheetGrid exportName="sessions" rows={data ?? []} columns={[
        { key: 'username', label: 'User' }, { key: 'full_name', label: 'Name' }, { key: 'ip_address', label: 'IP' },
        { key: 'created_at', label: 'Login at', exportValue: (r) => fmtDT(r.created_at) },
        { key: 'last_seen_at', label: 'Last seen', exportValue: (r) => fmtDT(r.last_seen_at) },
        { key: 'x', label: 'Action', render: (r) => <Button size="sm" variant="danger" onClick={() => api.delete(`/auth/sessions/${r.id}`).then(reload)}>Force logout</Button> },
      ]} />
    </div>
  )
}

export function SettingsPage() {
  useRecentPages('Admin · Settings')
  const [settings, setSettings] = useState<Record<string, any>>({})
  const [toggles, setToggles] = useState<any[]>([])
  const [msg, setMsg] = useState<{ kind: 'success' | 'error'; text: string } | null>(null)
  const load = () => {
    api.get('/admin/settings').then((r) => setSettings(r.data))
    api.get('/admin/notification-toggles').then((r) => setToggles(r.data))
  }
  useEffect(load, [])
  const save = async () => {
    try { await api.put('/admin/settings', settings); setMsg({ kind: 'success', text: 'Settings saved. Pages pick up the new refresh rate on next load.' }) } catch (e) { setMsg({ kind: 'error', text: errMsg(e) }) }
  }
  return (
    <div className="space-y-4">
      <PageHeader title="Runtime settings" subtitle="Admin-configurable parameters (refresh rate, code validity, escalation timers, windows)." />
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
      <Card title="System parameters" actions={<Button onClick={save}>Save</Button>}>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Object.entries(settings).map(([k, v]) => (
            <Field key={k} label={k.replace(/_/g, ' ')}>
              {typeof v === 'boolean'
                ? <input type="checkbox" checked={v} onChange={(e) => setSettings({ ...settings, [k]: e.target.checked })} />
                : <input aria-label={k} className={inputCls} value={String(v)} onChange={(e) => setSettings({ ...settings, [k]: typeof v === 'number' ? Number(e.target.value) : e.target.value })} />}
            </Field>
          ))}
        </div>
      </Card>
      <Card title="E-mail / SMS per workflow step (enable/disable)">
        <SpreadsheetGrid exportName="notification_toggles" rows={toggles} compact columns={[
          { key: 'module', label: 'Module' }, { key: 'step_code', label: 'Step' },
          { key: 'email_enabled', label: 'E-mail', render: (r) => <input type="checkbox" checked={r.email_enabled} onChange={(e) => api.patch(`/admin/notification-toggles/${r.id}`, { email_enabled: e.target.checked }).then(load)} /> },
          { key: 'sms_enabled', label: 'SMS', render: (r) => <input type="checkbox" checked={r.sms_enabled} onChange={(e) => api.patch(`/admin/notification-toggles/${r.id}`, { sms_enabled: e.target.checked }).then(load)} /> },
        ]} />
      </Card>
    </div>
  )
}

export function AuditPage() {
  useRecentPages('Admin · Audit trail')
  const [module, setModule] = useState('')
  const { data, updatedAt } = useAutoRefresh<any[]>('/admin/audit-logs', { module: module || undefined, limit: 500 }, { intervalMs: 5000 })
  return (
    <div>
      <PageHeader title="Audit trail" subtitle="Immutable log of every create, update, approve and login event." actions={<LastUpdated at={updatedAt} />} />
      <div className="mb-2 w-48"><select aria-label="Module filter" className={inputCls} value={module} onChange={(e) => setModule(e.target.value)}>
        <option value="">All modules</option>{['auth', 'admin', 'cas', 'portal', 'registration', 'ftc', 'comm_cert', 'realtime', 'outage_coord', 'availability', 'protection', 'alerts', 'sps', 'mis', 'master'].map((m) => <option key={m}>{m}</option>)}
      </select></div>
      <SpreadsheetGrid exportName="audit_trail" rows={data ?? []} compact columns={[
        { key: 'created_at', label: 'Time', exportValue: (r) => fmtDT(r.created_at) }, { key: 'username', label: 'User' },
        { key: 'module', label: 'Module' }, { key: 'action', label: 'Action' }, { key: 'entity_type', label: 'Entity' },
        { key: 'entity_id', label: 'Ref' }, { key: 'new', label: 'Details', exportValue: (r) => JSON.stringify(r.new ?? '') },
        { key: 'ip_address', label: 'IP' },
      ]} />
    </div>
  )
}
