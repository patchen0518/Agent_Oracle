// API service for backend communication
// Based on axios latest documentation (Context 7 lookup: 2025-01-27)

import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// Create axios instance with base configuration following latest patterns
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // 30 seconds timeout
  headers: {
    'Content-Type': 'application/json',
  },
  // Custom status validation - resolve for 2xx and 4xx, reject for 5xx
  validateStatus: function (status) {
    return status >= 200 && status < 500
  }
})

// Request interceptor for logging and configuration (development)
apiClient.interceptors.request.use(
  function (config) {
    // Log request details in development
    if (import.meta.env.DEV) {
      console.log('API Request:', config.method?.toUpperCase(), config.url)
    }
    return config
  },
  function (error) {
    console.error('API Request Error:', error)
    return Promise.reject(error)
  }
)

// Response interceptor for error handling and logging
apiClient.interceptors.response.use(
  function onFulfilled(response) {
    // Log successful responses in development
    if (import.meta.env.DEV) {
      console.log('API Response:', response.status, response.config.url)
    }
    return response
  },
  function onRejected(error) {
    // Enhanced error handling based on latest axios patterns
    if (error.response) {
      // Server responded with error status
      console.error('API Response Error:', {
        status: error.response.status,
        data: error.response.data,
        url: error.config?.url
      })
    } else if (error.request) {
      // Request made but no response received
      console.error('API Network Error:', error.message)
    } else {
      // Error in request setup
      console.error('API Request Setup Error:', error.message)
    }
    return Promise.reject(error)
  }
)

// Chat API functions using latest axios methods
export const postChatMessage = async (requestData) => {
  try {
    const response = await apiClient.post('/api/v1/chat', requestData)
    return response.data
  } catch (error) {
    // Enhanced error handling following latest axios error structure
    let errorMessage = 'Failed to send message'
    
    if (error.response) {
      // Server responded with error status
      errorMessage = error.response.data?.detail || `Server error: ${error.response.status}`
    } else if (error.request) {
      // Network error
      errorMessage = 'Network error - please check your connection'
    } else {
      // Request setup error
      errorMessage = error.message || 'Request failed'
    }
    
    throw new Error(errorMessage)
  }
}

// Health check function
export const checkHealth = async () => {
  try {
    const response = await apiClient.get('/health')
    return response.data
  } catch (error) {
    throw new Error('Backend is not available')
  }
}

export default apiClient