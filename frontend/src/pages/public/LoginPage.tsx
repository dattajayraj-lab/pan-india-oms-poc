// Dual login (External / Grid-India), CAPTCHA, 2FA OTP, forgot password/username (TS Cl. 2.1, 2.5, Ch.4; FRD UM-05..22).
import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api, errMsg } from '../../api/client'
import { setLanguage } from '../../i18n'
import { useAuth } from '../../store/auth'
import { Alert, Button, Field, cls, inputCls } from '../../components/common/ui'

type Mode = 'login' | 'otp' | 'forgot' | 'reset' | 'forgotUser'

function Captcha({ onChange, nonce }: { onChange: (token: string, answer: string) => void; nonce: number }) {
  const { t } = useTranslation()
  const [cap, setCap] = useState<{ captcha_token: string; question: string } | null>(null)
  const [ans, setAns] = useState('')
  const load = () => api.get('/auth/captcha').then((r) => { setCap(r.data); setAns(''); onChange(r.data.captcha_token, '') })
  useEffect(() => { load() }, [nonce]) // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <Field label={t('auth.captcha')}>
      <div className="flex items-center gap-2">
        <span className="select-none whitespace-nowrap rounded-lg bg-grid-950 px-3 py-2 font-mono text-sm tracking-widest text-saffron-400" aria-label="captcha question">{cap?.question ?? '…'}</span>
        <input aria-label="captcha answer" className={cls(inputCls, 'w-24')} value={ans} onChange={(e) => { setAns(e.target.value); onChange(cap?.captcha_token ?? '', e.target.value) }} />
        <button type="button" aria-label="New captcha" className="text-grid-600" onClick={load}>↻</button>
      </div>
    </Field>
  )
}

