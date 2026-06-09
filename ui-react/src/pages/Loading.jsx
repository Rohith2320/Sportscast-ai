import { useEffect, useState, useRef } from 'react'
import { useParams, useLocation, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { getJobStatus } from '../api'
import { SPORTS } from '../config'

const AGENT_STEPS = [
  { key: 'fetch', label: 'Fetching match data', icon: '📡' },
  { key: 'match', label: 'Analyzing match performance', icon: '📊' },
  { key: 'player', label: 'Analyzing player performances', icon: '👤' },
  { key: 'enrich', label: 'Enriching with context', icon: '🔍' },
  { key: 'narrative', label: 'Generating narrative', icon: '✍️' },
]

export default function Loading() {
  const { jobId } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const [job, setJob] = useState(null)
  const [dots, setDots] = useState('')
  const intervalRef = useRef(null)
  const pollRef = useRef(null)

  const sport = location.state?.sport || 'nba'
  const sportConfig = SPORTS[sport] || SPORTS.nba

  // Animated dots
  useEffect(() => {
    intervalRef.current = setInterval(() => {
      setDots(d => d.length >= 3 ? '' : d + '.')
    }, 400)
    return () => clearInterval(intervalRef.current)
  }, [])

  // Poll for job status
  useEffect(() => {
    if (!jobId) return

    const poll = async () => {
      try {
        const data = await getJobStatus(jobId)
        setJob(data)

        if (data.status === 'complete') {
          clearInterval(pollRef.current)
          setTimeout(() => {
            const gameId = data.result?.match_id || ''
            navigate(`/analysis/${sport}/${gameId}`, {
              state: { jobData: data }
            })
          }, 800)
        }

        if (data.status === 'failed') {
          clearInterval(pollRef.current)
        }
      } catch (err) {
        console.error('Poll error:', err)
      }
    }

    poll()
    pollRef.current = setInterval(poll, 2000)
    return () => clearInterval(pollRef.current)
  }, [jobId])

  const getCompletedSteps = () => {
    if (!job) return []
    const progress = job.progress || []
    const completed = []
    if (progress.some(p => p.toLowerCase().includes('fetch') || p.toLowerCase().includes('data'))) {
      completed.push('fetch')
    }
    if (progress.some(p => p.toLowerCase().includes('match') || p.toLowerCase().includes('analyz'))) {
      completed.push('match')
    }
    if (progress.some(p => p.toLowerCase().includes('player'))) {
      completed.push('player')
    }
    if (progress.some(p => p.toLowerCase().includes('enrich'))) {
      completed.push('enrich')
    }
    if (progress.some(p => p.toLowerCase().includes('narrative') || p.toLowerCase().includes('complete'))) {
      completed.push('narrative')
    }
    return completed
  }

  const completedSteps = getCompletedSteps()
  const currentStepIndex = completedSteps.length
  const isComplete = job?.status === 'complete'
  const isFailed = job?.status === 'failed'

  return (
    <motion.div
      style={{
        minHeight: '100vh',
        backgroundColor: '#0A0A0A',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '40px',
      }}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.25 }}
    >
      {/* Sport accent line at top */}
      <motion.div
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          height: '2px',
          backgroundColor: sportConfig.color,
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
            fontSize: '11px',
            color: sportConfig.color,
            letterSpacing: '3px',
            textTransform: 'uppercase',
            marginBottom: '12px',
            fontWeight: 700,
          }}>
            {sportConfig.icon} {sportConfig.label} Analysis
          </div>
          <h1 style={{
            fontFamily: 'Bebas Neue, sans-serif',
            fontSize: '52px',
            letterSpacing: '3px',
            color: '#FFFFFF',
            margin: 0,
            lineHeight: 1,
          }}>
            {isComplete ? 'ANALYSIS READY' : isFailed ? 'ANALYSIS FAILED' : `ANALYZING${dots}`}
          </h1>
          <p style={{
            fontSize: '13px',
            color: '#444',
            marginTop: '12px',
            letterSpacing: '1px',
          }}>
            {isComplete
              ? 'Redirecting to your analysis...'
              : isFailed
              ? job?.error || 'Something went wrong'
              : 'Multi-agent pipeline running'}
          </p>
        </motion.div>

        {/* Agent steps */}
        <div style={{
          backgroundColor: '#0D0D0D',
          border: '1px solid #1A1A1A',
          borderRadius: '16px',
          padding: '32px',
          marginBottom: '32px',
        }}>
          {AGENT_STEPS.map((step, i) => {
            const isDone = completedSteps.includes(step.key)
            const isActive = !isDone && i === currentStepIndex
            const isPending = !isDone && !isActive

            return (
              <motion.div
                key={step.key}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.08 }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '16px',
                  padding: '14px 0',
                  borderBottom: i < AGENT_STEPS.length - 1 ? '1px solid #111' : 'none',
                }}
              >
                {/* Status indicator */}
                <div style={{
                  width: '28px',
                  height: '28px',
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                  backgroundColor: isDone
                    ? sportConfig.color
                    : isActive
                    ? '#1A1A1A'
                    : '#0F0F0F',
                  border: `1px solid ${isDone ? sportConfig.color : isActive ? '#333' : '#1A1A1A'}`,
                  transition: 'all 0.3s',
                }}>
                  {isDone ? (
                    <motion.span
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      style={{ fontSize: '12px', color: '#000', fontWeight: 700 }}
                    >
                      ✓
                    </motion.span>
                  ) : isActive ? (
                    <motion.div
                      animate={{ rotate: 360 }}
                      transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                      style={{
                        width: '12px',
                        height: '12px',
                        border: `2px solid ${sportConfig.color}`,
                        borderTopColor: 'transparent',
                        borderRadius: '50%',
                      }}
                    />
                  ) : (
                    <div style={{
                      width: '6px',
                      height: '6px',
                      borderRadius: '50%',
                      backgroundColor: '#2A2A2A',
                    }} />
                  )}
                </div>

                {/* Step info */}
                <div style={{ flex: 1 }}>
                  <div style={{
                    fontSize: '13px',
                    fontWeight: isDone ? 500 : isActive ? 600 : 400,
                    color: isDone
                      ? '#888'
                      : isActive
                      ? '#FFFFFF'
                      : '#333',
                    transition: 'color 0.3s',
                  }}>
                    {step.label}
                  </div>
                  {isActive && (
                    <motion.div
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      style={{
                        fontSize: '11px',
                        color: sportConfig.color,
                        marginTop: '2px',
                        letterSpacing: '1px',
                      }}
                    >
                      Running{dots}
                    </motion.div>
                  )}
                </div>

                {/* Time badge */}
                {isDone && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    style={{
                      fontSize: '10px',
                      color: '#2A2A2A',
                      letterSpacing: '1px',
                    }}
                  >
                    ✓
                  </motion.div>
                )}
              </motion.div>
            )
          })}
        </div>

        {/* Progress messages */}
        {job?.progress && job.progress.length > 0 && (
          <div style={{ marginBottom: '24px' }}>
            {job.progress.slice(-3).map((msg, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                style={{
                  fontSize: '11px',
                  color: '#333',
                  padding: '3px 0',
                  letterSpacing: '0.5px',
                  fontFamily: 'monospace',
                }}
              >
                {msg}
              </motion.div>
            ))}
          </div>
        )}

        {/* Cancel button */}
        {!isComplete && !isFailed && (
          <div style={{ textAlign: 'center' }}>
            <button
              onClick={() => navigate('/')}
              style={{
                background: 'none',
                border: 'none',
                color: '#333',
                fontSize: '12px',
                cursor: 'pointer',
                letterSpacing: '1px',
                padding: '8px 16px',
                transition: 'color 0.2s',
                fontFamily: 'Inter, sans-serif',
              }}
              onMouseEnter={e => e.target.style.color = '#666'}
              onMouseLeave={e => e.target.style.color = '#333'}
            >
              ← Cancel
            </button>
          </div>
        )}

        {/* Failed state */}
        {isFailed && (
          <div style={{ textAlign: 'center' }}>
            <button
              onClick={() => navigate('/')}
              style={{
                padding: '12px 32px',
                fontSize: '12px',
                fontWeight: 700,
                letterSpacing: '2px',
                textTransform: 'uppercase',
                border: '1px solid #333',
                borderRadius: '8px',
                backgroundColor: 'transparent',
                color: '#888',
                cursor: 'pointer',
                fontFamily: 'Inter, sans-serif',
              }}
            >
              ← Try Again
            </button>
          </div>
        )}
      </div>
    </motion.div>
  )
}
