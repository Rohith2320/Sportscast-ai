import axios from 'axios'

const API = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 15000,
})

export const startAnalysis = async (sport, matchId, persona, forceRefresh) => {
  const res = await API.post('/analyze/', {
    sport,
    match_id: matchId,
    persona,
    force_refresh: forceRefresh,
  })
  return res.data
}

export const getJobStatus = async (jobId) => {
  const res = await API.get(`/analyze/${jobId}`)
  return res.data
}

export const getCachedGames = async (sport = null) => {
  const url = sport ? `/games/?sport=${sport}` : '/games/'
  const res = await API.get(url)
  return res.data
}

export const getGame = async (sport, gameId) => {
  const safeId = gameId.replace('/', '_')
  const res = await API.get(`/games/${sport}/${safeId}`)
  return res.data
}

export const sendChat = async (sport, gameId, query, chatHistory) => {
  const safeId = gameId.replace('/', '_')
  const res = await API.post('/chat/', {
    sport,
    game_id: safeId,
    query,
    chat_history: chatHistory,
  })
  return res.data
}

export const getHealth = async () => {
  const res = await API.get('/health')
  return res.data
}