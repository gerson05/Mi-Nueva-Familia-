'use client'

import { useEffect, useState, useCallback } from 'react'
import { supabase } from '@/lib/supabase'
import { Search, Users, CheckCircle, XCircle, ExternalLink, AlertTriangle, Clock } from 'lucide-react'

type Patrocinador = {
  id: string
  nombre: string
  cedula: string | null
  zona: string
  telefono: string | null
  estado: 'activo' | 'inactivo'
  fecha_inicio_patrocinio: string | null
  fecha_fin_patrocinio: string | null
  fp_public_url: string | null
  observaciones: string | null
}

function getPatrocinioStatus(fecha_fin: string | null): 'vigente' | 'por_vencer' | 'vencido' | 'sin_fecha' {
  if (!fecha_fin) return 'sin_fecha'
  const hoy = new Date()
  const fin = new Date(fecha_fin)
  const dias = Math.floor((fin.getTime() - hoy.getTime()) / (1000 * 60 * 60 * 24))
  if (dias < 0) return 'vencido'
  if (dias <= 30) return 'por_vencer'
  return 'vigente'
}

const PATROCINIO_STYLES = {
  vigente: 'text-green-400 bg-green-500/10 border-green-500/20',
  por_vencer: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20',
  vencido: 'text-red-400 bg-red-500/10 border-red-500/20',
  sin_fecha: 'text-gray-500 bg-gray-800 border-gray-700',
}
const PATROCINIO_LABEL = {
  vigente: 'Vigente',
  por_vencer: 'Por vencer',
  vencido: 'Vencido',
  sin_fecha: 'Sin fecha',
}

function formatFecha(f: string | null) {
  if (!f) return '—'
  const d = new Date(f)
  return d.toLocaleDateString('es-CO', { month: 'short', year: 'numeric' })
}

function diasRestantes(fecha_fin: string | null): number | null {
  if (!fecha_fin) return null
  const hoy = new Date()
  const fin = new Date(fecha_fin)
  return Math.floor((fin.getTime() - hoy.getTime()) / (1000 * 60 * 60 * 24))
}

