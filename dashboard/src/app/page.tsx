'use client'

import { useEffect, useState, useCallback } from 'react'
import { supabase, Aporte, Antecedente } from '@/lib/supabase'
import {
  getVigenciaStatus, getDiasRestantes,
  FUENTES, FUENTE_LABELS, STATUS_COLORS, STATUS_LABELS
} from '@/lib/utils'
import { FileText, AlertTriangle, ExternalLink, Search, Plus, Pencil, Trash2 } from 'lucide-react'
import AporteModal from '@/components/AporteModal'
import AntecedenteModal from '@/components/AntecedenteModal'

type PatrocinadorResumen = {
  patrocinador: string
  cedula: string
  zona: string
  aportes: Aporte[]
  antecedentes: Record<string, Antecedente | null>
}

type ModalState =
  | { type: 'aporte'; mode: 'add'; contexto: { patrocinador: string; cedula: string; zona: string } }
  | { type: 'aporte'; mode: 'edit'; aporte: Aporte }
  | { type: 'antecedente'; mode: 'add'; contexto: { patrocinador: string; cedula: string; zona: string }; fuente: string }
  | { type: 'antecedente'; mode: 'edit'; antecedente: Antecedente }
  | null

export default function Dashboard() {
  const [zonas, setZonas] = useState<string[]>([])
  const [zonaSeleccionada, setZonaSeleccionada] = useState<string>('todas')
  const [patrocinadores, setPatrocinadores] = useState<PatrocinadorResumen[]>([])
  const [busqueda, setBusqueda] = useState('')
  const [loading, setLoading] = useState(true)
  const [patrocinadorAbierto, setPatrocinadorAbierto] = useState<string | null>(null)
  const [modal, setModal] = useState<ModalState>(null)
  const [confirmDelete, setConfirmDelete] = useState<{ tipo: 'aporte' | 'antecedente'; id: string; storagePath: string } | null>(null)

  const cargarDatos = useCallback(async () => {
    setLoading(true)

    let qAportes = supabase.from('aportes').select('*').order('created_at', { ascending: false })
    if (zonaSeleccionada !== 'todas') qAportes = qAportes.eq('zona', zonaSeleccionada)
    const { data: aportes } = await qAportes

    let qAnt = supabase.from('antecedentes').select('*').order('fecha_consulta', { ascending: false })
    if (zonaSeleccionada !== 'todas') qAnt = qAnt.eq('zona', zonaSeleccionada)
    const { data: antecedentes } = await qAnt

    const { data: zonasData } = await supabase.from('aportes').select('zona')
    const zonasUnicas = [...new Set((zonasData as any[] || []).map(r => r.zona as string))].sort()
    setZonas(zonasUnicas)

    const mapa: Record<string, PatrocinadorResumen> = {}

    for (const a of (aportes || [])) {
      const key = a.cedula
      if (!mapa[key]) {
        mapa[key] = { patrocinador: a.patrocinador, cedula: a.cedula, zona: a.zona, aportes: [], antecedentes: { policia: null, procuraduria: null, contraloria: null, ofac: null } }
      }
      mapa[key].aportes.push(a)
    }

    for (const ant of (antecedentes || [])) {
      const key = ant.cedula
      if (!mapa[key]) {
        mapa[key] = { patrocinador: ant.patrocinador, cedula: ant.cedula, zona: ant.zona, aportes: [], antecedentes: { policia: null, procuraduria: null, contraloria: null, ofac: null } }
      }
      if (!mapa[key].antecedentes[ant.fuente]) {
        mapa[key].antecedentes[ant.fuente] = ant
      }
    }

    setPatrocinadores(Object.values(mapa))
    setLoading(false)
  }, [zonaSeleccionada])

  useEffect(() => { cargarDatos() }, [cargarDatos])

  async function eliminar() {
    if (!confirmDelete) return
    const { tipo, id, storagePath } = confirmDelete
    if (storagePath) await supabase.storage.from('recibos').remove([storagePath])
    if (tipo === 'aporte') await supabase.from('aportes').delete().eq('id', id)
    else await supabase.from('antecedentes').delete().eq('id', id)
    setConfirmDelete(null)
    cargarDatos()
  }

  const filtrados = patrocinadores.filter(p =>
    busqueda === '' ||
    p.patrocinador.toLowerCase().includes(busqueda.toLowerCase()) ||
    p.cedula.includes(busqueda)
  )

  const totalVencidos = patrocinadores.reduce((acc, p) =>
    acc + FUENTES.filter(f => p.antecedentes[f] && getVigenciaStatus(p.antecedentes[f]!.fecha_vencimiento) === 'vencido').length, 0)
  const totalPorVencer = patrocinadores.reduce((acc, p) =>
    acc + FUENTES.filter(f => p.antecedentes[f] && getVigenciaStatus(p.antecedentes[f]!.fecha_vencimiento) === 'por_vencer').length, 0)

  return (
    <div className="space-y-6">
      {/* Filtros */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Buscar patrocinador o cédula..."
            value={busqueda}
            onChange={e => setBusqueda(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-gray-900 border border-gray-700 rounded-lg text-sm focus:outline-none focus:border-blue-500"
          />
        </div>
        <select
          value={zonaSeleccionada}
          onChange={e => setZonaSeleccionada(e.target.value)}
          className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
        >
          <option value="todas">Todas las zonas</option>
          {zonas.map(z => <option key={z} value={z}>{z}</option>)}
        </select>
      </div>

      {/* Tarjetas resumen */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <div className="text-2xl font-bold text-white">{patrocinadores.length}</div>
          <div className="text-xs text-gray-400 mt-1">Patrocinadores</div>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <div className="text-2xl font-bold text-white">{patrocinadores.reduce((a, p) => a + p.aportes.length, 0)}</div>
          <div className="text-xs text-gray-400 mt-1">Aportes registrados</div>
        </div>
        <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4">
          <div className="text-2xl font-bold text-red-400">{totalVencidos}</div>
          <div className="text-xs text-red-400/70 mt-1">IAs vencidas</div>
        </div>
        <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-xl p-4">
          <div className="text-2xl font-bold text-yellow-400">{totalPorVencer}</div>
          <div className="text-xs text-yellow-400/70 mt-1">Por vencer (15 días)</div>
        </div>
      </div>

      {/* Tabla */}
      {loading ? (
        <div className="text-center py-16 text-gray-500">Cargando datos...</div>
      ) : filtrados.length === 0 ? (
        <div className="text-center py-16 text-gray-500">No se encontraron resultados.</div>
      ) : (
        <div className="space-y-3">
          {filtrados.map(p => {
            const abierto = patrocinadorAbierto === p.cedula
            const tieneAlerta = FUENTES.some(f => {
              const ant = p.antecedentes[f]
              if (!ant) return true
              return getVigenciaStatus(ant.fecha_vencimiento) !== 'vigente'
            })
            const ctx = { patrocinador: p.patrocinador, cedula: p.cedula, zona: p.zona }

            return (
              <div key={p.cedula} className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
                <button
                  onClick={() => setPatrocinadorAbierto(abierto ? null : p.cedula)}
                  className="w-full flex items-center gap-4 px-4 py-3 hover:bg-gray-800/50 transition-colors text-left"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-white truncate">{p.patrocinador}</span>
                      {tieneAlerta && <AlertTriangle className="w-4 h-4 text-yellow-400 shrink-0" />}
                    </div>
                    <div className="text-xs text-gray-400 mt-0.5">CC: {p.cedula} · {p.zona}</div>
                  </div>
                  <div className="flex gap-1 shrink-0">
                    {FUENTES.map(f => {
                      const ant = p.antecedentes[f]
                      const status = ant ? getVigenciaStatus(ant.fecha_vencimiento) : 'sin_registro'
                      return (
                        <span key={f} title={`${FUENTE_LABELS[f]}: ${STATUS_LABELS[status]}`}
                          className={`text-[10px] px-1.5 py-0.5 rounded border font-medium ${STATUS_COLORS[status]}`}>
                          {f === 'procuraduria' ? 'PROC' : f.toUpperCase()}
                        </span>
                      )
                    })}
                  </div>
                  <div className="flex items-center gap-1 text-xs text-gray-400 shrink-0">
                    <FileText className="w-3.5 h-3.5" />
                    {p.aportes.length}
                  </div>
                  <span className="text-gray-600 text-xs">{abierto ? '▲' : '▼'}</span>
                </button>

                {abierto && (
                  <div className="border-t border-gray-800 px-4 py-4 space-y-5">
                    {/* Antecedentes */}
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Investigaciones de Antecedentes</h3>
                      </div>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                        {FUENTES.map(f => {
                          const ant = p.antecedentes[f]
                          const status = ant ? getVigenciaStatus(ant.fecha_vencimiento) : 'sin_registro'
                          const dias = ant ? getDiasRestantes(ant.fecha_vencimiento) : null

                          return (
                            <div key={f} className={`rounded-lg border p-3 ${STATUS_COLORS[status]}`}>
                              <div className="flex items-start justify-between gap-1">
                                <div className="font-semibold text-sm">{FUENTE_LABELS[f]}</div>
                                <div className="flex gap-1 shrink-0">
                                  <button
                                    onClick={() => setModal({ type: 'antecedente', mode: ant ? 'edit' : 'add', ...(ant ? { antecedente: ant } : { contexto: ctx, fuente: f }) } as ModalState)}
                                    title={ant ? 'Editar' : 'Agregar'}
                                    className="p-0.5 rounded hover:bg-white/10 transition-colors">
                                    {ant ? <Pencil className="w-3 h-3" /> : <Plus className="w-3 h-3" />}
                                  </button>
                                  {ant && (
                                    <button
                                      onClick={() => setConfirmDelete({ tipo: 'antecedente', id: ant.id, storagePath: ant.storage_path })}
                                      title="Eliminar"
                                      className="p-0.5 rounded hover:bg-red-500/20 text-red-400 transition-colors">
                                      <Trash2 className="w-3 h-3" />
                                    </button>
                                  )}
                                </div>
                              </div>
                              <div className="text-xs mt-1 opacity-80">{STATUS_LABELS[status]}</div>
                              {ant && (
                                <>
                                  <div className="text-xs mt-1 opacity-60">
                                    {dias !== null && dias >= 0 ? `Vence en ${dias}d` : dias !== null ? `Venció hace ${Math.abs(dias)}d` : ''}
                                  </div>
                                  <a href={ant.public_url} target="_blank" rel="noopener noreferrer"
                                    className="inline-flex items-center gap-1 text-xs mt-2 underline opacity-80 hover:opacity-100">
                                    Ver PDF <ExternalLink className="w-3 h-3" />
                                  </a>
                                </>
                              )}
                              {!ant && <div className="text-xs mt-1 opacity-60">No consultado</div>}
                            </div>
                          )
                        })}
                      </div>
                    </div>

                    {/* Aportes */}
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Aportes</h3>
                        <button
                          onClick={() => setModal({ type: 'aporte', mode: 'add', contexto: ctx })}
                          className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 transition-colors">
                          <Plus className="w-3.5 h-3.5" /> Agregar aporte
                        </button>
                      </div>
                      {p.aportes.length === 0 ? (
                        <p className="text-xs text-gray-600 py-2">Sin aportes registrados.</p>
                      ) : (
                        <div className="overflow-x-auto">
                          <table className="w-full text-sm">
                            <thead>
                              <tr className="text-xs text-gray-500 border-b border-gray-800">
                                <th className="text-left pb-2 pr-4">Mes</th>
                                <th className="text-left pb-2 pr-4">Año</th>
                                <th className="text-left pb-2 pr-4">Valor</th>
                                <th className="text-left pb-2 pr-4">Método</th>
                                <th className="text-left pb-2 pr-4">Comprobante</th>
                                <th className="text-left pb-2 pr-4">PDF</th>
                                <th className="text-left pb-2">Acciones</th>
                              </tr>
                            </thead>
                            <tbody>
                              {p.aportes.map(a => (
                                <tr key={a.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                                  <td className="py-2 pr-4 text-white">{a.mes}</td>
                                  <td className="py-2 pr-4 text-gray-300">{a.año}</td>
                                  <td className="py-2 pr-4 text-green-400 font-medium">${a.valor}</td>
                                  <td className="py-2 pr-4 text-gray-300">{a.metodo}</td>
                                  <td className="py-2 pr-4 text-gray-400">{a.comprobante}</td>
                                  <td className="py-2 pr-4">
                                    {a.public_url && (
                                      <a href={a.public_url} target="_blank" rel="noopener noreferrer"
                                        className="inline-flex items-center gap-1 text-blue-400 hover:text-blue-300 text-xs">
                                        Ver <ExternalLink className="w-3 h-3" />
                                      </a>
                                    )}
                                  </td>
                                  <td className="py-2">
                                    <div className="flex gap-2">
                                      <button
                                        onClick={() => setModal({ type: 'aporte', mode: 'edit', aporte: a })}
                                        title="Editar"
                                        className="text-gray-400 hover:text-blue-400 transition-colors">
                                        <Pencil className="w-3.5 h-3.5" />
                                      </button>
                                      <button
                                        onClick={() => setConfirmDelete({ tipo: 'aporte', id: a.id, storagePath: a.storage_path })}
                                        title="Eliminar"
                                        className="text-gray-400 hover:text-red-400 transition-colors">
                                        <Trash2 className="w-3.5 h-3.5" />
                                      </button>
                                    </div>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Modales */}
      {modal?.type === 'aporte' && (
        <AporteModal
          open
          onClose={() => setModal(null)}
          onSaved={cargarDatos}
          mode={modal.mode}
          aporte={modal.mode === 'edit' ? modal.aporte : undefined}
          contexto={modal.mode === 'add' ? modal.contexto : undefined}
        />
      )}

      {modal?.type === 'antecedente' && (
        <AntecedenteModal
          open
          onClose={() => setModal(null)}
          onSaved={cargarDatos}
          mode={modal.mode}
          antecedente={modal.mode === 'edit' ? modal.antecedente : undefined}
          contexto={modal.mode === 'add' ? modal.contexto : undefined}
          fuenteInicial={modal.mode === 'add' ? modal.fuente : undefined}
        />
      )}

      {/* Confirmar eliminación */}
      {confirmDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => setConfirmDelete(null)} />
          <div className="relative bg-gray-900 border border-gray-800 rounded-xl p-6 max-w-sm w-full shadow-2xl">
            <h3 className="text-base font-semibold text-white mb-2">¿Eliminar registro?</h3>
            <p className="text-sm text-gray-400 mb-5">
              Esta acción eliminará el registro y el archivo PDF de Supabase. No se puede deshacer.
            </p>
            <div className="flex gap-2">
              <button onClick={() => setConfirmDelete(null)}
                className="flex-1 px-4 py-2 bg-gray-800 text-gray-300 rounded-lg text-sm hover:bg-gray-700 transition-colors">
                Cancelar
              </button>
              <button onClick={eliminar}
                className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg text-sm hover:bg-red-500 transition-colors">
                Eliminar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
