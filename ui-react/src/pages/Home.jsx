import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { SPORTS } from '../config'
import { getCachedGames, startAnalysis } from '../api'

export default function Home() {
  const navigate = useNavigate()
  const [selectedSport, setSelectedSport] = useState('nba')
  const [games, setGames] = useState([])
  const [filteredGames, setFilteredGames] = useState([])
  const [searchQuery, setSearchQuery] = useState('')
  const [matchInput, setMatchInput] = useState('latest')
  const [persona, setPersona] = useState('espn_formal')
  const [forceRefresh, setForceRefresh] = useState(false)
  const [loading, setLoading] = useState(false)
  const [gamesLoading, setGamesLoading] = useState(false)
  const [hoveredGame, setHoveredGame] = useState(null)

  const sport = SPORTS[selectedSport]

  // Fetch cached games when sport changes
  useEffect(() => {
    setGamesLoading(true)
    setSearchQuery('')
    getCachedGames(selectedSport)
      .then(data => {
        const g = data.games || []
        setGames(g)
        setFilteredGames(g)
      })
      .catch(() => {
        setGames([])
        setFilteredGames([])
      })
      .finally(() => setGamesLoading(false))
  }, [selectedSport])

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

  const getGameTitle = (game) => {
    if (game.title) return game.title
    const id = game.match_id || game.game_id
    if (game.sport === 'f1') {
      const parts = id.replace('_', '/').split('/')
      return parts.length === 2 ? `Round ${parts[1]} — ${parts[0]}` : id
    }
    if (game.sport === 'nba' || game.sport === 'mlb') return `Game ${id.slice(-4)}`
    return id.replace(/_/g, ' ').toUpperCase()
  }

  return (
    <motion.div
      style={{ minHeight: '100vh', backgroundColor: '#0A0A0A' }}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.25 }}
    >
      {/* ── HEADER ── */}
      <div style={{
        borderBottom: '1px solid #1A1A1A',
        backgroundColor: '#0D0D0D',
        padding: '0 40px',
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
                onClick={() => setSelectedSport(key)}
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
                <div style={{ fontSize: '48px', marginBottom: '16px' }}>{sport.icon}</div>
                {searchQuery ? (
                  <>
                    <p style={{ color: '#444', fontSize: '14px' }}>No results for "{searchQuery}"</p>
                    <p style={{ color: '#333', fontSize: '12px', marginTop: '4px' }}>
                      Try a different search or run a new analysis →
                    </p>
                  </>
                ) : (
                  <>
                    <p style={{ color: '#444', fontSize: '14px' }}>No {sport.label} analyses yet</p>
                    <p style={{ color: '#333', fontSize: '12px', marginTop: '4px' }}>
                      Run your first analysis →
                    </p>
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
                      backgroundColor: hoveredGame === game.game_id ? '#141414' : '#111',
                      border: `1px solid ${hoveredGame === game.game_id ? '#2E2E2E' : '#1A1A1A'}`,
                      borderRadius: '10px',
                      padding: '20px 24px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      cursor: 'pointer',
                      transition: 'all 0.2s',
                    }}
                  >
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
                        marginBottom: '6px', whiteSpace: 'nowrap',
                        overflow: 'hidden', textOverflow: 'ellipsis',
                      }}>
                        {getGameTitle(game)}
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <span style={{ fontSize: '12px', color: '#333' }}>
                          {game.cached_at?.slice(0, 10)}
                        </span>
                        <span style={{ fontSize: '11px', color: '#1A6A1A', fontWeight: 600 }}>
                          ● Cached
                        </span>
                      </div>
                    </div>

                    <motion.button
                      whileHover={{ scale: 1.05 }}
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
                onClick={() => setSelectedSport(key)}
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
    </motion.div>
  )
}
