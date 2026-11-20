// Master registry admin: entities, substations, grid elements (22 types), ownership changes (FRD RTO-15..20, UM-24).
import { useEffect, useState } from 'react'
import { api, errMsg } from '../../api/client'
import { useAutoRefresh, useRecentPages } from '../../store/hooks'
import SpreadsheetGrid from '../../components/common/SpreadsheetGrid'
import { Alert, Badge, Button, Card, Field, PageHeader, Tabs, inputCls } from '../../components/common/ui'

export default function MasterPage() {
  useRecentPages('Master registry')
  const [tab, setTab] = useState('elements')
  const { data: elements, reload } = useAutoRefresh<any[]>('/master/elements', undefined, { live: false })
  const { data: entities } = useAutoRefresh<any[]>('/master/entities', undefined, { live: false })
  const { data: subs } = useAutoRefresh<any[]>('/master/substations', undefined, { live: false })
  const { data: changes, reload: reloadChanges } = useAutoRefresh<any[]>('/master/ownership-changes', undefined, { live: false })
  const [types, setTypes] = useState<any[]>([])
  const [f, setF] = useState({ name: '', element_type: 'AC_LINE', centre_code: 'NRLDC', voltage_kv: 400, rating: '', from_substation_id: '', to_substation_id: '' })
  const [msg, setMsg] = useState<{ kind: 'success' | 'error'; text: string } | null>(null)
  useEffect(() => { api.get('/master/element-types').then((r) => setTypes(r.data)) }, [])
  return (
    <div className="space-y-3">
      <PageHeader title="Master registry" subtitle="Single master database used by all modules: entities, substations, elements with Unique Element IDs." />
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
      <Tabs active={tab} onChange={setTab} tabs={[{ key: 'elements', label: 'Grid elements', count: elements?.length }, { key: 'entities', label: 'Entities', count: entities?.length }, { key: 'subs', label: 'Substations', count: subs?.length }, { key: 'own', label: 'Ownership changes', count: changes?.filter((c) => c.status === 'PENDING').length }]} />
      {tab === 'elements' && (<>
        <Card title="Add element (ID auto-generated)">
          <div className="grid gap-2 md:grid-cols-7">
            <input aria-label="Name" placeholder="Element name" className={inputCls} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
            <select aria-label="Type" className={inputCls} value={f.element_type} onChange={(e) => setF({ ...f, element_type: e.target.value })}>{types.map((t) => <option key={t.code} value={t.code}>{t.label}</option>)}</select>
            <select aria-label="Centre" className={inputCls} value={f.centre_code} onChange={(e) => setF({ ...f, centre_code: e.target.value })}>{['NRLDC', 'ERLDC', 'WRLDC', 'SRLDC', 'NERLDC', 'NLDC'].map((c) => <option key={c}>{c}</option>)}</select>
            <input aria-label="kV" type="number" className={inputCls} value={f.voltage_kv} onChange={(e) => setF({ ...f, voltage_kv: Number(e.target.value) })} />
            <select aria-label="From" className={inputCls} value={f.from_substation_id} onChange={(e) => setF({ ...f, from_substation_id: e.target.value })}><option value="">From S/S</option>{subs?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
            <select aria-label="To" className={inputCls} value={f.to_substation_id} onChange={(e) => setF({ ...f, to_substation_id: e.target.value })}><option value="">To S/S</option>{subs?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
            <Button onClick={async () => { try { const { data } = await api.post('/master/elements', { ...f, from_substation_id: f.from_substation_id ? Number(f.from_substation_id) : null, to_substation_id: f.to_substation_id ? Number(f.to_substation_id) : null }); setMsg({ kind: 'success', text: `Created ${data.unique_element_id}` }); reload() } catch (e) { setMsg({ kind: 'error', text: errMsg(e) }) } }}>Add</Button>
          </div>
        </Card>
        <SpreadsheetGrid exportName="grid_elements" rows={elements ?? []} columns={[{ key: 'unique_element_id', label: 'Unique ID' }, { key: 'name', label: 'Element' }, { key: 'element_type_label', label: 'Type' }, { key: 'voltage_kv', label: 'kV' }, { key: 'centre', label: 'Centre' },
          { key: 'owners', label: 'Owners', exportValue: (r) => r.owners.map((o: any) => `${o.entity}(${o.role}${o.section_km ? ' ' + o.section_km + 'km' : ''})`).join(', ') },
          { key: 'status', label: 'Status', render: (r) => <Badge>{r.status}</Badge> }, { key: 'ftc_date', label: 'FTC' }]} />
      </>)}
      {tab === 'entities' && <SpreadsheetGrid exportName="entities" rows={entities ?? []} columns={[{ key: 'name', label: 'Name' }, { key: 'entity_type', label: 'Type' }, { key: 'sub_category', label: 'Sub-category' }, { key: 'sector', label: 'Sector' }, { key: 'state', label: 'State' }, { key: 'fnc_reg_no', label: 'F&C reg.' }, { key: 'nsws_reg_no', label: 'NSWS' }, { key: 'status', label: 'Status' },
        { key: 'x', label: 'Ownership', render: (r) => <Button size="sm" variant="ghost" onClick={() => { const n = prompt('New owner / name'); if (n) api.post(`/master/entities/${r.id}/ownership-change`, { new_owner: n }).then(reloadChanges) }}>Change…</Button> }]} />}
      {tab === 'subs' && <SpreadsheetGrid exportName="substations" rows={subs ?? []} columns={[{ key: 'code', label: 'Code' }, { key: 'name', label: 'Name' }, { key: 'centre', label: 'Centre' }, { key: 'state', label: 'State' }, { key: 'voltage_levels', label: 'kV', exportValue: (r) => r.voltage_levels.join('/') }, { key: 'substation_type', label: 'Type' }, { key: 'owner', label: 'Owner' }, { key: 'weather_area', label: 'Weather area' }]} />}
      {tab === 'own' && <SpreadsheetGrid exportName="ownership_changes" rows={changes ?? []} columns={[{ key: 'previous_owner', label: 'Previous' }, { key: 'new_owner', label: 'New' }, { key: 'status', label: 'Status', render: (r) => <Badge>{r.status}</Badge> },
        { key: 'x', label: 'Admin approval', render: (r) => r.status === 'PENDING' && <div className="flex gap-1"><Button size="sm" variant="success" onClick={() => api.post(`/master/ownership-changes/${r.id}/decide`, null, { params: { approve: true } }).then(reloadChanges)}>Approve</Button><Button size="sm" variant="danger" onClick={() => api.post(`/master/ownership-changes/${r.id}/decide`, null, { params: { approve: false } }).then(reloadChanges)}>Reject</Button></div> }]} />}
      <Field label=""><span /></Field>
    </div>
  )
}
