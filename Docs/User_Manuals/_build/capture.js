// Captures user-manual screenshots of the running OMS app with Edge.
const { chromium } = require('playwright-core')
const fs = require('fs')
const path = require('path')

const BASE = 'http://localhost:5173'
const OUT = process.argv[2]
const ONLY = process.argv[3] // optional role filter
fs.mkdirSync(OUT, { recursive: true })

// [file, path | {from, match}, optional action]
const PLAN = {
  public: { user: null, shots: [
    ['pub_landing', '/welcome'],
    ['pub_login', '/login'],
    ['pub_login_external', '/login?type=external'],
    ['pub_signup', '/signup'],
  ] },
  nr_coord: { user: 'nr_coord', type: 'GRID_INDIA', shots: [
    ['int_home', '/'],
    ['int_profile', '/profile'],
    ['cas_tickets', '/cas'],
    ['cas_detail', { from: '/cas', match: /^\/cas\/\d+$/ }],
    ['cas_dashboards', '/cas/dashboards'],
    ['cas_reports', '/cas/reports'],
    ['cas_kb', '/cas/kb'],
    ['reg_list', '/registration'],
    ['reg_detail', { from: '/registration', match: /^\/registration\/\d+$/ }],
    ['reg_nsws', '/registration/nsws'],
    ['reg_workload', '/registration/workload'],
    ['reg_fnc', '/registration/fnc-import'],
    ['reg_accounts', '/registration/account-requests'],
    ['ftc_list', '/ftc'],
    ['ftc_detail', '/ftc/2'],
    ['ftc_compliance', '/ftc/compliance'],
    ['ftc_startup', '/ftc/startup-power'],
    ['ftc_reports', '/ftc/reports'],
    ['cc_list', '/comm-cert'],
    ['cc_detail', { from: '/comm-cert', match: /^\/comm-cert\/\d+$/ }],
    ['mis_builder', '/mis'],
    ['mis_graphs', '/mis/graphs'],
    ['mis_genout', '/mis/generation-outage'],
    ['mis_bi', '/mis/bi'],
    ['int_hindi', '/', 'hindi'],
  ] },
  nr_shiftic: { user: 'nr_shiftic', type: 'GRID_INDIA', shots: [
    ['rt_control', '/realtime'],
    ['rt_shift', '/realtime/shift'],
    ['rt_request', '/realtime/request'],
    ['rt_codes', '/realtime/codes'],
    ['rt_elements', '/realtime/elements'],
    ['rt_remvar', '/realtime/re-mvar'],
    ['rt_shiftreport', '/realtime/shift-report'],
    ['rt_elog', '/realtime/elog'],
  ] },
  nr_outage: { user: 'nr_outage', type: 'GRID_INDIA', shots: [
    ['oc_list', '/outage'],
    ['oc_new', '/outage/new'],
    ['oc_d1', '/outage/d1'],
    ['av_sheet', '/availability'],
    ['av_verify', '/availability/verify'],
  ] },
  nr_protection: { user: 'nr_protection', type: 'GRID_INDIA', shots: [
    ['pr_events', '/protection'],
    ['pr_detail', { from: '/protection', match: /^\/protection\/\d+$/ }],
    ['pr_psc', '/protection/psc'],
    ['pr_sopr', '/protection/sopr'],
  ] },
  nr_alerts: { user: 'nr_alerts', type: 'GRID_INDIA', shots: [
    ['al_send', '/alerts'],
    ['al_contacts', '/alerts/contacts'],
    ['al_history', '/alerts/history'],
    ['sps_status', '/sps'],
  ] },
  re_dev: { user: 're_dev', type: 'EXTERNAL', shots: [
    ['ext_home', '/'],
    ['ext_cas_new', '/cas/new'],
    ['ext_cas_list', '/cas'],
    ['ext_reg_new', '/registration/new'],
    ['ext_reg_list', '/registration'],
    ['ext_ftc_list', '/ftc'],
    ['ext_ftc_new', '/ftc/new'],
    ['ext_cas_detail', { from: '/cas', match: /^\/cas\/\d+$/ }],
    ['ext_rt_request', '/realtime/request'],
  ] },
  tpcomm_user: { user: 'tpcomm_user', type: 'EXTERNAL', shots: [
    ['ext_cc_list', '/comm-cert'],
    ['ext_cc_new', '/comm-cert/new'],
  ] },
  pg_user: { user: 'pg_user', type: 'EXTERNAL', shots: [
    ['ext_oc_list', '/outage'],
    ['ext_oc_new', '/outage/new'],
    ['ext_av', '/availability'],
    ['ext_pr_events', '/protection'],
    ['ext_sps', '/sps'],
  ] },
  superadmin: { user: 'superadmin', type: 'GRID_INDIA', shots: [
    ['adm_home', '/'],
    ['adm_users', '/admin/users'],
    ['adm_sessions', '/admin/sessions'],
    ['adm_settings', '/admin/settings'],
    ['adm_audit', '/admin/audit'],
    ['adm_master', '/admin/master'],
    ['adm_portal', '/admin/portal'],
  ] },
}

