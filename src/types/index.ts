// Account Types
export interface Account {
  id: number
  telegram_id: number | null
  username: string | null
  phone: string | null
  first_name: string | null
  last_name: string | null
  status: AccountStatus
  proxy: Proxy | null
  proxy_id: number | null
  group: AccountGroup | null
  group_id: number | null
  tags: AccountTag[]
  last_checked_at: string | null
  last_used_at: string | null
  created_at: string
}

export type AccountStatus =
  | 'unchecked'
  | 'checking'
  | 'valid'
  | 'invalid'
  | 'banned'
  | 'spamblock'
  | 'session_expired'

// Proxy Types
export interface Proxy {
  id: number
  type: ProxyType
  host: string
  port: number
  username: string | null
  password?: string | null
  status: ProxyStatus
  accounts_count: number
  last_checked_at: string | null
  created_at: string
}

export type ProxyType = 'socks5' | 'socks4' | 'http' | 'https'
export type ProxyStatus = 'unchecked' | 'valid' | 'invalid'

export interface ProxyCreate {
  type: ProxyType
  host: string
  port: number
  username?: string
  password?: string
}

// Group Types
export interface AccountGroup {
  id: number
  name: string
  color: string | null
  accounts_count: number
  created_at: string
}

export interface GroupCreate {
  name: string
  color?: string
}

// Tag Types
export interface AccountTag {
  id: number
  name: string
  color: string
}

export interface TagCreate {
  name: string
  color?: string
}

// Filter Types
export interface AccountFilters {
  status?: AccountStatus | null
  group_id?: number | null
  tag_id?: number | null
  search?: string
}

// Bulk Action Types
export type BulkAction = 'delete' | 'set_proxy' | 'set_group' | 'add_tag' | 'remove_tag' | 'check'

export interface BulkActionParams {
  action: BulkAction
  account_ids: number[]
  value?: number
}

// API Response Types
export interface ApiResponse<T> {
  data?: T
  success?: boolean
  message?: string
  error?: string
}

export interface ImportResult {
  success: boolean
  imported: number
  errors: { index: number; error: string }[]
  accounts?: Account[]
}

export interface CheckResult {
  valid: boolean
  user_info?: {
    telegram_id: number
    username: string | null
    first_name: string | null
    last_name: string | null
    phone: string | null
  }
  error?: string
}
