import { useToast } from 'primevue/usetoast'
import { useI18n } from 'vue-i18n'
import { parseApiError, formatErrorMessage, type ApiError, ErrorCodes } from '@/utils/errorHandler'

export interface UseApiErrorOptions {
  defaultLife?: number
  showStackTrace?: boolean
}

/**
 * Composable for handling API errors with toast notifications
 */
export function useApiError(options: UseApiErrorOptions = {}) {
  const { defaultLife = 5000 } = options
  const toast = useToast()
  const { t, te } = useI18n()

  /**
   * Get localized error message
   */
  function getLocalizedMessage(error: ApiError): string {
    // Try to get localized message by error code
    const localeKey = `errors.${error.code}`
    if (te(localeKey)) {
      return t(localeKey)
    }

    // Fall back to error message
    return formatErrorMessage(error, t('errors.unknown'))
  }

  /**
   * Get error summary/title based on error code
   */
  function getErrorSummary(error: ApiError): string {
    const summaryKey = `errors.summary.${error.code}`
    if (te(summaryKey)) {
      return t(summaryKey)
    }

    // Default summaries by category
    if (error.code.includes('NETWORK') || error.code.includes('TIMEOUT')) {
      return t('errors.summary.network', 'Connection Error')
    }
    if (error.code.includes('AUTH') || error.code.includes('UNAUTHORIZED')) {
      return t('errors.summary.auth', 'Authentication Error')
    }
    if (error.code.includes('VALIDATION')) {
      return t('errors.summary.validation', 'Validation Error')
    }

    return t('errors.summary.default', 'Error')
  }

  /**
   * Show error toast notification
   */
  function showError(error: unknown, customMessage?: string) {
    const apiError = parseApiError(error)

    toast.add({
      severity: 'error',
      summary: getErrorSummary(apiError),
      detail: customMessage || getLocalizedMessage(apiError),
      life: defaultLife
    })

    // Log error for debugging
    if (import.meta.env.DEV) {
      console.error('[API Error]', apiError)
    }

    return apiError
  }

  /**
   * Show warning toast notification
   */
  function showWarning(message: string, summary?: string) {
    toast.add({
      severity: 'warn',
      summary: summary || t('common.warning', 'Warning'),
      detail: message,
      life: defaultLife
    })
  }

  /**
   * Show success toast notification
   */
  function showSuccess(message: string, summary?: string) {
    toast.add({
      severity: 'success',
      summary: summary || t('common.success', 'Success'),
      detail: message,
      life: 3000
    })
  }

  /**
   * Show info toast notification
   */
  function showInfo(message: string, summary?: string) {
    toast.add({
      severity: 'info',
      summary: summary || t('common.info', 'Info'),
      detail: message,
      life: 3000
    })
  }

  /**
   * Handle async operation with error handling
   */
  async function withErrorHandling<T>(
    operation: () => Promise<T>,
    options?: {
      successMessage?: string
      errorMessage?: string
      showSuccessToast?: boolean
    }
  ): Promise<T | null> {
    try {
      const result = await operation()

      if (options?.showSuccessToast && options.successMessage) {
        showSuccess(options.successMessage)
      }

      return result
    } catch (error) {
      showError(error, options?.errorMessage)
      return null
    }
  }

  /**
   * Check if error is of specific type
   */
  function isErrorType(error: unknown, code: keyof typeof ErrorCodes): boolean {
    const apiError = parseApiError(error)
    return apiError.code === ErrorCodes[code]
  }

  return {
    showError,
    showWarning,
    showSuccess,
    showInfo,
    withErrorHandling,
    parseApiError,
    isErrorType,
    getLocalizedMessage,
    ErrorCodes
  }
}
