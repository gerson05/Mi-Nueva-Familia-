'use client'

import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import { CheckCircle, XCircle, Clock, ExternalLink, ClipboardList } from 'lucide-react'

type RegistroAval = {
  id: string
  patrocinador: string
  cedula: string
  zona: string
  mes: string
  año: string
  valor: string
  estado: 'avalado' | 'rechazado' | 'pendiente'
  fecha_revision: string | null
  comentario_revision: string | null
  public_url: string | null
}

const ESTADO_STYLES = {
  avalado: { cls: 'bg-green-500/10 text-green-400 border-green-500/20', Icon: CheckCircle, label: 'Avalado' },
  rechazado: { cls: 'bg-red-500/10 text-red-400 border-red-500/20', Icon: XCircle, label: 'Rechazado' },
  pendiente: { cls: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20', Icon: Clock, label: 'Pendiente' },
}

function fmtFechaHora(f: string | null) {
  if (!f) return '—'
  return new Date(f).toLocaleString('es-CO', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export default function HistorialAval() {
  const [registros, setRegistros] = useState<RegistroAval[]>([])
  const [loading, setLoading] = useState(true)
  const [filtroEstado, setFiltroEstado] = useState<'todos' | 'avalado' | 'rechazado' | 'pendiente'>('todos')
  const [filtroZona, setFiltroZona] = useState<string>('todas')
  const [filtroAño, setFiltroAño] = useState<string>('todos')
  const [zonas, setZonas] = useState<string[]>([])
  const [años, setAños] = useState<string[]>([])

  useEffect(() => { cargar() }, [])

  async function cargar() {
    setLoading(true)
    const { data } = await supabase
      .from('aportes')
      .select('id, patrocinador, cedula, zona, mes, año, valor, estado, fecha_revision, comentario_revision, public_url')
      .order('fecha_revision', { ascending: false, nullsFirst: false })

    const lista = (data || []) as unknown as RegistroAval[]
    setRegistros(lista)
    setZonas([...new Set(lista.map(r => r.zona))].sort())
    setAños([...new Set((lista as any[]).map(r => r.año as string))].sort((a, b) => Number(b) - Number(a)))
    setLoading(false)
  }

  const filtrados = registros.filter(r => {
    if (filtroEstado !== 'todos' && (r.estado ?? 'pendiente') !== filtroEstado) return false
    if (filtroZona !== 'todas' && r.zona !== filtroZona) return false
    if (filtroAño !== 'todos' && (r as any).año !== filtroAño) return false
    return true
  })

  const totalAvalados = filtrados.filter(r => r.estado === 'avalado').length
  const totalRechazados = filtrados.filter(r => r.estado === 'rechazado').length
  const totalPendientes = filtrados.filter(r => !r.estado || r.estado === 'pendiente').length
  const valorAvalado = filtrados
    .filter(r => r.estado === 'avalado')
    .reduce((acc, r) => acc + (parseFloat(String(r.valor).replace(/[^0-9.]/g, '')) || 0), 0)

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <ClipboardList className="w-5 h-5 text-blue-400" />
        <h1 className="text-lg font-semibold text-white">Historial de Avales</h1>
      </div>

      {/* Tarjetas */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-green-500/10 border border-green-500/20 rounded-xl p-4">
          <div className="text-2xl font-bold text-green-400">{totalAvalados}</div>
          <div className="text-xs text-green-400/70 mt-1">Avalados</div>
        </div>
        <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4">
          <div className="text-2xl font-bold text-red-400">{totalRechazados}</div>
          <div className="text-xs text-red-400/70 mt-1">Rechazados</div>
        </div>
        <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-xl p-4">
          <div className="text-2xl font-bold text-yellow-400">{totalPendientes}</div>
          <div className="text-xs text-yellow-400/70 mt-1">Pendientes</div>
        </div>
        <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-4">
          <div className="text-xl font-bold text-blue-400">${valorAvalado.toLocaleString('es-CO')}</div>
          <div className="text-xs text-blue-400/70 mt-1">Valor avalado</div>
        </div>
      </div>

      {/* Filtros */}
      <div className="flex flex-wrap gap-3">
        <select value={filtroEstado} onChange={e => setFiltroEstado(e.target.value as any)}
          className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500">
          <option value="todos">Todos los estados</option>
          <option value="avalado">Avalados</option>
          <option value="rechazado">Rechazados</option>
          <option value="pendiente">Pendientes</option>
        </select>
        <select value={filtroZona} onChange={e => setFiltroZona(e.target.value)}
          className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500">
          <option value="todas">Todas las zonas</option>
          {zonas.map(z => <option key={z} value={z}>{z}</option>)}
        </select>
        <select value={filtroAño} onChange={e => setFiltroAño(e.target.value)}
          className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500">
          <option value="todos">Todos los años</option>
          {años.map(a => <option key={a} value={a}>{a}</option>)}
        </select>
        <span className="ml-auto self-center text-xs text-gray-500">{filtrados.length} registros</span>
      </div>

      {/* Tabla */}
      {loading ? (
        <div className="text-center py-16 text-gray-500">Cargando historial...</div>
      ) : filtrados.length === 0 ? (
        <div className="text-center py-16 text-gray-500">Sin registros.</div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-800">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-900 border-b border-gray-800 text-xs text-gray-400">
                <th className="text-left px-4 py-3 sticky left-0 bg-gray-900 min-w-[180px]">Patrocinador</th>
                <th className="text-left px-3 py-3 whitespace-nowrap">Zona</th>
                <th className="text-left px-3 py-3 whitespace-nowrap">Mes / Año</th>
                <th className="text-left px-3 py-3 whitespace-nowrap">Valor</th>
                <th className="text-left px-3 py-3 whitespace-nowrap">Estado</th>
                <th className="text-left px-3 py-3 whitespace-nowrap">Fecha revisión</th>
                <th className="text-left px-3 py-3 whitespace-nowrap">Observación</th>
                <th className="text-left px-3 py-3 whitespace-nowrap">PDF</th>
              </tr>
            </thead>
            <tbody>
              {filtrados.map((r, i) => {
                const estado = (r.estado ?? 'pendiente') as 'avalado' | 'rechazado' | 'pendiente'
                const { cls, Icon, label } = ESTADO_STYLES[estado]
                return (
                  <tr key={r.id}
                    className={`border-b border-gray-800/50 hover:bg-gray-800/20 transition-colors ${i % 2 === 0 ? '' : 'bg-gray-900/20'}`}>
                    <td className="px-4 py-3 sticky left-0 bg-gray-950">
                      <div className="font-medium text-white text-sm">{r.patrocinador}</div>
                      <div className="text-xs text-gray-500">CC: {r.cedula}</div>
                    </td>
                    <td className="px-3 py-3 text-gray-400 text-xs whitespace-nowrap">{r.zona}</td>
                    <td className="px-3 py-3 text-gray-300 text-xs whitespace-nowrap">{r.mes} {(r as any).año}</td>
                    <td className="px-3 py-3 text-green-400 font-semibold text-xs whitespace-nowrap">${r.valor}</td>
                    <td className="px-3 py-3">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md border text-xs font-medium ${cls}`}>
                        <Icon className="w-3 h-3" /> {label}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-gray-400 text-xs whitespace-nowrap">{fmtFechaHora(r.fecha_revision)}</td>
                    <td className="px-3 py-3 text-xs max-w-[200px]">
                      {r.comentario_revision
                        ? <span className="text-red-300/80">{r.comentario_revision}</span>
                        : <span className="text-gray-700">—</span>}
                    </td>
                    <td className="px-3 py-3">
                      {r.public_url && (
                        <a href={r.public_url} target="_blank" rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-blue-400 hover:text-blue-300 text-xs underline">
                          Ver <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
