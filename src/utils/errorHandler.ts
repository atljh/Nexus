/**
 * Structured API error handling utilities
 */

export interface ApiError {
  code: string
  message: string
  details?: Record<string, unknown>
  statusCode?: number
}

// Known error codes for i18n
export const ErrorCodes = {
  // Network errors
  NETWORK_ERROR: 'NETWORK_ERROR',
  TIMEOUT: 'TIMEOUT',
  CONNECTION_REFUSED: 'CONNECTION_REFUSED',

  // Auth errors
  UNAUTHORIZED: 'UNAUTHORIZED',
  SESSION_EXPIRED: 'SESSION_EXPIRED',
  INVALID_CREDENTIALS: 'INVALID_CREDENTIALS',

  // Account errors
  ACCOUNT_NOT_FOUND: 'ACCOUNT_NOT_FOUND',
  ACCOUNT_BANNED: 'ACCOUNT_BANNED',
  ACCOUNT_SPAMBLOCK: 'ACCOUNT_SPAMBLOCK',
  INVALID_SESSION: 'INVALID_SESSION',
  PROXY_REQUIRED: 'PROXY_REQUIRED',

  // Proxy errors
  PROXY_NOT_FOUND: 'PROXY_NOT_FOUND',
  PROXY_NOT_WORKING: 'PROXY_NOT_WORKING',
  PROXY_TIMEOUT: 'PROXY_TIMEOUT',

  // Import errors
  IMPORT_FAILED: 'IMPORT_FAILED',
  INVALID_FILE_FORMAT: 'INVALID_FILE_FORMAT',
  NO_VALID_SESSIONS: 'NO_VALID_SESSIONS',

  // 2FA errors
  TWO_FA_REQUIRED: 'TWO_FA_REQUIRED',
  TWO_FA_INVALID: 'TWO_FA_INVALID',

  // Generic errors
  VALIDATION_ERROR: 'VALIDATION_ERROR',
  SERVER_ERROR: 'SERVER_ERROR',
  UNKNOWN: 'UNKNOWN'
} as const

export type ErrorCode = (typeof ErrorCodes)[keyof typeof ErrorCodes]

/**
 * Parse an error from various sources into a structured ApiError
 */
export function parseApiError(error: unknown): ApiError {
  // Already an ApiError
  if (isApiError(error)) {
    return error
  }

  // Axios-like error with response
  if (isAxiosError(error)) {
    const response = error.response
    if (response?.data) {
      const data = response.data as Record<string, unknown>
      return {
        code: (data.code as string) || getCodeFromStatus(response.status),
        message: (data.detail as string) || (data.message as string) || error.message,
        details: data.details as Record<string, unknown>,
        statusCode: response.status
      }
    }
    return {
      code: ErrorCodes.NETWORK_ERROR,
      message: error.message || 'Network error',
      statusCode: response?.status
    }
  }

  // Standard Error
  if (error instanceof Error) {
    // Check for network errors
    if (error.message.includes('fetch') || error.message.includes('network')) {
      return {
        code: ErrorCodes.NETWORK_ERROR,
        message: error.message
      }
    }
    if (error.message.includes('timeout')) {
      return {
        code: ErrorCodes.TIMEOUT,
        message: error.message
      }
    }
    return {
      code: ErrorCodes.UNKNOWN,
      message: error.message
    }
  }

  // String error
  if (typeof error === 'string') {
    return {
      code: ErrorCodes.UNKNOWN,
      message: error
    }
  }

  // Unknown error type
  return {
    code: ErrorCodes.UNKNOWN,
    message: 'An unexpected error occurred'
  }
}

/**
 * Type guard for ApiError
 */
export function isApiError(error: unknown): error is ApiError {
  return (
    typeof error === 'object' &&
    error !== null &&
    'code' in error &&
    'message' in error &&
    typeof (error as ApiError).code === 'string' &&
    typeof (error as ApiError).message === 'string'
  )
}

/**
 * Type guard for Axios-like errors
 */
function isAxiosError(error: unknown): error is { response?: { status: number; data: unknown }; message: string } {
  return (
    typeof error === 'object' &&
    error !== null &&
    'message' in error &&
    typeof (error as { message: string }).message === 'string'
  )
}

/**
 * Get error code from HTTP status
 */
function getCodeFromStatus(status: number): ErrorCode {
  switch (status) {
    case 400:
      return ErrorCodes.VALIDATION_ERROR
    case 401:
      return ErrorCodes.UNAUTHORIZED
    case 403:
      return ErrorCodes.UNAUTHORIZED
    case 404:
      return ErrorCodes.ACCOUNT_NOT_FOUND
    case 408:
      return ErrorCodes.TIMEOUT
    case 500:
      return ErrorCodes.SERVER_ERROR
    case 502:
    case 503:
    case 504:
      return ErrorCodes.SERVER_ERROR
    default:
      return ErrorCodes.UNKNOWN
  }
}

/**
 * Create a user-friendly error message
 */
export function formatErrorMessage(error: ApiError, fallback = 'An error occurred'): string {
  if (error.message) {
    return error.message
  }
  return fallback
}
