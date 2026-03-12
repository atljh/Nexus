// Account Types
export interface Account {
  id: number
  telegram_id: number | null
  username: string | null
  phone: string | null
  first_name: string | null
  last_name: string | null
  status: AccountStatus
  spamblock: boolean | null
  is_premium: boolean
  geo: string | null
  register_time: string | null
  has_2fa: boolean
  password_hint: string | null
  two_fa_password: string | null
  two_fa_set_at: string | null
  metadata: Record<string, unknown> | null
  proxy: Proxy | null
  proxy_id: number | null
  group: AccountGroup | null
  group_id: number | null
  tags: AccountTag[]
  last_check_error_code: string | null
  last_check_error: string | null
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
  | 'muted'
  | 'spamblock'
  | 'frozen'
  | 'session_expired'
  | 'deactivated'
  | 'needs_reauth'
  | 'connection_failed'

// Proxy Types
export interface Proxy {
  id: number
  type: ProxyType
  host: string
  port: number
  username: string | null
  password?: string | null
  status: ProxyStatus
  ping_ms: number | null
  geo: string | null
  external_ip: string | null
  accounts_count: number
  last_checked_at: string | null
  created_at: string
}

export type ProxyType = 'socks5' | 'socks4' | 'http' | 'https'
export type ProxyStatus = 'unchecked' | 'working' | 'slow' | 'very_slow' | 'not_working' | 'timeout'

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
  proxy_id?: number | null
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
  status: AccountStatus
  user_info?: {
    telegram_id: number
    username: string | null
    first_name: string | null
    last_name: string | null
    phone: string | null
  }
  error_code?: string | null
  error?: string
}

// Batch Check Types
export interface CheckBatchOptions {
  checkSpamblock: boolean
  maxConcurrent: number
}

export interface CheckBatchResult {
  checked: number
  results: {
    id: number
    status: AccountStatus
    telegram_id: number | null
    username: string | null
    is_premium: boolean
    spamblock: boolean | null
    geo: string | null
    error_code: string | null
    error: string | null
  }[]
}

export interface ProxyCheckBatchResult {
  checked: number
  results: {
    id: number
    status: ProxyStatus
    ping_ms: number | null
    external_ip: string | null
    geo: string | null
  }[]
}

// Proxy Assignment Types
export interface ProxyAssignment {
  account_id: number
  proxy_id: number | null
}

export interface AssignProxiesRequest {
  assignments?: ProxyAssignment[]
  account_ids?: number[]
  proxy_ids?: number[]
  mode?: 'sequential' | 'random'
}

// Session+JSON Import Types
export interface SessionJsonImportResult {
  success: boolean
  imported: number
  errors: number
  accounts: {
    file: string
    telegram_id: number | null
    username: string | null
    phone: string | null
    geo: string | null
  }[]
  error_details: {
    file: string
    error: string
  }[]
}

// Task Types
export interface Task {
  id: number
  task_type: TaskType
  status: TaskStatus
  config: TaskConfig
  total_actions: number
  completed_actions: number
  failed_actions: number
  min_delay: number
  max_delay: number
  max_concurrent: number
  last_error: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
  accounts_count: number
  progress: number
}

export type TaskType = 'likes' | 'comments'
export type TaskStatus = 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled'

// Base config shared by all task types
export interface TaskConfig {
  // For likes tasks
  channel?: string
  post_id?: number | null
  reactions?: string[]
  emoji_mode?: 'single' | 'random' | 'all'
  invite_link?: string
  // For comments tasks
  channels?: string[]
  invite_links?: string[]
  templates?: string[]
  rotation_mode?: 'random' | 'round_robin'
  comments_per_account?: number
  mode?: 'single' | 'monitoring'
}

export interface TaskLog {
  id: number
  task_id: number
  account_id: number | null
  action_type: string
  target: string | null
  success: boolean
  message: string | null
  error: string | null
  extra_data: Record<string, unknown> | null
  created_at: string
}

export interface CreateLikesTaskParams {
  config: {
    channel: string
    post_id?: number | null
    invite_link?: string
    reactions: string[]
    emoji_mode: 'single' | 'random' | 'all'
  }
  account_ids: number[]
  total_actions?: number  // ignored by backend — auto-calculated from account count
  min_delay: number
  max_delay: number
  max_concurrent: number
}

export interface TaskStats {
  total: number
  running: number
  pending: number
  completed: number
  failed: number
}

// Reaction emoji options
export const REACTION_EMOJIS = [
  { value: '👍', label: '👍 Like' },
  { value: '❤️', label: '❤️ Heart' },
  { value: '🔥', label: '🔥 Fire' },
  { value: '👏', label: '👏 Clap' },
  { value: '🥰', label: '🥰 Love' },
  { value: '😢', label: '😢 Sad' },
  { value: '🎉', label: '🎉 Party' },
  { value: '🤔', label: '🤔 Think' },
  { value: '🤯', label: '🤯 Mind Blown' },
  { value: '😱', label: '😱 Shocked' },
] as const

