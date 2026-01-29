import { ref, watch, type Ref } from 'vue'

/**
 * Creates a debounced ref that updates after a delay
 * @param sourceRef - The source ref to debounce
 * @param delay - Delay in milliseconds (default: 300)
 * @returns A debounced ref
 */
export function useDebouncedRef<T>(sourceRef: Ref<T>, delay = 300): Ref<T> {
  const debouncedValue = ref(sourceRef.value) as Ref<T>
  let timeout: ReturnType<typeof setTimeout> | null = null

  watch(sourceRef, (newVal) => {
    if (timeout) {
      clearTimeout(timeout)
    }
    timeout = setTimeout(() => {
      debouncedValue.value = newVal
    }, delay)
  })

  return debouncedValue
}

/**
 * Creates a debounced callback function
 * @param fn - The function to debounce
 * @param delay - Delay in milliseconds (default: 300)
 * @returns A debounced function
 */
export function useDebouncedFn<T extends (...args: unknown[]) => unknown>(
  fn: T,
  delay = 300
): (...args: Parameters<T>) => void {
  let timeout: ReturnType<typeof setTimeout> | null = null

  return (...args: Parameters<T>) => {
    if (timeout) {
      clearTimeout(timeout)
    }
    timeout = setTimeout(() => {
      fn(...args)
    }, delay)
  }
}
