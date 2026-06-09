import { useState, useEffect, useRef } from 'react'
import { useParams, useLocation, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { getGame, sendChat } from '../api'
import { SPORTS } from '../config'

export default function Analysis() {
  const { sport, gameId } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const sportConfig = SPORTS[sport] || SPORTS.nba

  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('narrative')
  const [chatHistory, setChatHistory] = useState([])
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [cost, setCost] = useState(0)
  const chatEndRef = useRef(null)

  // Load analysis data
  useEffect(() => {
    const jobData = location.state?.jobData
    if (jobData?.result) {
      setResult(jobData.result)
      setCost(jobData.cost || 0)
      setLoading(false)
      return
    }

    // Load from cache via API
    const safeId = gameId.replace(/_/g, '/')
    getGame(sport, safeId)
      .then(data => {
        setResult(data)
        setLoading(false)
      })
      .catch(() => {
        setLoading(false)
      })
  }, [sport, gameId])

  // Auto scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatHistory])

  const handleChat = async (query) => {
    if (!query.trim() || chatLoading) return
    const q = query.trim()
    setChatInput('')
    setChatLoading(true)

    setChatHistory(prev => [...prev, { role: 'user', content: q }])

    try {
      const safeId = gameId.replace(/_/g, '/')
      const response = await sendChat(
        sport,
        safeId,
        q,
        chatHistory.map(m => ({ role: m.role, content: m.content }))
      )
      setChatHistory(prev => [...prev, {
        role: 'assistant',
        content: response.response,
        intent: response.intent,
      }])
    } catch (err) {
      setChatHistory(prev => [...prev, {
        role: 'assistant',
        content: 'Could not get a response. Please try again.',
        intent: 'error',
      }])
    } finally {
      setChatLoading(false)
    }
  }

  const formatNarrative = (text) => {
    if (!text) return []
    const lines = text.split('\n')
    const blocks = []
    let currentParagraph = []

    lines.forEach(line => {
      if (line.startsWith('# ')) {
        if (currentParagraph.length > 0) {
          blocks.push({ type: 'paragraph', content: currentParagraph.join(' ') })
          currentParagraph = []
        }
        blocks.push({ type: 'title', content: line.slice(2) })
      } else if (line.startsWith('## ') || line.startsWith('### ')) {
        if (currentParagraph.length > 0) {
          blocks.push({ type: 'paragraph', content: currentParagraph.join(' ') })
          currentParagraph = []
        }
        blocks.push({ type: 'heading', content: line.replace(/^#{2,3}\s/, '') })
      } else if (line.trim() === '') {
        if (currentParagraph.length > 0) {
          blocks.push({ type: 'paragraph', content: currentParagraph.join(' ') })
          currentParagraph = []
        }
      } else {
        currentParagraph.push(line.trim())
      }
    })

    if (currentParagraph.length > 0) {
      blocks.push({ type: 'paragraph', content: currentParagraph.join(' ') })
    }

    return blocks
  }

  const tabs = [
    { key: 'narrative', label: 'Narrative' },
    { key: 'match', label: 'Match Analysis' },
    { key: 'player', label: 'Player Analysis' },
    { key: 'chat', label: `Chat ${chatHistory.length > 0 ? `(${Math.floor(chatHistory.length / 2)})` : ''}` },
  ]

  if (loading) {
    return (
      <div style={{
        minHeight: '100vh',
        backgroundColor: '#0A0A0A',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
        <div style={{
          width: '32px',
          height: '32px',
          border: `2px solid ${sportConfig.color}`,
          borderTopColor: 'transparent',
          borderRadius: '50%',
          animation: 'spin 1s linear infinite',
        }} />
      </div>
    )
  }

  if (!result) {
    return (
      <div style={{
        minHeight: '100vh',
        backgroundColor: '#0A0A0A',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '16px',
      }}>
        <p style={{ color: '#666' }}>Analysis not found.</p>
        <button
          onClick={() => navigate('/')}
          style={{
            padding: '10px 24px',
            border: '1px solid #333',
            borderRadius: '6px',
            background: 'none',
            color: '#888',
            cursor: 'pointer',
            fontFamily: 'Inter, sans-serif',
          }}
        >
          ← Back to Home
        </button>
      </div>
    )
  }

  const narrativeBlocks = formatNarrative(result.narrative)
  const matchId = result.match_id || gameId

  return (
    <motion.div
      style={{ minHeight: '100vh', backgroundColor: '#0A0A0A' }}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.25 }}
    >
      {/* Sport accent bar */}
      <div style={{
        height: '2px',
        backgroundColor: sportConfig.color,
        width: '100%',
      }} />

      {/* Header */}
      <div style={{
        borderBottom: '1px solid #1A1A1A',
        backgroundColor: '#0D0D0D',
        padding: '24px 40px',
      }}>
        <div style={{
          maxWidth: '1400px',
          margin: '0 auto',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
            <button
              onClick={() => navigate('/')}
              style={{
                background: 'none',
                border: '1px solid #222',
                borderRadius: '6px',
                color: '#555',
                fontSize: '12px',
                cursor: 'pointer',
                padding: '6px 14px',
                fontFamily: 'Inter, sans-serif',
                letterSpacing: '1px',
                transition: 'color 0.2s, border-color 0.2s',
              }}
              onMouseEnter={e => {
                e.currentTarget.style.color = '#FFF'
                e.currentTarget.style.borderColor = '#444'
              }}
              onMouseLeave={e => {
                e.currentTarget.style.color = '#555'
                e.currentTarget.style.borderColor = '#222'
              }}
            >
              ← Back
            </button>
            <div>
              <div style={{
                fontSize: '10px',
                color: sportConfig.color,
                letterSpacing: '3px',
                textTransform: 'uppercase',
                fontWeight: 700,
                marginBottom: '4px',
              }}>
                {sportConfig.icon} {sportConfig.label} Analysis
              </div>
              <h1 style={{
                fontFamily: 'Bebas Neue, sans-serif',
                fontSize: '32px',
                letterSpacing: '2px',
                color: '#FFFFFF',
                margin: 0,
                lineHeight: 1,
              }}>
                {matchId.replace(/_/g, ' / ').toUpperCase()}
              </h1>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {cost === 0 ? (
              <span style={{
                padding: '4px 12px',
                borderRadius: '20px',
                fontSize: '10px',
                fontWeight: 700,
                letterSpacing: '1px',
                textTransform: 'uppercase',
                backgroundColor: '#0A2A0A',
                color: '#22C55E',
                border: '1px solid #1A3A1A',
              }}>
                ⚡ Cached — $0.00
              </span>
            ) : (
              <span style={{
                padding: '4px 12px',
                borderRadius: '20px',
                fontSize: '10px',
                fontWeight: 700,
                letterSpacing: '1px',
                textTransform: 'uppercase',
                backgroundColor: '#2A1A0A',
                color: '#F59E0B',
                border: '1px solid #4A3A1A',
              }}>
                Fresh — ${cost.toFixed(4)}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{
        borderBottom: '1px solid #1A1A1A',
        backgroundColor: '#0D0D0D',
        padding: '0 40px',
      }}>
        <div style={{
          maxWidth: '1400px',
          margin: '0 auto',
          display: 'flex',
          gap: '0',
        }}>
          {tabs.map(tab => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              style={{
                padding: '14px 24px',
                fontSize: '12px',
                fontWeight: activeTab === tab.key ? 600 : 400,
                letterSpacing: '1px',
                textTransform: 'uppercase',
                background: 'none',
                border: 'none',
                borderBottom: `2px solid ${activeTab === tab.key ? sportConfig.color : 'transparent'}`,
                color: activeTab === tab.key ? '#FFFFFF' : '#444',
                cursor: 'pointer',
                transition: 'color 0.2s, border-color 0.2s',
                fontFamily: 'Inter, sans-serif',
                marginBottom: '-1px',
              }}
              onMouseEnter={e => {
                if (activeTab !== tab.key) e.currentTarget.style.color = '#888'
              }}
              onMouseLeave={e => {
                if (activeTab !== tab.key) e.currentTarget.style.color = '#444'
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div style={{
        maxWidth: '1400px',
        margin: '0 auto',
        padding: '48px 40px',
      }}>
        <AnimatePresence mode="wait">

          {/* ── NARRATIVE TAB ── */}
          {activeTab === 'narrative' && (
            <motion.div
              key="narrative"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.2 }}
              style={{ maxWidth: '760px', margin: '0 auto' }}
            >
              {narrativeBlocks.map((block, i) => {
                if (block.type === 'title') {
                  return (
                    <h2 key={i} style={{
                      fontFamily: 'Bebas Neue, sans-serif',
                      fontSize: '36px',
                      letterSpacing: '2px',
                      color: '#FFFFFF',
                      marginBottom: '32px',
                      lineHeight: 1.1,
                    }}>
                      {block.content}
                    </h2>
                  )
                }
                if (block.type === 'heading') {
                  return (
                    <h3 key={i} style={{
                      fontSize: '13px',
                      fontWeight: 700,
                      letterSpacing: '2px',
                      textTransform: 'uppercase',
                      color: sportConfig.color,
                      marginTop: '40px',
                      marginBottom: '16px',
                    }}>
                      {block.content}
                    </h3>
                  )
                }
                return (
                  <p key={i} style={{
                    fontSize: '17px',
                    lineHeight: 1.85,
                    color: '#CCCCCC',
                    marginBottom: '24px',
                    fontWeight: 300,
                    letterSpacing: '0.2px',
                  }}>
                    {block.content}
                  </p>
                )
              })}
            </motion.div>
          )}

          {/* ── MATCH ANALYSIS TAB ── */}
          {activeTab === 'match' && (
            <motion.div
              key="match"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.2 }}
              style={{ maxWidth: '760px', margin: '0 auto' }}
            >
              {result.match_analysis ? (
                <div style={{
                  fontSize: '15px',
                  lineHeight: 1.8,
                  color: '#BBBBBB',
                  fontWeight: 300,
                }}>
                  {result.match_analysis.split('\n').map((line, i) => {
                    if (line.startsWith('# ')) return (
                      <h2 key={i} style={{
                        fontFamily: 'Bebas Neue, sans-serif',
                        fontSize: '32px',
                        letterSpacing: '2px',
                        color: '#FFF',
                        margin: '0 0 24px 0',
                      }}>{line.slice(2)}</h2>
                    )
                    if (line.startsWith('## ')) return (
                      <h3 key={i} style={{
                        fontSize: '12px',
                        fontWeight: 700,
                        letterSpacing: '2px',
                        textTransform: 'uppercase',
                        color: sportConfig.color,
                        margin: '32px 0 12px 0',
                      }}>{line.slice(3)}</h3>
                    )
                    if (line.startsWith('### ')) return (
                      <h4 key={i} style={{
                        fontSize: '14px',
                        fontWeight: 600,
                        color: '#888',
                        margin: '20px 0 8px 0',
                      }}>{line.slice(4)}</h4>
                    )
                    if (line.startsWith('**') && line.endsWith('**')) return (
                      <p key={i} style={{
                        fontWeight: 600,
                        color: '#FFFFFF',
                        margin: '16px 0 4px 0',
                        fontSize: '15px',
                      }}>{line.slice(2, -2)}</p>
                    )
                    if (line.trim() === '---') return (
                      <hr key={i} style={{ border: 'none', borderTop: '1px solid #1A1A1A', margin: '24px 0' }} />
                    )
                    if (line.trim() === '') return <div key={i} style={{ height: '12px' }} />
                    return <p key={i} style={{ margin: '0 0 8px 0' }}>{line}</p>
                  })}
                </div>
              ) : (
                <p style={{ color: '#444' }}>No match analysis available.</p>
              )}
            </motion.div>
          )}

          {/* ── PLAYER ANALYSIS TAB ── */}
          {activeTab === 'player' && (
            <motion.div
              key="player"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.2 }}
              style={{ maxWidth: '760px', margin: '0 auto' }}
            >
              {result.player_analysis ? (
                <div style={{
                  fontSize: '15px',
                  lineHeight: 1.8,
                  color: '#BBBBBB',
                  fontWeight: 300,
                }}>
                  {result.player_analysis.split('\n').map((line, i) => {
                    if (line.startsWith('PLAYER:')) return (
                      <div key={i} style={{
                        fontSize: '16px',
                        fontWeight: 700,
                        color: '#FFFFFF',
                        margin: '24px 0 4px 0',
                      }}>{line.slice(7).trim()}</div>
                    )
                    if (line.startsWith('RATING:')) {
                      const rating = line.slice(7).trim()
                      const ratingColor = rating === 'Excellent' ? '#22C55E'
                        : rating === 'Good' ? '#3B82F6'
                        : rating === 'Average' ? '#F59E0B'
                        : '#EF4444'
                      return (
                        <span key={i} style={{
                          display: 'inline-block',
                          padding: '2px 10px',
                          borderRadius: '4px',
                          fontSize: '11px',
                          fontWeight: 700,
                          letterSpacing: '1px',
                          textTransform: 'uppercase',
                          color: ratingColor,
                          border: `1px solid ${ratingColor}40`,
                          backgroundColor: `${ratingColor}10`,
                          margin: '4px 0 8px 0',
                        }}>{rating}</span>
                      )
                    }
                    if (line.startsWith('STATS:')) return (
                      <div key={i} style={{
                        fontSize: '12px',
                        color: sportConfig.color,
                        fontFamily: 'monospace',
                        margin: '4px 0',
                        letterSpacing: '0.5px',
                      }}>{line.slice(6).trim()}</div>
                    )
                    if (line.startsWith('TEAM:')) return (
                      <div key={i} style={{
                        fontSize: '11px',
                        color: '#444',
                        letterSpacing: '1px',
                        textTransform: 'uppercase',
                        margin: '2px 0',
                      }}>{line.slice(5).trim()}</div>
                    )
                    if (line.startsWith('INSIGHT:')) return (
                      <p key={i} style={{
                        fontSize: '14px',
                        color: '#AAAAAA',
                        lineHeight: 1.7,
                        margin: '8px 0',
                      }}>{line.slice(8).trim()}</p>
                    )
                    if (line.startsWith('IMPROVEMENT:')) return (
                      <p key={i} style={{
                        fontSize: '13px',
                        color: '#555',
                        lineHeight: 1.7,
                        margin: '6px 0',
                        fontStyle: 'italic',
                      }}>↑ {line.slice(12).trim()}</p>
                    )
                    if (line.trim() === '---') return (
                      <hr key={i} style={{ border: 'none', borderTop: '1px solid #1A1A1A', margin: '20px 0' }} />
                    )
                    if (line.startsWith('## ') || line.startsWith('# ')) return (
                      <h3 key={i} style={{
                        fontSize: '12px',
                        fontWeight: 700,
                        letterSpacing: '2px',
                        textTransform: 'uppercase',
                        color: sportConfig.color,
                        margin: '32px 0 12px 0',
                      }}>{line.replace(/^#{1,3}\s/, '')}</h3>
                    )
                    if (line.startsWith('**') && line.endsWith('**')) return (
                      <p key={i} style={{
                        fontWeight: 600,
                        color: '#FFFFFF',
                        margin: '16px 0 4px 0',
                        fontSize: '15px',
                      }}>{line.slice(2, -2)}</p>
                    )
                    if (line.trim() === '') return <div key={i} style={{ height: '8px' }} />
                    return <p key={i} style={{ margin: '0 0 6px 0' }}>{line}</p>
                  })}
                </div>
              ) : (
                <p style={{ color: '#444' }}>No player analysis available.</p>
              )}
            </motion.div>
          )}

          {/* ── CHAT TAB ── */}
          {activeTab === 'chat' && (
            <motion.div
              key="chat"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.2 }}
              style={{ maxWidth: '760px', margin: '0 auto' }}
            >
              {/* Suggested questions */}
              <div style={{
                display: 'flex',
                gap: '8px',
                flexWrap: 'wrap',
                marginBottom: '32px',
              }}>
                {sportConfig.suggestions.map((q, i) => (
                  <motion.button
                    key={i}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => handleChat(q)}
                    disabled={chatLoading}
                    style={{
                      padding: '8px 16px',
                      fontSize: '12px',
                      border: '1px solid #2A2A2A',
                      borderRadius: '20px',
                      backgroundColor: 'transparent',
                      color: '#666',
                      cursor: chatLoading ? 'not-allowed' : 'pointer',
                      fontFamily: 'Inter, sans-serif',
                      transition: 'all 0.2s',
                    }}
                    onMouseEnter={e => {
                      e.currentTarget.style.borderColor = sportConfig.color
                      e.currentTarget.style.color = sportConfig.color
                    }}
                    onMouseLeave={e => {
                      e.currentTarget.style.borderColor = '#2A2A2A'
                      e.currentTarget.style.color = '#666'
                    }}
                  >
                    {q}
                  </motion.button>
                ))}
              </div>

              {/* Chat messages */}
              <div style={{
                minHeight: '200px',
                marginBottom: '24px',
                display: 'flex',
                flexDirection: 'column',
                gap: '16px',
              }}>
                {chatHistory.length === 0 && (
                  <div style={{
                    textAlign: 'center',
                    padding: '48px 0',
                    color: '#333',
                    fontSize: '14px',
                  }}>
                    Ask anything about this game
                  </div>
                )}

                {chatHistory.map((msg, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    style={{
                      display: 'flex',
                      justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                    }}
                  >
                    {msg.role === 'user' ? (
                      <div style={{
                        maxWidth: '70%',
                        backgroundColor: '#1A1A2E',
                        borderRadius: '16px 16px 4px 16px',
                        padding: '12px 16px',
                        fontSize: '14px',
                        color: '#FFFFFF',
                        lineHeight: 1.6,
                      }}>
                        {msg.content}
                      </div>
                    ) : (
                      <div style={{
                        maxWidth: '85%',
                        backgroundColor: '#111',
                        border: '1px solid #1A1A1A',
                        borderRadius: '4px 16px 16px 16px',
                        padding: '16px',
                        fontSize: '14px',
                        color: '#CCCCCC',
                        lineHeight: 1.7,
                      }}>
                        {msg.intent && (
                          <div style={{
                            fontSize: '10px',
                            fontWeight: 700,
                            letterSpacing: '2px',
                            textTransform: 'uppercase',
                            color: '#333',
                            marginBottom: '8px',
                          }}>
                            {msg.intent}
                          </div>
                        )}
                        {msg.content}
                      </div>
                    )}
                  </motion.div>
                ))}

                {chatLoading && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    style={{ display: 'flex', gap: '4px', padding: '8px 0' }}
                  >
                    {[0, 1, 2].map(i => (
                      <motion.div
                        key={i}
                        animate={{ y: [0, -6, 0] }}
                        transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.15 }}
                        style={{
                          width: '6px',
                          height: '6px',
                          borderRadius: '50%',
                          backgroundColor: sportConfig.color,
                        }}
                      />
                    ))}
                  </motion.div>
                )}

                <div ref={chatEndRef} />
              </div>

              {/* Chat input */}
              <div style={{
                display: 'flex',
                gap: '12px',
                backgroundColor: '#0D0D0D',
                border: '1px solid #1A1A1A',
                borderRadius: '12px',
                padding: '12px 16px',
              }}>
                <input
                  type="text"
                  value={chatInput}
                  onChange={e => setChatInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleChat(chatInput)}
                  placeholder="Ask anything about this game..."
                  style={{
                    flex: 1,
                    background: 'none',
                    border: 'none',
                    outline: 'none',
                    color: '#FFFFFF',
                    fontSize: '14px',
                    fontFamily: 'Inter, sans-serif',
                  }}
                />
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={() => handleChat(chatInput)}
                  disabled={chatLoading || !chatInput.trim()}
                  style={{
                    padding: '8px 20px',
                    fontSize: '12px',
                    fontWeight: 700,
                    letterSpacing: '1px',
                    textTransform: 'uppercase',
                    borderRadius: '8px',
                    border: 'none',
                    backgroundColor: chatLoading || !chatInput.trim()
                      ? '#222' : sportConfig.color,
                    color: chatLoading || !chatInput.trim() ? '#444' : '#000',
                    cursor: chatLoading || !chatInput.trim() ? 'not-allowed' : 'pointer',
                    fontFamily: 'Inter, sans-serif',
                    transition: 'all 0.2s',
                    whiteSpace: 'nowrap',
                  }}
                >
                  Send →
                </motion.button>
              </div>
            </motion.div>
          )}

        </AnimatePresence>
      </div>
    </motion.div>
  )
}
