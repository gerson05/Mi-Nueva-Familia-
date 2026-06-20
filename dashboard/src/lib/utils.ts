import { VigenciaStatus } from './supabase'

export function getVigenciaStatus(fechaVencimiento: string): VigenciaStatus {
  const hoy = new Date()
  const vence = new Date(fechaVencimiento)
  const diasRestantes = Math.floor((vence.getTime() - hoy.getTime()) / (1000 * 60 * 60 * 24))
  if (diasRestantes < 0) return 'vencido'
  if (diasRestantes <= 15) return 'por_vencer'
  return 'vigente'
}

export function getDiasRestantes(fechaVencimiento: string): number {
  const hoy = new Date()
  const vence = new Date(fechaVencimiento)
  return Math.floor((vence.getTime() - hoy.getTime()) / (1000 * 60 * 60 * 24))
}

export const FUENTES = ['policia', 'procuraduria', 'contraloria', 'ofac'] as const
export const FUENTE_LABELS: Record<string, string> = {
  policia: 'Policía',
  procuraduria: 'Procuraduría',
  contraloria: 'Contraloría',
  ofac: 'OFAC',
}

export const STATUS_COLORS: Record<VigenciaStatus, string> = {
  vigente: 'bg-green-500/20 text-green-400 border-green-500/30',
  por_vencer: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  vencido: 'bg-red-500/20 text-red-400 border-red-500/30',
  sin_registro: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
}

export const STATUS_LABELS: Record<VigenciaStatus, string> = {
  vigente: 'Vigente',
  por_vencer: 'Por vencer',
  vencido: 'Vencido',
  sin_registro: 'Sin registro',
}
