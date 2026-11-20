// Profile: change password (policy enforced), upload signature image / DSC serial (TS Cl. 2.1, Ch.4; FRD UM-13, UM-17, UM-18).
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api, errMsg } from '../../api/client'
import { useAuth } from '../../store/auth'
import { useRecentPages } from '../../store/hooks'
import { Alert, Button, Card, Field, PageHeader, inputCls } from '../../components/common/ui'

export default function ProfilePage() {
  const { user, reload, flags } = useAuth()
  const { t } = useTranslation()
  const [params] = useSearchParams()
  useRecentPages(t('common.profile'))
  const [oldPwd, setOld] = useState('')
  const [newPwd, setNew] = useState('')
  const [confirm, setConfirm] = useState('')
  const [dsc, setDsc] = useState('')
  const [msg, setMsg] = useState<{ kind: 'error' | 'success'; text: string } | null>(null)

  const change = async () => {
    if (newPwd !== confirm) return setMsg({ kind: 'error', text: 'Passwords do not match' })
    try {
      await api.post('/auth/change-password', { old_password: oldPwd, new_password: newPwd })
      setMsg({ kind: 'success', text: 'Password changed' })
      setOld(''); setNew(''); setConfirm('')
      reload()
    } catch (e) { setMsg({ kind: 'error', text: errMsg(e) }) }
  }
  const uploadSig = async (file: File) => {
    const reader = new FileReader()
    reader.onload = async () => {
      try {
        await api.post('/auth/signature', { image_base64: reader.result, dsc_serial: dsc || undefined })
        setMsg({ kind: 'success', text: 'Signature saved' })
        reload()
      } catch (e) { setMsg({ kind: 'error', text: errMsg(e) }) }
    }
    reader.readAsDataURL(file)
  }
  return (
    <div className="space-y-4">
      <PageHeader title={t('common.profile')} subtitle={`${user?.username} · ${user?.roles.join(', ')}`} />
      {(params.get('force') || flags.must_change_password) && <Alert kind="warning">Your password must be changed before continuing (first login or password older than 90 days).</Alert>}
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
      <div className="grid gap-4 md:grid-cols-2">
        <Card title={t('auth.changePassword')}>
          <div className="space-y-3">
            <Field label="Current password"><input type="password" className={inputCls} value={oldPwd} onChange={(e) => setOld(e.target.value)} /></Field>
            <Field label={t('auth.newPassword')} hint={t('auth.passwordPolicy')}><input type="password" className={inputCls} value={newPwd} onChange={(e) => setNew(e.target.value)} /></Field>
            <Field label={t('auth.confirmPassword')}><input type="password" className={inputCls} value={confirm} onChange={(e) => setConfirm(e.target.value)} /></Field>
            <Button onClick={change}>{t('common.save')}</Button>
          </div>
        </Card>
        <Card title="Digital signature / signature image">
          <div className="space-y-3 text-sm">
            <p className="text-slate-600">Used to sign comments, consents and certificates. Status: <b>{user?.has_signature ? 'Signature on file' : 'Not uploaded'}</b></p>
            <Field label="DSC serial (optional)"><input className={inputCls} value={dsc} onChange={(e) => setDsc(e.target.value)} /></Field>
            <Field label="Signature image (PNG/JPG)"><input type="file" accept="image/png,image/jpeg" onChange={(e) => e.target.files?.[0] && uploadSig(e.target.files[0])} /></Field>
          </div>
        </Card>
      </div>
    </div>
  )
}
