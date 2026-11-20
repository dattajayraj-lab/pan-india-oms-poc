/**
 * Graphical case tracker: Green = completed, Red = pending, Amber = returned, Grey = not reached.
 * Clicking a node shows pending-point details (officer, login, since, remarks, forwarded by/to).
 * (TS Cl. 11.3(m), Fig.38/99; FRD CMN-20)
 */
import { useMemo, useState } from 'react'
import ReactFlow, { Background, MarkerType, type Edge, type Node } from 'reactflow'
import 'reactflow/dist/style.css'
import { fmtDT } from '../../store/hooks'

export interface TrackerStep {
  key: string
  label: string
  state: 'DONE' | 'PENDING' | 'RETURNED' | 'TODO' | string
  at?: string | null
  by?: string
  login?: string
  remarks?: string
  forwarded_to?: string
  lane?: number
}

const COLORS: Record<string, { bg: string; border: string; text: string }> = {
  DONE: { bg: '#dcfce7', border: '#16a34a', text: '#14532d' },
  PENDING: { bg: '#fee2e2', border: '#dc2626', text: '#7f1d1d' },
  RETURNED: { bg: '#fef3c7', border: '#d97706', text: '#78350f' },
  TODO: { bg: '#f1f5f9', border: '#94a3b8', text: '#475569' },
}

export default function CaseFlowchartTracker({ steps, height = 170 }: { steps: TrackerStep[]; height?: number }) {
  const [sel, setSel] = useState<TrackerStep | null>(null)
  const { nodes, edges } = useMemo(() => {
    const laneCount: Record<number, number> = {}
    const nodes: Node[] = steps.map((s, i) => {
      const lane = s.lane ?? 0
      const col = s.lane !== undefined ? (laneCount[lane] = (laneCount[lane] ?? -1) + 1) : i
      const c = COLORS[s.state] ?? COLORS.TODO
      return {
        id: s.key + i,
        position: { x: (s.lane !== undefined ? col : i) * 190, y: lane * 80 + 20 },
        data: { label: <div className="text-[11px] leading-tight"><b>{s.label}</b>{s.at && <div className="opacity-75">{fmtDT(s.at)}</div>}</div> },
        style: { background: c.bg, border: `2px solid ${c.border}`, color: c.text, width: 165, borderRadius: 8, cursor: 'pointer' },
        draggable: false,
      }
    })
    const edges: Edge[] = steps.slice(1).map((s, i) => ({
      id: `e${i}`, source: steps[i].key + i, target: s.key + (i + 1),
      markerEnd: { type: MarkerType.ArrowClosed }, animated: s.state === 'PENDING',
    }))
    return { nodes, edges }
  }, [steps])

  return (
    <div className="relative">
      <div style={{ height }} className="rounded-md border border-slate-200 bg-white" data-testid="case-tracker">
        <ReactFlow nodes={nodes} edges={edges} fitView proOptions={{ hideAttribution: true }} nodesConnectable={false}
          zoomOnScroll={false} panOnScroll onNodeClick={(_, n) => setSel(steps[nodes.findIndex((x) => x.id === n.id)])}>
          <Background gap={16} size={1} />
        </ReactFlow>
      </div>
      <div className="mt-1 flex gap-3 text-[11px] text-slate-500">
        {Object.entries({ DONE: 'Completed', PENDING: 'Pending', RETURNED: 'Returned', TODO: 'Not reached' }).map(([k, v]) => (
          <span key={k} className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: COLORS[k].border }} />{v}</span>
        ))}
        <span className="ml-auto">Click a step for details</span>
      </div>
      {sel && (
        <div role="dialog" className="absolute right-2 top-2 z-10 w-72 rounded-md border bg-white p-3 text-xs shadow-lg">
          <div className="mb-1 flex justify-between font-semibold"><span>{sel.label}</span><button onClick={() => setSel(null)} aria-label="Close">✕</button></div>
          <dl className="grid grid-cols-3 gap-1">
            <dt className="text-slate-500">Status</dt><dd className="col-span-2">{sel.state}</dd>
            <dt className="text-slate-500">{sel.state === 'PENDING' ? 'Pending with' : 'Officer'}</dt><dd className="col-span-2">{sel.by || '—'}</dd>
            {sel.login && (<><dt className="text-slate-500">Login ID</dt><dd className="col-span-2">{sel.login}</dd></>)}
            <dt className="text-slate-500">{sel.state === 'PENDING' ? 'Pending since' : 'Date/time'}</dt><dd className="col-span-2">{sel.at ? fmtDT(sel.at) : '—'}</dd>
            {sel.forwarded_to && (<><dt className="text-slate-500">Forwarded to</dt><dd className="col-span-2">{sel.forwarded_to}</dd></>)}
            <dt className="text-slate-500">Remarks</dt><dd className="col-span-2 whitespace-pre-wrap">{sel.remarks || '—'}</dd>
          </dl>
        </div>
      )}
    </div>
  )
}
