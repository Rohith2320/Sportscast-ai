import { useEffect, useState, useRef } from 'react'
import { useParams, useLocation, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Helmet } from 'react-helmet-async'
import { getJobStatus, API_BASE_URL } from '../api'
import { SPORTS } from '../config'
import { useWindowSize } from '../hooks/useWindowSize'

const AGENT_STEPS = [
  { key: 'fetch',     label: 'Fetching match data',           secsRemaining: 80, icon: '📡' },
  { key: 'match',     label: 'Analyzing match performance',   secsRemaining: 65, icon: '📊' },
  { key: 'player',    label: 'Analyzing player performances', secsRemaining: 50, icon: '👤' },
  { key: 'enrich',    label: 'Enriching with context',        secsRemaining: 30, icon: '✨' },
  { key: 'narrative', label: 'Generating narrative',          secsRemaining: 12, icon: '📝' },
]

const SPORT_FETCH_MSG = {
  nba:      'Fetching NBA box score and play-by-play data',
  mlb:      'Fetching MLB box score and pitching data',
  f1:       'Fetching F1 race results and telemetry',
  soccer:   'Fetching match statistics and lineups',
  valorant: 'Fetching VCT match data and round history',
}

// Parse pipeline error into a human-readable actionable message
function getHumanError(error, sport) {
  if (!error) return null
  const e = error.toLowerCase()

  if (sport === 'nba') {
    if (e.includes('season has ended') || e.includes('no recent') || e.includes('season')) {
      return {
        title: 'NBA Season Has Ended',
        message: 'The NBA 2025-26 season is over. Browse the cached playoff analyses on the home page, or try a team name that has a cached game.',
        examples: ['Knicks', 'Celtics', 'Thunder'],
      }
    }
    if (e.includes("team '") || e.includes('not found') || e.includes('try full name')) {
      return {
        title: 'Team Not Found',
        message: 'That team name was not recognized. Try one of these:',
        examples: ['Knicks', 'Celtics', 'Thunder', 'Lakers', 'Warriors'],
      }
    }
  }

  if (sport === 'f1') {
    if (e.includes('no race') || e.includes('404') || e.includes('not found') || e.includes('invalid')) {
      return {
        title: 'Race Not Found',
        message: "Try a race name like 'Monaco', 'Canada', or 'Miami' — or use the season/round format.",
        examples: ['Monaco', 'Canada', 'Miami'],
      }
    }
  }

  if (sport === 'soccer') {
    return {
      title: 'Soccer Analysis',
      message: "Only Premier League matches are currently supported. Try 'latest' for the most recent EPL match.",
      examples: ['latest', 'premier_league'],
    }
  }

  if (sport === 'mlb') {
    return {
      title: 'MLB Analysis',
      message: "Try 'latest' for the most recent game, or enter a specific game ID.",
      examples: ['latest', '824916'],
    }
  }

  return null
}

