import { useState, useEffect, useRef } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Helmet } from 'react-helmet-async'
import { SPORTS } from '../config'
import { getCachedGames, startAnalysis, getHealth, discoverLatest } from '../api'
import { useWindowSize } from '../hooks/useWindowSize'

const NBA_SEASON_ENDED = false

const SPORT_HINTS = {
  nba:      'NBA Finals live! Try: Knicks, Spurs — Game 4 tonight',
  f1:       'Use race names: Monaco, Canada, Miami — or format 2026/6',
  soccer:   "EPL teams only: 'latest', 'Arsenal', 'Chelsea', 'Liverpool', 'Brighton'",
  valorant: "Use 'latest' for the most recent VCT match",
  mlb:      "Use 'latest' or a game ID like '824916'",
}

const SPORT_PLACEHOLDERS = {
  nba:      'Knicks, Celtics, Thunder...',
  f1:       'Monaco, Canada, latest...',
  soccer:   'latest, premier_league...',
  valorant: 'latest...',
  mlb:      'latest, 824916...',
}

export default function Home() {
  const navigate = useNavigate()
  const location = useLocation()
  const { isMobile } = useWindowSize()

  const [selectedSport, setSelectedSport] = useState(() => sessionStorage.getItem('lastSport') || 'nba')
  const [allGames, setAllGames] = useState({})
  const [games, setGames] = useState([])
  const [matchInput, setMatchInput] = useState(() => location.state?.prefill || '')
  const [persona, setPersona] = useState('espn_formal')
  const [forceRefresh, setForceRefresh] = useState(false)
  const [loading, setLoading] = useState(false)
  const [gamesLoading, setGamesLoading] = useState(false)
  const [hoveredGame, setHoveredGame] = useState(null)
  const [discovering, setDiscovering] = useState(false)
  const [apiDown, setApiDown] = useState(false)
  const [recentGames, setRecentGames] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem('recentGames') || '[]') } catch { return [] }
  })
  const [showOnboarding, setShowOnboarding] = useState(() => {
    try { return !localStorage.getItem('hasVisited') } catch { return false }
  })

  const failCountRef = useRef(0)
  const healthTimerRef = useRef(null)
  const handleAnalyzeRef = useRef(null)

  const sport = SPORTS[selectedSport]

  // Health check
  useEffect(() => {
    const checkHealth = () => {
      getHealth()
        .then(() => { failCountRef.current = 0; setApiDown(false) })
        .catch(() => { failCountRef.current += 1; if (failCountRef.current >= 2) setApiDown(true) })
    }
    checkHealth()
    healthTimerRef.current = setInterval(checkHealth, 15000)
    return () => clearInterval(healthTimerRef.current)
  }, [])

  // Preload all sports
  useEffect(() => {
    setGamesLoading(true)
    Promise.all(
      ['nba', 'f1', 'soccer', 'valorant', 'mlb'].map(s =>
        getCachedGames(s).then(d => [s, d.games || []]).catch(() => [s, []])
      )
    ).then(results => {
      const map = Object.fromEntries(results)
      setAllGames(map)
      const initial = sessionStorage.getItem('lastSport') || 'nba'
      setGames(map[initial] || [])
    }).finally(() => setGamesLoading(false))
  }, [])

  // Update displayed games when sport changes
  useEffect(() => {
    if (Object.keys(allGames).length === 0) return
    const g = allGames[selectedSport] || []
    setGames(g)
  }, [selectedSport, allGames])

  // Pre-fill from navigation state
  useEffect(() => {
    if (location.state?.prefill) {
      setMatchInput(location.state.prefill)
      if (location.state.sport) {
        setSelectedSport(location.state.sport)
        sessionStorage.setItem('lastSport', location.state.sport)
      }
    }
  }, [location.state])

  const handleAnalyze = async () => {
    if (!matchInput.trim()) return
    setLoading(true)
    try {
      const data = await startAnalysis(selectedSport, matchInput, persona, forceRefresh)
      if (data.job_id) {
        navigate(`/loading/${data.job_id}`, { state: { sport: selectedSport, matchId: matchInput } })
      }
    } catch (err) {
      console.error(err)
      setLoading(false)
    }
  }

  handleAnalyzeRef.current = handleAnalyze

  // Cmd/Ctrl+Enter keyboard shortcut
  useEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        e.preventDefault()
        handleAnalyzeRef.current?.()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  const handleViewGame = (game) => {
    const safeId = game.game_id.replace(/\//g, '_')
    navigate(`/analysis/${game.sport}/${safeId}`)
  }

  const handleDiscover = async () => {
    if (discovering || loading) return
    setDiscovering(true)
    try {
      const found = await discoverLatest(selectedSport)
      const data = await startAnalysis(selectedSport, found.match_id, persona, false)
      if (data.job_id) {
        navigate(`/loading/${data.job_id}`, { state: { sport: selectedSport, matchId: found.match_id } })
      }
    } catch (err) {
      console.error('Discovery failed:', err)
      if (selectedSport !== 'nba') setMatchInput('latest')
    } finally {
      setDiscovering(false)
    }
  }

  const dismissOnboarding = () => {
    try { localStorage.setItem('hasVisited', '1') } catch {}
    setShowOnboarding(false)
  }

  const parseCardTitle = (game) => {
    let raw = game.title || ''
    if (!raw) return { title: (game.match_id || game.game_id).replace(/_/g, ' '), score: null }

    let score = null, title = raw
    const commaScore = raw.match(/^(.+?)\s+(\d+),\s+(.+?)\s+(\d+)$/)
    if (commaScore) {
      const [, t1, s1, t2, s2] = commaScore
      const shorten = t => { const p = t.trim().split(' '); return p.length > 2 ? p.slice(-2).join(' ') : t.trim() }
      return { title: `${shorten(t1)} vs ${shorten(t2)}`, score: `${s1}–${s2}` }
    }
    const dashScore = raw.match(/(\d+)[–-](\d+)/)
    if (dashScore) {
      score = `${dashScore[1]}–${dashScore[2]}`
      title = raw.replace(dashScore[0], '').replace(/\s{2,}/g, ' ').replace(/[:\|].*$/, '').trim()
    }
    return { title: title || raw, score }
  }

  const formatMatchDate = (game) => {
    const dateStr = game.match_date || game.cached_at
    if (!dateStr) return ''
    try { return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) } catch { return '' }
  }

  const counts = Object.fromEntries(
    Object.keys(SPORTS).map(k => [k, (allGames[k] || []).length])
  )

  const isNba = selectedSport === 'nba'

  return (
    <>
      <Helmet>
        <title>SportsCast AI — Multi-Agent Sports Analysis</title>
        <meta name="description" content="AI broadcast-quality sports analysis. NBA, F1, MLB, Soccer, Valorant powered by a 5-agent LangGraph pipeline with Claude Opus 4." />
        <meta property="og:title" content="SportsCast AI — Multi-Agent Sports Analysis" />
        <meta property="og:description" content="Five specialized AI agents analyze live match data and generate broadcast-quality narratives." />
        <meta property="og:type" content="website" />
      </Helmet>

      {/* ── ONBOARDING OVERLAY ── */}
      <AnimatePresence>
        {showOnboarding && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={dismissOnboarding}
            style={{
              position: 'fixed', inset: 0,
              backgroundColor: 'rgba(0,0,0,0.88)',
              zIndex: 999,
              display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center',
              padding: '24px',
            }}
          >
            <motion.div
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.1 }}
              onClick={e => e.stopPropagation()}
              style={{
                backgroundColor: '#111', border: `1px solid ${sport.color}30`,
                borderRadius: '20px', padding: '40px 48px',
                maxWidth: '480px', width: '100%',
                boxShadow: `0 0 60px ${sport.color}15`,
              }}
            >
              <div style={{
                fontSize: '10px', color: sport.color, letterSpacing: '3px',
                textTransform: 'uppercase', marginBottom: '20px', fontWeight: 700,
              }}>
                Welcome to SportsCast AI
              </div>
              <h2 style={{
                fontFamily: 'Bebas Neue, sans-serif', fontSize: '32px',
                color: '#FFF', letterSpacing: '2px', margin: '0 0 32px 0',
              }}>
                HOW IT WORKS
              </h2>

              {[
                { n: '1', title: 'Pick a sport', desc: 'Choose NBA, F1, MLB, Soccer, or Valorant from the selector.' },
                { n: '2', title: 'Analyze a match', desc: "Click Discover Latest or enter a team name. The 5-agent pipeline runs in 60–90 seconds." },
                { n: '3', title: 'Ask the AI anything', desc: 'Use the Chat tab to ask tactical, factual, or predictive questions about any game.' },
              ].map(step => (
                <div key={step.n} style={{ display: 'flex', gap: '16px', marginBottom: '20px' }}>
                  <div style={{
                    width: '28px', height: '28px', borderRadius: '50%', flexShrink: 0,
                    backgroundColor: sport.color, color: '#000',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: '12px', fontWeight: 700,
                  }}>
                    {step.n}
                  </div>
                  <div>
                    <div style={{ fontSize: '13px', fontWeight: 600, color: '#FFF', marginBottom: '3px' }}>
                      {step.title}
                    </div>
                    <div style={{ fontSize: '12px', color: '#666', lineHeight: 1.6 }}>
                      {step.desc}
                    </div>
                  </div>
                </div>
              ))}

              <motion.button
                whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}
                onClick={dismissOnboarding}
                style={{
                  width: '100%', marginTop: '8px', padding: '14px',
                  fontSize: '12px', fontWeight: 700, letterSpacing: '2px',
                  textTransform: 'uppercase', border: 'none', borderRadius: '8px',
                  backgroundColor: sport.color, color: '#000',
                  cursor: 'pointer', fontFamily: 'Inter, sans-serif',
                }}
              >
                Got it — Let me explore →
              </motion.button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <motion.div
        style={{ minHeight: '100vh', backgroundColor: '#0A0A0A' }}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.25 }}
      >
        {/* API DOWN BANNER */}
        <AnimatePresence>
          {apiDown && (
            <motion.div
              initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.25 }}
              style={{
                backgroundColor: '#150808', borderBottom: '1px solid #3A1010',
                padding: isMobile ? '8px 16px' : '8px 40px', textAlign: 'center',
              }}
            >
              <span style={{ fontSize: '12px', color: '#F87171', letterSpacing: '0.5px' }}>
                API server not responding — start FastAPI on port 8000
              </span>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── HERO ── */}
        <div style={{
          borderTop: `2px solid ${sport.color}`,
          background: `radial-gradient(ellipse at 50% 0%, ${sport.color}10 0%, transparent 65%), #0A0A0A`,
          transition: 'border-top-color 0.4s, background 0.4s',
          padding: isMobile ? '60px 24px 48px' : '100px 40px 80px',
          textAlign: 'center',
        }}>
          <motion.div
            key={selectedSport}
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
          >
            <div style={{
              fontSize: '10px', color: sport.color, letterSpacing: '4px',
              textTransform: 'uppercase', fontWeight: 700, marginBottom: '20px',
            }}>
              {sport.icon} {sport.label} Mode Active
            </div>
            <h1 style={{
              fontFamily: 'Bebas Neue, sans-serif',
              fontSize: isMobile ? '52px' : '88px',
              lineHeight: 0.95, letterSpacing: '3px', color: '#FFFFFF',
              margin: '0 0 8px 0',
            }}>
              SPORTS ANALYSIS.
            </h1>
            <h1 style={{
              fontFamily: 'Bebas Neue, sans-serif',
              fontSize: isMobile ? '52px' : '88px',
              lineHeight: 0.95, letterSpacing: '3px',
              color: sport.color, margin: '0 0 28px 0',
              transition: 'color 0.4s',
            }}>
              POWERED BY AI.
            </h1>
            <p style={{
              fontSize: isMobile ? '14px' : '16px', color: '#666',
              maxWidth: '520px', margin: '0 auto',
              lineHeight: 1.7, letterSpacing: '0.3px',
            }}>
              Five specialized AI agents analyze live match data and generate broadcast-quality narratives in 60–90 seconds.
            </p>
          </motion.div>
        </div>

        {/* 2px sport color divider */}
        <div style={{ height: '1px', backgroundColor: `${sport.color}30` }} />

        {/* ── SPORT SELECTOR ── */}
        <div style={{
          backgroundColor: '#0D0D0D',
          borderBottom: '1px solid #1A1A1A',
          padding: isMobile ? '20px 16px' : '24px 40px',
        }}>
          <div style={{
            display: 'flex', justifyContent: 'center',
            gap: isMobile ? '8px' : '12px',
            flexWrap: 'nowrap', overflowX: 'auto',
            WebkitOverflowScrolling: 'touch', scrollbarWidth: 'none',
            paddingBottom: '2px',
          }}>
            {Object.entries(SPORTS).map(([key, config]) => {
              const isActive = key === selectedSport
              const count = counts[key] || 0
              return (
                <motion.button
                  key={key}
                  onClick={() => {
                    setSelectedSport(key)
                    sessionStorage.setItem('lastSport', key)
                    setMatchInput('')
                  }}
                  whileHover={{ scale: 1.04 }}
                  whileTap={{ scale: 0.96 }}
                  style={{
                    padding: isMobile ? '8px 14px' : '10px 22px',
                    fontSize: '11px', fontWeight: 700,
                    letterSpacing: '2px', textTransform: 'uppercase',
                    borderRadius: '24px', flexShrink: 0, whiteSpace: 'nowrap',
                    border: `1px solid ${isActive ? config.color : '#2A2A2A'}`,
                    backgroundColor: isActive ? config.color : 'transparent',
                    color: isActive ? '#000' : '#555',
                    cursor: 'pointer', fontFamily: 'Inter, sans-serif',
                    transition: 'all 0.2s',
                    display: 'flex', alignItems: 'center', gap: '6px',
                  }}
                >
                  <span>{config.icon}</span>
                  <span>{config.label}</span>
                  {count > 0 && (
                    <span style={{
                      fontSize: '9px', fontWeight: 700,
                      backgroundColor: isActive ? 'rgba(0,0,0,0.25)' : '#1A1A1A',
                      color: isActive ? '#000' : config.color,
                      borderRadius: '10px', padding: '1px 6px',
                      lineHeight: '14px',
                    }}>
                      {count}
                    </span>
                  )}
                </motion.button>
              )
            })}
          </div>
        </div>

        {/* ── CONTENT GRID ── */}
        <div style={{
          maxWidth: '1400px', margin: '0 auto',
          padding: isMobile ? '24px 16px' : '48px 40px',
          display: 'grid',
          gridTemplateColumns: isMobile ? '1fr' : '1fr 360px',
          gap: isMobile ? '32px' : '48px',
          alignItems: 'start',
        }}>

          {/* ── RIGHT (on mobile: first) — New Analysis Panel ── */}
          {isMobile && <RightPanel
            selectedSport={selectedSport} sport={sport} matchInput={matchInput}
            setMatchInput={setMatchInput} persona={persona} setPersona={setPersona}
            forceRefresh={forceRefresh} setForceRefresh={setForceRefresh}
            loading={loading} discovering={discovering}
            handleAnalyze={handleAnalyze} handleDiscover={handleDiscover}
            isMobile={isMobile}
          />}

          {/* ── LEFT — Game Cards ── */}
          <div>
            {/* NBA Finals 2026 Banner — NBA only */}
            <AnimatePresence>
              {selectedSport === 'nba' && (
                <motion.div
                  key="nba-finals-banner"
                  initial={{ opacity: 0, y: -8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.3 }}
                  style={{
                    marginBottom: '20px',
                    padding: '16px 20px',
                    borderRadius: '12px',
                    border: '1px solid #FF6B35',
                    backgroundColor: 'rgba(255,107,53,0.06)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '14px',
                    flexWrap: 'wrap',
                  }}
                >
                  <div style={{ fontSize: '28px', lineHeight: 1 }}>🏆</div>
                  <div style={{ flex: 1, minWidth: '200px' }}>
                    <div style={{ fontSize: '13px', fontWeight: 700, color: '#FF6B35', letterSpacing: '0.5px', marginBottom: '3px' }}>
                      NBA Finals 2026 — New York Knicks vs San Antonio Spurs
                    </div>
                    <div style={{ fontSize: '11px', color: '#888', letterSpacing: '0.3px' }}>
                      Knicks lead 3-1 · Game 5 Sunday June 12
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* World Cup 2026 Banner — Soccer only */}
            <AnimatePresence>
              {selectedSport === 'soccer' && (
                <motion.div
                  key="wc-banner"
                  initial={{ opacity: 0, y: -8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.3 }}
                  style={{
                    marginBottom: '20px',
                    padding: '16px 20px',
                    borderRadius: '12px',
                    border: '1px solid #00D4AA',
                    backgroundColor: 'rgba(0,212,170,0.06)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '14px',
                    flexWrap: 'wrap',
                  }}
                >
                  <div style={{ fontSize: '28px', lineHeight: 1 }}>🏆</div>
                  <div style={{ flex: 1, minWidth: '180px' }}>
                    <div style={{ fontSize: '13px', fontWeight: 700, color: '#00D4AA', letterSpacing: '0.5px', marginBottom: '3px' }}>
                      FIFA World Cup 2026 is LIVE — Premier League data only on free tier
                    </div>
                    <div style={{ fontSize: '11px', color: '#888', letterSpacing: '0.3px' }}>
                      World Cup 2026 data requires paid API access · Use EPL teams below
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            <div style={{
              display: 'flex', alignItems: 'center',
              justifyContent: 'space-between', marginBottom: '20px',
            }}>
              <div style={{
                fontSize: '10px', fontWeight: 700,
                letterSpacing: '3px', textTransform: 'uppercase', color: '#666',
              }}>
                {sport.label} Analyses
              </div>
              <div style={{ fontSize: '10px', color: sport.color, letterSpacing: '2px', textTransform: 'uppercase' }}>
                {games.length} Cached
              </div>
            </div>

            <AnimatePresence mode="wait">
              {gamesLoading ? (
                <motion.div key="loading" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                  style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {[1, 2, 3].map(i => (
                    <div key={i} style={{
                      height: '100px', backgroundColor: '#111', borderRadius: '12px', opacity: 0.4 + i * 0.15,
                    }} />
                  ))}
                </motion.div>
              ) : games.length === 0 ? (
                <motion.div key="empty" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                  style={{
                    border: '1px dashed #1E1E1E', borderRadius: '16px',
                    padding: '48px 32px', textAlign: 'center',
                  }}>
                  <div style={{ fontSize: '48px', marginBottom: '16px' }}>{sport.icon}</div>
                  <h2 style={{
                    fontFamily: 'Bebas Neue, sans-serif', fontSize: '40px',
                    color: '#FFF', letterSpacing: '3px', margin: '0 0 12px 0',
                  }}>
                    {sport.label}
                  </h2>
                  <p style={{ color: '#555', fontSize: '14px', margin: '0 0 8px 0', lineHeight: 1.7 }}>
                    {{
                      nba: 'Use team names: Knicks, Celtics, Thunder, Lakers',
                      f1: 'Use race names: Monaco, Canada, Miami — or format 2026/6',
                      soccer: "EPL teams only: 'latest', Arsenal, Chelsea, Liverpool, Brighton",
                      valorant: "Use 'latest' for the most recent VCT match",
                      mlb: "Use 'latest' or a game ID like '824916'",
                    }[selectedSport]}
                  </p>
                  <p style={{ color: '#666', fontSize: '12px', margin: 0 }}>
                    No cached analyses yet. Run your first analysis →
                  </p>
                </motion.div>
              ) : (
                <motion.div key={selectedSport}
                  initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                  style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {games.map((game, i) => {
                    const { title, score } = parseCardTitle(game)
                    const isHovered = hoveredGame === game.game_id
                    return (
                      <motion.div
                        key={game.game_id}
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: i * 0.04 }}
                        whileHover={{ y: -2 }}
                        onClick={() => handleViewGame(game)}
                        onHoverStart={() => setHoveredGame(game.game_id)}
                        onHoverEnd={() => setHoveredGame(null)}
                        style={{
                          background: isHovered
                            ? `linear-gradient(135deg, rgba(255,255,255,0.05) 0%, transparent 100%)`
                            : `linear-gradient(135deg, rgba(255,255,255,0.02) 0%, transparent 100%)`,
                          border: `1px solid ${isHovered ? sport.color + '40' : '#1A1A1A'}`,
                          boxShadow: isHovered ? `0 4px 24px ${sport.color}15` : 'none',
                          borderRadius: '12px', padding: '20px 24px',
                          display: 'flex', alignItems: 'center',
                          justifyContent: 'space-between', cursor: 'pointer',
                          transition: 'border-color 0.2s, box-shadow 0.2s',
                        }}
                      >
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{
                            fontSize: '9px', fontWeight: 700,
                            letterSpacing: '3px', textTransform: 'uppercase',
                            color: sport.color, marginBottom: '6px',
                          }}>
                            {sport.icon} {sport.label}
                          </div>
                          <div style={{
                            fontSize: '15px', fontWeight: 600, color: '#FFFFFF',
                            whiteSpace: 'nowrap', overflow: 'hidden',
                            textOverflow: 'ellipsis', marginBottom: score ? '4px' : '8px',
                          }}>
                            {title}
                          </div>
                          {score && (
                            <div style={{
                              fontSize: '13px', color: sport.color,
                              fontFamily: 'monospace', fontWeight: 600,
                              marginBottom: '8px', letterSpacing: '1px',
                            }}>
                              {score}
                            </div>
                          )}
                          {game.narrative_excerpt && (
                            <div style={{
                              fontSize: '12px', color: '#555', lineHeight: 1.6,
                              fontStyle: 'italic', marginBottom: '8px',
                              overflow: 'hidden', display: '-webkit-box',
                              WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
                            }}>
                              {game.narrative_excerpt}
                            </div>
                          )}
                          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                            <span style={{ fontSize: '11px', color: '#666' }}>{formatMatchDate(game)}</span>
                            <span style={{ fontSize: '10px', color: '#22C55E', fontWeight: 600 }}>● Cached</span>
                          </div>
                        </div>

                        <motion.button
                          whileHover={{ scale: 1.05, x: 3 }}
                          whileTap={{ scale: 0.95 }}
                          onClick={e => { e.stopPropagation(); handleViewGame(game) }}
                          style={{
                            padding: '8px 18px', fontSize: '11px', fontWeight: 700,
                            letterSpacing: '1px', textTransform: 'uppercase',
                            border: `1px solid ${isHovered ? sport.color : '#2A2A2A'}`,
                            borderRadius: '6px',
                            backgroundColor: isHovered ? `${sport.color}15` : 'transparent',
                            color: isHovered ? sport.color : '#555',
                            cursor: 'pointer', fontFamily: 'Inter, sans-serif',
                            transition: 'all 0.2s', whiteSpace: 'nowrap',
                            marginLeft: '16px', flexShrink: 0,
                          }}
                        >
                          Read →
                        </motion.button>
                      </motion.div>
                    )
                  })}
                </motion.div>
              )}
            </AnimatePresence>

            {/* Recently Viewed */}
            {recentGames.length > 0 && (
              <div style={{ marginTop: '32px' }}>
                <div style={{
                  fontSize: '9px', color: '#666', letterSpacing: '2px',
                  textTransform: 'uppercase', marginBottom: '12px',
                }}>
                  Recently Viewed
                </div>
                {recentGames.map((g, i) => {
                  const s = SPORTS[g.sport] || SPORTS.nba
                  return (
                    <motion.div
                      key={i} whileHover={{ x: 2 }}
                      onClick={() => navigate(`/analysis/${g.sport}/${g.gameId.replace(/\//g, '_')}`)}
                      style={{
                        display: 'flex', alignItems: 'center', gap: '10px',
                        padding: '8px 0', cursor: 'pointer',
                        borderBottom: '1px solid #0F0F0F',
                      }}
                    >
                      <span style={{ fontSize: '13px' }}>{s.icon}</span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{
                          fontSize: '12px', color: '#888',
                          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                        }}>
                          {g.title}
                        </div>
                      </div>
                      <span style={{
                        fontSize: '9px', fontWeight: 700, letterSpacing: '1px',
                        textTransform: 'uppercase', color: s.color,
                        border: `1px solid ${s.color}40`, borderRadius: '3px', padding: '1px 5px',
                      }}>
                        {s.label}
                      </span>
                    </motion.div>
                  )
                })}
              </div>
            )}
          </div>

          {/* ── RIGHT (on desktop) — Analysis Panel ── */}
          {!isMobile && <RightPanel
            selectedSport={selectedSport} sport={sport} matchInput={matchInput}
            setMatchInput={setMatchInput} persona={persona} setPersona={setPersona}
            forceRefresh={forceRefresh} setForceRefresh={setForceRefresh}
            loading={loading} discovering={discovering}
            handleAnalyze={handleAnalyze} handleDiscover={handleDiscover}
            isMobile={isMobile}
          />}
        </div>

        {/* ── FOOTER ── */}
        <div style={{
          borderTop: '1px solid #0F0F0F',
          padding: isMobile ? '24px 16px' : '32px 40px',
        }}>
          <p style={{
            maxWidth: '760px', margin: '0 auto',
            fontSize: '11px', color: '#555', lineHeight: 1.8,
            textAlign: 'center', letterSpacing: '0.5px',
          }}>
            Built with LangGraph, Claude Opus 4, GPT-4o-mini, FastAPI, and React.
            5-agent pipeline: fetch, match analysis, player analysis, enrichment, and narrative.
          </p>
        </div>
      </motion.div>
    </>
  )
}

