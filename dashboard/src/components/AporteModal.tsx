'use client'

import { useState } from 'react'
import { supabase, Aporte } from '@/lib/supabase'
import { MESES, METODOS_PAGO } from '@/lib/utils'
import Modal from './Modal'
import { Upload, Loader2 } from 'lucide-react'

const SUPABASE_URL = 'https://xhigifzmylcaxkxzqzom.supabase.co'

type Props = {
  open: boolean
  onClose: () => void
  onSaved: () => void
  mode: 'add' | 'edit'
  aporte?: Aporte
  contexto?: { patrocinador: string; cedula: string; zona: string }
}

export default function AporteModal({ open, onClose, onSaved, mode, aporte, contexto }: Props) {
  const ctx = aporte ?? contexto!
  const [form, setForm] = useState({
    mes: aporte?.mes ?? '',
    año: aporte?.año ?? new Date().getFullYear().toString(),
    valor: aporte?.valor ?? '',
    metodo: aporte?.metodo ?? '',
    comprobante: aporte?.comprobante ?? '',
    banco: aporte?.banco ?? '',
    fecha_aporte: aporte?.fecha_aporte ?? new Date().toISOString().split('T')[0],
  })
  const [archivo, setArchivo] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  function set(k: string, v: string) { setForm(f => ({ ...f, [k]: v })) }

  async function guardar() {
    if (!form.mes || !form.año || !form.valor) { setError('Mes, año y valor son obligatorios'); return }
    if (mode === 'add' && !archivo) { setError('Debes adjuntar el PDF del comprobante'); return }
    setLoading(true); setError('')

    try {
      let storage_path = aporte?.storage_path ?? ''
      let public_url = aporte?.public_url ?? ''

      if (archivo) {
        const ext = archivo.name.split('.').pop()
        const nombre = `${ctx.patrocinador}_${form.mes}_${form.año}_${Date.now()}.${ext}`
          .replace(/[^a-zA-Z0-9._-]/g, '_')
        const path = `${ctx.zona}/${ctx.patrocinador}/aportes/${nombre}`

        if (aporte?.storage_path) {
          await supabase.storage.from('recibos').remove([aporte.storage_path])
        }

        const { error: upErr } = await supabase.storage.from('recibos').upload(path, archivo, { upsert: true })
        if (upErr) throw upErr

        storage_path = path
        public_url = `${SUPABASE_URL}/storage/v1/object/public/recibos/${path}`
      }

      if (mode === 'add') {
        const { error: dbErr } = await supabase.from('aportes').insert({
          zona: ctx.zona,
          patrocinador: ctx.patrocinador,
          cedula: ctx.cedula,
          ...form,
          storage_path,
          public_url,
          filename: archivo!.name,
        })
        if (dbErr) throw dbErr
      } else {
        const { error: dbErr } = await supabase.from('aportes').update({
          ...form,
          ...(archivo ? { storage_path, public_url, filename: archivo.name } : {}),
        }).eq('id', aporte!.id)
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
  const input = (k: string, type = 'text', placeholder = '') => (
    <input
      type={type}
      value={(form as Record<string, string>)[k]}
      onChange={e => set(k, e.target.value)}
      placeholder={placeholder}
      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
    />
  )

  return (
    <Modal open={open} onClose={onClose} title={mode === 'add' ? 'Agregar Aporte' : 'Editar Aporte'}>
      <div className="space-y-4">
        <div className="bg-gray-800/50 rounded-lg px-3 py-2 text-sm text-gray-300">
          <span className="font-medium text-white">{ctx.patrocinador}</span>
          <span className="text-gray-500 ml-2">CC: {ctx.cedula}</span>
          <span className="text-gray-500 ml-2">· {ctx.zona}</span>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            {label('Mes *')}
            <select value={form.mes} onChange={e => set('mes', e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500">
              <option value="">Seleccionar...</option>
              {MESES.map(m => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
          <div>
            {label('Año *')}
            {input('año', 'text', '2024')}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            {label('Valor *')}
            {input('valor', 'text', '50000')}
          </div>
          <div>
            {label('Método de pago')}
            <select value={form.metodo} onChange={e => set('metodo', e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500">
              <option value="">Seleccionar...</option>
              {METODOS_PAGO.map(m => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            {label('N° Comprobante')}
            {input('comprobante', 'text', '12345')}
          </div>
          <div>
            {label('Banco')}
            {input('banco', 'text', 'Bancolombia')}
          </div>
        </div>

        <div>
          {label('Fecha del aporte')}
          {input('fecha_aporte', 'date')}
        </div>

        <div>
          {label(mode === 'add' ? 'PDF Comprobante *' : 'Reemplazar PDF (opcional)')}
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
            {mode === 'add' ? 'Guardar aporte' : 'Guardar cambios'}
          </button>
        </div>
      </div>
    </Modal>
  )
}
