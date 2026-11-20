// Interactive charts with hover tooltips (crosshair across all series) and PNG/CSV download (TS Cl. 11.2(e); FRD CMS-11).
import { useRef } from 'react'
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { Button } from '../common/ui'

export const PALETTE = ['#1f6fb8', '#f28c1b', '#16a34a', '#dc2626', '#7c3aed', '#0891b2', '#ca8a04', '#db2777', '#475569', '#65a30d']

export interface ChartProps {
  type: 'line' | 'bar' | 'pie' | 'stacked' | 'area'
  data: Record<string, any>[]
  xKey: string
  series: string[]
  height?: number
  title?: string
  downloadName?: string
}

export default function DynamicChart({ type, data, xKey, series, height = 260, title, downloadName }: ChartProps) {
  const ref = useRef<HTMLDivElement>(null)
  const downloadPng = () => {
    const svg = ref.current?.querySelector('svg')
    if (!svg) return
    const xml = new XMLSerializer().serializeToString(svg)
    const img = new Image()
    const { width, height: h } = svg.getBoundingClientRect()
    img.onload = () => {
      const c = document.createElement('canvas')
      c.width = width * 2
      c.height = h * 2
      const ctx = c.getContext('2d')!
      ctx.fillStyle = '#fff'
      ctx.fillRect(0, 0, c.width, c.height)
      ctx.scale(2, 2)
      ctx.drawImage(img, 0, 0)
      const a = document.createElement('a')
      a.href = c.toDataURL('image/png')
      a.download = `${downloadName ?? 'chart'}.png`
      a.click()
    }
    img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(xml)))
  }
  const downloadCsv = () => {
    const rows = [[xKey, ...series].join(','), ...data.map((d) => [d[xKey], ...series.map((s) => d[s] ?? '')].join(','))]
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([rows.join('\n')], { type: 'text/csv' }))
    a.download = `${downloadName ?? 'chart'}.csv`
    a.click()
  }
  const common = (
    <>
      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
      <XAxis dataKey={xKey} tick={{ fontSize: 11 }} />
      <YAxis tick={{ fontSize: 11 }} />
      <Tooltip cursor={{ strokeDasharray: '3 3' }} />
      <Legend wrapperStyle={{ fontSize: 11 }} />
    </>
  )
  let chart
  if (type === 'pie') {
    const s = series[0]
    chart = (
      <PieChart>
        <Pie data={data} dataKey={s} nameKey={xKey} outerRadius="75%" label={{ fontSize: 10 }}>
          {data.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
        </Pie>
        <Tooltip /><Legend wrapperStyle={{ fontSize: 11 }} />
      </PieChart>
    )
  } else if (type === 'bar' || type === 'stacked') {
    chart = <BarChart data={data}>{common}{series.map((s, i) => <Bar key={s} dataKey={s} fill={PALETTE[i % PALETTE.length]} stackId={type === 'stacked' ? 'a' : undefined} />)}</BarChart>
  } else if (type === 'area') {
    chart = <AreaChart data={data}>{common}{series.map((s, i) => <Area key={s} type="monotone" dataKey={s} stroke={PALETTE[i % PALETTE.length]} fill={PALETTE[i % PALETTE.length]} fillOpacity={0.2} />)}</AreaChart>
  } else {
    chart = <LineChart data={data}>{common}{series.map((s, i) => <Line key={s} type="monotone" dataKey={s} stroke={PALETTE[i % PALETTE.length]} dot={false} strokeWidth={2} />)}</LineChart>
  }
  return (
    <div>
      {(title || downloadName) && (
        <div className="mb-1 flex items-center justify-between">
          <div className="text-xs font-semibold text-slate-700">{title}</div>
          <div className="flex gap-1">
            <Button size="sm" variant="ghost" onClick={downloadPng}>PNG</Button>
            <Button size="sm" variant="ghost" onClick={downloadCsv}>CSV</Button>
          </div>
        </div>
      )}
      <div ref={ref} style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">{chart}</ResponsiveContainer>
      </div>
    </div>
  )
}

export function objToSeries(o: Record<string, number> | undefined, key = 'name', val = 'value') {
  return Object.entries(o ?? {}).map(([k, v]) => ({ [key]: k, [val]: v }))
}
