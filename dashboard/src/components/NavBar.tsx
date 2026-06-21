'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Sun, Moon } from 'lucide-react'
import { useTheme } from '@/components/ThemeProvider'

const LINKS = [
  { href: '/', label: 'Aportes Nuevos' },
  { href: '/resumen', label: 'Resumen Anual' },
  { href: '/patrocinadores', label: 'Patrocinadores' },
  { href: '/historial', label: 'Historial Avales' },
]

export default function NavBar() {
  const pathname = usePathname()
  const { theme, toggle } = useTheme()

  return (
    <div className="flex items-center gap-1 flex-1">
      <nav className="flex gap-1 flex-1 flex-wrap">
        {LINKS.map(({ href, label }) => {
          const active = href === '/' ? pathname === '/' : pathname.startsWith(href)
          return (
            <Link key={href} href={href}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all duration-150 border ${
                active
                  ? 'bg-blue-600/10 dark:bg-blue-600/20 text-blue-700 dark:text-blue-400 border-blue-300/60 dark:border-blue-500/40'
                  : 'text-slate-600 dark:text-gray-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-gray-800 border-transparent hover:border-slate-200 dark:hover:border-gray-700'
              }`}>
              {label}
            </Link>
          )
        })}
      </nav>
      <button
        onClick={toggle}
        aria-label={theme === 'dark' ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'}
        className="ml-2 p-2 rounded-lg text-slate-500 dark:text-gray-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-gray-800 border border-transparent hover:border-slate-200 dark:hover:border-gray-700 transition-all duration-150 cursor-pointer shrink-0"
      >
        {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
      </button>
    </div>
  )
}
