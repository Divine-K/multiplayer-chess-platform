import { apiRequest } from './client'

export interface ReadinessStatus {
  status: string
  database: string
}

export const healthApi = {
  readiness: (signal?: AbortSignal) =>
    apiRequest<ReadinessStatus>('/health/ready', { authenticated: false, signal }),
}
