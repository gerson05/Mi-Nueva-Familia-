'use client'

import { useEffect, useState, useCallback, useRef } from 'react'
import { supabase } from '@/lib/supabase'
import React from 'react'
import {
  Search, Users, CheckCircle, XCircle, AlertTriangle, Clock,
  Upload, Loader2, ChevronDown, ChevronRight, FileText, CreditCard, Shield,
  Calendar
} from 'lucide-react'

const SUPABASE_URL = 'https://xhigifzmylcaxkxzqzom.supabase.co'
const BUCKET = 'recibos'

const MES_NUM: Record<string, number> = {
  ENERO: 1, FEBRERO: 2, MARZO: 3, ABRIL: 4, MAYO: 5, JUNIO: 6,
  JULIO: 7, AGOSTO: 8, SEPTIEMBRE: 9, OCTUBRE: 10, NOVIEMBRE: 11, DICIEMBRE: 12,
  ENE: 1, FEB: 2, MAR: 3, ABR: 4, MAY: 5, JUN: 6,
  JUL: 7, AGO: 8, SEP: 9, SEPT: 9, OCT: 10, NOV: 11, DIC: 12,
}

type Patrocinador = {
  id: string
  nombre: string
  cedula: string | null
  zona: string
  telefono: string | null
  estado: 'activo' | 'inactivo'
  fecha_inicio_patrocinio: string | null
  fecha_fin_patrocinio: string | null
  fp_storage_path: string | null
  fp_public_url: string | null
  cedula_storage_path: string | null
  cedula_pdf_url: string | null
  observaciones: string | null
}

type Aporte = {
  id: string
  mes: string
  año: string
  valor: string
  estado: string | null
  public_url: string | null
  metodo: string | null
  banco: string | null
}

type Antecedente = {
  id: string
  fuente: string
  fecha_consulta: string
  fecha_vencimiento: string | null
  public_url: string | null
  estado_vigencia: string | null
}

type DetallePat = {
  aportes: Aporte[]
  antecedentes: Antecedente[]
}

function getPatrocinioStatus(fecha_fin: string | null) {
  if (!fecha_fin) return 'sin_fecha'
  const dias = Math.floor((new Date(fecha_fin).getTime() - Date.now()) / 86400000)
  if (dias < 0) return 'vencido'
  if (dias <= 30) return 'por_vencer'
  return 'vigente'
}

const P_STYLES: Record<string, string> = {
  vigente: 'text-green-400 bg-green-500/10 border-green-500/20',
  por_vencer: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20',
  vencido: 'text-red-400 bg-red-500/10 border-red-500/20',
  sin_fecha: 'text-gray-500 bg-gray-800 border-gray-700',
}
const P_LABEL: Record<string, string> = {
  vigente: 'Vigente', por_vencer: 'Por vencer', vencido: 'Vencido', sin_fecha: 'Sin fecha',
}

const ESTADO_AVAL: Record<string, { cls: string; label: string }> = {
  avalado: { cls: 'text-green-400 bg-green-500/10', label: 'Avalado' },
  rechazado: { cls: 'text-red-400 bg-red-500/10', label: 'Rechazado' },
  pendiente: { cls: 'text-yellow-400 bg-yellow-500/10', label: 'Pendiente' },
}

function fmtFecha(f: string | null) {
  if (!f) return '—'
  return new Date(f).toLocaleDateString('es-CO', { month: 'short', year: 'numeric' })
}