async function login(page, user, type) {
  await page.goto(BASE + '/login')
  const res = await page.evaluate(async ({ user, type }) => {
    const j = async (r) => { const t = await r.json(); if (!r.ok) throw new Error(JSON.stringify(t)); return t }
    const cap = await j(await fetch('/api/v1/auth/captcha'))
    const q = cap.question.replace('= ?', '').replace('×', '*')
    const answer = String(Function('return ' + q)())
    let r = await j(await fetch('/api/v1/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: user, password: 'Grid@2026', login_type: type, captcha_token: cap.captcha_token, captcha_answer: answer }) }))
    if (r.otp_required) {
      r = await j(await fetch('/api/v1/auth/verify-otp', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ challenge_id: r.challenge_id, otp: r.dev_otp }) }))
    }
    sessionStorage.setItem('oms.token', r.access_token)
    localStorage.setItem('oms.lang', 'en')
    return r.user?.username
  }, { user, type })
  return res
}

async function settle(page) {
  await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {})
  await page.waitForFunction(() => !document.body.innerText.includes('Loading…'), null, { timeout: 15000 }).catch(() => {})
  await page.waitForTimeout(1200)
  // close any modal (e.g. contact review) so it doesn't hide the page
  for (let i = 0; i < 2; i++) {
    const dlg = await page.$('[role="dialog"]')
    if (!dlg) break
    await page.keyboard.press('Escape')
    await page.waitForTimeout(400)
    const btn = await page.$('[role="dialog"] button:has-text("Later"), [role="dialog"] button:has-text("Close"), [role="dialog"] button[aria-label="Close"]')
    if (btn) await btn.click().catch(() => {})
    await page.waitForTimeout(400)
  }
}

;(async () => {
  const browser = await chromium.launch({ executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true })
  const report = []
  for (const [role, spec] of Object.entries(PLAN)) {
    if (ONLY && ONLY !== role) continue
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.25 })
    const page = await ctx.newPage()
    try {
      if (spec.user) await login(page, spec.user, spec.type)
      for (const [name, target, action] of spec.shots) {
        let url = target
        if (typeof target === 'object') {
          await page.goto(BASE + target.from); await settle(page)
          const hrefs = await page.$$eval('a[href]', (as) => as.map((a) => a.getAttribute('href')))
          url = hrefs.find((h) => target.match.test(h))
          if (!url) { report.push(`${name}: no detail link on ${target.from}`); continue }
        }
        await page.goto(BASE + url); await settle(page)
        if (action === 'hindi') {
          const b = await page.$('button:has-text("हिं")'); if (b) { await b.click(); await page.waitForTimeout(1200) }
        }
        await page.screenshot({ path: path.join(OUT, name + '.png') })
        report.push(`${name}: ${url}`)
        if (action === 'hindi') await page.evaluate(() => localStorage.setItem('oms.lang', 'en'))
      }
    } catch (e) { report.push(`${role}: ERROR ${e.message}`) }
    await ctx.close()
  }
  await browser.close()
  console.log(report.join('\n'))
})()