export default function PatrocinadoresGestion() {
  const [patrocinadores, setPatrocinadores] = useState<Patrocinador[]>([])
  const [loading, setLoading] = useState(true)
  const [busqueda, setBusqueda] = useState('')
  const [filtroEstado, setFiltroEstado] = useState<'todos' | 'activo' | 'inactivo'>('activo')
  const [filtroZona, setFiltroZona] = useState<string>('todas')
  const [zonas, setZonas] = useState<string[]>([])
  const [toggleLoading, setToggleLoading] = useState<string | null>(null)

  const cargar = useCallback(async () => {
    setLoading(true)
    const { data } = await supabase.from('patrocinadores').select('*').order('nombre')
    const lista = (data || []) as Patrocinador[]
    setPatrocinadores(lista)
    const zonasUnicas = [...new Set(lista.map(p => p.zona))].sort()
    setZonas(zonasUnicas)
    setLoading(false)
  }, [])

  useEffect(() => { cargar() }, [cargar])

  async function toggleEstado(p: Patrocinador) {
    setToggleLoading(p.id)
    const nuevo = p.estado === 'activo' ? 'inactivo' : 'activo'
    await supabase.from('patrocinadores').update({ estado: nuevo }).eq('id', p.id)
    setToggleLoading(null)
    cargar()
  }

  const filtrados = patrocinadores.filter(p => {
    if (filtroEstado !== 'todos' && p.estado !== filtroEstado) return false
    if (filtroZona !== 'todas' && p.zona !== filtroZona) return false
    if (busqueda) {
      const q = busqueda.toLowerCase()
      return p.nombre.toLowerCase().includes(q) || (p.cedula ?? '').includes(q)
    }
    return true
  })

  const activos = patrocinadores.filter(p => p.estado === 'activo').length
  const inactivos = patrocinadores.filter(p => p.estado === 'inactivo').length
  const porVencer = patrocinadores.filter(p => p.estado === 'activo' && getPatrocinioStatus(p.fecha_fin_patrocinio) === 'por_vencer').length
  const vencidos = patrocinadores.filter(p => p.estado === 'activo' && getPatrocinioStatus(p.fecha_fin_patrocinio) === 'vencido').length

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-2">
        <Users className="w-5 h-5 text-blue-400" />
        <h1 className="text-lg font-semibold text-white">Gestión de Patrocinadores</h1>
      </div>

      {/* Tarjetas */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-green-500/10 border border-green-500/20 rounded-xl p-4">
          <div className="text-2xl font-bold text-green-400">{activos}</div>
          <div className="text-xs text-green-400/70 mt-1">Activos</div>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <div className="text-2xl font-bold text-gray-400">{inactivos}</div>
          <div className="text-xs text-gray-500 mt-1">Inactivos</div>
        </div>
        <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-xl p-4">
          <div className="text-2xl font-bold text-yellow-400">{porVencer}</div>
          <div className="text-xs text-yellow-400/70 mt-1">Patrocinio por vencer</div>
        </div>
        <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4">
          <div className="text-2xl font-bold text-red-400">{vencidos}</div>
          <div className="text-xs text-red-400/70 mt-1">Patrocinio vencido</div>
        </div>
      </div>

      {/* Filtros */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input type="text" placeholder="Buscar por nombre o cédula..."
            value={busqueda} onChange={e => setBusqueda(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-gray-900 border border-gray-700 rounded-lg text-sm focus:outline-none focus:border-blue-500" />
        </div>
        <select value={filtroEstado} onChange={e => setFiltroEstado(e.target.value as any)}
          className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500">
          <option value="todos">Todos</option>
          <option value="activo">Activos</option>
          <option value="inactivo">Inactivos</option>
        </select>
        {zonas.length > 1 && (
          <select value={filtroZona} onChange={e => setFiltroZona(e.target.value)}
            className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500">
            <option value="todas">Todas las zonas</option>
            {zonas.map(z => <option key={z} value={z}>{z}</option>)}
          </select>
        )}
      </div>

      {/* Lista */}
      {loading ? (
        <div className="text-center py-16 text-gray-500">Cargando patrocinadores...</div>
      ) : filtrados.length === 0 ? (
        <div className="text-center py-16 text-gray-500">Sin resultados.</div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-800">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-900 border-b border-gray-800 text-xs text-gray-400">
                <th className="text-left px-4 py-3 sticky left-0 bg-gray-900 min-w-[220px]">Nombre</th>
                <th className="text-left px-3 py-3 whitespace-nowrap">Cédula</th>
                <th className="text-left px-3 py-3 whitespace-nowrap">Zona</th>
                <th className="text-left px-3 py-3 whitespace-nowrap">Período patrocinio</th>
                <th className="text-left px-3 py-3 whitespace-nowrap">Estado patrocinio</th>
                <th className="text-left px-3 py-3 whitespace-nowrap">FP</th>
                <th className="text-left px-3 py-3 whitespace-nowrap">Estado</th>
              </tr>
            </thead>
            <tbody>
              {filtrados.map((p, i) => {
                const pStatus = getPatrocinioStatus(p.fecha_fin_patrocinio)
                const dias = diasRestantes(p.fecha_fin_patrocinio)
                return (
                  <tr key={p.id} className={`border-b border-gray-800/50 hover:bg-gray-800/20 transition-colors ${i % 2 === 0 ? '' : 'bg-gray-900/20'} ${p.estado === 'inactivo' ? 'opacity-50' : ''}`}>
                    <td className="px-4 py-3 sticky left-0 bg-gray-950">
                      <div className="font-medium text-white">{p.nombre}</div>
                      {p.telefono && <div className="text-xs text-gray-500">{p.telefono}</div>}
                    </td>
                    <td className="px-3 py-3 text-gray-400 text-xs">{p.cedula || '—'}</td>
                    <td className="px-3 py-3 text-gray-400 text-xs whitespace-nowrap">{p.zona}</td>
                    <td className="px-3 py-3 text-xs whitespace-nowrap">
                      {p.fecha_inicio_patrocinio ? (
                        <span className="text-gray-300">
                          {formatFecha(p.fecha_inicio_patrocinio)} → {formatFecha(p.fecha_fin_patrocinio)}
                        </span>
                      ) : <span className="text-gray-600">—</span>}
                    </td>
                    <td className="px-3 py-3">
                      {p.estado === 'activo' ? (
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md border text-xs font-medium ${PATROCINIO_STYLES[pStatus]}`}>
                          {pStatus === 'vencido' && <XCircle className="w-3 h-3" />}
                          {pStatus === 'por_vencer' && <AlertTriangle className="w-3 h-3" />}
                          {pStatus === 'vigente' && <CheckCircle className="w-3 h-3" />}
                          {pStatus === 'sin_fecha' && <Clock className="w-3 h-3" />}
                          {PATROCINIO_LABEL[pStatus]}
                          {dias !== null && pStatus !== 'sin_fecha' && (
                            <span className="opacity-70">
                              {dias >= 0 ? ` (${dias}d)` : ` (${Math.abs(dias)}d ago)`}
                            </span>
                          )}
                        </span>
                      ) : <span className="text-gray-600 text-xs">—</span>}
                    </td>
                    <td className="px-3 py-3">
                      {p.fp_public_url ? (
                        <a href={p.fp_public_url} target="_blank" rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 underline">
                          Ver <ExternalLink className="w-3 h-3" />
                        </a>
                      ) : <span className="text-gray-600 text-xs">—</span>}
                    </td>
                    <td className="px-3 py-3">
                      <button
                        onClick={() => toggleEstado(p)}
                        disabled={toggleLoading === p.id}
                        className={`px-3 py-1 rounded-md text-xs font-medium transition-colors disabled:opacity-50 ${
                          p.estado === 'activo'
                            ? 'bg-green-500/20 text-green-400 hover:bg-red-500/20 hover:text-red-400 border border-green-500/30 hover:border-red-500/30'
                            : 'bg-gray-800 text-gray-400 hover:bg-green-500/20 hover:text-green-400 border border-gray-700 hover:border-green-500/30'
                        }`}>
                        {toggleLoading === p.id ? '...' : p.estado === 'activo' ? 'Activo' : 'Inactivo'}
                      </button>
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