function fmtFechaCorta(f: string | null) {
  if (!f) return '—'
  return new Date(f).toLocaleDateString('es-CO', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

function aporteEnPeriodo(a: Aporte, inicio: string | null, fin: string | null): boolean {
  if (!inicio || !fin) return true
  const mesNum = MES_NUM[(a.mes || '').toUpperCase().trim()] ?? 0
  const año = parseInt((a as any).año ?? a.año ?? '0')
  if (!mesNum || !año) return true
  const fecha = new Date(año, mesNum - 1, 1)
  return fecha >= new Date(inicio) && fecha <= new Date(fin)
}

function norm(s: string) {
  return s.toUpperCase().normalize('NFD').replace(/[̀-ͯ]/g, '').trim()
}

function DocSlot({
  label, url, loading, onUpload, icon: Icon,
}: {
  label: string
  url: string | null
  loading: boolean
  onUpload: (f: File) => void
  icon: React.ElementType
}) {
  const ref = useRef<HTMLInputElement | null>(null)
  return (
    <div className="flex items-center gap-3 p-3 bg-gray-900 rounded-lg border border-gray-800">
      <Icon className="w-4 h-4 text-gray-400 shrink-0" />
      <span className="text-sm text-gray-300 flex-1">{label}</span>
      <div className="flex items-center gap-2">
        {url ? (
          <a href={url} target="_blank" rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-blue-500/15 hover:bg-blue-500/25 border border-blue-500/30 hover:border-blue-500/50 text-blue-400 hover:text-blue-300 text-xs font-medium transition-all duration-200 cursor-pointer whitespace-nowrap">
            <FileText className="w-3 h-3" /> Ver PDF
          </a>
        ) : (
          <span className="text-xs text-gray-600 italic">Sin documento</span>
        )}
        <label className="cursor-pointer" title={url ? 'Actualizar' : 'Subir'}>
          {loading
            ? <Loader2 className="w-3.5 h-3.5 text-gray-400 animate-spin" />
            : <Upload className="w-3.5 h-3.5 text-gray-500 hover:text-blue-400 transition-colors" />
          }
          <input type="file" accept=".pdf" className="hidden" ref={ref}
            onChange={e => { const f = e.target.files?.[0]; if (f) { onUpload(f); if (ref.current) ref.current.value = '' } }}
          />
        </label>
      </div>
    </div>
  )
}

function PanelDetalle({ p, detalle, onReload }: {
  p: Patrocinador
  detalle: DetallePat
  onReload: () => void
}) {
  const [tab, setTab] = useState<'consignaciones' | 'documentos'>('consignaciones')
  const [fpLoading, setFpLoading] = useState(false)
  const [cedulaLoading, setCedulaLoading] = useState(false)

  // Años disponibles en todos los aportes de este patrocinador
  const añosDisponibles = [...new Set(
    detalle.aportes.map(a => (a as any).año as string).filter(Boolean)
  )].sort((a, b) => Number(b) - Number(a))

  // Año del período actual para mostrar por defecto
  const añoActual = p.fecha_fin_patrocinio
    ? new Date(p.fecha_fin_patrocinio).getFullYear().toString()
    : añosDisponibles[0] ?? new Date().getFullYear().toString()

  const [añoVista, setAñoVista] = useState<string>(añoActual)

  const aportesPeriodo = detalle.aportes.filter(a =>
    (a as any).año === añoVista
  )

  const totalAportes = aportesPeriodo.reduce(
    (s, a) => s + (parseFloat(String(a.valor).replace(/[^0-9.]/g, '')) || 0), 0
  )

  async function subirDoc(tipo: 'fp' | 'cedula', file: File) {
    if (tipo === 'fp') setFpLoading(true)
    else setCedulaLoading(true)

    const nombreSafe = p.nombre.replace(/[^a-zA-Z0-9._-]/g, '_')
    const prefix = tipo === 'fp' ? 'FP' : 'CEDULA'
    const storagePath = `${p.zona}/patrocinadores/${nombreSafe}/${prefix}_${nombreSafe}.pdf`
    const { error } = await supabase.storage.from(BUCKET).upload(storagePath, file, {
      upsert: true, contentType: 'application/pdf'
    })
    if (!error) {
      const publicUrl = `${SUPABASE_URL}/storage/v1/object/public/${BUCKET}/${storagePath}`
      const update = tipo === 'fp'
        ? { fp_storage_path: storagePath, fp_public_url: publicUrl }
        : { cedula_storage_path: storagePath, cedula_pdf_url: publicUrl }
      await supabase.from('patrocinadores').update(update).eq('id', p.id)
    }

    if (tipo === 'fp') setFpLoading(false)
    else setCedulaLoading(false)
    onReload()
  }

  const antVigentes = detalle.antecedentes.filter(a => {
    if (!a.fecha_vencimiento) return true
    return new Date(a.fecha_vencimiento) >= new Date()
  })
  const antVencidos = detalle.antecedentes.filter(a =>
    a.fecha_vencimiento && new Date(a.fecha_vencimiento) < new Date()
  )

  return (
    <div className="bg-gray-950 border-t border-gray-800">
      {/* Tabs */}
      <div className="flex border-b border-gray-800 px-4">
        {(['consignaciones', 'documentos'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px ${
              tab === t
                ? 'border-blue-500 text-blue-400'
                : 'border-transparent text-gray-500 hover:text-gray-300'
            }`}>
            {t === 'consignaciones' ? 'Consignaciones' : 'Documentos'}
          </button>
        ))}
      </div>

      <div className="p-4">
        {/* ── CONSIGNACIONES ── */}
        {tab === 'consignaciones' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500">Año:</span>
                <div className="flex gap-1">
                  {añosDisponibles.map(año => (
                    <button key={año} onClick={() => setAñoVista(año)}
                      className={`px-2.5 py-0.5 rounded text-xs font-medium transition-colors ${
                        añoVista === año
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700'
                      }`}>
                      {año}
                    </button>
                  ))}
                </div>
              </div>
              <span className="text-sm font-semibold text-green-400 shrink-0">
                Total: ${totalAportes.toLocaleString('es-CO')}
              </span>
            </div>

            {aportesPeriodo.length === 0 ? (
              <div className="text-center py-8 text-gray-600 text-sm">Sin consignaciones en este período</div>
            ) : (
              <div className="overflow-x-auto rounded-lg border border-gray-800">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-gray-900 border-b border-gray-800 text-gray-400">
                      <th className="text-left px-3 py-2">Mes / Año</th>
                      <th className="text-left px-3 py-2">Valor</th>
                      <th className="text-left px-3 py-2">Método</th>
                      <th className="text-left px-3 py-2">Estado</th>
                      <th className="text-left px-3 py-2">Comprobante</th>
                    </tr>
                  </thead>
                  <tbody>
                    {aportesPeriodo.map((a, i) => {
                      const estado = (a.estado ?? 'pendiente') as string
                      const eStyle = ESTADO_AVAL[estado] ?? ESTADO_AVAL.pendiente
                      return (
                        <tr key={a.id}
                          className={`border-b border-gray-800/50 ${i % 2 === 0 ? '' : 'bg-gray-900/20'}`}>
                          <td className="px-3 py-2 text-gray-300">
                            {a.mes} {(a as any).año}
                          </td>
                          <td className="px-3 py-2 text-green-400 font-semibold">
                            {a.valor != null ? `$${a.valor}` : <span className="text-gray-700">—</span>}
                          </td>
                          <td className="px-3 py-2 text-gray-400">
                            {(a.metodo || a.banco)
                              ? `${a.metodo || ''}${a.banco ? ` / ${a.banco}` : ''}`.trim().replace(/^\/\s*/, '')
                              : <span className="text-gray-700">—</span>}
                          </td>
                          <td className="px-3 py-2">
                            <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${eStyle.cls}`}>
                              {eStyle.label}
                            </span>
                          </td>
                          <td className="px-3 py-2">
                            {a.public_url ? (
                              <a href={a.public_url} target="_blank" rel="noopener noreferrer"
                                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-blue-500/15 hover:bg-blue-500/25 border border-blue-500/30 hover:border-blue-500/50 text-blue-400 hover:text-blue-300 text-xs font-medium transition-all duration-200 cursor-pointer whitespace-nowrap">
                                <FileText className="w-3 h-3" /> Ver
                              </a>
                            ) : <span className="text-gray-700">—</span>}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* ── DOCUMENTOS ── */}
        {tab === 'documentos' && (
          <div className="space-y-4">
            {/* Período actual */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Calendar className="w-4 h-4 text-blue-400" />
                <span className="text-sm font-medium text-gray-200">
                  Período: {fmtFecha(p.fecha_inicio_patrocinio)} → {fmtFecha(p.fecha_fin_patrocinio)}
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <DocSlot
                  label="Formato de Postulación (FP)"
                  url={p.fp_public_url}
                  loading={fpLoading}
                  onUpload={f => subirDoc('fp', f)}
                  icon={FileText}
                />
                <DocSlot
                  label="Cédula de ciudadanía"
                  url={p.cedula_pdf_url}
                  loading={cedulaLoading}
                  onUpload={f => subirDoc('cedula', f)}
                  icon={CreditCard}
                />
              </div>
            </div>

            {/* Investigaciones de antecedentes */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Shield className="w-4 h-4 text-purple-400" />
                <span className="text-sm font-medium text-gray-200">
                  Investigaciones de Antecedentes
                </span>
                {detalle.antecedentes.length > 0 && (
                  <span className="text-xs text-gray-500">
                    ({antVigentes.length} vigentes, {antVencidos.length} vencidas)
                  </span>
                )}
              </div>

              {detalle.antecedentes.length === 0 ? (
                <div className="text-sm text-gray-600 py-3 text-center border border-gray-800 rounded-lg">
                  Sin IAs registradas
                </div>
              ) : (
                <div className="space-y-2">
                  {detalle.antecedentes.map(ant => {
                    const vencida = ant.fecha_vencimiento
                      ? new Date(ant.fecha_vencimiento) < new Date()
                      : false
                    const porVencer = ant.fecha_vencimiento && !vencida
                      ? Math.floor((new Date(ant.fecha_vencimiento).getTime() - Date.now()) / 86400000) <= 15
                      : false
                    return (
                      <div key={ant.id}
                        className={`flex items-center gap-3 p-3 rounded-lg border text-xs ${
                          vencida
                            ? 'bg-red-500/5 border-red-500/20'
                            : porVencer
                            ? 'bg-yellow-500/5 border-yellow-500/20'
                            : 'bg-gray-900 border-gray-800'
                        }`}>
                        <Shield className={`w-3.5 h-3.5 shrink-0 ${
                          vencida ? 'text-red-400' : porVencer ? 'text-yellow-400' : 'text-purple-400'
                        }`} />
                        <div className="flex-1 min-w-0">
                          <div className="font-medium text-gray-200">{ant.fuente}</div>
                          <div className="text-gray-500 mt-0.5">
                            Consulta: {fmtFechaCorta(ant.fecha_consulta)}
                            {ant.fecha_vencimiento && (
                              <span className={`ml-2 ${vencida ? 'text-red-400' : porVencer ? 'text-yellow-400' : 'text-gray-500'}`}>
                                · Vence: {fmtFechaCorta(ant.fecha_vencimiento)}
                                {vencida && ' ⚠ VENCIDA'}
                                {porVencer && !vencida && ' ⚠ por vencer'}
                              </span>
                            )}
                          </div>
                        </div>
                        {ant.public_url && (
                          <a href={ant.public_url} target="_blank" rel="noopener noreferrer"
                            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-blue-500/15 hover:bg-blue-500/25 border border-blue-500/30 hover:border-blue-500/50 text-blue-400 hover:text-blue-300 text-xs font-medium transition-all duration-200 cursor-pointer whitespace-nowrap shrink-0">
                            <FileText className="w-3 h-3" /> Ver PDF
                          </a>
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
    </div>
  )
}

export default function PatrocinadoresGestion() {
  const [patrocinadores, setPatrocinadores] = useState<Patrocinador[]>([])
  const [loading, setLoading] = useState(true)
  const [busqueda, setBusqueda] = useState('')
  const [filtroEstado, setFiltroEstado] = useState<'todos' | 'activo' | 'inactivo'>('activo')
  const [filtroZona, setFiltroZona] = useState<string>('todas')
  const [zonas, setZonas] = useState<string[]>([])
  const [toggleLoading, setToggleLoading] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [detalles, setDetalles] = useState<Record<string, DetallePat>>({})
  const [detalleLoading, setDetalleLoading] = useState<string | null>(null)
  const [pagina, setPagina] = useState(1)
  const POR_PAGINA = 15

  const cargar = useCallback(async () => {
    setLoading(true)
    const { data } = await supabase.from('patrocinadores').select('*').order('nombre')
    const lista = (data || []) as Patrocinador[]
    setPatrocinadores(lista)
    setZonas([...new Set(lista.map(p => p.zona))].sort())
    setLoading(false)
  }, [])

  useEffect(() => { cargar() }, [cargar])

  async function cargarDetalle(p: Patrocinador) {
    if (detalles[p.id]) return
    setDetalleLoading(p.id)

    const identifier = p.cedula
      ? { col: 'cedula', val: p.cedula }
      : { col: 'patrocinador', val: p.nombre }

    const [{ data: aData }, { data: antData }] = await Promise.all([
      p.cedula
        ? supabase.from('aportes').select('id, mes, año, valor, estado, public_url, metodo, banco').eq('cedula', p.cedula).order('año').order('mes')
        : supabase.from('aportes').select('id, mes, año, valor, estado, public_url, metodo, banco').ilike('patrocinador', p.nombre).order('año').order('mes'),
      p.cedula
        ? supabase.from('antecedentes').select('id, fuente, fecha_consulta, fecha_vencimiento, public_url').eq('cedula', p.cedula).order('fecha_consulta', { ascending: false })
        : supabase.from('antecedentes').select('id, fuente, fecha_consulta, fecha_vencimiento, public_url').ilike('nombre', p.nombre).order('fecha_consulta', { ascending: false }),
    ])

    setDetalles(prev => ({
      ...prev,
      [p.id]: {
        aportes: (aData || []) as any[],
        antecedentes: (antData || []) as any[],
      }
    }))
    setDetalleLoading(null)
  }

  async function toggleEstado(p: Patrocinador) {
    setToggleLoading(p.id)
    await supabase.from('patrocinadores').update({ estado: p.estado === 'activo' ? 'inactivo' : 'activo' }).eq('id', p.id)
    setToggleLoading(null)
    cargar()
  }

  async function handleExpand(p: Patrocinador) {
    if (expandedId === p.id) {
      setExpandedId(null)
      return
    }
    setExpandedId(p.id)
    await cargarDetalle(p)
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

  const totalPaginas = Math.ceil(filtrados.length / POR_PAGINA)
  const paginaActual = Math.min(pagina, totalPaginas || 1)
  const paginados = filtrados.slice((paginaActual - 1) * POR_PAGINA, paginaActual * POR_PAGINA)

  const activos = patrocinadores.filter(p => p.estado === 'activo').length
  const inactivos = patrocinadores.filter(p => p.estado === 'inactivo').length
  const porVencer = patrocinadores.filter(p => p.estado === 'activo' && getPatrocinioStatus(p.fecha_fin_patrocinio) === 'por_vencer').length
  const vencidos = patrocinadores.filter(p => p.estado === 'activo' && getPatrocinioStatus(p.fecha_fin_patrocinio) === 'vencido').length

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Users className="w-5 h-5 text-blue-400" />
        <h1 className="text-lg font-semibold text-white">Gestión de Patrocinadores</h1>
      </div>

      {/* Tarjetas */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-emerald-50 border border-emerald-200 dark:bg-emerald-500/10 dark:border-emerald-500/25 rounded-xl p-4 flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-emerald-100 dark:bg-emerald-500/20 flex items-center justify-center shrink-0">
            <CheckCircle className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
          </div>
          <div>
            <div className="text-2xl font-bold text-emerald-800 dark:text-emerald-400">{activos}</div>
            <div className="text-xs text-emerald-700/80 dark:text-emerald-400/70 mt-0.5">Activos</div>
          </div>
        </div>
        <div className="bg-slate-100 border border-slate-200 dark:bg-gray-900 dark:border-gray-800 rounded-xl p-4 flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-slate-200 dark:bg-gray-800 flex items-center justify-center shrink-0">
            <XCircle className="w-5 h-5 text-slate-400 dark:text-gray-400" />
          </div>
          <div>
            <div className="text-2xl font-bold text-slate-600 dark:text-gray-400">{inactivos}</div>
            <div className="text-xs text-slate-500 dark:text-gray-500 mt-0.5">Inactivos</div>
          </div>
        </div>
        <div className="bg-amber-50 border border-amber-200 dark:bg-amber-500/10 dark:border-amber-500/25 rounded-xl p-4 flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-amber-100 dark:bg-amber-500/20 flex items-center justify-center shrink-0">
            <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400" />
          </div>
          <div>
            <div className="text-2xl font-bold text-amber-800 dark:text-amber-400">{porVencer}</div>
            <div className="text-xs text-amber-700/80 dark:text-amber-400/70 mt-0.5">Por vencer</div>
          </div>
        </div>
        <div className="bg-red-50 border border-red-200 dark:bg-red-500/10 dark:border-red-500/25 rounded-xl p-4 flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-red-100 dark:bg-red-500/20 flex items-center justify-center shrink-0">
            <Clock className="w-5 h-5 text-red-600 dark:text-red-400" />
          </div>
          <div>
            <div className="text-2xl font-bold text-red-800 dark:text-red-400">{vencidos}</div>
            <div className="text-xs text-red-700/80 dark:text-red-400/70 mt-0.5">Patrocinio vencido</div>
          </div>
        </div>
      </div>

      {/* Filtros */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input type="text" placeholder="Buscar por nombre o cédula..."
            value={busqueda} onChange={e => { setBusqueda(e.target.value); setPagina(1) }}
            className="w-full pl-9 pr-4 py-2 bg-white dark:bg-gray-900 border border-slate-300 dark:border-gray-700 rounded-lg text-sm text-slate-900 dark:text-gray-100 placeholder:text-slate-400 dark:placeholder:text-gray-500 focus:outline-none focus:border-blue-500" />
        </div>
        <select value={filtroEstado} onChange={e => { setFiltroEstado(e.target.value as any); setPagina(1) }}
          className="bg-white dark:bg-gray-900 border border-slate-300 dark:border-gray-700 rounded-lg px-3 py-2 text-sm text-slate-900 dark:text-gray-100 focus:outline-none focus:border-blue-500">
          <option value="todos">Todos</option>
          <option value="activo">Activos</option>
          <option value="inactivo">Inactivos</option>
        </select>
        <select value={filtroZona} onChange={e => { setFiltroZona(e.target.value); setPagina(1) }}
          className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500">
          <option value="todas">Todas las zonas</option>
          {zonas.map(z => <option key={z} value={z}>{z}</option>)}
        </select>
      </div>

      {/* Tabla */}
      {loading ? (
        <div className="text-center py-16 text-gray-500">Cargando patrocinadores...</div>
      ) : filtrados.length === 0 ? (
        <div className="text-center py-16 text-gray-500">Sin resultados.</div>
      ) : (
        <>
        <div className="rounded-xl border border-gray-800 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-900 border-b border-gray-800 text-xs text-gray-400">
                <th className="w-8 px-2 py-3"></th>
                <th className="text-left px-4 py-3 min-w-[200px]">Nombre</th>
                <th className="text-left px-3 py-3 whitespace-nowrap">Cédula</th>
                <th className="text-left px-3 py-3 whitespace-nowrap">Zona</th>
                <th className="text-left px-3 py-3 whitespace-nowrap">Período patrocinio</th>
                <th className="text-left px-3 py-3 whitespace-nowrap">Estado patrocinio</th>
                <th className="text-left px-3 py-3 whitespace-nowrap">Estado</th>
              </tr>
            </thead>
            <tbody>
              {paginados.map((p, i) => {
                const pStatus = getPatrocinioStatus(p.fecha_fin_patrocinio)
                const dias = p.fecha_fin_patrocinio
                  ? Math.floor((new Date(p.fecha_fin_patrocinio).getTime() - Date.now()) / 86400000)
                  : null
                const isExpanded = expandedId === p.id
                const detalle = detalles[p.id]

                return (
                  <React.Fragment key={p.id}>
                    <tr
                      className={`border-b border-gray-800/50 hover:bg-gray-800/20 transition-colors cursor-pointer ${
                        i % 2 === 0 ? '' : 'bg-gray-900/20'
                      } ${p.estado === 'inactivo' ? 'opacity-50' : ''} ${isExpanded ? 'bg-gray-800/30' : ''}`}
                      onClick={() => handleExpand(p)}>
                      <td className="px-2 py-3 text-center">
                        {detalleLoading === p.id
                          ? <Loader2 className="w-3.5 h-3.5 text-gray-400 animate-spin mx-auto" />
                          : isExpanded
                          ? <ChevronDown className="w-3.5 h-3.5 text-blue-400 mx-auto" />
                          : <ChevronRight className="w-3.5 h-3.5 text-gray-600 mx-auto" />
                        }
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-medium text-white">{p.nombre}</div>
                        {p.telefono && <div className="text-xs text-gray-500">{p.telefono}</div>}
                      </td>
                      <td className="px-3 py-3 text-gray-300 text-xs font-mono" onClick={e => e.stopPropagation()}>
                        {p.cedula || <span className="text-gray-600">—</span>}
                      </td>
                      <td className="px-3 py-3 text-gray-400 text-xs whitespace-nowrap">{p.zona}</td>
                      <td className="px-3 py-3 text-xs whitespace-nowrap">
                        {p.fecha_inicio_patrocinio ? (
                          <span className="text-gray-300">
                            {fmtFecha(p.fecha_inicio_patrocinio)} → {fmtFecha(p.fecha_fin_patrocinio)}
                          </span>
                        ) : <span className="text-gray-600">—</span>}
                      </td>
                      <td className="px-3 py-3">
                        {p.estado === 'activo' ? (
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md border text-xs font-medium ${P_STYLES[pStatus]}`}>
                            {pStatus === 'vencido' && <XCircle className="w-3 h-3" />}
                            {pStatus === 'por_vencer' && <AlertTriangle className="w-3 h-3" />}
                            {pStatus === 'vigente' && <CheckCircle className="w-3 h-3" />}
                            {pStatus === 'sin_fecha' && <Clock className="w-3 h-3" />}
                            {P_LABEL[pStatus]}
                            {dias !== null && pStatus !== 'sin_fecha' && (
                              <span className="opacity-70">{dias >= 0 ? ` (${dias}d)` : ` (${Math.abs(dias)}d ago)`}</span>
                            )}
                          </span>
                        ) : <span className="text-gray-600 text-xs">—</span>}
                      </td>
                      <td className="px-3 py-3" onClick={e => e.stopPropagation()}>
                        <button
                          onClick={() => toggleEstado(p)}
                          disabled={toggleLoading === p.id}
                          className={`px-3 py-1 rounded-md text-xs font-medium transition-colors disabled:opacity-50 border ${
                            p.estado === 'activo'
                              ? 'bg-green-500/20 text-green-400 hover:bg-red-500/20 hover:text-red-400 border-green-500/30 hover:border-red-500/30'
                              : 'bg-gray-800 text-gray-400 hover:bg-green-500/20 hover:text-green-400 border-gray-700 hover:border-green-500/30'
                          }`}>
                          {toggleLoading === p.id ? '...' : p.estado === 'activo' ? 'Activo' : 'Inactivo'}
                        </button>
                      </td>
                    </tr>
                    {isExpanded && detalle && (
                      <tr>
                        <td colSpan={7} className="p-0">
                          <PanelDetalle
                            p={p}
                            detalle={detalle}
                            onReload={() => {
                              setDetalles(prev => { const n = { ...prev }; delete n[p.id]; return n })
                              cargar().then(() => cargarDetalle(p))
                            }}
                          />
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                )
              })}
            </tbody>
          </table>
        </div>

        {/* Paginación */}
        {totalPaginas > 1 && (
          <div className="flex items-center justify-between pt-2">
            <span className="text-xs text-gray-500">
              {filtrados.length} patrocinadores · página {paginaActual} de {totalPaginas}
            </span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setPagina(1)}
                disabled={paginaActual === 1}
                className="px-2 py-1 rounded text-xs text-gray-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed">
                «
              </button>
              <button
                onClick={() => setPagina(p => Math.max(1, p - 1))}
                disabled={paginaActual === 1}
                className="px-2 py-1 rounded text-xs text-gray-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed">
                ‹
              </button>
              {Array.from({ length: totalPaginas }, (_, i) => i + 1)
                .filter(n => n === 1 || n === totalPaginas || Math.abs(n - paginaActual) <= 2)
                .reduce<(number | '...')[]>((acc, n, idx, arr) => {
                  if (idx > 0 && n - (arr[idx - 1] as number) > 1) acc.push('...')
                  acc.push(n)
                  return acc
                }, [])
                .map((n, idx) => n === '...'
                  ? <span key={`e${idx}`} className="px-1 text-xs text-gray-600">…</span>
                  : <button key={n}
                      onClick={() => setPagina(n as number)}
                      className={`w-7 h-7 rounded text-xs font-medium transition-colors ${
                        paginaActual === n
                          ? 'bg-blue-600 text-white'
                          : 'text-gray-400 hover:text-white hover:bg-gray-800'
                      }`}>
                      {n}
                    </button>
                )}
              <button
                onClick={() => setPagina(p => Math.min(totalPaginas, p + 1))}
                disabled={paginaActual === totalPaginas}
                className="px-2 py-1 rounded text-xs text-gray-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed">
                ›
              </button>
              <button
                onClick={() => setPagina(totalPaginas)}
                disabled={paginaActual === totalPaginas}
                className="px-2 py-1 rounded text-xs text-gray-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed">
                »
              </button>
            </div>
          </div>
        )}
        </>
      )}
    </div>
  )
}
