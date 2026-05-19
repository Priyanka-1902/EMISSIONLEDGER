import axios from 'axios'
import { useAuthStore } from '../stores/auth'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'https://api.emissionledger.in',
  timeout: 30_000,
})

// Attach JWT and tenant context to every request
api.interceptors.request.use(config => {
  const { token, tenant } = useAuthStore.getState()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  if (tenant?.id) {
    config.headers['X-Tenant-ID'] = tenant.id
  }
  return config
})

// Auto-refresh token on 401
api.interceptors.response.use(
  res => res,
  async error => {
    const originalRequest = error.config
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true
      try {
        const { refreshToken } = useAuthStore.getState()
        await refreshToken()
        const { token } = useAuthStore.getState()
        originalRequest.headers.Authorization = `Bearer ${token}`
        return api(originalRequest)
      } catch {
        useAuthStore.getState().logout()
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)
