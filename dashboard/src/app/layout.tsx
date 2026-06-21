import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import NavBar from '@/components/NavBar'
import './globals.css'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Mi Nueva Familia — Panel Zonal',
  description: 'Revisión de aportes y antecedentes por zona',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body className={`${inter.className} bg-gray-950 text-gray-100 min-h-screen`}>
        <header className="border-b border-gray-800 bg-gray-900/95 backdrop-blur-md sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-4 py-3 flex items-center gap-6">
            <div className="flex items-center gap-2.5 shrink-0">
              <div className="w-7 h-7 rounded-lg bg-blue-600 flex items-center justify-center shrink-0">
                <span className="text-white text-xs font-bold leading-none">MF</span>
              </div>
              <span className="text-base font-semibold text-white">Mi Nueva Familia</span>
            </div>
            <NavBar />
          </div>
        </header>
        <main className="max-w-7xl mx-auto px-4 py-6">
          {children}
        </main>
      </body>
    </html>
  )
}
