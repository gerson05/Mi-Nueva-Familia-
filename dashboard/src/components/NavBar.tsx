'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

const LINKS = [
  { href: '/', label: 'Aportes Nuevos' },
  { href: '/resumen', label: 'Resumen Anual' },
  { href: '/patrocinadores', label: 'Patrocinadores' },
  { href: '/historial', label: 'Historial Avales' },
]

export default function NavBar() {
  const pathname = usePathname()
  return (
    <nav className="flex gap-1">
      {LINKS.map(({ href, label }) => {
        const active = href === '/' ? pathname === '/' : pathname.startsWith(href)
        return (
          <Link key={href} href={href}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all duration-150 border ${
              active
                ? 'bg-blue-600/20 text-blue-400 border-blue-500/40'
                : 'text-gray-400 hover:text-white hover:bg-gray-800 border-transparent hover:border-gray-700'
            }`}>
            {label}
          </Link>
        )
      })}
    </nav>
  )
}