export default function LoginPage() {
  const { t, i18n } = useTranslation()
  const { completeLogin } = useAuth()
  const nav = useNavigate()
  const [params] = useSearchParams()
  const [loginType, setLoginType] = useState<'GRID_INDIA' | 'EXTERNAL'>(params.get('type') === 'external' ? 'EXTERNAL' : 'GRID_INDIA')
  const [mode, setMode] = useState<Mode>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [captcha, setCaptcha] = useState({ token: '', answer: '' })
  const [nonce, setNonce] = useState(0)
  const [challenge, setChallenge] = useState<{ challenge_id: string; dev_otp?: string; masked_destination?: string } | null>(null)
  const [otp, setOtp] = useState('')
  const [newPwd, setNewPwd] = useState('')
  const [email, setEmail] = useState('')
  const [msg, setMsg] = useState<{ kind: 'error' | 'success' | 'info'; text: string } | null>(null)
  const [busy, setBusy] = useState(false)

  const run = async (fn: () => Promise<void>) => {
    setBusy(true)
    setMsg(null)
    try { await fn() } catch (e) { setMsg({ kind: 'error', text: errMsg(e) }); setNonce((n) => n + 1) } finally { setBusy(false) }
  }

  const doLogin = () => run(async () => {
    const { data } = await api.post('/auth/login', { username, password, login_type: loginType, captcha_token: captcha.token, captcha_answer: captcha.answer })
    if (data.otp_required) { setChallenge(data); setMode('otp') } else { await completeLogin(data.access_token); nav('/') }
  })
  const doOtp = () => run(async () => {
    const { data } = await api.post('/auth/verify-otp', { challenge_id: challenge!.challenge_id, otp })
    await completeLogin(data.access_token)
    nav(data.must_change_password ? '/profile?force=1' : '/')
  })
  const doForgot = () => run(async () => {
    const { data } = await api.post('/auth/forgot-password', { identifier: username, captcha_token: captcha.token, captcha_answer: captcha.answer })
    setMsg({ kind: 'success', text: data.message })
    if (data.challenge_id) { setChallenge(data); setMode('reset') }
  })
  const doReset = () => run(async () => {
    const { data } = await api.post('/auth/reset-password', { challenge_id: challenge!.challenge_id, otp, new_password: newPwd })
    setMsg({ kind: 'success', text: data.message }); setMode('login'); setNonce((n) => n + 1)
  })
  const doForgotUser = () => run(async () => {
    const { data } = await api.post('/auth/forgot-username', { email, captcha_token: captcha.token, captcha_answer: captcha.answer })
    setMsg({ kind: 'success', text: data.message }); setMode('login')
  })

  return (
    <div className="grid min-h-screen bg-white lg:grid-cols-[1.1fr_1fr]">
      <aside className="relative hidden overflow-hidden bg-gradient-to-br from-grid-800 via-grid-900 to-grid-950 p-12 text-white lg:flex lg:flex-col">
        <svg className="absolute inset-0 h-full w-full opacity-[0.06]" aria-hidden>
          <defs><pattern id="grid" width="48" height="48" patternUnits="userSpaceOnUse"><path d="M48 0H0V48" fill="none" stroke="white" strokeWidth="1" /></pattern></defs>
          <rect width="100%" height="100%" fill="url(#grid)" />
        </svg>
        <Link to="/welcome" className="relative flex items-center gap-3">
          <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-saffron-400 to-saffron-600 shadow-lg"><svg viewBox="0 0 24 24" className="h-6 w-6 fill-white" aria-hidden><path d="M13.5 2 5 13.5h6L9.5 22 19 9.5h-6z" /></svg></span>
          <span><span className="block text-lg font-bold">Grid-India OMS</span><span className="block text-xs text-grid-300">Grid Controller of India Limited</span></span>
        </Link>
        <div className="relative mt-auto max-w-lg">
          <div className="text-xs font-semibold uppercase tracking-widest text-saffron-400">Pan-India · NLDC + 5 RLDCs</div>
          <h1 className="mt-3 text-4xl font-bold leading-tight tracking-tight">{t('app.title')}</h1>
          <p className="mt-4 text-base text-grid-200">One secure platform for registration, first time charging, real-time outage codes, outage coordination, availability, protection studies and MIS.</p>
          <div className="mt-8 grid grid-cols-3 gap-4 text-sm">
            {[['11', 'integrated modules'], ['6', 'load despatch centres'], ['24×7', 'control-room ready']].map(([n, l]) => (
              <div key={l} className="rounded-xl bg-white/5 p-3 ring-1 ring-white/10"><div className="text-2xl font-bold text-white">{n}</div><div className="text-[11px] text-grid-300">{l}</div></div>
            ))}
          </div>
        </div>
        <div className="relative mt-10 text-[11px] text-grid-400">GeM bid GEM/2026/B/8083674 · Proof of concept</div>
      </aside>
      <div className="flex flex-col">
        <div className="flex items-center justify-between px-6 py-4">
          <Link to="/welcome" className="text-sm font-semibold text-grid-700 lg:invisible">Grid-India OMS</Link>
          <button className="rounded-lg px-2.5 py-1.5 text-xs font-semibold text-grid-700 ring-1 ring-slate-200 hover:bg-grid-50" onClick={() => setLanguage(i18n.language === 'hi' ? 'en' : 'hi')}>{i18n.language === 'hi' ? 'English' : 'हिन्दी'}</button>
        </div>
        <div className="flex flex-1 items-center justify-center px-6 pb-12">
        <div className="w-full max-w-sm">
          <h2 className="text-2xl font-bold tracking-tight text-slate-900">Sign in</h2>
          <p className="mb-6 mt-1 text-sm text-slate-500">Choose your login type to continue.</p>
          <div className="mb-5 grid grid-cols-2 gap-1 rounded-xl bg-slate-100 p-1" role="tablist">
            {(['GRID_INDIA', 'EXTERNAL'] as const).map((lt) => (
              <button key={lt} role="tab" aria-selected={loginType === lt} onClick={() => { setLoginType(lt); setMode('login') }}
                className={cls('rounded-lg py-2 text-sm font-semibold transition', loginType === lt ? 'bg-white text-grid-800 shadow-card' : 'text-slate-500 hover:text-slate-700')}>
                {lt === 'GRID_INDIA' ? t('auth.gridIndiaLogin') : t('auth.externalLogin')}
              </button>
            ))}
          </div>
          {msg && <div className="mb-3"><Alert kind={msg.kind}>{msg.text}</Alert></div>}

          {mode === 'login' && (
            <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); doLogin() }}>
              <Field label={t('auth.username')}><input autoComplete="username" className={inputCls} value={username} onChange={(e) => setUsername(e.target.value)} required /></Field>
              <Field label={t('auth.password')}><input type="password" autoComplete="current-password" className={inputCls} value={password} onChange={(e) => setPassword(e.target.value)} required /></Field>
              <Captcha nonce={nonce} onChange={(token, answer) => setCaptcha({ token, answer })} />
              <Button className="w-full" disabled={busy}>{t('common.login')}</Button>
              <div className="flex justify-between text-xs">
                <button type="button" className="text-grid-600" onClick={() => { setMode('forgot'); setMsg(null) }}>{t('auth.forgotPassword')}</button>
                <button type="button" className="text-grid-600" onClick={() => { setMode('forgotUser'); setMsg(null) }}>{t('auth.forgotUsername')}</button>
              </div>
              {loginType === 'EXTERNAL' && <Link to="/signup" className="block text-center text-xs text-grid-600">{t('auth.signUp')}</Link>}
            </form>
          )}
          {mode === 'otp' && challenge && (
            <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); doOtp() }}>
              <p className="text-sm text-slate-600">{t('auth.otpSent')} {challenge.masked_destination}</p>
              {challenge.dev_otp && <Alert kind="info">{t('auth.devOtp')}: <b data-testid="dev-otp">{challenge.dev_otp}</b></Alert>}
              <Field label={t('auth.otp')}><input inputMode="numeric" autoFocus className={inputCls} value={otp} onChange={(e) => setOtp(e.target.value)} /></Field>
              <Button className="w-full" disabled={busy}>{t('auth.verify')}</Button>
            </form>
          )}
          {mode === 'forgot' && (
            <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); doForgot() }}>
              <Field label={`${t('auth.username')} / E-mail`}><input className={inputCls} value={username} onChange={(e) => setUsername(e.target.value)} required /></Field>
              <Captcha nonce={nonce} onChange={(token, answer) => setCaptcha({ token, answer })} />
              <Button className="w-full" disabled={busy}>{t('auth.resetPassword')}</Button>
              <button type="button" className="text-xs text-grid-600" onClick={() => setMode('login')}>← {t('common.login')}</button>
            </form>
          )}
          {mode === 'reset' && challenge && (
            <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); doReset() }}>
              {challenge.dev_otp && <Alert kind="info">{t('auth.devOtp')}: <b>{challenge.dev_otp}</b></Alert>}
              <Field label={t('auth.otp')}><input className={inputCls} value={otp} onChange={(e) => setOtp(e.target.value)} /></Field>
              <Field label={t('auth.newPassword')} hint={t('auth.passwordPolicy')}><input type="password" className={inputCls} value={newPwd} onChange={(e) => setNewPwd(e.target.value)} /></Field>
              <Button className="w-full" disabled={busy}>{t('auth.resetPassword')}</Button>
            </form>
          )}
          {mode === 'forgotUser' && (
            <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); doForgotUser() }}>
              <Field label="E-mail"><input type="email" className={inputCls} value={email} onChange={(e) => setEmail(e.target.value)} required /></Field>
              <Captcha nonce={nonce} onChange={(token, answer) => setCaptcha({ token, answer })} />
              <Button className="w-full" disabled={busy}>{t('common.submit')}</Button>
              <button type="button" className="text-xs text-grid-600" onClick={() => setMode('login')}>← {t('common.login')}</button>
            </form>
          )}
          <p className="mt-8 rounded-lg bg-slate-50 px-3 py-2 text-center text-[11px] text-slate-500 ring-1 ring-slate-200">POC demo users: superadmin, nr_coord, nr_shiftic, re_dev, pg_user · password Grid@2026</p>
        </div>
        </div>
      </div>
    </div>
  )
}
