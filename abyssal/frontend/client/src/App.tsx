import { Routes, Route, Link, useLocation } from 'react-router-dom'
import SearchPage from './pages/SearchPage'
import DirectoryPage from './pages/DirectoryPage'
import SitePage from './pages/SitePage'
import WaybackPage from './pages/WaybackPage'
import AdminPage from './pages/AdminPage'

export default function App() {
  const loc = useLocation()
  const isSearch = loc.pathname === '/'

  return (
    <div className="min-h-screen flex flex-col">
      {/* Top nav — minimal, search-focused */}
      {!isSearch && (
        <nav className="border-b border-gray-800 px-4 py-2 flex items-center gap-4 text-sm">
          <Link to="/" className="font-bold text-cyan-400">Abyssal</Link>
          <Link to="/browse" className="text-gray-400 hover:text-white">Directory</Link>
          <Link to="/wayback" className="text-gray-400 hover:text-white">Wayback</Link>
          <Link to="/admin" className="text-gray-400 hover:text-white">Admin</Link>
        </nav>
      )}

      <main className="flex-1">
        <Routes>
          <Route path="/" element={<SearchPage />} />
          <Route path="/browse" element={<DirectoryPage />} />
          <Route path="/site/:hostname" element={<SitePage />} />
          <Route path="/wayback" element={<WaybackPage />} />
          <Route path="/admin" element={<AdminPage />} />
        </Routes>
      </main>
    </div>
  )
}
