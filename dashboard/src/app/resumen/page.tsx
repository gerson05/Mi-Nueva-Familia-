'use client'

import { useEffect, useState } from 'react'
import { supabase, Aporte } from '@/lib/supabase'
import { TrendingUp, Download } from 'lucide-react'

const MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

const MESES_SHORT = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
  'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']

type FilaPatrocinador = {
  patrocinador: string
  cedula: string
  aportesPorMes: Record<string, Aporte[]>
  total: number
}

export default function ResumenPage() {
  const [zonas, setZonas] = useState<string[]>([])
  const [zonaSeleccionada, setZonaSeleccionada] = useState<string>('')
  const [añoSeleccionado, setAñoSeleccionado] = useState<string>(new Date().getFullYear().toString())
  const [años, setAños] = useState<string[]>([])
  const [filas, setFilas] = useState<FilaPatrocinador[]>([])
  const [loading, setLoading] = useState(true)
  const [totalesMes, setTotalesMes] = useState<Record<string, number>>({})
  const [totalGeneral, setTotalGeneral] = useState(0)

  useEffect(() => {
    cargarMetadata()
  }, [])

  useEffect(() => {
    if (zonaSeleccionada) cargarResumen()
  }, [zonaSeleccionada, añoSeleccionado])

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
      .from('aportes')
      .select('*')
      .eq('zona', zonaSeleccionada)
      .eq('año', añoSeleccionado)
      .order('patrocinador')

    const mapa: Record<string, FilaPatrocinador> = {}
    const totMes: Record<string, number> = {}
    let totGen = 0

    for (const a of (aportes || [])) {
      const key = a.cedula
      if (!mapa[key]) {
        mapa[key] = { patrocinador: a.patrocinador, cedula: a.cedula, aportesPorMes: {}, total: 0 }
      }
      const mes = a.mes
      if (!mapa[key].aportesPorMes[mes]) mapa[key].aportesPorMes[mes] = []
      mapa[key].aportesPorMes[mes].push(a)

      const valor = parseFloat(String(a.valor).replace(/[^0-9.]/g, '')) || 0
      mapa[key].total += valor
      totMes[mes] = (totMes[mes] || 0) + valor
      totGen += valor
    }

    setFilas(Object.values(mapa).sort((a, b) => a.patrocinador.localeCompare(b.patrocinador)))
    setTotalesMes(totMes)
    setTotalGeneral(totGen)
    setLoading(false)
  }

  function formatValor(val: number) {
    if (val === 0) return ''
    return '$' + val.toLocaleString('es-CO')
  }

  function cellClass(aportes: Aporte[] | undefined) {
    if (!aportes || aportes.length === 0) return 'text-gray-700'
    return 'text-green-400 font-medium'
  }

  return (
    <div className="space-y-6">
      {/* Header filtros */}
      <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-blue-400" />
          <h1 className="text-lg font-semibold text-white">Resumen Anual de Aportes</h1>
        </div>
        <div className="flex gap-2 sm:ml-auto">
          <select
            value={añoSeleccionado}
            onChange={e => setAñoSeleccionado(e.target.value)}
            className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
          >
            {años.map(a => <option key={a} value={a}>{a}</option>)}
          </select>
          <select
            value={zonaSeleccionada}
            onChange={e => setZonaSeleccionada(e.target.value)}
            className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
          >
            {zonas.map(z => <option key={z} value={z}>{z}</option>)}
          </select>
        </div>
      </div>

      {/* Tarjetas resumen */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <div className="text-2xl font-bold text-white">{filas.length}</div>
          <div className="text-xs text-gray-400 mt-1">Patrocinadores</div>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <div className="text-2xl font-bold text-white">
            {filas.reduce((acc, f) => acc + Object.keys(f.aportesPorMes).length, 0)}
          </div>
          <div className="text-xs text-gray-400 mt-1">Aportes en {añoSeleccionado}</div>
        </div>
        <div className="bg-green-500/10 border border-green-500/20 rounded-xl p-4 col-span-2">
          <div className="text-2xl font-bold text-green-400">
            ${totalGeneral.toLocaleString('es-CO')}
          </div>
          <div className="text-xs text-green-400/70 mt-1">Total recaudado {añoSeleccionado}</div>
        </div>
      </div>

      {/* Tabla */}
      {loading ? (
        <div className="text-center py-16 text-gray-500">Cargando resumen...</div>
      ) : filas.length === 0 ? (
        <div className="text-center py-16 text-gray-500">Sin aportes para {zonaSeleccionada} en {añoSeleccionado}.</div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-800">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-900 border-b border-gray-800">
                <th className="text-left px-4 py-3 text-gray-400 font-medium whitespace-nowrap sticky left-0 bg-gray-900 min-w-[200px]">
                  Patrocinador
                </th>
                {MESES_SHORT.map(m => (
                  <th key={m} className="text-center px-2 py-3 text-gray-400 font-medium whitespace-nowrap min-w-[70px]">
                    {m}
                  </th>
                ))}
                <th className="text-right px-4 py-3 text-gray-400 font-medium whitespace-nowrap">
                  Total
                </th>
              </tr>
            </thead>
            <tbody>
              {filas.map((fila, i) => (
                <tr key={fila.cedula}
                  className={`border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors ${i % 2 === 0 ? '' : 'bg-gray-900/30'}`}>
                  <td className="px-4 py-2.5 sticky left-0 bg-gray-950 hover:bg-gray-800/30">
                    <div className="font-medium text-white">{fila.patrocinador}</div>
                    <div className="text-xs text-gray-500">CC: {fila.cedula}</div>
                  </td>
                  {MESES.map(mes => {
                    const aportesMes = fila.aportesPorMes[mes]
                    const valor = aportesMes?.reduce((acc, a) =>
                      acc + (parseFloat(String(a.valor).replace(/[^0-9.]/g, '')) || 0), 0) || 0
                    const tieneAporte = aportesMes && aportesMes.length > 0

                    return (
                      <td key={mes} className="text-center px-2 py-2.5">
                        {tieneAporte ? (
                          <span title={`${mes}: ${formatValor(valor)}`}
                            className="inline-flex flex-col items-center gap-0.5">
                            <span className="text-green-400 font-medium text-xs">
                              {formatValor(valor)}
                            </span>
                            {aportesMes!.map(a => (
                              a.public_url ? (
                                <a key={a.id} href={a.public_url} target="_blank" rel="noopener noreferrer"
                                  className="text-[10px] text-blue-400 hover:text-blue-300 underline">
                                  ver
                                </a>
                              ) : null
                            ))}
                          </span>
                        ) : (
                          <span className="text-gray-700">—</span>
                        )}
                      </td>
                    )
                  })}
                  <td className="text-right px-4 py-2.5 text-green-400 font-bold">
                    ${fila.total.toLocaleString('es-CO')}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-gray-700 bg-gray-900">
                <td className="px-4 py-3 text-gray-400 font-semibold sticky left-0 bg-gray-900">
                  Total por mes
                </td>
                {MESES.map(mes => (
                  <td key={mes} className="text-center px-2 py-3 text-blue-400 font-semibold text-xs">
                    {totalesMes[mes] ? '$' + totalesMes[mes].toLocaleString('es-CO') : '—'}
                  </td>
                ))}
                <td className="text-right px-4 py-3 text-green-400 font-bold">
                  ${totalGeneral.toLocaleString('es-CO')}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </div>
  )
}
