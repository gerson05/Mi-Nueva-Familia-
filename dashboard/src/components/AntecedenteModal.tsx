'use client'

import { useState } from 'react'
import { supabase, Antecedente } from '@/lib/supabase'
import { FUENTES, FUENTE_LABELS } from '@/lib/utils'
import Modal from './Modal'
import { Upload, Loader2 } from 'lucide-react'

const SUPABASE_URL = 'https://xhigifzmylcaxkxzqzom.supabase.co'

type Props = {
  open: boolean
  onClose: () => void
  onSaved: () => void
  mode: 'add' | 'edit'
  antecedente?: Antecedente
  contexto?: { patrocinador: string; cedula: string; zona: string }
  fuenteInicial?: string
}

export default function AntecedenteModal({ open, onClose, onSaved, mode, antecedente, contexto, fuenteInicial }: Props) {
  const ctx = antecedente ?? contexto!
  const [form, setForm] = useState({
    fuente: antecedente?.fuente ?? fuenteInicial ?? '',
    fecha_consulta: antecedente?.fecha_consulta ?? new Date().toISOString().split('T')[0],
    fecha_vencimiento: antecedente?.fecha_vencimiento ?? (() => {
      const d = new Date(); d.setDate(d.getDate() + 90); return d.toISOString().split('T')[0]
    })(),
  })
  const [archivo, setArchivo] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  function set(k: string, v: string) {
    setForm(f => {
      const next = { ...f, [k]: v }
      if (k === 'fecha_consulta') {
        const d = new Date(v); d.setDate(d.getDate() + 90)
        next.fecha_vencimiento = d.toISOString().split('T')[0]
      }
      return next
    })
  }

  async function guardar() {
    if (!form.fuente || !form.fecha_consulta) { setError('Fuente y fecha son obligatorias'); return }
    if (mode === 'add' && !archivo) { setError('Debes adjuntar el PDF'); return }
    setLoading(true); setError('')

    try {
      let storage_path = antecedente?.storage_path ?? ''
      let public_url = antecedente?.public_url ?? ''

      if (archivo) {
        const ext = archivo.name.split('.').pop()
        const nombre = `${form.fuente}_${form.fecha_consulta}_${Date.now()}.${ext}`
          .replace(/[^a-zA-Z0-9._-]/g, '_')
        const path = `${ctx.zona}/${ctx.patrocinador}-${ctx.cedula}/antecedentes/${form.fuente}/${nombre}`

        if (antecedente?.storage_path) {
          await supabase.storage.from('recibos').remove([antecedente.storage_path])
        }

        const { error: upErr } = await supabase.storage.from('recibos').upload(path, archivo, { upsert: true })
        if (upErr) throw upErr

        storage_path = path
        public_url = `${SUPABASE_URL}/storage/v1/object/public/recibos/${path}`
      }

      if (mode === 'add') {
        const { error: dbErr } = await supabase.from('antecedentes').insert({
          zona: ctx.zona,
          patrocinador: ctx.patrocinador,
          cedula: ctx.cedula,
          fuente: form.fuente,
          fecha_consulta: form.fecha_consulta,
          fecha_vencimiento: form.fecha_vencimiento,
          storage_path,
          public_url,
        })
        if (dbErr) throw dbErr
      } else {
        const { error: dbErr } = await supabase.from('antecedentes').update({
          fecha_consulta: form.fecha_consulta,
          fecha_vencimiento: form.fecha_vencimiento,
          ...(archivo ? { storage_path, public_url } : {}),
        }).eq('id', antecedente!.id)
        if (dbErr) throw dbErr
      }

      onSaved(); onClose()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Error al guardar')
    } finally {
      setLoading(false)
    }
  }

  const label = (t: string) => <label className="block text-xs text-gray-400 mb-1">{t}</label>

  return (
    <Modal open={open} onClose={onClose} title={mode === 'add' ? 'Agregar Antecedente' : 'Editar Antecedente'}>
      <div className="space-y-4">
        <div className="bg-gray-800/50 rounded-lg px-3 py-2 text-sm text-gray-300">
          <span className="font-medium text-white">{ctx.patrocinador}</span>
          <span className="text-gray-500 ml-2">CC: {ctx.cedula}</span>
          <span className="text-gray-500 ml-2">· {ctx.zona}</span>
        </div>

        <div>
          {label('Fuente *')}
          <select value={form.fuente} onChange={e => set('fuente', e.target.value)}
            disabled={mode === 'edit'}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 disabled:opacity-60">
            <option value="">Seleccionar...</option>
            {FUENTES.map(f => <option key={f} value={f}>{FUENTE_LABELS[f]}</option>)}
          </select>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            {label('Fecha consulta *')}
            <input type="date" value={form.fecha_consulta} onChange={e => set('fecha_consulta', e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500" />
          </div>
          <div>
            {label('Fecha vencimiento (auto +90 días)')}
            <input type="date" value={form.fecha_vencimiento} onChange={e => set('fecha_vencimiento', e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500" />
          </div>
        </div>

        <div>
          {label(mode === 'add' ? 'PDF Antecedente *' : 'Reemplazar PDF (opcional)')}
          <label className="flex items-center gap-3 w-full bg-gray-800 border border-dashed border-gray-600 rounded-lg px-3 py-3 cursor-pointer hover:border-blue-500 transition-colors">
            <Upload className="w-4 h-4 text-gray-400 shrink-0" />
            <span className="text-sm text-gray-400 truncate">
              {archivo ? archivo.name : 'Seleccionar archivo PDF'}
            </span>
            <input type="file" accept=".pdf" className="hidden"
              onChange={e => setArchivo(e.target.files?.[0] ?? null)} />
          </label>
        </div>

        {error && <p className="text-red-400 text-sm">{error}</p>}

        <div className="flex gap-2 pt-2">
          <button onClick={onClose} disabled={loading}
            className="flex-1 px-4 py-2 bg-gray-800 text-gray-300 rounded-lg text-sm hover:bg-gray-700 transition-colors disabled:opacity-50">
            Cancelar
          </button>
          <button onClick={guardar} disabled={loading}
            className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-500 transition-colors disabled:opacity-50 flex items-center justify-center gap-2">
            {loading && <Loader2 className="w-4 h-4 animate-spin" />}
            {mode === 'add' ? 'Guardar antecedente' : 'Guardar cambios'}
          </button>
        </div>
      </div>
    </Modal>
  )
}
