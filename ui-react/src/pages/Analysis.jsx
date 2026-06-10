import { useState, useEffect, useRef } from 'react'
import { useParams, useLocation, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Helmet } from 'react-helmet-async'
import { getGame, sendChat, generateTTS, getLatestTrace } from '../api'
import { SPORTS } from '../config'
import { useWindowSize } from '../hooks/useWindowSize'

export default function Analysis() {
  const { sport, gameId } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const sportConfig = SPORTS[sport] || SPORTS.nba
  const { isMobile } = useWindowSize()

  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('narrative')
  const [chatHistory, setChatHistory] = useState([])
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [cost, setCost] = useState(null)
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [voiceLoading, setVoiceLoading] = useState(false)
  const [usingElevenLabs, setUsingElevenLabs] = useState(false)
  const [copied, setCopied] = useState(false)
  const [shareCopied, setShareCopied] = useState(false)
  const [costPopoverOpen, setCostPopoverOpen] = useState(false)
  const [traceUrl, setTraceUrl] = useState(null)
  const audioRef = useRef(null)
  const chatEndRef = useRef(null)
  const costBadgeRef = useRef(null)

  // Load analysis data
  useEffect(() => {
    const jobData = location.state?.jobData
    if (jobData?.result) {
      setResult(jobData.result)
      setCost(jobData.cost ?? null)
      setLoading(false)
      saveRecentGame(sport, gameId, jobData.result)
      return
    }
    const safeId = gameId.replace(/_/g, '/')
    getGame(sport, safeId)
      .then(data => {
        setResult(data)
        setLoading(false)
        saveRecentGame(sport, gameId, data)
      })
      .catch(() => setLoading(false))
  }, [sport, gameId])

  // Close cost popover on outside click
  useEffect(() => {
    if (!costPopoverOpen) return
    const handler = (e) => {
      if (costBadgeRef.current && !costBadgeRef.current.contains(e.target)) {
        setCostPopoverOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [costPopoverOpen])

  // Stop audio on unmount / result change
  useEffect(() => {
    return () => window.speechSynthesis?.cancel()
  }, [result])

  // Fetch LangSmith trace URL
  useEffect(() => {
    getLatestTrace().then(data => { if (data.trace_url) setTraceUrl(data.trace_url) })
  }, [])

  // Auto-scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatHistory])

  const saveRecentGame = (sport, gameId, data) => {
    try {
      const firstLine = (data?.match_analysis || data?.narrative || '')
        .split('\n').find(l => l.startsWith('# '))
      const title = firstLine ? firstLine.slice(2).trim() : gameId
      const existing = JSON.parse(sessionStorage.getItem('recentGames') || '[]')
      const filtered = existing.filter(g => g.gameId !== gameId)
      const updated = [{ sport, gameId, title }, ...filtered].slice(0, 3)
      sessionStorage.setItem('recentGames', JSON.stringify(updated))
    } catch {}
  }

  const handleChat = async (query) => {
    if (!query.trim() || chatLoading) return
    const q = query.trim()
    setChatInput('')
    setChatLoading(true)
    setChatHistory(prev => [...prev, { role: 'user', content: q }])
    try {
      const safeId = gameId.replace(/_/g, '/')
      const response = await sendChat(
        sport, safeId, q,
        chatHistory.map(m => ({ role: m.role, content: m.content }))
      )
      setChatHistory(prev => [...prev, {
        role: 'assistant',
        content: response.response,
        intent: response.intent,
      }])
    } catch {
      setChatHistory(prev => [...prev, {
        role: 'assistant',
        content: 'Could not get a response. Please try again.',
        intent: 'error',
      }])
    } finally {
      setChatLoading(false)
    }
  }

  const stripMarkdown = (text) => {
    if (!text) return ''
    return text
      .replace(/^#{1,6}\s+/gm, '')
      .replace(/\*\*(.*?)\*\*/g, '$1')
      .replace(/\*(.*?)\*/g, '$1')
      .replace(/`(.*?)`/g, '$1')
      .replace(/---+/g, '')
      .trim()
  }

  const _speakWebSpeech = (text) => {
    if (!window.speechSynthesis) return
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.rate = 0.9
    const voices = window.speechSynthesis.getVoices()
    const preferred = voices.find(v => v.name.toLowerCase().includes('google uk english male'))
      || voices.find(v => v.lang === 'en-GB')
      || voices[0]
    if (preferred) utterance.voice = preferred
    utterance.onend = () => setIsSpeaking(false)
    utterance.onerror = () => setIsSpeaking(false)
    window.speechSynthesis.speak(utterance)
    setIsSpeaking(true)
  }

  const handleVoice = async () => {
    if (isSpeaking) {
      if (audioRef.current) { audioRef.current.pause(); audioRef.current = null }
      window.speechSynthesis?.cancel()
      setIsSpeaking(false)
      return
    }
    const text = stripMarkdown(result?.narrative || '')
    setVoiceLoading(true)
    try {
      const ttsResult = await generateTTS(text)
      if (ttsResult.fallback) {
        setUsingElevenLabs(false)
        setVoiceLoading(false)
        _speakWebSpeech(text)
        return
      }
      if (ttsResult.success && ttsResult.audio_base64) {
        setUsingElevenLabs(true)
        const blob = new Blob(
          [Uint8Array.from(atob(ttsResult.audio_base64), c => c.charCodeAt(0))],
          { type: 'audio/mpeg' }
        )
        const url = URL.createObjectURL(blob)
        const audio = new Audio(url)
        audioRef.current = audio
        audio.onended = () => { setIsSpeaking(false); URL.revokeObjectURL(url) }
        audio.onerror = () => { setIsSpeaking(false); URL.revokeObjectURL(url) }
        audio.play()
        setIsSpeaking(true)
      }
    } catch {
      setUsingElevenLabs(false)
      _speakWebSpeech(text)
    } finally {
      setVoiceLoading(false)
    }
  }

  const handleCopyNarrative = () => {
    const text = stripMarkdown(result?.narrative || '')
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  const handleShare = () => {
    navigator.clipboard.writeText(window.location.href).then(() => {
      setShareCopied(true)
      setTimeout(() => setShareCopied(false), 2000)
    })
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

  const extractScore = (matchAnalysis) => {
    const titleLine = (matchAnalysis || '').split('\n').find(l => l.startsWith('# '))
    if (!titleLine) return null
    const raw = titleLine.slice(2).trim()
    // NBA/MLB: "Name 115, Name 110" — two numbers near end
    const commaMatch = raw.match(/(\d{1,3}),\s*[A-Za-z\s&.'()-]+\s*(\d{1,3})\s*$/)
    if (commaMatch) return `${commaMatch[1]} - ${commaMatch[2]}`
    // Soccer/Valorant: "Name 3-1 Name"
    const dashMatch = raw.match(/\b(\d{1,2})-(\d{1,2})\b/)
    if (dashMatch) return `${dashMatch[1]} - ${dashMatch[2]}`
    return null
  }

  const getPullQuote = (blocks) => {
    const firstPara = blocks.find(b => b.type === 'paragraph')
    if (!firstPara) return null
    const match = firstPara.content.match(/^[^.!?]+[.!?]+/)
    return match ? match[0].trim() : null
  }

  const chatMsgCount = Math.floor(chatHistory.length / 2)
  const tabs = [
    { key: 'narrative', label: 'Narrative' },
    { key: 'match',     label: 'Match Analysis' },
    { key: 'player',    label: 'Player Analysis' },
    { key: 'chat',      label: 'Chat', badge: chatMsgCount > 0 ? chatMsgCount : null },
  ]

  if (loading) {
    return (
      <div style={{
        minHeight: '100vh', backgroundColor: '#0A0A0A',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <div style={{
          width: '32px', height: '32px',
          border: `2px solid ${sportConfig.color}`,
          borderTopColor: 'transparent', borderRadius: '50%',
          animation: 'spin 1s linear infinite',
        }} />
      </div>
    )
  }

  if (!result) {
    return (
      <div style={{
        minHeight: '100vh', backgroundColor: '#0A0A0A',
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', gap: '16px',
      }}>
        <p style={{ color: '#666' }}>Analysis not found.</p>
        <button onClick={() => navigate('/')}
          style={{
            padding: '10px 24px', border: '1px solid #333', borderRadius: '6px',
            background: 'none', color: '#888', cursor: 'pointer', fontFamily: 'Inter, sans-serif',
          }}>
          Back to Home
        </button>
      </div>
    )
  }

  const narrativeBlocks = formatNarrative(result.narrative)
  const matchId = result.match_id || gameId
  const pullQuote = getPullQuote(narrativeBlocks)
  const scoreDisplay = extractScore(result.match_analysis)

  const parseMatchTitle = () => {
    const firstLine = (result.match_analysis || result.narrative || '')
      .split('\n').find(l => l.startsWith('# '))
    if (firstLine) {
      let title = firstLine.slice(2).trim()
      title = title.replace(/\s*[\d]+[,\s]+[\d]+\s*$/, '').trim()
      title = title.replace(/\s*[\d]+-[\d]+\s*$/, '').trim()
      if (title.length > 3) return title.toUpperCase()
    }
    return matchId.replace(/_/g, ' / ').toUpperCase()
  }
  const pageTitle = parseMatchTitle()

  const pageSubtitle = (() => {
    const parts = [sportConfig.label]
    if (result?.match_date) {
      try {
        const d = new Date(result.match_date)
        parts.push(d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }))
      } catch {}
    }
    parts.push(result?.persona === 'tactical_coach' ? 'Tactical Coach' : 'ESPN Formal')
    parts.push('claude-opus-4-8')
    return parts.join(' · ')
  })()

  // Stats strip: score + sport + fresh/cached
  const statsItems = [
    {
      label: sport === 'f1' ? 'RACE' : 'FINAL',
      value: scoreDisplay || (sport === 'f1' ? sportConfig.label : '—'),
      color: scoreDisplay ? '#FFFFFF' : '#333',
    },
    { label: 'SPORT', value: sportConfig.label, color: sportConfig.color },
    {
      label: cost !== null && cost > 0 ? 'FRESH' : 'CACHED',
      value: cost !== null && cost > 0 ? `$${cost.toFixed(4)}` : '$0.00',
      color: cost !== null && cost > 0 ? '#F59E0B' : '#22C55E',
    },
  ]

  return (
    <>
      <Helmet>
        <title>{pageTitle} — SportsCast AI</title>
        <meta name="description" content={`AI broadcast analysis: ${pageTitle}. ${sportConfig.label} game analyzed by SportsCast AI multi-agent pipeline.`} />
        <meta property="og:title" content={`${pageTitle} — SportsCast AI`} />
        <meta property="og:description" content={`${sportConfig.label} broadcast analysis powered by multi-agent AI.`} />
        <meta property="og:type" content="website" />
        <style>{`
          @media print {
            body > * { display: none !important; }
            #print-narrative { display: block !important; }
            #print-narrative { color: #000; background: #fff; padding: 40px; font-family: Georgia, serif; }
          }
        `}</style>
      </Helmet>

      <motion.div
        style={{ minHeight: '100vh', backgroundColor: '#0A0A0A' }}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.25 }}
      >
        {/* Sport accent bar */}
        <div style={{ height: '2px', backgroundColor: sportConfig.color, width: '100%' }} />

        {/* ── HEADER ── */}
        <div style={{
          borderBottom: '1px solid #1A1A1A',
          backgroundColor: '#0D0D0D',
          padding: isMobile ? '14px 16px' : '24px 40px',
        }}>
          <div style={{
            maxWidth: '1400px', margin: '0 auto',
            display: 'flex',
            flexDirection: isMobile ? 'column' : 'row',
            alignItems: isMobile ? 'flex-start' : 'center',
            justifyContent: 'space-between',
            gap: isMobile ? '12px' : '0',
          }}>
            {/* Left: back + title */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', minWidth: 0 }}>
              <button
                onClick={() => navigate('/')}
                style={{
                  background: 'none', border: '1px solid #222', borderRadius: '6px',
                  color: '#555', fontSize: '11px', cursor: 'pointer',
                  padding: '6px 12px', fontFamily: 'Inter, sans-serif',
                  letterSpacing: '1px', transition: 'color 0.2s, border-color 0.2s', flexShrink: 0,
                  whiteSpace: 'nowrap',
                }}
                onMouseEnter={e => { e.currentTarget.style.color = '#FFF'; e.currentTarget.style.borderColor = '#444' }}
                onMouseLeave={e => { e.currentTarget.style.color = '#555'; e.currentTarget.style.borderColor = '#222' }}
              >
                ← {sportConfig.label} Analyses
              </button>
              <div style={{ minWidth: 0 }}>
                <div style={{
                  fontSize: '10px', color: sportConfig.color, letterSpacing: '3px',
                  textTransform: 'uppercase', fontWeight: 700, marginBottom: '4px',
                }}>
                  {sportConfig.icon} {sportConfig.label} Analysis
                </div>
                <h1 style={{
                  fontFamily: 'Bebas Neue, sans-serif',
                  fontSize: isMobile ? '20px' : '32px',
                  letterSpacing: '2px', color: '#FFFFFF', margin: 0, lineHeight: 1,
                  whiteSpace: isMobile ? 'normal' : 'nowrap',
                  overflow: 'hidden', textOverflow: 'ellipsis',
                }}>
                  {pageTitle}
                </h1>
                <div style={{ fontSize: '11px', color: '#444', marginTop: '5px', letterSpacing: '0.5px' }}>
                  {pageSubtitle}
                </div>
              </div>
            </div>

            {/* Right: action buttons */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', flexShrink: 0 }}>
              {/* Share — hide on mobile to save space */}
              {!isMobile && (
                <motion.button
                  whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
                  onClick={handleShare}
                  style={{
                    padding: '4px 12px', fontSize: '11px', fontWeight: 600,
                    letterSpacing: '1px', borderRadius: '20px',
                    border: '1px solid #2A2A2A', background: 'none',
                    color: shareCopied ? '#22C55E' : '#555',
                    cursor: 'pointer', fontFamily: 'Inter, sans-serif', transition: 'color 0.2s',
                  }}
                >
                  {shareCopied ? 'Copied' : 'Share'}
                </motion.button>
              )}

              {/* Copy narrative */}
              <motion.button
                whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
                onClick={handleCopyNarrative}
                title="Copy narrative text"
                style={{
                  width: '32px', height: '32px', borderRadius: '50%',
                  border: '1px solid #2A2A2A', background: 'none',
                  color: copied ? '#22C55E' : '#555',
                  cursor: 'pointer', fontSize: '15px',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  transition: 'color 0.2s',
                }}
              >
                {copied ? '✓' : '📋'}
              </motion.button>

              {/* Voice — text labels */}
              <motion.button
                whileHover={{ scale: voiceLoading ? 1 : 1.05 }}
                whileTap={{ scale: voiceLoading ? 1 : 0.95 }}
                onClick={handleVoice}
                disabled={voiceLoading}
                animate={isSpeaking ? {
                  boxShadow: ['0 0 0px transparent', `0 0 10px ${sportConfig.color}30`, '0 0 0px transparent']
                } : {}}
                transition={{ duration: 1.5, repeat: Infinity }}
                style={{
                  padding: '4px 12px', fontSize: '11px', fontWeight: 600,
                  letterSpacing: '1px', borderRadius: '20px',
                  border: `1px solid ${isSpeaking ? sportConfig.color : '#2A2A2A'}`,
                  background: isSpeaking ? `${sportConfig.color}15` : 'none',
                  color: isSpeaking ? sportConfig.color : voiceLoading ? '#444' : '#555',
                  cursor: voiceLoading ? 'wait' : 'pointer',
                  fontFamily: 'Inter, sans-serif', transition: 'all 0.2s',
                  whiteSpace: 'nowrap',
                  display: 'flex', alignItems: 'center', gap: '6px',
                }}
              >
                {voiceLoading ? (
                  <>
                    <motion.div
                      animate={{ rotate: 360 }}
                      transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                      style={{
                        width: '8px', height: '8px',
                        border: `1.5px solid currentColor`,
                        borderTopColor: 'transparent', borderRadius: '50%',
                      }}
                    />
                    Generating...
                  </>
                ) : isSpeaking ? 'Playing... (stop)' : 'AI Commentary'}
              </motion.button>

              {/* Cost badge — clickable popover */}
              <div ref={costBadgeRef} style={{ position: 'relative' }}>
                <span
                  onClick={() => setCostPopoverOpen(v => !v)}
                  style={{
                    padding: '4px 12px', borderRadius: '20px', fontSize: '10px', fontWeight: 700,
                    letterSpacing: '1px', textTransform: 'uppercase', cursor: 'pointer',
                    userSelect: 'none', transition: 'opacity 0.2s',
                    ...(cost === null || cost === 0
                      ? { backgroundColor: '#0A2A0A', color: '#22C55E', border: '1px solid #1A3A1A' }
                      : { backgroundColor: '#2A1A0A', color: '#F59E0B', border: '1px solid #4A3A1A' }),
                  }}
                >
                  {cost === null || cost === 0 ? 'Cached $0.00' : `Fresh $${cost.toFixed(4)}`}
                </span>

                {costPopoverOpen && (
                  <motion.div
                    initial={{ opacity: 0, y: -6 }}
                    animate={{ opacity: 1, y: 0 }}
                    style={{
                      position: 'absolute', right: 0, top: 'calc(100% + 8px)',
                      width: '220px', backgroundColor: '#111',
                      border: '1px solid #2A2A2A', borderRadius: '10px',
                      padding: '16px', zIndex: 100,
                      boxShadow: '0 8px 24px rgba(0,0,0,0.7)',
                    }}
                  >
                    <div style={{ fontSize: '10px', color: '#555', letterSpacing: '1.5px', textTransform: 'uppercase', marginBottom: '10px' }}>
                      Pipeline Cost
                    </div>
                    <div style={{ fontSize: '22px', fontWeight: 700, color: '#FFF', marginBottom: '14px' }}>
                      {cost !== null && cost > 0 ? `$${cost.toFixed(4)}` : '$0.00'}
                    </div>
                    <div style={{ fontSize: '11px', color: '#555', lineHeight: 2 }}>
                      <div>Match + Player <span style={{ color: '#444', float: 'right' }}>claude-sonnet-4-6</span></div>
                      <div>Narrative <span style={{ color: '#444', float: 'right' }}>claude-opus-4-8</span></div>
                      <div>Chat <span style={{ color: '#444', float: 'right' }}>gpt-4o-mini</span></div>
                    </div>
                    <div style={{ fontSize: '10px', color: '#333', marginTop: '12px', borderTop: '1px solid #1A1A1A', paddingTop: '10px' }}>
                      Chat responses billed separately per message.
                    </div>
                  </motion.div>
                )}
              </div>

              {/* Export PDF */}
              {!isMobile && (
                <motion.button
                  whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
                  onClick={() => window.print()}
                  style={{
                    padding: '4px 12px', fontSize: '11px', fontWeight: 600,
                    letterSpacing: '1px', borderRadius: '20px',
                    border: '1px solid #2A2A2A', background: 'none',
                    color: '#555', cursor: 'pointer',
                    fontFamily: 'Inter, sans-serif', transition: 'color 0.2s',
                  }}
                >
                  Export PDF
                </motion.button>
              )}

              {/* LangSmith trace link */}
              {traceUrl && !isMobile && (
                <a
                  href={traceUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    fontSize: '10px', color: '#555', textDecoration: 'none',
                    letterSpacing: '0.5px', whiteSpace: 'nowrap',
                    borderBottom: '1px solid #333', paddingBottom: '1px',
                  }}
                >
                  Pipeline trace →
                </a>
              )}
            </div>
          </div>
        </div>

        {/* ── STATS STRIP — score centered in 48px Bebas Neue ── */}
        {scoreDisplay && (
          <div style={{
            backgroundColor: '#0D0D0D',
            borderBottom: '1px solid #1A1A1A',
            padding: isMobile ? '16px' : '20px 40px',
            textAlign: 'center',
          }}>
            <div style={{
              fontSize: '9px', color: '#444', letterSpacing: '2px',
              textTransform: 'uppercase', marginBottom: '4px',
            }}>
              {sport === 'f1' ? 'RACE RESULT' : 'FINAL SCORE'}
            </div>
            <div style={{
              fontFamily: 'Bebas Neue, sans-serif',
              fontSize: isMobile ? '36px' : '48px',
              letterSpacing: '4px', color: '#FFFFFF', lineHeight: 1,
            }}>
              {scoreDisplay}
            </div>
          </div>
        )}

        {/* Secondary stats: sport + cost indicator */}
        <div style={{
          backgroundColor: '#0D0D0D',
          borderBottom: '1px solid #1A1A1A',
          padding: isMobile ? '10px 16px' : '12px 40px',
        }}>
          <div style={{
            maxWidth: '1400px', margin: '0 auto',
            display: 'flex', gap: isMobile ? '20px' : '40px', alignItems: 'center',
          }}>
            <div>
              <div style={{ fontSize: '8px', color: '#333', letterSpacing: '2px', textTransform: 'uppercase', marginBottom: '2px' }}>SPORT</div>
              <div style={{ fontSize: '13px', fontWeight: 600, color: sportConfig.color }}>{sportConfig.label}</div>
            </div>
            <div>
              <div style={{ fontSize: '8px', color: '#333', letterSpacing: '2px', textTransform: 'uppercase', marginBottom: '2px' }}>
                {cost !== null && cost > 0 ? 'FRESH' : 'CACHED'}
              </div>
              <div style={{ fontSize: '13px', fontWeight: 600, color: cost !== null && cost > 0 ? '#F59E0B' : '#22C55E' }}>
                {cost !== null && cost > 0 ? `$${cost.toFixed(4)}` : '$0.00'}
              </div>
            </div>
          </div>
        </div>

        {/* ── TABS ── */}
        <div style={{
          borderBottom: '1px solid #1A1A1A',
          backgroundColor: '#0D0D0D',
          padding: isMobile ? '0 0 0 0' : '0 40px',
          overflowX: 'auto',
          WebkitOverflowScrolling: 'touch',
          scrollbarWidth: 'none',
        }}>
          <div style={{
            maxWidth: '1400px', margin: '0 auto',
            display: 'flex', gap: '0',
            paddingLeft: isMobile ? '16px' : '0',
            paddingRight: isMobile ? '16px' : '0',
            minWidth: 'min-content',
          }}>
            {tabs.map(tab => {
              const isActive = activeTab === tab.key
              return (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  style={{
                    padding: isMobile ? '10px 14px' : '10px 20px',
                    fontSize: '12px', fontWeight: isActive ? 600 : 400,
                    letterSpacing: '1px', textTransform: 'uppercase',
                    border: 'none', borderBottom: `2px solid ${isActive ? sportConfig.color : 'transparent'}`,
                    backgroundColor: isActive ? `${sportConfig.color}26` : 'transparent',
                    color: isActive ? sportConfig.color : '#444',
                    cursor: 'pointer', transition: 'color 0.2s, background-color 0.2s, border-color 0.2s',
                    fontFamily: 'Inter, sans-serif', marginBottom: '-1px',
                    borderRadius: '6px 6px 0 0', whiteSpace: 'nowrap',
                    display: 'flex', alignItems: 'center', gap: '6px',
                  }}
                  onMouseEnter={e => { if (!isActive) e.currentTarget.style.color = '#888' }}
                  onMouseLeave={e => { if (!isActive) e.currentTarget.style.color = '#444' }}
                >
                  {tab.label}
                  {tab.badge && (
                    <span style={{
                      fontSize: '9px', fontWeight: 700,
                      backgroundColor: sportConfig.color,
                      color: '#000', borderRadius: '10px',
                      padding: '1px 6px', lineHeight: '14px',
                    }}>
                      {tab.badge}
                    </span>
                  )}
                </button>
              )
            })}
          </div>
        </div>

        {/* ── CONTENT ── */}
        <div style={{
          maxWidth: '1400px', margin: '0 auto',
          padding: isMobile ? '24px 16px' : '48px 40px',
        }}>
          <AnimatePresence mode="wait">

            {/* ── NARRATIVE TAB ── */}
            {activeTab === 'narrative' && (
              <motion.div
                key="narrative"
                id="print-narrative"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.2 }}
                style={{ maxWidth: '680px', margin: '0 auto' }}
              >
                {/* Pull quote — first sentence in sport color, 24px */}
                {pullQuote && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.1 }}
                    style={{
                      fontSize: isMobile ? '19px' : '24px',
                      lineHeight: 1.5,
                      color: sportConfig.color,
                      marginBottom: '32px',
                      fontStyle: 'italic',
                      fontWeight: 300,
                      paddingLeft: '20px',
                      borderLeft: `4px solid ${sportConfig.color}`,
                      letterSpacing: '0.2px',
                    }}
                  >
                    {pullQuote}
                  </motion.div>
                )}

                {(() => {
                  let firstParaSeen = false
                  return narrativeBlocks.map((block, i) => {
                    if (block.type === 'title') {
                      return (
                        <h2 key={i} style={{
                          fontFamily: 'Bebas Neue, sans-serif',
                          fontSize: isMobile ? '28px' : '36px',
                          letterSpacing: '2px', color: '#FFFFFF',
                          marginBottom: '32px', lineHeight: 1.1,
                        }}>
                          {block.content}
                        </h2>
                      )
                    }
                    if (block.type === 'heading') {
                      return (
                        <h3 key={i} style={{
                          fontSize: '13px', fontWeight: 700, letterSpacing: '2px',
                          textTransform: 'uppercase', color: sportConfig.color,
                          marginTop: '40px', marginBottom: '16px',
                        }}>
                          {block.content}
                        </h3>
                      )
                    }
                    const isFirst = !firstParaSeen
                    if (!firstParaSeen) firstParaSeen = true
                    return (
                      <p key={i} style={{
                        fontSize: isMobile ? '16px' : '17px',
                        lineHeight: 1.85, color: '#CCCCCC', marginBottom: '24px',
                        fontWeight: 300, letterSpacing: '0.2px',
                        ...(isFirst ? {
                          borderLeft: `3px solid ${sportConfig.color}4D`,
                          paddingLeft: '20px',
                        } : {}),
                      }}>
                        {block.content}
                      </p>
                    )
                  })
                })()}
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
                  <div style={{ fontSize: '15px', lineHeight: 1.8, color: '#BBBBBB', fontWeight: 300 }}>
                    {result.match_analysis.split('\n').map((line, i) => {
                      if (line.startsWith('# ')) return (
                        <h2 key={i} style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: '32px', letterSpacing: '2px', color: '#FFF', margin: '0 0 24px 0' }}>
                          {line.slice(2)}
                        </h2>
                      )
                      if (line.startsWith('## ')) return (
                        <h3 key={i} style={{ fontSize: '12px', fontWeight: 700, letterSpacing: '2px', textTransform: 'uppercase', color: sportConfig.color, margin: '32px 0 12px 0' }}>
                          {line.slice(3)}
                        </h3>
                      )
                      if (line.startsWith('### ')) return (
                        <h4 key={i} style={{ fontSize: '14px', fontWeight: 600, color: '#888', margin: '20px 0 8px 0' }}>
                          {line.slice(4)}
                        </h4>
                      )
                      if (line.startsWith('**') && line.endsWith('**')) return (
                        <p key={i} style={{ fontWeight: 600, color: '#FFFFFF', margin: '16px 0 4px 0', fontSize: '15px' }}>
                          {line.slice(2, -2)}
                        </p>
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
                  <div style={{ fontSize: '15px', lineHeight: 1.8, color: '#BBBBBB', fontWeight: 300 }}>
                    {result.player_analysis.split('\n').map((line, i) => {
                      if (line.startsWith('PLAYER:')) return (
                        <div key={i} style={{ fontSize: '16px', fontWeight: 700, color: '#FFFFFF', margin: '24px 0 4px 0' }}>
                          {line.slice(7).trim()}
                        </div>
                      )
                      if (line.startsWith('RATING:')) {
                        const rating = line.slice(7).trim()
                        const ratingColor = rating === 'Excellent' ? '#22C55E' : rating === 'Good' ? '#3B82F6' : rating === 'Average' ? '#F59E0B' : '#EF4444'
                        return (
                          <span key={i} style={{
                            display: 'inline-block', padding: '2px 10px', borderRadius: '4px',
                            fontSize: '11px', fontWeight: 700, letterSpacing: '1px',
                            textTransform: 'uppercase', color: ratingColor,
                            border: `1px solid ${ratingColor}40`, backgroundColor: `${ratingColor}10`,
                            margin: '4px 0 8px 0',
                          }}>
                            {rating}
                          </span>
                        )
                      }
                      if (line.startsWith('STATS:')) return (
                        <div key={i} style={{ fontSize: '12px', color: sportConfig.color, fontFamily: 'monospace', margin: '4px 0', letterSpacing: '0.5px' }}>
                          {line.slice(6).trim()}
                        </div>
                      )
                      if (line.startsWith('TEAM:')) return (
                        <div key={i} style={{ fontSize: '11px', color: '#444', letterSpacing: '1px', textTransform: 'uppercase', margin: '2px 0' }}>
                          {line.slice(5).trim()}
                        </div>
                      )
                      if (line.startsWith('INSIGHT:')) return (
                        <p key={i} style={{ fontSize: '14px', color: '#AAAAAA', lineHeight: 1.7, margin: '8px 0' }}>
                          {line.slice(8).trim()}
                        </p>
                      )
                      if (line.startsWith('IMPROVEMENT:')) return (
                        <p key={i} style={{ fontSize: '13px', color: '#555', lineHeight: 1.7, margin: '6px 0', fontStyle: 'italic' }}>
                          {line.slice(12).trim()}
                        </p>
                      )
                      if (line.trim() === '---') return <hr key={i} style={{ border: 'none', borderTop: '1px solid #1A1A1A', margin: '20px 0' }} />
                      if (line.startsWith('## ') || line.startsWith('# ')) return (
                        <h3 key={i} style={{ fontSize: '12px', fontWeight: 700, letterSpacing: '2px', textTransform: 'uppercase', color: sportConfig.color, margin: '32px 0 12px 0' }}>
                          {line.replace(/^#{1,3}\s/, '')}
                        </h3>
                      )
                      if (line.startsWith('**') && line.endsWith('**')) return (
                        <p key={i} style={{ fontWeight: 600, color: '#FFFFFF', margin: '16px 0 4px 0', fontSize: '15px' }}>
                          {line.slice(2, -2)}
                        </p>
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
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '32px' }}>
                  {sportConfig.suggestions.map((q, i) => (
                    <motion.button
                      key={i}
                      whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
                      onClick={() => handleChat(q)}
                      disabled={chatLoading}
                      style={{
                        padding: '8px 16px', fontSize: '12px',
                        border: '1px solid #2A2A2A', borderRadius: '20px',
                        backgroundColor: 'transparent', color: '#666',
                        cursor: chatLoading ? 'not-allowed' : 'pointer',
                        fontFamily: 'Inter, sans-serif', transition: 'all 0.2s',
                      }}
                      onMouseEnter={e => { e.currentTarget.style.borderColor = sportConfig.color; e.currentTarget.style.color = sportConfig.color }}
                      onMouseLeave={e => { e.currentTarget.style.borderColor = '#2A2A2A'; e.currentTarget.style.color = '#666' }}
                    >
                      {q}
                    </motion.button>
                  ))}
                </div>

                {/* Chat messages */}
                <div style={{ minHeight: '200px', marginBottom: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  {chatHistory.length === 0 && (
                    <div style={{ textAlign: 'center', padding: '48px 0', color: '#333', fontSize: '14px' }}>
                      Ask anything about this game
                    </div>
                  )}

                  {chatHistory.map((msg, i) => (
                    <motion.div
                      key={i}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      style={{ display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start' }}
                    >
                      {msg.role === 'user' ? (
                        <div style={{
                          maxWidth: '70%', backgroundColor: '#1A1A2E',
                          borderRadius: '16px 16px 4px 16px', padding: '12px 16px',
                          fontSize: '14px', color: '#FFFFFF', lineHeight: 1.6,
                        }}>
                          {msg.content}
                        </div>
                      ) : (
                        <div style={{
                          maxWidth: '85%', backgroundColor: '#111',
                          border: '1px solid #1A1A1A', borderRadius: '4px 16px 16px 16px',
                          padding: '16px', fontSize: '14px', color: '#CCCCCC', lineHeight: 1.7,
                        }}>
                          {msg.intent && (() => {
                            const intentStyles = {
                              analytical:    { bg: '#1E3A5F', color: '#3B82F6', border: '#2A4A6F' },
                              factual:       { bg: '#1A3A1A', color: '#22C55E', border: '#2A4A2A' },
                              predictive:    { bg: '#2D1B4E', color: '#8B5CF6', border: '#3D2B5E' },
                              emotional:     { bg: '#3A1A0A', color: '#F59E0B', border: '#4A2A1A' },
                              comparative:   { bg: '#1A2A3A', color: '#06B6D4', border: '#2A3A4A' },
                              out_of_scope:  { bg: '#1A1A1A', color: '#666',    border: '#2A2A2A' },
                              clarification: { bg: '#1A1A1A', color: '#888',    border: '#2A2A2A' },
                            }
                            const s = intentStyles[msg.intent] || intentStyles.out_of_scope
                            return (
                              <div style={{
                                display: 'inline-block', fontSize: '9px', fontWeight: 700,
                                letterSpacing: '2px', textTransform: 'uppercase',
                                color: s.color, backgroundColor: s.bg, border: `1px solid ${s.border}`,
                                borderRadius: '4px', padding: '2px 8px', marginBottom: '8px',
                              }}>
                                {msg.intent}
                              </div>
                            )
                          })()}
                          {msg.content}
                        </div>
                      )}
                    </motion.div>
                  ))}

                  {chatLoading && (
                    <motion.div
                      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                      style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 0' }}
                    >
                      <span style={{ fontSize: '12px', color: sportConfig.color, letterSpacing: '0.5px', fontStyle: 'italic' }}>
                        AI Analyst is thinking
                      </span>
                      <div style={{ display: 'flex', gap: '3px' }}>
                        {[0, 1, 2].map(j => (
                          <motion.div
                            key={j}
                            animate={{ opacity: [0.2, 1, 0.2] }}
                            transition={{ duration: 1.2, repeat: Infinity, delay: j * 0.3 }}
                            style={{ width: '5px', height: '5px', borderRadius: '50%', backgroundColor: sportConfig.color }}
                          />
                        ))}
                      </div>
                    </motion.div>
                  )}

                  <div ref={chatEndRef} />
                </div>

                {/* Chat input */}
                <div style={{
                  display: 'flex', gap: '12px', backgroundColor: '#0D0D0D',
                  border: '1px solid #1A1A1A', borderRadius: '12px', padding: '12px 16px',
                }}>
                  <input
                    type="text"
                    value={chatInput}
                    onChange={e => setChatInput(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleChat(chatInput)}
                    placeholder="Ask anything about this game..."
                    style={{
                      flex: 1, background: 'none', border: 'none', outline: 'none',
                      color: '#FFFFFF', fontSize: '14px', fontFamily: 'Inter, sans-serif',
                    }}
                  />
                  <motion.button
                    whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
                    onClick={() => handleChat(chatInput)}
                    disabled={chatLoading || !chatInput.trim()}
                    style={{
                      padding: '8px 20px', fontSize: '12px', fontWeight: 700,
                      letterSpacing: '1px', textTransform: 'uppercase', borderRadius: '8px',
                      border: 'none',
                      backgroundColor: chatLoading || !chatInput.trim() ? '#222' : sportConfig.color,
                      color: chatLoading || !chatInput.trim() ? '#444' : '#000',
                      cursor: chatLoading || !chatInput.trim() ? 'not-allowed' : 'pointer',
                      fontFamily: 'Inter, sans-serif', transition: 'all 0.2s', whiteSpace: 'nowrap',
                    }}
                  >
                    Send
                  </motion.button>
                </div>
              </motion.div>
            )}

          </AnimatePresence>
        </div>
      </motion.div>
    </>
  )
}