// Comment Template Types
export interface CommentTemplate {
  id: number
  name: string
  content: string
  is_default: boolean
  created_at: string
}

export interface CreateCommentTemplateParams {
  name: string
  content: string
  is_default?: boolean
}

// Comments Task Types
export interface CommentsTaskConfig {
  channels: string[]
  invite_links?: string[]
  post_id?: number
  templates: string[]
  rotation_mode: 'random' | 'round_robin'
  comments_per_account: number
  mode: 'single' | 'monitoring'
}

export interface CreateCommentsTaskParams {
  config: CommentsTaskConfig
  account_ids: number[]
  total_actions: number
  min_delay: number
  max_delay: number
  max_concurrent?: number
}

export interface TargetChannel {
  id: number
  task_id: number
  channel_username: string
  channel_id: number | null
  channel_title: string | null
  status: 'pending' | 'joined' | 'error' | 'cannot_comment'
  can_comment: boolean
  error_message: string | null
  comments_sent: number
  created_at: string
}

// Default comment templates
export const DEFAULT_COMMENT_TEMPLATES = [
  {
    name: 'Positive Reaction',
    content: '{Wow|Amazing|Great|Awesome|Nice}! {This is|That\'s} {really|so|very} {cool|interesting|helpful}! {👍|🔥|❤️|👏}'
  },
  {
    name: 'Question',
    content: '{Interesting|Cool|Nice}! {Can you|Could you|Would you} {tell|explain} more about {this|it}? {🤔|❓}'
  },
  {
    name: 'Agreement',
    content: '{Totally|Completely|Absolutely} {agree|true}! {I think so too|Same here|Exactly}. {💯|✅|👍}'
  },
  {
    name: 'Thanks',
    content: '{Thanks|Thank you|Thx} for {sharing|posting|this}! {Very|Really|So} {useful|helpful|informative}! {🙏|❤️|👍}'
  },
  {
    name: 'Simple',
    content: '{Nice|Cool|Great|Good|Awesome} {post|content|stuff}! {👍|🔥|❤️|💯}'
  }
] as const

// ============================================================
// 2FA Types
// ============================================================

export interface TwoFAStatus {
  has_2fa: boolean
  password_hint: string | null
  error: string | null
}

export interface TwoFASetRequest {
  password: string
  hint?: string
}

export interface TwoFAChangeRequest {
  current_password: string
  new_password: string
  new_hint?: string
}

export interface TwoFARemoveRequest {
  current_password: string
}

export interface TwoFAResult {
  success: boolean
  message?: string
  error?: string
}

// ============================================================
// Account Authorization Types
// ============================================================

export type AuthStep = 'phone' | 'code' | 'password' | 'success'

export interface ProxyConfig {
  type: 'socks5' | 'socks4' | 'http' | 'https'
  host: string
  port: number
  username?: string
  password?: string
}

export interface AuthStartRequest {
  phone: string
  proxy?: ProxyConfig
}

export interface AuthStartResponse {
  session_id: string
  phone: string
  status: 'code_sent'
  message: string
}

export interface AuthVerifyRequest {
  session_id: string
  code: string
  password?: string
}

export interface AuthVerifyResponse {
  status: 'success' | 'password_required'
  account_id?: number
  telegram_id?: number
  username?: string | null
  phone?: string | null
  message?: string
}

export interface AuthSessionInfo {
  phone: string
  needs_password: boolean
  expires_at: string
  created_at: string
}

// ============================================================
// WebK Viewer Types
// ============================================================

export interface WebKSessionData {
  dc: number
  [key: string]: unknown // dc2_auth_key, dc2_server_salt, etc.
  user_auth?: {
    dcID: number
    id: number
    date: number
  }
  account1?: Record<string, unknown>
  auth_key_fingerprint?: string
}

export interface WebKHealthStatus {
  sessionPresent: boolean
  connected: boolean
  dcId: number | null
  userId: number | null
  timestamp: number
}

export interface DeviceFingerprint {
  device_model?: string
  system_version?: string
  app_version?: string
  lang_code?: string
  system_lang_code?: string
}

export interface WebKSessionResponse {
  success: boolean
  session_data: WebKSessionData
  proxy: ProxyConfig
  device_fingerprint: DeviceFingerprint | null
  account: {
    id: number
    telegram_id: number
    username: string | null
    phone: string | null
    first_name: string | null
    last_name: string | null
  }
}

export interface WebViewState {
  loading: boolean
  error: string | null
  sessionInjected: boolean
  connected: boolean
  partition: string | null
}
