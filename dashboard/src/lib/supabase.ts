import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL = 'https://xhigifzmylcaxkxzqzom.supabase.co'
const SUPABASE_KEY = process.env.NEXT_PUBLIC_SUPABASE_KEY!

export const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

export type Aporte = {
  id: string
  created_at: string
  zona: string
  patrocinador: string
  cedula: string
  mes: string
  año: string
  valor: string
  metodo: string
  comprobante: string
  banco: string
  fecha_aporte: string
  filename: string
  storage_path: string
  public_url: string
}

export type Antecedente = {
  id: string
  created_at: string
  zona: string
  patrocinador: string
  cedula: string
  fuente: string
  fecha_consulta: string
  fecha_vencimiento: string
  storage_path: string
  public_url: string
}

export type VigenciaStatus = 'vigente' | 'por_vencer' | 'vencido' | 'sin_registro'
