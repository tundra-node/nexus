import { Routes, Route, Link } from 'react-router-dom'
import SearchPage      from './pages/SearchPage'
import DirectoryPage   from './pages/DirectoryPage'
import SitePage        from './pages/SitePage'
import WaybackPage     from './pages/WaybackPage'
import AddressBookPage from './pages/AddressBookPage'

export default function App() {
  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-b from-[#0a1628] via-gray-950 to-gray-950">
      <nav className="border-b border-gray-800/50 bg-gray-950/80 backdrop-blur-sm px-4 py-2 flex items-center gap-4 text-sm">
        <Link to="/" className="font-bold bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">Abyssal</Link>
        <Link to="/browse"       className="text-gray-400 hover:text-white">Directory</Link>
        <Link to="/wayback"      className="text-gray-400 hover:text-white">Wayback</Link>
        <Link to="/addressbook"  className="text-gray-400 hover:text-white">Address Book</Link>
      </nav>

      <main className="flex-1">
        <Routes>
          <Route path="/"            element={<SearchPage />} />
          <Route path="/browse"      element={<DirectoryPage />} />
          <Route path="/site/:hostname" element={<SitePage />} />
          <Route path="/wayback"     element={<WaybackPage />} />
          <Route path="/addressbook" element={<AddressBookPage />} />
        </Routes>
      </main>
    </div>
  )
}
