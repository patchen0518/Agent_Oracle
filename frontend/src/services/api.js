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
    const enhancedError = new Error()
    
    if (error.response) {
      // Server responded with error status
      enhancedError.response = error.response
      enhancedError.message = error.response.data?.detail || `HTTP ${error.response.status}`
      
      console.error('API Response Error:', {
        status: error.response.status,
        data: error.response.data,
        url: error.config?.url
      })
    } else if (error.request) {
      // Request made but no response received (network error)
      enhancedError.request = error.request
      enhancedError.message = 'Network error - unable to reach server'
      
      console.error('API Network Error:', error.message)
    } else if (error.code === 'ECONNABORTED') {
      // Request timeout
      enhancedError.code = 'ECONNABORTED'
      enhancedError.message = 'Request timeout - server took too long to respond'
      
      console.error('API Timeout Error:', error.message)
    } else {
      // Error in request setup
      enhancedError.message = error.message || 'Request configuration error'
      
      console.error('API Request Setup Error:', error.message)
    }
    
    // Preserve original error properties
    enhancedError.config = error.config
    enhancedError.isAxiosError = error.isAxiosError
    
    return Promise.reject(enhancedError)
  }
)

// Chat API functions using latest axios methods
export const postChatMessage = async (requestData) => {
  try {
    const response = await apiClient.post('/api/v1/chat', requestData)
    return response.data
  } catch (error) {
    // Enhanced error handling with specific error types
    const enhancedError = new Error()
    
    if (error.response) {
      // Server responded with error status
      const status = error.response.status
      const data = error.response.data
      
      enhancedError.response = error.response
      
      if (status === 400) {
        enhancedError.message = data?.detail || 'Invalid message format'
      } else if (status === 401) {
        enhancedError.message = 'Authentication failed - API key invalid'
      } else if (status === 429) {
        enhancedError.message = 'Rate limit exceeded - please wait before sending another message'
      } else if (status === 502) {
        enhancedError.message = 'AI service temporarily unavailable'
      } else if (status === 503) {
        enhancedError.message = 'Service temporarily unavailable'
      } else if (status >= 500) {
        enhancedError.message = 'Server error - please try again later'
      } else {
        enhancedError.message = data?.detail || `Server error: ${status}`
      }
    } else if (error.request) {
      // Network error
      enhancedError.request = error.request
      enhancedError.message = 'Unable to connect to server - check your internet connection'
    } else if (error.code === 'ECONNABORTED') {
      // Timeout error
      enhancedError.code = 'ECONNABORTED'
      enhancedError.message = 'Request timed out - the server is taking too long to respond'
    } else {
      // Request setup error
      enhancedError.message = error.message || 'Failed to send message'
    }
    
    throw enhancedError
  }
}

// Health check function
export const checkHealth = async () => {
  try {
    const response = await apiClient.get('/health')
    return response.data
  } catch (error) {
    const enhancedError = new Error()
    
    if (error.response) {
      enhancedError.response = error.response
      enhancedError.message = `Backend unhealthy (HTTP ${error.response.status})`
    } else if (error.request) {
      enhancedError.request = error.request
      enhancedError.message = 'Backend server is not reachable'
    } else {
      enhancedError.message = 'Health check failed'
    }
    
    throw enhancedError
  }
}

export default apiClient