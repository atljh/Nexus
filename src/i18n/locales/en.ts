export default {
  common: {
    save: 'Save',
    cancel: 'Cancel',
    delete: 'Delete',
    edit: 'Edit',
    add: 'Add',
    check: 'Check',
    import: 'Import',
    export: 'Export',
    close: 'Close',
    confirm: 'Confirm',
    create: 'Create',
    confirmation: 'Confirmation',
    yes: 'Yes',
    no: 'No',
    loading: 'Loading...',
    error: 'Error',
    success: 'Success',
    warning: 'Warning',
    info: 'Info',
    noData: 'No data',
    actions: 'Actions',
    status: 'Status',
    type: 'Type',
    never: 'Never',
    optional: 'optional',
    color: 'Color',
    back: 'Back',
    done: 'Done'
  },

  nav: {
    dashboard: 'Dashboard',
    accounts: 'Accounts',
    proxy: 'Proxy',
    autoLikes: 'Auto Likes',
    autoComments: 'Auto Comments',
    settings: 'Settings'
  },

  sidebar: {
    backendConnected: 'Backend connected',
    backendDisconnected: 'Backend disconnected'
  },

  dashboard: {
    title: 'Dashboard',
    accounts: 'Accounts',
    accountsActive: '{count} active',
    proxies: 'Proxies',
    proxiesWorking: '{count} working',
    likesToday: 'Likes Today',
    tasksCount: '{count} tasks',
    commentsToday: 'Comments Today',
    quickActions: 'Quick Actions',
    addAccount: 'Add Account',
    addProxy: 'Add Proxy',
    newLikeTask: 'New Like Task'
  },

  accounts: {
    title: 'Accounts',
    import: 'Import',
    checkAll: 'Check All',
    importAccounts: 'Import Accounts',
    noAccounts: 'No accounts yet',
    account: 'Account',
    proxy: 'Proxy',
    noProxy: 'No proxy',
    group: 'Group',
    tags: 'Tags',
    deleteConfirm: 'Delete account @{name}?',

    importDialog: {
      title: 'Import Accounts',
      useProxy: 'Proxy',
      selectProxy: 'Select proxy',
      noProxyDirect: 'No proxy (direct connection)',
      proxyRequired: 'Proxy is required for import',
      noWorkingProxies: 'No working proxies. Add and check proxies first.',
      addNewProxy: 'Add Proxy',
      addAndCheck: 'Add & Check',
      proxyString: 'String',
      proxyForm: 'Form',
      proxyStringLabel: 'Proxy string',
      proxyStringPlaceholder: 'host:port or host:port:user:pass'
    },

    tdata: {
      title: 'tdata',
      description: 'Import from Telegram Desktop (tdata folder as .zip)',
      step1: 'Close Telegram Desktop',
      step2: 'Find tdata folder in app data',
      step3: 'Create a .zip archive of tdata folder',
      step4: 'Upload the .zip file below',
      selectFile: 'Select tdata.zip'
    },

    jsonSession: {
      title: 'JSON Session',
      description: 'Import Telethon/Pyrogram session files (.json format)',
      format: 'JSON should contain:',
      selectFile: 'Select session.json'
    },

    sessionString: {
      title: 'Session String',
      description: 'Paste Telethon session string directly',
      label: 'Session String',
      placeholder: '1BQANOTEuMTA4L...',
      importButton: 'Import Session'
    },

    sessionJson: {
      title: 'Session + JSON',
      description: 'Import .session files with matching .json metadata files',
      sessionFiles: 'Session Files',
      jsonFiles: 'JSON Files',
      selectSessionFiles: 'Select .session files',
      selectJsonFiles: 'Select .json files',
      filesSelected: '{count} files selected',
      importButton: 'Import Pairs'
    },

    dropZone: {
      dropTitle: 'Drop files here or click to select',
      dropHint: 'Supports multiple files at once',
      selectedFiles: 'Selected files',
      importButton: 'Import',
      orPasteSession: 'or paste session string'
    },

    batchCheck: {
      title: 'Batch Check Accounts',
      description: 'Check multiple accounts in parallel',
      checkSpamblock: 'Check spamblock status',
      spamblockWarning: 'Spamblock check requires sending messages to @SpamBot',
      maxConcurrent: 'Max concurrent checks',
      startCheck: 'Start Check',
      progress: 'Checking: {current}/{total}',
      complete: 'Check complete: {valid} valid, {invalid} invalid'
    },

    status: {
      valid: 'valid',
      invalid: 'invalid',
      banned: 'banned',
      spamblock: 'spamblock',
      session_expired: 'session expired',
      checking: 'checking',
      unchecked: 'unchecked',
      muted: 'muted',
      deactivated: 'deactivated',
      needs_reauth: 'needs reauth',
      connection_failed: 'connection failed'
    },

    messages: {
      loadError: 'Failed to load accounts',
      importSuccess: 'Account imported successfully',
      importedCount: 'Imported {count} accounts',
      importFailed: 'Failed to import',
      importPartialFail: '{count} accounts failed to import',
      enterSessionString: 'Please enter a session string',
      accountValid: 'Account Valid',
      accountWorking: '@{name} is working',
      accountInvalid: 'Account Invalid',
      sessionNotValid: 'Session is not valid',
      checkFailed: 'Check Failed',
      checkingAll: 'Checking all accounts in background',
      deleted: 'Account deleted successfully',
      deleteFailed: 'Failed to delete account',
      bulkSuccess: 'Action completed for {count} accounts',
      selectAccountsFirst: 'Please select accounts first',
      selectSessionFiles: 'Please select session files',
      selectJsonFiles: 'Please select JSON files',
      batchCheckComplete: 'Batch check complete: {valid} valid, {invalid} invalid',
      sessionJsonImported: 'Imported {count} accounts from session+json pairs',
      sessionJsonErrors: '{count} files failed to import'
    },

    allStatuses: 'All statuses',
    searchPlaceholder: 'Search by username, phone...',
    filterByStatus: 'Filter by status',
    selected: 'Selected: {count}',
    bulkDeleteConfirm: 'Delete {count} accounts?',

    bulk: {
      actions: 'Actions',
      check: 'Check',
      setProxy: 'Set Proxy',
      noProxy: 'No Proxy',
      setGroup: 'Set Group',
      noGroup: 'No Group',
      delete: 'Delete'
    },

    twoFA: {
      title: '2FA Management',
      status: '2FA Status',
      checking: 'Checking 2FA status...',
      enabled: '2FA Enabled',
      disabled: '2FA Disabled',
      hint: 'Password Hint',
      set: 'Set 2FA',
      change: 'Change 2FA',
      remove: 'Remove 2FA',
      password: 'Password',
      enterPassword: 'Enter password',
      confirmPassword: 'Confirm Password',
      confirmPasswordPlaceholder: 'Confirm password',
      currentPassword: 'Current Password',
      enterCurrentPassword: 'Enter current password',
      newPassword: 'New Password',
      enterNewPassword: 'Enter new password',
      confirmNewPassword: 'Confirm New Password',
      confirmNewPasswordPlaceholder: 'Confirm new password',
      newHint: 'New Hint',
      passwordHint: 'Password Hint (optional)',
      hintPlaceholder: 'e.g. My cat name',
      removeWarning: 'Removing 2FA will make your account less secure',
      setSuccess: '2FA enabled successfully',
      changeSuccess: '2FA password changed successfully',
      removeSuccess: '2FA removed successfully',
      errors: {
        alreadyEnabled: '2FA is already enabled',
        notEnabled: '2FA is not enabled',
        invalidPassword: 'Invalid password',
        passwordMismatch: 'Passwords do not match'
      }
    },

    auth: {
      title: 'Add New Account',
      steps: {
        phone: 'Phone',
        code: 'Code',
        password: '2FA',
        success: 'Done'
      },
      phone: {
        title: 'Enter Phone Number',
        description: 'Enter the phone number associated with your Telegram account',
        label: 'Phone Number',
        placeholder: '+1234567890',
        hint: 'Include country code (e.g., +1 for US, +7 for RU)'
      },
      code: {
        title: 'Enter SMS Code',
        description: 'Enter the verification code sent to your phone',
        label: 'Code',
        placeholder: '12345'
      },
      password: {
        title: 'Enter 2FA Password',
        description: 'This account has two-factor authentication enabled',
        label: '2FA Password',
        placeholder: 'Your 2FA password'
      },
      proxy: {
        title: 'Proxy (Recommended)',
        placeholder: 'Select proxy',
        noProxy: 'No proxy (direct connection)'
      },
      success: {
        title: 'Account Added',
        description: 'Your account has been successfully authorized'
      },
      sendCode: 'Send Code',
      verify: 'Verify',
      resendCode: 'Resend Code',
      resendIn: 'Resend in',
      codeSent: 'Verification code sent',
      codeResent: 'Code resent successfully',
      errors: {
        invalidPhone: 'Invalid phone number',
        invalidCode: 'Invalid verification code',
        invalidPassword: 'Invalid 2FA password',
        phoneFlood: 'Too many attempts. Try again later',
        phoneBanned: 'This phone number is banned'
      }
    },

    addAccount: 'Add Account'
  },

  groups: {
    title: 'Groups',
    allAccounts: 'All Accounts',
    create: 'Create Group',
    name: 'Name',
    namePlaceholder: 'Enter group name',
    created: 'Group created',
    deleted: 'Group deleted'
  },

  tags: {
    title: 'Tags',
    create: 'Create Tag',
    name: 'Name',
    namePlaceholder: 'Enter tag name',
    created: 'Tag created',
    deleted: 'Tag deleted'
  },

  proxy: {
    title: 'Proxy',
    addProxy: 'Add Proxy',
    checkAll: 'Check All',
    noProxies: 'No proxies yet',
    auth: 'Auth',
    accounts: 'Accounts',
    lastCheck: 'Last Check',
    deleteConfirm: 'Delete proxy {host}:{port}?',

    addDialog: {
      title: 'Add Proxy',
      type: 'Type',
      host: 'Host',
      port: 'Port',
      username: 'Username',
      password: 'Password',
      bulkImport: 'Bulk Import (one per line)',
      bulkFormat: 'Format: host:port or host:port:user:pass'
    },

    editDialog: {
      title: 'Edit Proxy'
    },

    messages: {
      loadError: 'Failed to load proxies',
      proxyValid: 'Proxy Valid',
      proxyInvalid: 'Proxy Invalid',
      checkFailed: 'Failed to check proxy',
      checking: 'Checking all proxies',
      checkComplete: 'Checked {count} proxies',
      addedCount: 'Added {count} proxies',
      added: 'Proxy added',
      addFailed: 'Failed to add proxy',
      updated: 'Proxy updated',
      updateFailed: 'Failed to update proxy',
      deleted: 'Proxy deleted',
      deleteFailed: 'Failed to delete proxy',
      enterHostPort: 'Please enter host and port'
    }
  },

  settings: {
    title: 'Settings',
    application: 'Application',
    dataLocation: 'Data Location',
    clearAllData: 'Clear All Data',
    clearAllDataDesc: 'Remove all accounts, proxies and tasks',
    change: 'Change',
    clear: 'Clear',
    language: 'Language',
    languageDesc: 'Choose your preferred language',
    theme: 'Theme',
    themeDesc: 'Application color theme',
    themeLight: 'Light',
    themeDark: 'Dark',
    themeSystem: 'System'
  },

  comingSoon: 'Coming in Stage 3',

  autoLikes: {
    createTask: 'Create Task',
    channel: 'Channel',
    channelPlaceholder: '@channel or https://t.me/channel',
    mode: 'Mode',
    modes: {
      single: 'Single Post',
      monitoring: 'Monitor New Posts'
    },
    postId: 'Post ID',
    postIdPlaceholder: 'Post number (empty = latest)',
    reaction: 'Reaction',
    totalReactions: 'Total Reactions',
    minDelay: 'Min Delay',
    maxDelay: 'Max Delay',
    filterByGroup: 'Filter by Group',
    selectAccounts: 'Select Accounts',
    selectAccountsPlaceholder: 'Choose accounts for task',
    available: 'available',
    startTask: 'Create & Start',
    tasks: 'Tasks',
    noTasks: 'No tasks yet',
    progress: 'Progress',
    taskDetails: 'Task Details',
    failed: 'Failed',
    lastError: 'Last Error',
    startedAt: 'Started At',
    completedAt: 'Completed At',
    logs: 'Action Log',
    noLogs: 'No logs yet',
    time: 'Time',
    target: 'Target',
    result: 'Result',
    message: 'Message',
    status: {
      pending: 'pending',
      running: 'running',
      paused: 'paused',
      completed: 'completed',
      failed: 'failed',
      cancelled: 'cancelled'
    },
    errors: {
      channelRequired: 'Please enter a channel',
      accountsRequired: 'Select at least one account'
    },
    messages: {
      taskCreated: 'Task created',
      createFailed: 'Failed to create task',
      taskStarted: 'Task started',
      taskDeleted: 'Task deleted'
    }
  },

  autoComments: {
    createTask: 'Create Task',
    settings: 'Settings',
    templates: 'Templates',
    accounts: 'Accounts',
    channels: 'Channels',
    channelsPlaceholder: 'Enter @channel and press Enter',
    channelsHint: 'Add multiple channels with Enter or comma',
    mode: 'Mode',
    modes: {
      single: 'Single Post',
      monitoring: 'Monitor New Posts'
    },
    rotationMode: 'Account Rotation',
    rotation: {
      random: 'Random',
      roundRobin: 'Round Robin'
    },
    commentsPerAccount: 'Comments Per Account',
    totalComments: 'Total Comments',
    minDelay: 'Min Delay',
    maxDelay: 'Max Delay',
    filterByGroup: 'Filter by Group',
    selectAccounts: 'Select Accounts',
    selectAccountsPlaceholder: 'Choose accounts for task',
    available: 'available',
    selectTemplates: 'Select Templates',
    selectTemplatesPlaceholder: 'Choose comment templates',
    customTemplates: 'Custom Templates',
    customTemplatesPlaceholder: 'Enter comment text',
    createTemplate: 'Create Template',
    loadDefaults: 'Load Defaults',
    templateName: 'Template Name',
    templateNamePlaceholder: 'e.g. Positive Review',
    templateContent: 'Comment Text',
    templateContentPlaceholder: '{Great|Awesome|Nice}! {Very|Super} {useful|interesting}!',
    spintaxHint: 'Use {option1|option2|option3} for random variations',
    preview: 'Preview variations:',
    startTask: 'Create & Start',
    tasks: 'Tasks',
    noTasks: 'No tasks yet',
    progress: 'Progress',
    taskDetails: 'Task Details',
    failed: 'Failed',
    lastError: 'Last Error',
    targetChannels: 'Target Channels',
    noChannels: 'No channels',
    channel: 'Channel',
    title: 'Title',
    sent: 'Sent',
    error: 'Error',
    logs: 'Action Log',
    noLogs: 'No logs yet',
    time: 'Time',
    target: 'Target',
    result: 'Result',
    comment: 'Comment',
    status: {
      pending: 'pending',
      running: 'running',
      paused: 'paused',
      completed: 'completed',
      failed: 'failed',
      cancelled: 'cancelled'
    },
    errors: {
      channelsRequired: 'Add at least one channel',
      templatesRequired: 'Select or add at least one template',
      accountsRequired: 'Select at least one account',
      templateRequired: 'Fill in template name and content'
    },
    messages: {
      taskCreated: 'Task created',
      createFailed: 'Failed to create task',
      taskStarted: 'Task started',
      taskDeleted: 'Task deleted',
      templateCreated: 'Template created',
      templateDeleted: 'Template deleted',
      defaultsLoaded: 'Default templates loaded'
    }
  }
}
