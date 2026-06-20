'use client'

import { useEffect, useState, useCallback } from 'react'
import { supabase, Aporte, Antecedente } from '@/lib/supabase'
import {
  getVigenciaStatus, getDiasRestantes,
  FUENTES, FUENTE_LABELS, STATUS_COLORS, STATUS_LABELS
} from '@/lib/utils'
import {
  FileText, AlertTriangle, ExternalLink, Search, Plus,
  Pencil, Trash2, CheckCircle, XCircle, Clock, MessageSquare, Send, Copy, Check
} from 'lucide-react'
import AporteModal from '@/components/AporteModal'
import AntecedenteModal from '@/components/AntecedenteModal'

type AporteConAval = Aporte & {
  estado?: 'pendiente' | 'avalado' | 'rechazado'
  comentario_revision?: string
  fecha_revision?: string
  revisor?: string
}

type PatrocinadorResumen = {
  patrocinador: string
  cedula: string
  zona: string
  aportes: AporteConAval[]
  antecedentes: Record<string, Antecedente | null>
}

type ModalState =
  | { type: 'aporte'; mode: 'add'; contexto: { patrocinador: string; cedula: string; zona: string } }
  | { type: 'aporte'; mode: 'edit'; aporte: Aporte }
  | { type: 'antecedente'; mode: 'add'; contexto: { patrocinador: string; cedula: string; zona: string }; fuente: string }
  | { type: 'antecedente'; mode: 'edit'; antecedente: Antecedente }
  | null

type RechazoState = { id: string; comentario: string } | null