// ── RIGHT PANEL — extracted to avoid duplication on mobile/desktop ──
function RightPanel({
  selectedSport, sport, matchInput, setMatchInput, persona, setPersona,
  forceRefresh, setForceRefresh, loading, discovering,
  handleAnalyze, handleDiscover, isMobile,
}) {
  const isNba = selectedSport === 'nba'
  const discoverDisabled = discovering || loading

  return (
    <div style={{ position: isMobile ? 'static' : 'sticky', top: '40px' }}>
      <div style={{
        fontSize: '10px', fontWeight: 700,
        letterSpacing: '3px', textTransform: 'uppercase',
        color: '#666', marginBottom: '16px',
      }}>
        Analyze a Match
      </div>

      <div style={{
        backgroundColor: '#111', border: '1px solid #1A1A1A',
        borderRadius: '14px', padding: '24px',
      }}>
        {/* ⚡ Discover Latest — PRIMARY */}
        <motion.button
          whileHover={{ scale: discoverDisabled ? 1 : 1.02 }}
          whileTap={{ scale: discoverDisabled ? 1 : 0.98 }}
          onClick={handleDiscover}
          disabled={discoverDisabled}
          style={{
            width: '100%', padding: '16px',
            fontSize: '12px', fontWeight: 700,
            letterSpacing: '2px', textTransform: 'uppercase',
            borderRadius: '10px', border: 'none',
            backgroundColor: discoverDisabled ? '#222' : sport.color,
            color: discoverDisabled ? '#555' : '#000',
            cursor: discoverDisabled ? 'not-allowed' : 'pointer',
            fontFamily: 'Inter, sans-serif', transition: 'all 0.2s',
            marginBottom: '16px',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
          }}
        >
          {discovering ? (
            <>
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                style={{
                  width: '12px', height: '12px',
                  border: `2px solid currentColor`,
                  borderTopColor: 'transparent', borderRadius: '50%',
                }}
              />
              Finding latest...
            </>
          ) : (
            `⚡ Discover Latest ${sport.label}`
          )}
        </motion.button>

        {/* Separator */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px',
        }}>
          <div style={{ flex: 1, height: '1px', backgroundColor: '#1A1A1A' }} />
          <span style={{ fontSize: '10px', color: '#555', letterSpacing: '1px' }}>OR ENTER MANUALLY</span>
          <div style={{ flex: 1, height: '1px', backgroundColor: '#1A1A1A' }} />
        </div>

        {/* Input */}
        <div style={{ marginBottom: '12px' }}>
          <input
            type="text"
            value={matchInput}
            onChange={e => setMatchInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleAnalyze()}
            placeholder={SPORT_PLACEHOLDERS[selectedSport] || 'Match ID or latest...'}
            style={{
              width: '100%', backgroundColor: '#0A0A0A',
              border: '1px solid #2A2A2A', borderRadius: '8px',
              padding: '10px 14px', color: '#FFF', fontSize: '14px',
              outline: 'none', fontFamily: 'Inter, sans-serif',
              boxSizing: 'border-box', transition: 'border-color 0.2s',
            }}
            onFocus={e => e.target.style.borderColor = '#444'}
            onBlur={e => e.target.style.borderColor = '#2A2A2A'}
          />
          <div style={{ fontSize: '10px', color: '#888', marginTop: '5px', letterSpacing: '0.5px' }}>
            {SPORT_HINTS[selectedSport]}
          </div>
        </div>

        {/* Persona */}
        <div style={{ marginBottom: '14px' }}>
          <select
            value={persona}
            onChange={e => setPersona(e.target.value)}
            style={{
              width: '100%', backgroundColor: '#0A0A0A',
              border: '1px solid #2A2A2A', borderRadius: '8px',
              padding: '10px 14px', color: '#FFF', fontSize: '13px',
              outline: 'none', fontFamily: 'Inter, sans-serif', cursor: 'pointer',
            }}
          >
            <option value="espn_formal">ESPN Formal</option>
            <option value="tactical_coach">Tactical Coach</option>
          </select>
        </div>

        {/* Force refresh */}
        <div
          onClick={() => setForceRefresh(!forceRefresh)}
          style={{
            display: 'flex', alignItems: 'center', gap: '10px',
            marginBottom: '18px', cursor: 'pointer',
          }}
        >
          <div style={{
            width: '16px', height: '16px',
            border: `1px solid ${forceRefresh ? sport.color : '#333'}`,
            borderRadius: '3px',
            backgroundColor: forceRefresh ? sport.color : 'transparent',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexShrink: 0, transition: 'all 0.2s',
          }}>
            {forceRefresh && <span style={{ color: '#000', fontSize: '10px', fontWeight: 700 }}>✓</span>}
          </div>
          <span style={{ fontSize: '12px', color: '#555' }}>Force fresh analysis</span>
        </div>

        {/* Analyze button */}
        <motion.button
          onClick={handleAnalyze}
          disabled={loading || !matchInput.trim()}
          whileHover={{ scale: (loading || !matchInput.trim()) ? 1 : 1.02 }}
          whileTap={{ scale: (loading || !matchInput.trim()) ? 1 : 0.98 }}
          style={{
            width: '100%', padding: '14px',
            fontSize: '12px', fontWeight: 700,
            letterSpacing: '2px', textTransform: 'uppercase',
            borderRadius: '8px', border: 'none',
            backgroundColor: (loading || !matchInput.trim()) ? '#222' : sport.color,
            color: (loading || !matchInput.trim()) ? '#444' : '#000',
            cursor: (loading || !matchInput.trim()) ? 'not-allowed' : 'pointer',
            fontFamily: 'Inter, sans-serif', transition: 'all 0.2s',
          }}
        >
          {loading ? 'Starting...' : `Analyze ${sport.label} →`}
        </motion.button>

        <div style={{
          marginTop: '10px', fontSize: '10px', color: '#666',
          textAlign: 'center', letterSpacing: '0.5px',
        }}>
          Cmd+Enter to analyze
        </div>
      </div>

      {/* All sports quick select */}
      <div style={{
        marginTop: '16px', backgroundColor: '#0D0D0D',
        border: '1px solid #1A1A1A', borderRadius: '12px', padding: '18px',
      }}>
        <div style={{
          fontSize: '9px', color: '#666', letterSpacing: '2px',
          textTransform: 'uppercase', marginBottom: '12px',
        }}>
          All Sports
        </div>
        {Object.entries(SPORTS).map(([key, config]) => (
          <div
            key={key}
            onClick={() => {
              setMatchInput('')
              sessionStorage.setItem('lastSport', key)
            }}
            style={{
              display: 'flex', alignItems: 'center', gap: '10px',
              padding: '7px 0', cursor: 'pointer',
              borderBottom: '1px solid #0F0F0F',
            }}
          >
            <span style={{ fontSize: '14px' }}>{config.icon}</span>
            <span style={{
              fontSize: '12px', flex: 1,
              color: selectedSport === key ? config.color : '#AAAAAA',
              fontWeight: selectedSport === key ? 600 : 400, transition: 'color 0.2s',
            }}>
              {config.label}
            </span>
            <span style={{ fontSize: '10px', color: '#555' }}>{config.desc}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
