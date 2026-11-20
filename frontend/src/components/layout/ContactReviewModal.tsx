// 3-monthly contact review pop-up with pre-filled details and a "retain" option (TS Cl. 2.1 p.24; FRD UM-04).
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, errMsg } from '../../api/client'
import { useAuth } from '../../store/auth'
import { Alert, Button, Field, Modal, inputCls } from '../common/ui'

export default function ContactReviewModal() {
  const { user, reload } = useAuth()
  const { t } = useTranslation()
  const [email, setEmail] = useState(user?.email ?? '')
  const [mobile, setMobile] = useState(user?.mobile ?? '')
  const [otpState, setOtpState] = useState<{ challenge_id: string; dev_otp?: string } | null>(null)
  const [otp, setOtp] = useState('')
  const [err, setErr] = useState('')
  const [open, setOpen] = useState(true)

  const submit = async (retain: boolean) => {
    setErr('')
    try {
      const { data } = await api.post('/auth/verify-contacts', retain ? { retain: true } : { retain: false, email, mobile })
      if (data.verification) setOtpState(data.verification)
      else { setOpen(false); reload() }
    } catch (e) {
      setErr(errMsg(e))
    }
  }
  const verify = async () => {
    try {
      await api.post('/auth/verify-contact-otp', { challenge_id: otpState!.challenge_id, otp })
      setOpen(false)
      reload()
    } catch (e) {
      setErr(errMsg(e))
    }
  }
  return (
    <Modal open={open} onClose={() => setOpen(false)} title={t('auth.contactReview')}>
      <div className="space-y-3">
        <p className="text-sm text-slate-600">{t('auth.contactReviewHelp')}</p>
        {err && <Alert kind="error">{err}</Alert>}
        {!otpState ? (
          <>
            <Field label="E-mail"><input className={inputCls} value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
            <Field label="Mobile"><input className={inputCls} value={mobile} onChange={(e) => setMobile(e.target.value)} /></Field>
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => submit(true)}>{t('auth.retain')}</Button>
              <Button onClick={() => submit(false)}>{t('auth.update')}</Button>
            </div>
          </>
        ) : (
          <>
            {otpState.dev_otp && <Alert kind="warning">{t('auth.devOtp')}: <b>{otpState.dev_otp}</b></Alert>}
            <Field label={t('auth.otp')}><input className={inputCls} value={otp} onChange={(e) => setOtp(e.target.value)} /></Field>
            <Button onClick={verify}>{t('auth.verify')}</Button>
          </>
        )}
      </div>
    </Modal>
  )
}