export default function Loading() {
  const { jobId } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const { isMobile } = useWindowSize()

  const sport = location.state?.sport || 'nba'
  const sportConfig = SPORTS[sport] || SPORTS.nba

  const [job, setJob] = useState({ status: 'queued', progress: [], cost: null, result: null, error: null })
  const [dots, setDots] = useState('')
  const sseRef = useRef(null)
  const dotsRef = useRef(null)

  // Animated dots
  useEffect(() => {
    dotsRef.current = setInterval(() => {
      setDots(d => d.length >= 3 ? '' : d + '.')
    }, 400)
    return () => clearInterval(dotsRef.current)
  }, [])

  // SSE connection — replaces polling
  useEffect(() => {
    if (!jobId) return

    const sse = new EventSource(`${API_BASE_URL}/analyze/${jobId}/stream`)
    sseRef.current = sse

    sse.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)

        if (data.type === 'progress') {
          setJob(prev => ({
            ...prev,
            status: 'running',
            progress: [...prev.progress, data.message],
          }))
        } else if (data.type === 'complete') {
          sse.close()
          getJobStatus(jobId)
            .then(fullJob => {
              setJob(fullJob)
              setTimeout(() => {
                const gameId = fullJob.result?.match_id || ''
                navigate(`/analysis/${sport}/${gameId}`, { state: { jobData: fullJob } })
              }, 800)
            })
            .catch(() => navigate('/'))
        } else if (data.type === 'failed') {
          sse.close()
          setJob(prev => ({ ...prev, status: 'failed', error: data.error }))
        }
      } catch {}
    }

    sse.onerror = () => { sse.close() }

    return () => { sse.close() }
  }, [jobId])

  const getCompletedSteps = () => {
    const progress = job.progress || []
    const completed = []
    if (progress.some(p => p.toLowerCase().includes('fetch') || p.toLowerCase().includes('data'))) completed.push('fetch')
    if (progress.some(p => p.toLowerCase().includes('match') || p.toLowerCase().includes('analyz'))) completed.push('match')
    if (progress.some(p => p.toLowerCase().includes('player'))) completed.push('player')
    if (progress.some(p => p.toLowerCase().includes('enrich'))) completed.push('enrich')
    if (progress.some(p => p.toLowerCase().includes('narrative') || p.toLowerCase().includes('complete'))) completed.push('narrative')
    return completed
  }

  const completedSteps = getCompletedSteps()
  const currentStepIndex = completedSteps.length
  const isComplete = job.status === 'complete'
  const isFailed = job.status === 'failed'
  const humanError = isFailed ? getHumanError(job.error, sport) : null

  return (
    <>
      <Helmet>
        <title>{isComplete ? 'Analysis Ready' : 'Analyzing...'} — SportsCast AI</title>
      </Helmet>
      <motion.div
        style={{
          minHeight: '100vh',
          backgroundColor: '#0A0A0A',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: isMobile ? '20px 16px' : '40px',
        }}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.25 }}
      >
        {/* Sport accent line */}
        <motion.div
          style={{
            position: 'fixed', top: 0, left: 0, right: 0,
            height: '2px', backgroundColor: sportConfig.color,
          }}
          initial={{ scaleX: 0 }}
          animate={{ scaleX: isComplete ? 1 : 0.7 }}
          transition={{ duration: 1.5, ease: 'easeOut' }}
        />

        <div style={{ maxWidth: '600px', width: '100%' }}>

          {/* Header */}
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            style={{ marginBottom: '40px', textAlign: 'center' }}
          >
            <div style={{
              fontSize: '11px', color: sportConfig.color,
              letterSpacing: '3px', textTransform: 'uppercase',
              marginBottom: '12px', fontWeight: 700,
            }}>
              {sportConfig.icon} {sportConfig.label} Analysis
            </div>
            <h1 style={{
              fontFamily: 'Bebas Neue, sans-serif',
              fontSize: isMobile ? '38px' : '52px',
              letterSpacing: '3px', color: '#FFFFFF', margin: 0, lineHeight: 1,
            }}>
              {isComplete ? 'ANALYSIS READY' : isFailed ? 'ANALYSIS FAILED' : `ANALYZING${dots}`}
            </h1>
            {!isFailed && (
              <p style={{
                fontSize: isMobile ? '12px' : '13px',
                color: '#444', marginTop: '12px', letterSpacing: '1px',
              }}>
                {isComplete
                  ? 'Redirecting to your analysis...'
                  : 'Multi-agent pipeline running'}
              </p>
            )}
          </motion.div>

          {/* ── PIPELINE VISUALIZATION ── */}
          {!isFailed && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.2 }}
              style={{
                marginBottom: '32px',
                padding: isMobile ? '20px 12px' : '24px 32px',
                backgroundColor: '#0D0D0D',
                border: '1px solid #1A1A1A',
                borderRadius: '16px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', width: '100%' }}>
                {AGENT_STEPS.map((step, i) => {
                  const isDone = completedSteps.includes(step.key)
                  const isActive = !isDone && i === currentStepIndex
                  const nodeColor = isDone ? sportConfig.color : isActive ? sportConfig.color : '#1A1A1A'

                  return (
                    <div key={step.key} style={{ display: 'flex', alignItems: 'flex-start', flex: 1 }}>
                      {/* Node */}
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0 }}>
                        <motion.div
                          animate={isActive ? {
                            boxShadow: [
                              `0 0 0 0 ${sportConfig.color}40`,
                              `0 0 0 8px ${sportConfig.color}00`,
                            ],
                          } : {}}
                          transition={{ duration: 1.2, repeat: Infinity }}
                          style={{
                            width: '40px', height: '40px', borderRadius: '50%',
                            backgroundColor: isDone ? sportConfig.color : '#111',
                            border: `2px solid ${nodeColor}`,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            fontSize: '16px', transition: 'all 0.4s',
                            position: 'relative',
                          }}
                        >
                          {isDone ? (
                            <motion.span
                              initial={{ scale: 0 }}
                              animate={{ scale: 1 }}
                              style={{ fontSize: '14px', color: '#000', fontWeight: 700 }}
                            >
                              ✓
                            </motion.span>
                          ) : isActive ? (
                            <motion.div
                              animate={{ rotate: 360 }}
                              transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                              style={{
                                width: '14px', height: '14px',
                                border: `2px solid ${sportConfig.color}`,
                                borderTopColor: 'transparent', borderRadius: '50%',
                              }}
                            />
                          ) : (
                            <span style={{ fontSize: '13px', opacity: 0.3 }}>{step.icon}</span>
                          )}
                        </motion.div>

                        {/* Label */}
                        <div style={{
                          fontSize: isMobile ? '8px' : '9px',
                          letterSpacing: '0.5px',
                          textTransform: 'uppercase',
                          color: isDone ? sportConfig.color : isActive ? '#FFF' : '#333',
                          marginTop: '8px',
                          textAlign: 'center',
                          fontWeight: isDone || isActive ? 600 : 400,
                          transition: 'color 0.3s',
                          maxWidth: '50px',
                        }}>
                          {isMobile ? step.key : step.icon}
                        </div>
                      </div>

                      {/* Connector line */}
                      {i < AGENT_STEPS.length - 1 && (
                        <div style={{ flex: 1, marginTop: '19px', padding: '0 4px' }}>
                          <motion.div
                            style={{ height: '2px', borderRadius: '1px' }}
                            animate={{
                              backgroundColor: isDone ? sportConfig.color : '#1A1A1A',
                            }}
                            transition={{ duration: 0.5, delay: 0.1 }}
                          />
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>

              {/* Active step description */}
              {!isComplete && currentStepIndex < AGENT_STEPS.length && (
                <motion.div
                  key={currentStepIndex}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  style={{
                    marginTop: '16px',
                    paddingTop: '16px',
                    borderTop: '1px solid #111',
                    fontSize: '12px',
                    color: '#555',
                    textAlign: 'center',
                    letterSpacing: '0.5px',
                  }}
                >
                  {currentStepIndex === 0
                    ? (SPORT_FETCH_MSG[sport] || SPORT_FETCH_MSG.nba)
                    : AGENT_STEPS[currentStepIndex]?.label}
                  {currentStepIndex > 0 && (
                    <span style={{ color: '#333', marginLeft: '8px' }}>
                      · Agent <span style={{ color: sportConfig.color }}>{currentStepIndex}/{AGENT_STEPS.length}</span> complete
                    </span>
                  )}
                </motion.div>
              )}
            </motion.div>
          )}

          {/* Progress bar */}
          {!isFailed && (
            <div style={{
              width: '100%', height: '2px', backgroundColor: '#1A1A1A',
              borderRadius: '2px', marginBottom: '32px', overflow: 'hidden',
            }}>
              <motion.div
                style={{
                  height: '100%', borderRadius: '2px',
                  backgroundColor: isComplete ? '#22C55E' : sportConfig.color,
                }}
                animate={{
                  width: isComplete ? '100%' : `${Math.max(5, (completedSteps.length / AGENT_STEPS.length) * 100)}%`,
                  boxShadow: isComplete ? '0 0 8px #22C55E' : `0 0 6px ${sportConfig.color}`,
                }}
                transition={{ duration: 0.6, ease: 'easeOut' }}
              />
            </div>
          )}

          {/* ── FAILED STATE — Human readable error ── */}
          {isFailed && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              style={{
                backgroundColor: '#0D0D0D',
                border: '1px solid #2A1A1A',
                borderRadius: '16px',
                padding: isMobile ? '20px' : '32px',
                marginBottom: '24px',
              }}
            >
              {humanError ? (
                <>
                  <div style={{ fontSize: '16px', fontWeight: 600, color: '#FFF', marginBottom: '10px' }}>
                    {humanError.title}
                  </div>
                  <p style={{ fontSize: '14px', color: '#888', lineHeight: 1.7, marginBottom: '20px' }}>
                    {humanError.message}
                  </p>
                  <div style={{ marginBottom: '8px' }}>
                    <div style={{ fontSize: '10px', color: '#444', letterSpacing: '1.5px', textTransform: 'uppercase', marginBottom: '10px' }}>
                      Try these instead
                    </div>
                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                      {humanError.examples.map(ex => (
                        <button
                          key={ex}
                          onClick={() => navigate('/', { state: { prefill: ex, sport } })}
                          style={{
                            padding: '8px 16px', fontSize: '12px', fontWeight: 600,
                            border: `1px solid ${sportConfig.color}40`,
                            borderRadius: '20px', background: `${sportConfig.color}10`,
                            color: sportConfig.color, cursor: 'pointer',
                            fontFamily: 'Inter, sans-serif',
                          }}
                        >
                          {ex}
                        </button>
                      ))}
                    </div>
                  </div>
                </>
              ) : (
                <>
                  <div style={{ fontSize: '13px', color: '#888', marginBottom: '12px' }}>
                    Pipeline error:
                  </div>
                  <pre style={{
                    fontSize: '12px', color: '#F87171',
                    fontFamily: 'monospace', background: '#150808',
                    padding: '12px', borderRadius: '6px',
                    whiteSpace: 'pre-wrap', wordBreak: 'break-all',
                    margin: 0,
                  }}>
                    {job.error}
                  </pre>
                </>
              )}

              <div style={{ marginTop: '24px', display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                <motion.button
                  whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}
                  onClick={() => navigate('/')}
                  style={{
                    padding: '12px 24px', fontSize: '12px', fontWeight: 700,
                    letterSpacing: '2px', textTransform: 'uppercase',
                    border: `1px solid ${sportConfig.color}`, borderRadius: '8px',
                    backgroundColor: sportConfig.color, color: '#000',
                    cursor: 'pointer', fontFamily: 'Inter, sans-serif',
                  }}
                >
                  ← Back to Home
                </motion.button>
              </div>
            </motion.div>
          )}

          {/* Progress log */}
          {job.progress.length > 0 && !isFailed && (
            <div style={{ marginBottom: '24px' }}>
              {job.progress.slice(-3).map((msg, i) => (
                <motion.div key={i} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}
                  style={{
                    fontSize: '11px', color: '#333', padding: '3px 0',
                    letterSpacing: '0.5px', fontFamily: 'monospace',
                  }}>
                  {msg}
                </motion.div>
              ))}
            </div>
          )}

          {/* Cancel */}
          {!isComplete && !isFailed && (
            <div style={{ textAlign: 'center' }}>
              <button
                onClick={() => navigate('/')}
                style={{
                  background: 'none', border: 'none', color: '#333',
                  fontSize: '12px', cursor: 'pointer', letterSpacing: '1px',
                  padding: '8px 16px', transition: 'color 0.2s', fontFamily: 'Inter, sans-serif',
                }}
                onMouseEnter={e => e.target.style.color = '#666'}
                onMouseLeave={e => e.target.style.color = '#333'}
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      </motion.div>
    </>
  )
}