const ESTADO_STYLES = {
  pendiente: { cls: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20', label: 'Pendiente', Icon: Clock },
  avalado: { cls: 'bg-green-500/10 text-green-400 border-green-500/20', label: 'Avalado', Icon: CheckCircle },
  rechazado: { cls: 'bg-red-500/10 text-red-400 border-red-500/20', label: 'Rechazado', Icon: XCircle },
}

export default function Dashboard() {
  const [zonas, setZonas] = useState<string[]>([])
  const [zonaSeleccionada, setZonaSeleccionada] = useState<string>('todas')
  const [patrocinadores, setPatrocinadores] = useState<PatrocinadorResumen[]>([])
  const [fpMap, setFpMap] = useState<Record<string, string>>({}) // cedula -> fp_public_url
  const [busqueda, setBusqueda] = useState('')
  const [loading, setLoading] = useState(true)
  const [patrocinadorAbierto, setPatrocinadorAbierto] = useState<string | null>(null)
  const [modal, setModal] = useState<ModalState>(null)
  const [confirmDelete, setConfirmDelete] = useState<{ tipo: 'aporte' | 'antecedente'; id: string; storagePath: string } | null>(null)
  const [rechazo, setRechazo] = useState<RechazoState>(null)
  const [avalLoading, setAvalLoading] = useState<string | null>(null)
  const [mensajeWsp, setMensajeWsp] = useState<string | null>(null)
  const [copiado, setCopiado] = useState(false)

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

    // Cargar FPs — indexar por cedula Y nombre normalizado (sin tildes)
    const { data: pats } = await supabase.from('patrocinadores').select('nombre, cedula, fp_public_url, fecha_inicio_patrocinio, fecha_fin_patrocinio')
    const newFpMap: Record<string, string> = {}
    const norm = (s: string) => s.toUpperCase().normalize('NFD').replace(/[̀-ͯ]/g, '').trim()
    for (const pat of (pats || [])) {
      const url = pat.fp_public_url
      if (!url) continue
      if (pat.cedula) newFpMap[pat.cedula] = url
      if (pat.nombre) newFpMap[norm(pat.nombre)] = url
    }
    setFpMap(newFpMap)

    const mapa: Record<string, PatrocinadorResumen> = {}

    for (const a of (aportes || [])) {
      const key = a.cedula
      if (!mapa[key]) {
        mapa[key] = { patrocinador: a.patrocinador, cedula: a.cedula, zona: a.zona, aportes: [], antecedentes: { policia: null, procuraduria: null, contraloria: null, ofac: null } }
      }
      mapa[key].aportes.push(a as AporteConAval)
    }

    for (const ant of (antecedentes || [])) {
      const key = ant.cedula
      if (!mapa[key]) continue
      if (!mapa[key].antecedentes[ant.fuente]) {
        mapa[key].antecedentes[ant.fuente] = ant
      }
    }

    setPatrocinadores(Object.values(mapa))
    setLoading(false)
  }, [zonaSeleccionada])

  useEffect(() => { cargarDatos() }, [cargarDatos])

  async function marcarAval(id: string, estado: 'avalado' | 'rechazado', comentario?: string) {
    setAvalLoading(id)
    await supabase.from('aportes').update({
      estado,
      comentario_revision: comentario ?? null,
      fecha_revision: new Date().toISOString(),
    }).eq('id', id)
    setAvalLoading(null)
    setRechazo(null)
    cargarDatos()
  }

  async function eliminar() {
    if (!confirmDelete) return
    const { tipo, id, storagePath } = confirmDelete
    if (storagePath) await supabase.storage.from('recibos').remove([storagePath])
    if (tipo === 'aporte') await supabase.from('aportes').delete().eq('id', id)
    else await supabase.from('antecedentes').delete().eq('id', id)
    setConfirmDelete(null)
    cargarDatos()
  }

  function generarMensajeWsp() {
    const zona = zonaSeleccionada === 'todas' ? 'Todas las zonas' : zonaSeleccionada
    const fecha = new Date().toLocaleDateString('es-CO', { day: '2-digit', month: '2-digit', year: 'numeric' })

    const avalados: string[] = []
    const rechazados: string[] = []
    const pendientes: string[] = []

    for (const p of patrocinadores) {
      for (const a of p.aportes) {
        const estado = a.estado ?? 'pendiente'
        const linea = `${p.patrocinador} (CC: ${p.cedula}) — ${a.mes} ${a.año} — $${a.valor}`
        if (estado === 'avalado') avalados.push(`• ${linea}`)
        else if (estado === 'rechazado') {
          rechazados.push(`• ${linea}`)
          if (a.comentario_revision) rechazados.push(`  _Motivo: ${a.comentario_revision}_`)
        } else pendientes.push(`• ${linea}`)
      }
    }

    const partes: string[] = [
      `📋 *Revisión de Aportes — ${zona}*`,
      `📅 ${fecha}`,
      '',
    ]
    if (avalados.length) {
      partes.push('✅ *CON AVAL:*')
      partes.push(...avalados)
      partes.push('')
    }
    if (rechazados.length) {
      partes.push('❌ *SIN AVAL (requieren corrección):*')
      partes.push(...rechazados)
      partes.push('')
    }
    if (pendientes.length) {
      partes.push('⏳ *PENDIENTES DE REVISIÓN:*')
      partes.push(...pendientes)
      partes.push('')
    }
    partes.push(`_Total: ${avalados.length} con aval · ${rechazados.length} sin aval · ${pendientes.length} pendientes_`)

    setMensajeWsp(partes.join('\n'))
    setCopiado(false)
  }

  async function copiarMensaje() {
    if (!mensajeWsp) return
    await navigator.clipboard.writeText(mensajeWsp)
    setCopiado(true)
    setTimeout(() => setCopiado(false), 2500)
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
  const totalPendientes = patrocinadores.reduce((acc, p) =>
    acc + p.aportes.filter(a => !a.estado || a.estado === 'pendiente').length, 0)

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
        <button
          onClick={generarMensajeWsp}
          className="flex items-center gap-2 px-3 py-2 bg-green-700 hover:bg-green-600 text-white rounded-lg text-sm transition-colors whitespace-nowrap">
          <Send className="w-4 h-4" /> Resumen WhatsApp
        </button>
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
        <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-xl p-4">
          <div className="text-2xl font-bold text-yellow-400">{totalPendientes}</div>
          <div className="text-xs text-yellow-400/70 mt-1">Pendientes de aval</div>
        </div>
        <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4">
          <div className="text-2xl font-bold text-red-400">{totalVencidos + totalPorVencer}</div>
          <div className="text-xs text-red-400/70 mt-1">IAs por atender</div>
        </div>
      </div>

      {/* Lista patrocinadores */}
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
            const pendientes = p.aportes.filter(a => !a.estado || a.estado === 'pendiente').length
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
                      {pendientes > 0 && (
                        <span className="text-[10px] bg-yellow-500/20 text-yellow-400 border border-yellow-500/30 px-1.5 py-0.5 rounded font-medium shrink-0">
                          {pendientes} pendiente{pendientes > 1 ? 's' : ''}
                        </span>
                      )}
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
                    {/* Formato de Postulación */}
                    {(() => {
                      const norm = (s: string) => s.toUpperCase().normalize('NFD').replace(/[̀-ͯ]/g, '').trim()
                      const fpUrl = fpMap[p.cedula] || fpMap[norm(p.patrocinador)]
                      return (
                        <div className="flex items-center gap-3 bg-gray-800/60 border border-gray-700 rounded-lg px-3 py-2">
                          <FileText className="w-4 h-4 text-blue-400 shrink-0" />
                          <span className="text-xs font-medium text-gray-300">Formato de Postulación</span>
                          {fpUrl ? (
                            <a href={fpUrl} target="_blank" rel="noopener noreferrer"
                              className="ml-auto inline-flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 underline shrink-0">
                              Ver PDF <ExternalLink className="w-3 h-3" />
                            </a>
                          ) : (
                            <span className="ml-auto text-xs text-gray-600">Sin documento</span>
                          )}
                        </div>
                      )
                    })()}
                    {/* Antecedentes */}
                    <div>
                      <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Investigaciones de Antecedentes</h3>
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
                          <Plus className="w-3.5 h-3.5" /> Agregar
                        </button>
                      </div>
                      {p.aportes.length === 0 ? (
                        <p className="text-xs text-gray-600 py-2">Sin aportes registrados.</p>
                      ) : (
                        <div className="space-y-2">
                          {p.aportes.map(a => {
                            const estado = a.estado ?? 'pendiente'
                            const { cls, label, Icon } = ESTADO_STYLES[estado]
                            const esRechazo = rechazo?.id === a.id

                            return (
                              <div key={a.id} className={`rounded-lg border ${cls} p-3`}>
                                {/* Fila principal */}
                                <div className="flex flex-wrap items-start gap-x-4 gap-y-1">
                                  <div className="flex items-center gap-1.5">
                                    <Icon className="w-3.5 h-3.5 shrink-0" />
                                    <span className="text-xs font-semibold">{label}</span>
                                  </div>
                                  <span className="text-sm font-bold text-white">{a.mes} {a.año}</span>
                                  <span className="text-sm font-bold text-green-400">${a.valor}</span>
                                  {a.metodo && <span className="text-xs text-gray-300">{a.metodo}</span>}
                                  {a.banco && <span className="text-xs text-gray-400">{a.banco}</span>}
                                  {a.comprobante && <span className="text-xs text-gray-500">#{a.comprobante}</span>}
                                  {a.fecha_aporte && <span className="text-xs text-gray-500">{a.fecha_aporte}</span>}
                                  {a.public_url && (
                                    <a href={a.public_url} target="_blank" rel="noopener noreferrer"
                                      className="inline-flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 underline">
                                      Ver PDF <ExternalLink className="w-3 h-3" />
                                    </a>
                                  )}
                                </div>

                                {/* Comentario de rechazo */}
                                {estado === 'rechazado' && a.comentario_revision && (
                                  <div className="mt-2 flex items-start gap-1.5 text-xs text-red-300/80">
                                    <MessageSquare className="w-3 h-3 mt-0.5 shrink-0" />
                                    <span>{a.comentario_revision}</span>
                                  </div>
                                )}

                                {/* Acciones de aval */}
                                <div className="mt-2 flex flex-wrap items-center gap-2">
                                  {estado !== 'avalado' && (
                                    <button
                                      onClick={() => marcarAval(a.id, 'avalado')}
                                      disabled={avalLoading === a.id}
                                      className="flex items-center gap-1 text-xs px-2.5 py-1 bg-green-600 text-white rounded-md hover:bg-green-500 disabled:opacity-50 transition-colors">
                                      <CheckCircle className="w-3 h-3" /> Dar aval
                                    </button>
                                  )}
                                  {estado !== 'rechazado' && (
                                    <button
                                      onClick={() => setRechazo(esRechazo ? null : { id: a.id, comentario: '' })}
                                      disabled={avalLoading === a.id}
                                      className="flex items-center gap-1 text-xs px-2.5 py-1 bg-red-600/80 text-white rounded-md hover:bg-red-500 disabled:opacity-50 transition-colors">
                                      <XCircle className="w-3 h-3" /> Rechazar
                                    </button>
                                  )}
                                  {estado !== 'pendiente' && (
                                    <button
                                      onClick={() => marcarAval(a.id, 'pendiente' as any)}
                                      disabled={avalLoading === a.id}
                                      className="text-xs text-gray-500 hover:text-gray-300 transition-colors">
                                      Resetear
                                    </button>
                                  )}
                                  <div className="ml-auto flex gap-2">
                                    <button onClick={() => setModal({ type: 'aporte', mode: 'edit', aporte: a })}
                                      title="Editar" className="text-gray-500 hover:text-blue-400 transition-colors">
                                      <Pencil className="w-3.5 h-3.5" />
                                    </button>
                                    <button onClick={() => setConfirmDelete({ tipo: 'aporte', id: a.id, storagePath: a.storage_path })}
                                      title="Eliminar" className="text-gray-500 hover:text-red-400 transition-colors">
                                      <Trash2 className="w-3.5 h-3.5" />
                                    </button>
                                  </div>
                                </div>

                                {/* Formulario de rechazo inline */}
                                {esRechazo && (
                                  <div className="mt-3 space-y-2">
                                    <textarea
                                      value={rechazo.comentario}
                                      onChange={e => setRechazo({ id: a.id, comentario: e.target.value })}
                                      placeholder="Describe el error encontrado en el aporte..."
                                      rows={2}
                                      className="w-full bg-gray-900 border border-red-500/30 rounded-lg px-3 py-2 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-red-400 resize-none"
                                    />
                                    <div className="flex gap-2">
                                      <button onClick={() => setRechazo(null)}
                                        className="text-xs px-3 py-1.5 bg-gray-800 text-gray-400 rounded-md hover:bg-gray-700 transition-colors">
                                        Cancelar
                                      </button>
                                      <button
                                        onClick={() => marcarAval(a.id, 'rechazado', rechazo.comentario)}
                                        disabled={!rechazo.comentario.trim() || avalLoading === a.id}
                                        className="text-xs px-3 py-1.5 bg-red-600 text-white rounded-md hover:bg-red-500 disabled:opacity-50 transition-colors">
                                        Confirmar rechazo
                                      </button>
                                    </div>
                                  </div>
                                )}
                              </div>
                            )
                          })}
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

      {/* Modal mensaje WhatsApp */}
      {mensajeWsp && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => setMensajeWsp(null)} />
          <div className="relative bg-gray-900 border border-gray-800 rounded-xl w-full max-w-lg shadow-2xl">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
              <h2 className="text-base font-semibold text-white flex items-center gap-2">
                <Send className="w-4 h-4 text-green-400" /> Resumen para WhatsApp
              </h2>
              <button onClick={() => setMensajeWsp(null)} className="text-gray-400 hover:text-white text-2xl leading-none">&times;</button>
            </div>
            <div className="px-6 py-4 space-y-3">
              <pre className="whitespace-pre-wrap text-xs text-gray-300 bg-gray-800 rounded-lg p-4 max-h-80 overflow-y-auto font-sans leading-relaxed">
                {mensajeWsp}
              </pre>
              <button
                onClick={copiarMensaje}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-green-600 hover:bg-green-500 text-white rounded-lg text-sm font-medium transition-colors">
                {copiado ? <><Check className="w-4 h-4" /> ¡Copiado!</> : <><Copy className="w-4 h-4" /> Copiar mensaje</>}
              </button>
              <p className="text-xs text-gray-500 text-center">Pega directamente en WhatsApp — los * y _ se formatean automáticamente</p>
            </div>
          </div>
        </div>
      )}

      {/* Confirmar eliminación */}
      {confirmDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => setConfirmDelete(null)} />
          <div className="relative bg-gray-900 border border-gray-800 rounded-xl p-6 max-w-sm w-full shadow-2xl">
            <h3 className="text-base font-semibold text-white mb-2">¿Eliminar registro?</h3>
            <p className="text-sm text-gray-400 mb-5">
              Elimina el registro y el PDF de Supabase. No se puede deshacer.
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
