import { Routes, Route, useLocation } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import Home from './pages/Home'
import Loading from './pages/Loading'
import Analysis from './pages/Analysis'

export default function App() {
  const location = useLocation()

  return (
    <div className="min-h-screen bg-[#0A0A0A]">
      <AnimatePresence mode="wait">
        <Routes location={location} key={location.pathname}>
          <Route path="/" element={<Home />} />
          <Route path="/loading/:jobId" element={<Loading />} />
          <Route path="/analysis/:sport/:gameId" element={<Analysis />} />
        </Routes>
      </AnimatePresence>
    </div>
  )
}