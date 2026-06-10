import { useEffect, useState, useRef } from 'react'
import { useParams, useLocation, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Helmet } from 'react-helmet-async'
import { getJobStatus, API_BASE_URL } from '../api'
import { SPORTS } from '../config'
import { useWindowSize } from '../hooks/useWindowSize'

const AGENT_STEPS = [
  { key: 'fetch',     label: 'Fetching match data',           secsRemaining: 80 },
  { key: 'match',     label: 'Analyzing match performance',   secsRemaining: 65 },
  { key: 'player',    label: 'Analyzing player performances', secsRemaining: 50 },
  { key: 'enrich',    label: 'Enriching with context',        secsRemaining: 30 },
  { key: 'narrative', label: 'Generating narrative',          secsRemaining: 12 },
]

const SPORT_FETCH_MSG = {
  nba:      'Fetching NBA box score and play-by-play data',
  mlb:      'Fetching MLB box score and pitching data',
  f1:       'Fetching F1 race results and telemetry',
  soccer:   'Fetching match statistics and lineups',
  valorant: 'Fetching VCT match data and round history',
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
          // Fetch full result for the match_id navigation target
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

    sse.onerror = () => {
      // SSE dropped — close silently, job still runs server-side
      sse.close()
    }

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

        <div style={{ maxWidth: '560px', width: '100%' }}>

          {/* Header */}
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            style={{ marginBottom: '48px', textAlign: 'center' }}
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
            <p style={{
              fontSize: isMobile ? '12px' : '13px',
              color: '#444', marginTop: '12px', letterSpacing: '1px',
            }}>
              {isComplete
                ? 'Redirecting to your analysis...'
                : isFailed
                ? (job.error || 'Something went wrong')
                : 'Multi-agent pipeline running'}
            </p>

            {!isComplete && !isFailed && (
              <div style={{ marginTop: '20px' }}>
                <p style={{ fontSize: '13px', color: '#555', lineHeight: 1.7, margin: '0 0 6px 0' }}>
                  Our AI pipeline is fetching live match data and generating broadcast-quality analysis.
                </p>
                <p style={{ fontSize: '12px', color: '#3A3A3A', margin: 0 }}>
                  Fresh analysis takes 60-90 seconds. Cached analyses load instantly.
                </p>
                {currentStepIndex === 0 && (
                  <p style={{ fontSize: '12px', color: sportConfig.color, marginTop: '8px', opacity: 0.8 }}>
                    {SPORT_FETCH_MSG[sport] || SPORT_FETCH_MSG.nba}...
                  </p>
                )}
                {currentStepIndex > 0 && currentStepIndex < AGENT_STEPS.length && (
                  <p style={{ fontSize: '12px', color: '#444', marginTop: '8px' }}>
                    Agent{' '}
                    <span style={{ color: sportConfig.color, fontWeight: 600 }}>
                      {currentStepIndex}/{AGENT_STEPS.length}
                    </span>
                    {' '}complete &middot; ~{AGENT_STEPS[currentStepIndex].secsRemaining}s remaining
                  </p>
                )}
              </div>
            )}
          </motion.div>

          {/* Progress bar */}
          <div style={{
            width: '100%', height: '3px', backgroundColor: '#1A1A1A',
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

          {/* Agent steps */}
          <div style={{
            backgroundColor: '#0D0D0D', border: '1px solid #1A1A1A',
            borderRadius: '16px', padding: isMobile ? '20px' : '32px', marginBottom: '32px',
          }}>
            {AGENT_STEPS.map((step, i) => {
              const isDone = completedSteps.includes(step.key)
              const isActive = !isDone && i === currentStepIndex

              return (
                <motion.div
                  key={step.key}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.08 }}
                  style={{
                    display: 'flex', alignItems: 'center', gap: '16px',
                    padding: '14px 0',
                    borderBottom: i < AGENT_STEPS.length - 1 ? '1px solid #111' : 'none',
                  }}
                >
                  <div style={{
                    width: '28px', height: '28px', borderRadius: '50%', flexShrink: 0,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    backgroundColor: isDone ? sportConfig.color : isActive ? '#1A1A1A' : '#0F0F0F',
                    border: `1px solid ${isDone ? sportConfig.color : isActive ? '#333' : '#1A1A1A'}`,
                    transition: 'all 0.3s',
                  }}>
                    {isDone ? (
                      <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }}
                        style={{ fontSize: '12px', color: '#000', fontWeight: 700 }}>
                        ✓
                      </motion.span>
                    ) : isActive ? (
                      <motion.div
                        animate={{ rotate: 360 }}
                        transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                        style={{
                          width: '12px', height: '12px',
                          border: `2px solid ${sportConfig.color}`,
                          borderTopColor: 'transparent', borderRadius: '50%',
                        }}
                      />
                    ) : (
                      <div style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#2A2A2A' }} />
                    )}
                  </div>

                  <div style={{ flex: 1 }}>
                    <div style={{
                      fontSize: '13px',
                      fontWeight: isDone ? 500 : isActive ? 600 : 400,
                      color: isDone ? '#888' : isActive ? '#FFFFFF' : '#333',
                      transition: 'color 0.3s',
                    }}>
                      {step.label}
                    </div>
                    {isActive && (
                      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                        style={{ fontSize: '11px', color: sportConfig.color, marginTop: '2px', letterSpacing: '1px' }}>
                        Running{dots}
                      </motion.div>
                    )}
                  </div>

                  {isDone && (
                    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                      style={{ fontSize: '10px', color: '#2A2A2A' }}>
                      ✓
                    </motion.div>
                  )}
                </motion.div>
              )
            })}
          </div>

          {/* Progress log */}
          {job.progress.length > 0 && (
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

          {/* Failed */}
          {isFailed && (
            <div style={{ textAlign: 'center' }}>
              <button
                onClick={() => navigate('/')}
                style={{
                  padding: '12px 32px', fontSize: '12px', fontWeight: 700,
                  letterSpacing: '2px', textTransform: 'uppercase',
                  border: '1px solid #333', borderRadius: '8px',
                  backgroundColor: 'transparent', color: '#888',
                  cursor: 'pointer', fontFamily: 'Inter, sans-serif',
                }}>
                Try Again
              </button>
            </div>
          )}

        </div>
      </motion.div>
    </>
  )
}
