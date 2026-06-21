'use client'

import { useEffect, useState } from 'react'
import { supabase, Aporte } from '@/lib/supabase'
import { TrendingUp, CheckCircle, XCircle, Clock, X, Users, FileText, DollarSign } from 'lucide-react'

const MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
const MESES_SHORT = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
  'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']

type AporteConAval = Aporte & {
  estado?: 'pendiente' | 'avalado' | 'rechazado'
  comentario_revision?: string
}

type FilaPatrocinador = {
  patrocinador: string
  cedula: string
  aportesPorMes: Record<string, AporteConAval[]>
  total: number
}

const ESTADO_ICON = {
  avalado: <CheckCircle className="w-4 h-4 text-green-400" />,
  rechazado: <XCircle className="w-4 h-4 text-red-400" />,
  pendiente: <Clock className="w-4 h-4 text-yellow-400" />,
}
const ESTADO_LABEL = { avalado: 'Avalado', rechazado: 'Rechazado', pendiente: 'Pendiente' }
const ESTADO_COLOR = {
  avalado: 'text-green-400',
  rechazado: 'text-red-400',
  pendiente: 'text-yellow-400',
}

export default function ResumenPage() {
  const [zonas, setZonas] = useState<string[]>([])
  const [zonaSeleccionada, setZonaSeleccionada] = useState<string>('')
  const [añoSeleccionado, setAñoSeleccionado] = useState<string>(new Date().getFullYear().toString())
  const [años, setAños] = useState<string[]>([])
  const [filas, setFilas] = useState<FilaPatrocinador[]>([])
  const [todos, setTodos] = useState<AporteConAval[]>([])
  const [loading, setLoading] = useState(true)
  const [totalesMes, setTotalesMes] = useState<Record<string, number>>({})
  const [totalGeneral, setTotalGeneral] = useState(0)
  const [detalle, setDetalle] = useState<{ patrocinador: string; mes: string; aportes: AporteConAval[] } | null>(null)

  useEffect(() => { cargarMetadata() }, [])
  useEffect(() => { if (zonaSeleccionada) cargarResumen() }, [zonaSeleccionada, añoSeleccionado])

  async function cargarMetadata() {
    const { data } = await supabase.from('aportes').select('zona, año')
    if (!data) return
    const zonasUnicas = [...new Set((data as any[]).map(r => r.zona as string))].sort()
    const añosUnicos = [...new Set((data as any[]).map(r => r.año as string))].sort((a, b) => Number(b) - Number(a))
    setZonas(zonasUnicas)
    setAños(añosUnicos)
    if (zonasUnicas.length > 0) setZonaSeleccionada(zonasUnicas[0])
    if (añosUnicos.length > 0 && !añosUnicos.includes(añoSeleccionado)) setAñoSeleccionado(añosUnicos[0])
  }

  async function cargarResumen() {
    setLoading(true)
    const { data: aportes } = await supabase
      .from('aportes').select('*')
      .eq('zona', zonaSeleccionada).eq('año', añoSeleccionado)
      .order('patrocinador')

    const mapa: Record<string, FilaPatrocinador> = {}
    const totMes: Record<string, number> = {}
    let totGen = 0

    for (const a of (aportes || []) as AporteConAval[]) {
      const key = a.cedula
      if (!mapa[key]) mapa[key] = { patrocinador: a.patrocinador, cedula: a.cedula, aportesPorMes: {}, total: 0 }
      const mesNorm = a.mes.charAt(0).toUpperCase() + a.mes.slice(1).toLowerCase()
      if (!mapa[key].aportesPorMes[mesNorm]) mapa[key].aportesPorMes[mesNorm] = []
      mapa[key].aportesPorMes[mesNorm].push(a)
      const valor = parseFloat(String(a.valor).replace(/[^0-9.]/g, '')) || 0
      mapa[key].total += valor
      totMes[mesNorm] = (totMes[mesNorm] || 0) + valor
      totGen += valor
    }

    setFilas(Object.values(mapa).sort((a, b) => a.patrocinador.localeCompare(b.patrocinador)))
    setTodos((aportes || []) as AporteConAval[])
    setTotalesMes(totMes)
    setTotalGeneral(totGen)
    setLoading(false)
  }

  const fmt = (val: number) => '$' + val.toLocaleString('es-CO')

  function abrirDetalle(fila: FilaPatrocinador, mes: string) {
    const aps = fila.aportesPorMes[mes]
    if (!aps?.length) return
    setDetalle({ patrocinador: fila.patrocinador, mes, aportes: aps })
  }

  function estadoCelda(aps: AporteConAval[]) {
    if (aps.some(a => a.estado === 'rechazado')) return 'rechazado'
    if (aps.every(a => a.estado === 'avalado')) return 'avalado'
    return 'pendiente'
  }

  const CELL_COLORS: Record<string, string> = {
    avalado: 'bg-green-500/15 border-green-500/30 text-green-400 hover:bg-green-500/25',
    rechazado: 'bg-red-500/15 border-red-500/30 text-red-400 hover:bg-red-500/25',
    pendiente: 'bg-yellow-500/10 border-yellow-500/20 text-yellow-300 hover:bg-yellow-500/20',
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-blue-400" />
          <h1 className="text-lg font-semibold text-white">Resumen Anual de Aportes</h1>
        </div>
        <div className="flex gap-2 sm:ml-auto">
          <select value={añoSeleccionado} onChange={e => setAñoSeleccionado(e.target.value)}
            className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500">
            {años.map(a => <option key={a} value={a}>{a}</option>)}
          </select>
          <select value={zonaSeleccionada} onChange={e => setZonaSeleccionada(e.target.value)}
            className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500">
            {zonas.map(z => <option key={z} value={z}>{z}</option>)}
          </select>
        </div>
      </div>

      {/* Tarjetas */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-gray-800 flex items-center justify-center shrink-0">
            <Users className="w-5 h-5 text-gray-300" />
          </div>
          <div>
            <div className="text-2xl font-bold text-white">{filas.length}</div>
            <div className="text-xs text-gray-400 mt-0.5">Patrocinadores</div>
          </div>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-gray-800 flex items-center justify-center shrink-0">
            <FileText className="w-5 h-5 text-gray-300" />
          </div>
          <div>
            <div className="text-2xl font-bold text-white">{todos.length}</div>
            <div className="text-xs text-gray-400 mt-0.5">Aportes en {añoSeleccionado}</div>
          </div>
        </div>
        <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-xl p-4 flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-yellow-500/20 flex items-center justify-center shrink-0">
            <Clock className="w-5 h-5 text-yellow-400" />
          </div>
          <div>
            <div className="text-2xl font-bold text-yellow-400">
              {todos.filter(a => !a.estado || a.estado === 'pendiente').length}
            </div>
            <div className="text-xs text-yellow-400/70 mt-0.5">Pendientes de aval</div>
          </div>
        </div>
        <div className="bg-green-500/10 border border-green-500/20 rounded-xl p-4 flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-green-500/20 flex items-center justify-center shrink-0">
            <DollarSign className="w-5 h-5 text-green-400" />
          </div>
          <div>
            <div className="text-2xl font-bold text-green-400">{fmt(totalGeneral)}</div>
            <div className="text-xs text-green-400/70 mt-0.5">Total recaudado</div>
          </div>
        </div>
      </div>

      <p className="text-xs text-gray-500">Haz clic en una celda de mes para ver el detalle completo del aporte.</p>

      {loading ? (
        <div className="text-center py-16 text-gray-500">Cargando resumen...</div>
      ) : filas.length === 0 ? (
        <div className="text-center py-16 text-gray-500">Sin aportes para {zonaSeleccionada} en {añoSeleccionado}.</div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-800">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-900 border-b border-gray-800">
                <th className="text-left px-4 py-3 text-gray-400 font-medium sticky left-0 bg-gray-900 min-w-[200px]">Patrocinador</th>
                {MESES_SHORT.map(m => (
                  <th key={m} className="text-center px-2 py-3 text-gray-400 font-medium whitespace-nowrap min-w-[60px] text-xs">{m}</th>
                ))}
                <th className="text-right px-4 py-3 text-gray-400 font-medium whitespace-nowrap">Total</th>
              </tr>
            </thead>
            <tbody>
              {filas.map((fila, i) => (
                <tr key={fila.cedula} className={`border-b border-gray-800/50 ${i % 2 === 0 ? '' : 'bg-gray-900/20'}`}>
                  <td className="px-4 py-3 sticky left-0 bg-gray-950">
                    <div className="font-medium text-white text-sm">{fila.patrocinador}</div>
                    <div className="text-xs text-gray-500">CC: {fila.cedula}</div>
                  </td>
                  {MESES.map(mes => {
                    const aps = fila.aportesPorMes[mes]
                    if (!aps?.length) {
                      return <td key={mes} className="text-center px-2 py-3 text-gray-700 text-xs">—</td>
                    }
                    const valor = aps.reduce((acc, a) => acc + (parseFloat(String(a.valor).replace(/[^0-9.]/g, '')) || 0), 0)
                    const estado = estadoCelda(aps)
                    return (
                      <td key={mes} className="text-center px-1 py-2">
                        <button
                          onClick={() => abrirDetalle(fila, mes)}
                          className={`w-full rounded-md border px-1 py-1.5 text-xs font-medium transition-colors cursor-pointer ${CELL_COLORS[estado]}`}
                          title={`${mes}: ${fmt(valor)} — Clic para ver detalle`}>
                          {fmt(valor)}
                        </button>
                      </td>
                    )
                  })}
                  <td className="text-right px-4 py-3 text-green-400 font-bold">{fmt(fila.total)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-gray-700 bg-gray-900">
                <td className="px-4 py-3 text-gray-400 font-semibold sticky left-0 bg-gray-900 text-xs">Total por mes</td>
                {MESES.map(mes => (
                  <td key={mes} className="text-center px-2 py-3 text-blue-400 font-semibold text-xs">
                    {totalesMes[mes] ? fmt(totalesMes[mes]) : '—'}
                  </td>
                ))}
                <td className="text-right px-4 py-3 text-green-400 font-bold">{fmt(totalGeneral)}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}

      {/* Modal detalle */}
      {detalle && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => setDetalle(null)} />
          <div className="relative bg-gray-900 border border-gray-800 rounded-xl w-full max-w-lg shadow-2xl">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
              <div>
                <h2 className="text-base font-semibold text-white">{detalle.patrocinador}</h2>
                <p className="text-xs text-gray-400 mt-0.5">{detalle.mes} {añoSeleccionado} · {zonaSeleccionada}</p>
              </div>
              <button onClick={() => setDetalle(null)} className="text-gray-400 hover:text-white text-2xl leading-none"><X className="w-5 h-5" /></button>
            </div>
            <div className="px-6 py-4 space-y-3">
              {detalle.aportes.map(a => {
                const estado = a.estado ?? 'pendiente'
                return (
                  <div key={a.id} className="bg-gray-800 rounded-lg p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {ESTADO_ICON[estado]}
                        <span className={`text-sm font-semibold ${ESTADO_COLOR[estado]}`}>{ESTADO_LABEL[estado]}</span>
                      </div>
                      {a.public_url && (
                        <a href={a.public_url} target="_blank" rel="noopener noreferrer"
                          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-blue-500/15 hover:bg-blue-500/25 border border-blue-500/30 hover:border-blue-500/50 text-blue-400 hover:text-blue-300 text-xs font-medium transition-all duration-200 cursor-pointer">
                          <FileText className="w-3 h-3" /> Ver PDF
                        </a>
                      )}
                    </div>
                    <div className="grid grid-cols-2 gap-y-2 gap-x-4 text-sm">
                      <div>
                        <div className="text-xs text-gray-500">Valor</div>
                        <div className="text-green-400 font-bold">${a.valor}</div>
                      </div>
                      <div>
                        <div className="text-xs text-gray-500">Método</div>
                        <div className="text-white">{a.metodo || '—'}</div>
                      </div>
                      <div>
                        <div className="text-xs text-gray-500">Comprobante</div>
                        <div className="text-gray-300">{a.comprobante || '—'}</div>
                      </div>
                      <div>
                        <div className="text-xs text-gray-500">Banco</div>
                        <div className="text-gray-300">{a.banco || '—'}</div>
                      </div>
                      <div>
                        <div className="text-xs text-gray-500">Fecha aporte</div>
                        <div className="text-gray-300">{a.fecha_aporte || '—'}</div>
                      </div>
                      <div>
                        <div className="text-xs text-gray-500">Cédula</div>
                        <div className="text-gray-300">{a.cedula}</div>
                      </div>
                    </div>
                    {estado === 'rechazado' && a.comentario_revision && (
                      <div className="bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                        <div className="text-xs text-red-400 font-medium mb-1">Motivo de rechazo:</div>
                        <div className="text-xs text-red-300">{a.comentario_revision}</div>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
