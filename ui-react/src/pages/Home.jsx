import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { SPORTS } from '../config'
import { getCachedGames, startAnalysis, getHealth, discoverLatest } from '../api'

export default function Home() {
  const navigate = useNavigate()
  const [selectedSport, setSelectedSport] = useState(() => sessionStorage.getItem('lastSport') || 'nba')
  const [allGames, setAllGames] = useState({})
  const [games, setGames] = useState([])
  const [filteredGames, setFilteredGames] = useState([])
  const [searchQuery, setSearchQuery] = useState('')
  const [matchInput, setMatchInput] = useState('')
  const [persona, setPersona] = useState('espn_formal')
  const [forceRefresh, setForceRefresh] = useState(false)
  const [loading, setLoading] = useState(false)
  const [gamesLoading, setGamesLoading] = useState(false)
  const [hoveredGame, setHoveredGame] = useState(null)
  const [discovering, setDiscovering] = useState(false)
  const [apiDown, setApiDown] = useState(false)
  const failCountRef = useRef(0)
  const healthTimerRef = useRef(null)
  const [recentGames, setRecentGames] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem('recentGames') || '[]') } catch { return [] }
  })

  const sport = SPORTS[selectedSport]

  // Health check: poll every 15s, show banner after 2 consecutive failures, auto-dismiss on recovery
  useEffect(() => {
    const checkHealth = () => {
      getHealth()
        .then(() => {
          failCountRef.current = 0
          setApiDown(false)
        })
        .catch(() => {
          failCountRef.current += 1
          if (failCountRef.current >= 2) setApiDown(true)
        })
    }
    checkHealth()
    healthTimerRef.current = setInterval(checkHealth, 15000)
    return () => clearInterval(healthTimerRef.current)
  }, [])

  // Preload all sports on mount
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
      setFilteredGames(map[initial] || [])
    }).finally(() => setGamesLoading(false))
  }, [])

  // Update displayed games when sport changes (instant — reads from cache)
  useEffect(() => {
    if (Object.keys(allGames).length === 0) return
    setSearchQuery('')
    const g = allGames[selectedSport] || []
    setGames(g)
    setFilteredGames(g)
  }, [selectedSport, allGames])

  // Filter games by search query
  useEffect(() => {
    if (!searchQuery.trim()) {
      setFilteredGames(games)
      return
    }
    const q = searchQuery.toLowerCase()
    setFilteredGames(games.filter(g => {
      const title = (g.title || '').toLowerCase()
      const id = (g.match_id || g.game_id || '').toLowerCase()
      return title.includes(q) || id.includes(q)
    }))
  }, [searchQuery, games])

  const handleAnalyze = async () => {
    if (!matchInput.trim()) return
    setLoading(true)
    try {
      const data = await startAnalysis(selectedSport, matchInput, persona, forceRefresh)
      if (data.job_id) {
        navigate(`/loading/${data.job_id}`, {
          state: { sport: selectedSport, matchId: matchInput }
        })
      }
    } catch (err) {
      console.error(err)
      setLoading(false)
    }
  }

  const handleViewGame = (game) => {
    const safeId = game.game_id.replace(/\//g, '_')
    navigate(`/analysis/${game.sport}/${safeId}`)
  }

  const handleDiscover = async () => {
    if (discovering || loading) return
    setDiscovering(true)
    try {
      const found = await discoverLatest(selectedSport)
      // Auto-fill and immediately trigger analysis
      const data = await startAnalysis(selectedSport, found.match_id, persona, false)
      if (data.job_id) {
        navigate(`/loading/${data.job_id}`, {
          state: { sport: selectedSport, matchId: found.match_id }
        })
      }
    } catch (err) {
      console.error('Discovery failed:', err)
      // Fall back to "latest" for non-NBA sports
      if (selectedSport !== 'nba') {
        setMatchInput('latest')
      }
    } finally {
      setDiscovering(false)
    }
  }

  const parseCardTitle = (game) => {
    let raw = game.title || ''
    if (!raw) {
      const id = game.match_id || game.game_id
      if (game.sport === 'f1') {
        const parts = id.replace('_', '/').split('/')
        return { title: parts.length === 2 ? `Round ${parts[1]}: ${parts[0]}` : id, score: null }
      }
      return { title: id.replace(/_/g, ' '), score: null }
    }

    // Pattern: "OKC Thunder 115, Lakers 110" → "OKC Thunder vs Lakers" + "115–110"
    // Pattern: "Brighton 3-0 Leeds" → "Brighton vs Leeds" + "3–0"
    // Pattern: "Team A 2 vs Team B 1" etc.
    let score = null
    let title = raw

    // "Name Score, Name Score" format (NBA/MLB style)
    const commaScore = raw.match(/^(.+?)\s+(\d+),\s+(.+?)\s+(\d+)$/)
    if (commaScore) {
      const [, t1, s1, t2, s2] = commaScore
      // Shorten team names: last word only if > 3 words
      const shorten = t => {
        const parts = t.trim().split(' ')
        return parts.length > 2 ? parts.slice(-2).join(' ') : t.trim()
      }
      title = `${shorten(t1)} vs ${shorten(t2)}`
      score = `${s1}–${s2}`
      return { title, score }
    }

    // "Name N-N Name" or "Name N–N Name" format
    const dashScore = raw.match(/(\d+)[–-](\d+)/)
    if (dashScore) {
      score = `${dashScore[1]}–${dashScore[2]}`
      title = raw.replace(dashScore[0], '').replace(/\s{2,}/g, ' ').trim()
    }

    // Strip trailing colon or subtext
    title = title.replace(/[:\|].*$/, '').trim()
    return { title: title || raw, score }
  }

  const formatMatchDate = (game) => {
    const dateStr = game.match_date || game.cached_at
    if (!dateStr) return ''
    try {
      const d = new Date(dateStr)
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    } catch { return '' }
  }

  return (
    <motion.div
      style={{ minHeight: '100vh', backgroundColor: '#0A0A0A' }}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.25 }}
    >
      {/* ── API DOWN BANNER ── */}
      <AnimatePresence>
        {apiDown && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.25 }}
            style={{
              backgroundColor: '#150808',
              borderBottom: '1px solid #3A1010',
              padding: '8px 40px',
              textAlign: 'center',
            }}
          >
            <span style={{ fontSize: '12px', color: '#F87171', letterSpacing: '0.5px' }}>
              ⚠️ API server not responding — start FastAPI on port 8000 to use SportsCast AI
            </span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── HEADER ── */}
      <div style={{
        borderBottom: '1px solid #1A1A1A',
        backgroundColor: '#0D0D0D',
        padding: '0 40px',
        borderTop: `2px solid ${sport.color}`,
        background: `radial-gradient(ellipse at top left, ${sport.color}08 0%, transparent 60%), #0D0D0D`,
        transition: 'border-top-color 0.4s, background 0.4s',
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          paddingTop: '28px',
          paddingBottom: '20px',
          maxWidth: '1400px',
          margin: '0 auto',
        }}>
          <div>
            <h1 style={{
              fontFamily: 'Bebas Neue, sans-serif',
              fontSize: '60px',
              lineHeight: 1,
              letterSpacing: '3px',
              color: '#FFFFFF',
              margin: 0,
            }}>
              SPORTSCAST <span style={{ color: sport.color }}>AI</span>
            </h1>
            <p style={{
              fontSize: '10px',
              color: '#444',
              letterSpacing: '3px',
              textTransform: 'uppercase',
              marginTop: '6px',
            }}>
              Multi-Agent Sports Analysis · Claude Sonnet & GPT-4o-mini
            </p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '10px', color: '#333', letterSpacing: '2px', textTransform: 'uppercase' }}>Active Sport</div>
              <div style={{ fontSize: '14px', fontWeight: 600, color: sport.color, marginTop: '4px' }}>
                {sport.icon} {sport.label}
              </div>
            </div>
            <div style={{
              width: '8px', height: '8px', borderRadius: '50%',
              backgroundColor: '#22C55E', boxShadow: '0 0 8px #22C55E',
            }} />
          </div>
        </div>

        {/* Sport selector */}
        <div style={{
          display: 'flex', gap: '8px', paddingBottom: '16px',
          maxWidth: '1400px', margin: '0 auto',
        }}>
          {Object.entries(SPORTS).map(([key, config]) => {
            const isActive = key === selectedSport
            return (
              <motion.button
                key={key}
                onClick={() => { setSelectedSport(key); sessionStorage.setItem('lastSport', key); setMatchInput('') }}
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                style={{
                  padding: '8px 20px',
                  fontSize: '11px',
                  fontWeight: 700,
                  letterSpacing: '2px',
                  textTransform: 'uppercase',
                  borderRadius: '4px',
                  border: `1px solid ${isActive ? config.color : '#2A2A2A'}`,
                  backgroundColor: isActive ? config.color : 'transparent',
                  color: isActive ? '#000' : '#555',
                  cursor: 'pointer',
                  fontFamily: 'Inter, sans-serif',
                  transition: 'color 0.2s',
                }}
              >
                {config.icon} {config.label}
              </motion.button>
            )
          })}
        </div>
      </div>

      {/* ── MAIN CONTENT ── */}
      <div style={{
        maxWidth: '1400px', margin: '0 auto',
        padding: '40px', display: 'grid',
        gridTemplateColumns: '1fr 380px', gap: '40px', alignItems: 'start',
      }}>

        {/* ── LEFT: Games List ── */}
        <div>
          {/* Header + Search */}
          <div style={{ marginBottom: '20px' }}>
            <div style={{
              display: 'flex', alignItems: 'center',
              justifyContent: 'space-between', marginBottom: '16px',
            }}>
              <div style={{
                fontSize: '11px', fontWeight: 700,
                letterSpacing: '3px', textTransform: 'uppercase', color: '#444',
              }}>
                {sport.label} Analyses
              </div>
              <div style={{ fontSize: '11px', color: sport.color, letterSpacing: '2px', textTransform: 'uppercase' }}>
                {games.length} Cached
              </div>
            </div>

            {/* Search bar */}
            <div style={{ position: 'relative' }}>
              <span style={{
                position: 'absolute', left: '14px', top: '50%',
                transform: 'translateY(-50%)', color: '#444', fontSize: '14px',
              }}>🔍</span>
              <input
                type="text"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                placeholder={`Search ${sport.label} games...`}
                style={{
                  width: '100%',
                  backgroundColor: '#0D0D0D',
                  border: '1px solid #1A1A1A',
                  borderRadius: '8px',
                  padding: '10px 14px 10px 38px',
                  color: '#FFF',
                  fontSize: '13px',
                  outline: 'none',
                  fontFamily: 'Inter, sans-serif',
                  boxSizing: 'border-box',
                  transition: 'border-color 0.2s',
                }}
                onFocus={e => e.target.style.borderColor = '#333'}
                onBlur={e => e.target.style.borderColor = '#1A1A1A'}
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  style={{
                    position: 'absolute', right: '14px', top: '50%',
                    transform: 'translateY(-50%)', background: 'none',
                    border: 'none', color: '#444', cursor: 'pointer', fontSize: '16px',
                  }}
                >×</button>
              )}
            </div>
          </div>

          <AnimatePresence mode="wait">
            {gamesLoading ? (
              <motion.div key="loading" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {[1, 2, 3].map(i => (
                  <div key={i} style={{
                    height: '88px', backgroundColor: '#111', borderRadius: '10px',
                    opacity: 0.5 + i * 0.15,
                  }} />
                ))}
              </motion.div>
            ) : filteredGames.length === 0 ? (
              <motion.div key="empty" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                style={{
                  border: '1px dashed #1E1E1E', borderRadius: '12px',
                  padding: '64px', textAlign: 'center',
                }}>
                <div style={{ fontSize: '56px', marginBottom: '12px' }}>{sport.icon}</div>
                {searchQuery ? (
                  <>
                    <p style={{ color: '#444', fontSize: '14px' }}>No results for "{searchQuery}"</p>
                    <p style={{ color: '#333', fontSize: '12px', marginTop: '4px' }}>
                      Try a different search or run a new analysis →
                    </p>
                  </>
                ) : (
                  <>
                    <h2 style={{
                      fontFamily: 'Bebas Neue, sans-serif', fontSize: '48px',
                      color: '#FFF', letterSpacing: '3px', margin: '0 0 12px 0',
                    }}>{sport.label}</h2>
                    <p style={{ color: '#555', fontSize: '14px', margin: '0 0 24px 0' }}>
                      {{
                        nba: 'AI-powered box score breakdowns, player ratings, and game narratives',
                        f1: 'Race telemetry analysis, driver performance, and strategy breakdowns',
                        soccer: 'Match analysis, tactical insights, and player performance ratings',
                        valorant: 'VCT round analysis, agent picks, and clutch moment breakdowns',
                        mlb: 'Pitching matchups, hitting analysis, and game-deciding moments',
                      }[selectedSport]}
                    </p>
                    {selectedSport === 'nba' ? (
                      <p style={{ color: '#444', fontSize: '13px' }}>
                        Enter a team name in the panel to analyze their latest game
                      </p>
                    ) : (
                      <motion.button
                        whileHover={{ scale: 1.03 }}
                        whileTap={{ scale: 0.97 }}
                        onClick={handleDiscover}
                        disabled={discovering}
                        style={{
                          padding: '12px 32px', fontSize: '12px', fontWeight: 700,
                          letterSpacing: '2px', textTransform: 'uppercase',
                          border: `1px solid ${sport.color}`, borderRadius: '8px',
                          backgroundColor: 'transparent', color: sport.color,
                          cursor: discovering ? 'wait' : 'pointer', fontFamily: 'Inter, sans-serif',
                        }}
                      >
                        {discovering ? 'Finding...' : `⚡ Discover Latest ${sport.label} →`}
                      </motion.button>
                    )}
                  </>
                )}
              </motion.div>
            ) : (
              <motion.div key={selectedSport + searchQuery}
                initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {filteredGames.map((game, i) => (
                  <motion.div
                    key={game.game_id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.04 }}
                    onClick={() => handleViewGame(game)}
                    onMouseEnter={() => setHoveredGame(game.game_id)}
                    onMouseLeave={() => setHoveredGame(null)}
                    style={{
                      backgroundColor: hoveredGame === game.game_id
                        ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.02)',
                      backdropFilter: 'blur(10px)',
                      background: hoveredGame === game.game_id
                        ? `linear-gradient(135deg, rgba(255,255,255,0.06) 0%, transparent 100%)`
                        : `linear-gradient(135deg, rgba(255,255,255,0.03) 0%, transparent 100%)`,
                      border: `1px solid ${hoveredGame === game.game_id ? '#2E2E2E' : '#1A1A1A'}`,
                      boxShadow: hoveredGame === game.game_id ? `0 0 20px ${sport.color}20` : 'none',
                      borderRadius: '10px',
                      padding: '20px 24px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      cursor: 'pointer',
                      transition: 'all 0.3s ease',
                    }}
                  >
                    {(() => {
                      const { title, score } = parseCardTitle(game)
                      return (
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{
                        fontSize: '10px', fontWeight: 700,
                        letterSpacing: '3px', textTransform: 'uppercase',
                        color: sport.color, marginBottom: '6px',
                      }}>
                        {sport.icon} {sport.label}
                      </div>
                      <div style={{
                        fontSize: '16px', fontWeight: 600, color: '#FFFFFF',
                        marginBottom: score ? '2px' : '6px', whiteSpace: 'nowrap',
                        overflow: 'hidden', textOverflow: 'ellipsis',
                      }}>
                        {title}
                      </div>
                      {score && (
                        <div style={{
                          fontSize: '13px', color: sport.color, fontFamily: 'monospace',
                          fontWeight: 600, marginBottom: '6px', letterSpacing: '1px',
                        }}>
                          {score}
                        </div>
                      )}
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <span style={{ fontSize: '12px', color: '#333' }}>
                          {formatMatchDate(game)}
                        </span>
                        <span style={{ fontSize: '11px', color: '#1A6A1A', fontWeight: 600 }}>
                          ● Cached
                        </span>
                      </div>
                    </div>
                      )
                    })()}

                    <motion.button
                      whileHover={{ scale: 1.05, x: 3 }}
                      whileTap={{ scale: 0.95 }}
                      onClick={e => { e.stopPropagation(); handleViewGame(game) }}
                      style={{
                        padding: '8px 20px', fontSize: '11px', fontWeight: 700,
                        letterSpacing: '2px', textTransform: 'uppercase',
                        border: '1px solid #2A2A2A', borderRadius: '6px',
                        backgroundColor: 'transparent', color: '#555',
                        cursor: 'pointer', fontFamily: 'Inter, sans-serif',
                        transition: 'all 0.2s', whiteSpace: 'nowrap',
                        marginLeft: '16px', flexShrink: 0,
                      }}
                      onMouseEnter={e => {
                        e.currentTarget.style.borderColor = sport.color
                        e.currentTarget.style.color = sport.color
                      }}
                      onMouseLeave={e => {
                        e.currentTarget.style.borderColor = '#2A2A2A'
                        e.currentTarget.style.color = '#555'
                      }}
                    >
                      View →
                    </motion.button>
                  </motion.div>
                ))}
              </motion.div>
            )}
          </AnimatePresence>

          {/* World Cup 2026 Banner — Soccer only */}
          {selectedSport === 'soccer' && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              style={{
                marginTop: '20px',
                background: 'rgba(0,212,170,0.07)',
                border: '1px solid #00D4AA',
                borderRadius: '10px',
                padding: '16px 20px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '16px',
              }}
            >
              <div>
                <div style={{ fontSize: '13px', fontWeight: 600, color: '#00D4AA', marginBottom: '4px' }}>
                  🏆 FIFA World Cup 2026 is LIVE
                </div>
                <div style={{ fontSize: '11px', color: '#666', lineHeight: 1.5 }}>
                  48 teams · 3 host nations · USA, Canada, Mexico
                </div>
              </div>
              <motion.button
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                onClick={handleDiscover}
                disabled={discovering}
                style={{
                  padding: '8px 16px', fontSize: '11px', fontWeight: 700,
                  letterSpacing: '1px', textTransform: 'uppercase',
                  border: '1px solid #00D4AA', borderRadius: '6px',
                  background: 'transparent', color: '#00D4AA',
                  cursor: discovering ? 'wait' : 'pointer', whiteSpace: 'nowrap',
                  fontFamily: 'Inter, sans-serif',
                }}
              >
                {discovering ? '...' : 'Analyze →'}
              </motion.button>
            </motion.div>
          )}

          {/* Discover Latest */}
          <div style={{ marginTop: '20px' }}>
            <motion.button
              whileHover={{ scale: discovering || loading ? 1 : 1.02 }}
              whileTap={{ scale: discovering || loading ? 1 : 0.97 }}
              onClick={handleDiscover}
              disabled={discovering || loading}
              style={{
                width: '100%', padding: '11px 16px',
                fontSize: '12px', fontWeight: 600, letterSpacing: '1px',
                textTransform: 'uppercase',
                border: `1px solid ${discovering ? sport.color : '#2A2A2A'}`,
                borderRadius: '8px',
                backgroundColor: discovering ? `${sport.color}10` : 'transparent',
                color: discovering ? sport.color : '#555',
                cursor: discovering || loading ? 'not-allowed' : 'pointer',
                fontFamily: 'Inter, sans-serif',
                transition: 'all 0.2s',
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
                      border: `2px solid ${sport.color}`,
                      borderTopColor: 'transparent', borderRadius: '50%',
                    }}
                  />
                  Finding latest {sport.label}...
                </>
              ) : (
                `⚡ Discover Latest ${sport.label}`
              )}
            </motion.button>
          </div>

          {/* Recently Viewed */}
          {recentGames.length > 0 && (
            <div style={{ marginTop: '28px' }}>
              <div style={{
                fontSize: '10px', color: '#333', letterSpacing: '2px',
                textTransform: 'uppercase', marginBottom: '10px',
              }}>
                Recently Viewed
              </div>
              {recentGames.map((g, i) => {
                const s = SPORTS[g.sport] || SPORTS.nba
                return (
                  <motion.div
                    key={i}
                    whileHover={{ x: 2 }}
                    onClick={() => navigate(`/analysis/${g.sport}/${g.gameId.replace(/\//g, '_')}`)}
                    style={{
                      display: 'flex', alignItems: 'center', gap: '10px',
                      padding: '8px 0', cursor: 'pointer',
                      borderBottom: '1px solid #111',
                    }}
                  >
                    <span style={{ fontSize: '13px' }}>{s.icon}</span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{
                        fontSize: '12px', color: '#888',
                        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                      }}>{g.title}</div>
                    </div>
                    <span style={{
                      fontSize: '9px', fontWeight: 700, letterSpacing: '1px',
                      textTransform: 'uppercase', color: s.color,
                      border: `1px solid ${s.color}40`, borderRadius: '3px',
                      padding: '1px 5px',
                    }}>{s.label}</span>
                  </motion.div>
                )
              })}
            </div>
          )}
        </div>

        {/* ── RIGHT: New Analysis Panel ── */}
        <div style={{ position: 'sticky', top: '40px' }}>
          <div style={{
            fontSize: '11px', fontWeight: 700,
            letterSpacing: '3px', textTransform: 'uppercase',
            color: '#444', marginBottom: '20px',
          }}>
            ⚡ New Analysis
          </div>

          <div style={{
            backgroundColor: '#111', border: '1px solid #1A1A1A',
            borderRadius: '12px', padding: '24px',
          }}>
            <div style={{ marginBottom: '16px' }}>
              <label style={{
                fontSize: '10px', color: '#444', letterSpacing: '2px',
                textTransform: 'uppercase', display: 'block', marginBottom: '8px',
              }}>
                Team / Match ID / Latest
              </label>
              <input
                type="text"
                value={matchInput}
                onChange={e => setMatchInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleAnalyze()}
                placeholder={
                  selectedSport === 'nba' ? 'Lakers, Knicks, Thunder...' :
                  selectedSport === 'mlb' ? 'latest, 824916...' :
                  selectedSport === 'f1' ? 'latest...' :
                  selectedSport === 'soccer' ? 'premier_league, latest...' :
                  'latest...'
                }
                style={{
                  width: '100%', backgroundColor: '#0A0A0A',
                  border: '1px solid #2A2A2A', borderRadius: '6px',
                  padding: '10px 14px', color: '#FFF', fontSize: '14px',
                  outline: 'none', fontFamily: 'Inter, sans-serif',
                  boxSizing: 'border-box', transition: 'border-color 0.2s',
                }}
                onFocus={e => e.target.style.borderColor = '#444'}
                onBlur={e => e.target.style.borderColor = '#2A2A2A'}
              />
              {/* Sport-specific hint */}
              <div style={{ fontSize: '10px', color: '#333', marginTop: '6px', letterSpacing: '0.5px' }}>
                {selectedSport === 'nba' && 'Use team name e.g. Lakers, Knicks'}
                {selectedSport === 'mlb' && 'Use "latest" for most recent game'}
                {selectedSport === 'f1' && 'Use "latest" for most recent race'}
                {selectedSport === 'soccer' && 'Use "premier_league" or "latest"'}
                {selectedSport === 'valorant' && 'Use "latest" for most recent match'}
              </div>
            </div>

            <div style={{ marginBottom: '16px' }}>
              <label style={{
                fontSize: '10px', color: '#444', letterSpacing: '2px',
                textTransform: 'uppercase', display: 'block', marginBottom: '8px',
              }}>
                Persona
              </label>
              <select
                value={persona}
                onChange={e => setPersona(e.target.value)}
                style={{
                  width: '100%', backgroundColor: '#0A0A0A',
                  border: '1px solid #2A2A2A', borderRadius: '6px',
                  padding: '10px 14px', color: '#FFF', fontSize: '14px',
                  outline: 'none', fontFamily: 'Inter, sans-serif', cursor: 'pointer',
                }}
              >
                <option value="espn_formal">ESPN Formal</option>
                <option value="tactical_coach">Tactical Coach</option>
              </select>
            </div>

            <div
              style={{
                display: 'flex', alignItems: 'center', gap: '10px',
                marginBottom: '20px', cursor: 'pointer',
              }}
              onClick={() => setForceRefresh(!forceRefresh)}
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

            <motion.button
              data-analyze
              onClick={handleAnalyze}
              disabled={loading}
              whileHover={{ scale: loading ? 1 : 1.02 }}
              whileTap={{ scale: loading ? 1 : 0.98 }}
              style={{
                width: '100%', padding: '14px', fontSize: '12px',
                fontWeight: 700, letterSpacing: '2px', textTransform: 'uppercase',
                borderRadius: '8px', border: 'none',
                backgroundColor: loading ? '#333' : sport.color,
                color: '#000', cursor: loading ? 'not-allowed' : 'pointer',
                fontFamily: 'Inter, sans-serif', transition: 'background-color 0.2s',
              }}
            >
              {loading ? 'Starting...' : `Analyze ${sport.label} →`}
            </motion.button>
          </div>

          {/* Supported sports */}
          <div style={{
            marginTop: '16px', backgroundColor: '#0D0D0D',
            border: '1px solid #1A1A1A', borderRadius: '12px', padding: '20px',
          }}>
            <div style={{
              fontSize: '10px', color: '#333', letterSpacing: '2px',
              textTransform: 'uppercase', marginBottom: '12px',
            }}>
              All Sports
            </div>
            {Object.entries(SPORTS).map(([key, config]) => (
              <div
                key={key}
                onClick={() => { setSelectedSport(key); sessionStorage.setItem('lastSport', key); setMatchInput('') }}
                style={{
                  display: 'flex', alignItems: 'center', gap: '10px',
                  padding: '7px 0', cursor: 'pointer',
                  borderBottom: '1px solid #111',
                }}
              >
                <span style={{ fontSize: '14px' }}>{config.icon}</span>
                <span style={{
                  fontSize: '12px',
                  color: selectedSport === key ? config.color : '#444',
                  fontWeight: selectedSport === key ? 600 : 400,
                  transition: 'color 0.2s', flex: 1,
                }}>
                  {config.label}
                </span>
                <span style={{ fontSize: '11px', color: '#2A2A2A' }}>{config.desc}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── ABOUT FOOTER ── */}
      <div style={{
        borderTop: '1px solid #111',
        padding: '32px 40px',
        marginTop: '0',
      }}>
        <p style={{
          maxWidth: '760px', margin: '0 auto',
          fontSize: '12px', color: '#333', lineHeight: 1.8,
          textAlign: 'center', letterSpacing: '0.3px',
        }}>
          <span style={{ color: '#444', fontWeight: 600 }}>SportsCast AI</span> is a multi-agent sports analysis system.
          Unlike data lookup tools, it uses a 5-agent LangGraph pipeline (fetch, match analysis, player analysis,
          enrichment, and narrative) to generate original broadcast-quality analysis from live match data.
          Built with LangGraph, Claude Sonnet 4, GPT-4o-mini, FastAPI, and React.
        </p>
      </div>
    </motion.div>
  )
}
