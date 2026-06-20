'use client'

import { useEffect, useState } from 'react'
import { supabase, Aporte } from '@/lib/supabase'
import { TrendingUp, ExternalLink, CheckCircle, XCircle, Clock, LayoutList, Grid3x3 } from 'lucide-react'

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
  avalado: <CheckCircle className="w-3 h-3 text-green-400 shrink-0" />,
  rechazado: <XCircle className="w-3 h-3 text-red-400 shrink-0" />,
  pendiente: <Clock className="w-3 h-3 text-yellow-400 shrink-0" />,
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
  const [vista, setVista] = useState<'grilla' | 'detalle'>('detalle')

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
      if (!mapa[key].aportesPorMes[a.mes]) mapa[key].aportesPorMes[a.mes] = []
      mapa[key].aportesPorMes[a.mes].push(a)
      const valor = parseFloat(String(a.valor).replace(/[^0-9.]/g, '')) || 0
      mapa[key].total += valor
      totMes[a.mes] = (totMes[a.mes] || 0) + valor
      totGen += valor
    }

    setFilas(Object.values(mapa).sort((a, b) => a.patrocinador.localeCompare(b.patrocinador)))
    setTodos(((aportes || []) as AporteConAval[]).sort((a, b) => a.patrocinador.localeCompare(b.patrocinador)))
    setTotalesMes(totMes)
    setTotalGeneral(totGen)
    setLoading(false)
  }

  const fmt = (val: number) => val === 0 ? '' : '$' + val.toLocaleString('es-CO')

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-blue-400" />
          <h1 className="text-lg font-semibold text-white">Resumen Anual de Aportes</h1>
        </div>
        <div className="flex gap-2 sm:ml-auto flex-wrap">
          {/* Toggle vista */}
          <div className="flex bg-gray-900 border border-gray-700 rounded-lg overflow-hidden">
            <button onClick={() => setVista('detalle')}
              className={`flex items-center gap-1.5 px-3 py-2 text-xs transition-colors ${vista === 'detalle' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'}`}>
              <LayoutList className="w-3.5 h-3.5" /> Detalle
            </button>
            <button onClick={() => setVista('grilla')}
              className={`flex items-center gap-1.5 px-3 py-2 text-xs transition-colors ${vista === 'grilla' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'}`}>
              <Grid3x3 className="w-3.5 h-3.5" /> Grilla
            </button>
          </div>
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
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <div className="text-2xl font-bold text-white">{filas.length}</div>
          <div className="text-xs text-gray-400 mt-1">Patrocinadores</div>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <div className="text-2xl font-bold text-white">{todos.length}</div>
          <div className="text-xs text-gray-400 mt-1">Aportes en {añoSeleccionado}</div>
        </div>
        <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-xl p-4">
          <div className="text-2xl font-bold text-yellow-400">
            {todos.filter(a => !a.estado || a.estado === 'pendiente').length}
          </div>
          <div className="text-xs text-yellow-400/70 mt-1">Pendientes de aval</div>
        </div>
        <div className="bg-green-500/10 border border-green-500/20 rounded-xl p-4">
          <div className="text-2xl font-bold text-green-400">${totalGeneral.toLocaleString('es-CO')}</div>
          <div className="text-xs text-green-400/70 mt-1">Total recaudado</div>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-16 text-gray-500">Cargando resumen...</div>
      ) : filas.length === 0 ? (
        <div className="text-center py-16 text-gray-500">Sin aportes para {zonaSeleccionada} en {añoSeleccionado}.</div>
      ) : vista === 'detalle' ? (
        /* Vista Detalle — como el Excel */
        <div className="overflow-x-auto rounded-xl border border-gray-800">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-900 border-b border-gray-800 text-xs text-gray-400">
                <th className="text-left px-4 py-3 sticky left-0 bg-gray-900 min-w-[180px]">Patrocinador</th>
                <th className="text-left px-3 py-3 whitespace-nowrap">Cédula</th>
                <th className="text-left px-3 py-3 whitespace-nowrap">Mes</th>
                <th className="text-left px-3 py-3 whitespace-nowrap">Valor</th>
                <th className="text-left px-3 py-3 whitespace-nowrap">Método</th>
                <th className="text-left px-3 py-3 whitespace-nowrap">Comprobante</th>
                <th className="text-left px-3 py-3 whitespace-nowrap">Banco</th>
                <th className="text-left px-3 py-3 whitespace-nowrap">Fecha aporte</th>
                <th className="text-left px-3 py-3 whitespace-nowrap">Estado</th>
                <th className="text-left px-3 py-3 whitespace-nowrap">PDF</th>
              </tr>
            </thead>
            <tbody>
              {todos.map((a, i) => {
                const estado = a.estado ?? 'pendiente'
                return (
                  <tr key={a.id}
                    className={`border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors ${i % 2 === 0 ? '' : 'bg-gray-900/30'}`}>
                    <td className="px-4 py-2.5 sticky left-0 bg-gray-950 font-medium text-white text-xs">{a.patrocinador}</td>
                    <td className="px-3 py-2.5 text-gray-400 text-xs whitespace-nowrap">{a.cedula}</td>
                    <td className="px-3 py-2.5 text-gray-200 text-xs whitespace-nowrap">{a.mes}</td>
                    <td className="px-3 py-2.5 text-green-400 font-semibold text-xs whitespace-nowrap">${a.valor}</td>
                    <td className="px-3 py-2.5 text-gray-300 text-xs whitespace-nowrap">{a.metodo}</td>
                    <td className="px-3 py-2.5 text-gray-400 text-xs whitespace-nowrap">{a.comprobante}</td>
                    <td className="px-3 py-2.5 text-gray-400 text-xs whitespace-nowrap">{a.banco}</td>
                    <td className="px-3 py-2.5 text-gray-400 text-xs whitespace-nowrap">{a.fecha_aporte}</td>
                    <td className="px-3 py-2.5 text-xs whitespace-nowrap">
                      <div className="flex items-center gap-1.5">
                        {ESTADO_ICON[estado]}
                        <span className={
                          estado === 'avalado' ? 'text-green-400' :
                          estado === 'rechazado' ? 'text-red-400' : 'text-yellow-400'
                        }>
                          {estado.charAt(0).toUpperCase() + estado.slice(1)}
                        </span>
                      </div>
                      {estado === 'rechazado' && a.comentario_revision && (
                        <div className="text-[10px] text-red-300/70 mt-0.5 max-w-[160px] truncate" title={a.comentario_revision}>
                          {a.comentario_revision}
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-2.5">
                      {a.public_url && (
                        <a href={a.public_url} target="_blank" rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-blue-400 hover:text-blue-300 text-xs">
                          Ver <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-gray-700 bg-gray-900 text-xs">
                <td colSpan={3} className="px-4 py-3 text-gray-400 font-semibold sticky left-0 bg-gray-900">
                  Total — {todos.length} aportes
                </td>
                <td className="px-3 py-3 text-green-400 font-bold">${totalGeneral.toLocaleString('es-CO')}</td>
                <td colSpan={6} />
              </tr>
            </tfoot>
          </table>
        </div>
      ) : (
        /* Vista Grilla — mensual */
        <div className="overflow-x-auto rounded-xl border border-gray-800">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-900 border-b border-gray-800">
                <th className="text-left px-4 py-3 text-gray-400 font-medium whitespace-nowrap sticky left-0 bg-gray-900 min-w-[200px]">Patrocinador</th>
                {MESES_SHORT.map(m => (
                  <th key={m} className="text-center px-2 py-3 text-gray-400 font-medium whitespace-nowrap min-w-[70px] text-xs">{m}</th>
                ))}
                <th className="text-right px-4 py-3 text-gray-400 font-medium whitespace-nowrap">Total</th>
              </tr>
            </thead>
            <tbody>
              {filas.map((fila, i) => (
                <tr key={fila.cedula}
                  className={`border-b border-gray-800/50 hover:bg-gray-800/30 ${i % 2 === 0 ? '' : 'bg-gray-900/30'}`}>
                  <td className="px-4 py-2.5 sticky left-0 bg-gray-950">
                    <div className="font-medium text-white text-sm">{fila.patrocinador}</div>
                    <div className="text-xs text-gray-500">CC: {fila.cedula}</div>
                  </td>
                  {MESES.map(mes => {
                    const aps = fila.aportesPorMes[mes]
                    const valor = aps?.reduce((acc, a) => acc + (parseFloat(String(a.valor).replace(/[^0-9.]/g, '')) || 0), 0) || 0
                    return (
                      <td key={mes} className="text-center px-2 py-2.5">
                        {aps?.length ? (
                          <span className="inline-flex flex-col items-center gap-0.5">
                            <span className="text-green-400 font-medium text-xs">{fmt(valor)}</span>
                            {aps.map(a => a.public_url ? (
                              <a key={a.id} href={a.public_url} target="_blank" rel="noopener noreferrer"
                                className="text-[10px] text-blue-400 hover:text-blue-300 underline">ver</a>
                            ) : null)}
                          </span>
                        ) : <span className="text-gray-700">—</span>}
                      </td>
                    )
                  })}
                  <td className="text-right px-4 py-2.5 text-green-400 font-bold">${fila.total.toLocaleString('es-CO')}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-gray-700 bg-gray-900">
                <td className="px-4 py-3 text-gray-400 font-semibold sticky left-0 bg-gray-900 text-xs">Total por mes</td>
                {MESES.map(mes => (
                  <td key={mes} className="text-center px-2 py-3 text-blue-400 font-semibold text-xs">
                    {totalesMes[mes] ? '$' + totalesMes[mes].toLocaleString('es-CO') : '—'}
                  </td>
                ))}
                <td className="text-right px-4 py-3 text-green-400 font-bold">${totalGeneral.toLocaleString('es-CO')}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </div>
  )
}
