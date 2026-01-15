export default {
  common: {
    save: 'Зберегти',
    cancel: 'Скасувати',
    delete: 'Видалити',
    edit: 'Редагувати',
    add: 'Додати',
    check: 'Перевірити',
    import: 'Імпорт',
    export: 'Експорт',
    close: 'Закрити',
    confirm: 'Підтвердити',
    create: 'Створити',
    confirmation: 'Підтвердження',
    yes: 'Так',
    no: 'Ні',
    loading: 'Завантаження...',
    error: 'Помилка',
    success: 'Успішно',
    warning: 'Увага',
    info: 'Інформація',
    noData: 'Немає даних',
    actions: 'Дії',
    status: 'Статус',
    type: 'Тип',
    never: 'Ніколи',
    optional: 'опціонально',
    color: 'Колір'
  },

  nav: {
    dashboard: 'Головна',
    accounts: 'Акаунти',
    proxy: 'Проксі',
    autoLikes: 'Авто-лайки',
    autoComments: 'Авто-коментарі',
    settings: 'Налаштування'
  },

  sidebar: {
    backendConnected: 'Сервер підключено',
    backendDisconnected: 'Сервер відключено'
  },

  dashboard: {
    title: 'Головна',
    accounts: 'Акаунти',
    accountsActive: '{count} активних',
    proxies: 'Проксі',
    proxiesWorking: '{count} робочих',
    likesToday: 'Лайків сьогодні',
    tasksCount: '{count} завдань',
    commentsToday: 'Коментарів сьогодні',
    quickActions: 'Швидкі дії',
    addAccount: 'Додати акаунт',
    addProxy: 'Додати проксі',
    newLikeTask: 'Нове завдання лайків'
  },

  accounts: {
    title: 'Акаунти',
    import: 'Імпорт',
    checkAll: 'Перевірити всі',
    importAccounts: 'Імпортувати акаунти',
    noAccounts: 'Акаунтів поки немає',
    account: 'Акаунт',
    proxy: 'Проксі',
    noProxy: 'Без проксі',
    group: 'Група',
    tags: 'Теги',
    deleteConfirm: 'Видалити акаунт @{name}?',

    importDialog: {
      title: 'Імпорт акаунтів',
      useProxy: 'Використовувати проксі',
      selectProxy: 'Оберіть проксі',
      noProxyDirect: 'Без проксі (пряме підключення)'
    },

    tdata: {
      title: 'tdata',
      description: 'Імпорт з Telegram Desktop (папка tdata в .zip)',
      step1: 'Закрийте Telegram Desktop',
      step2: 'Знайдіть папку tdata в даних програми',
      step3: 'Створіть .zip архів папки tdata',
      step4: 'Завантажте .zip файл нижче',
      selectFile: 'Обрати tdata.zip'
    },

    jsonSession: {
      title: 'JSON сесія',
      description: 'Імпорт сесій Telethon/Pyrogram (формат .json)',
      format: 'JSON повинен містити:',
      selectFile: 'Обрати session.json'
    },

    sessionString: {
      title: 'Рядок сесії',
      description: 'Вставте рядок сесії Telethon напряму',
      label: 'Рядок сесії',
      placeholder: '1BQANOTEuMTA4L...',
      importButton: 'Імпортувати сесію'
    },

    status: {
      valid: 'активний',
      invalid: 'недійсний',
      banned: 'забанений',
      spamblock: 'спам-блок',
      session_expired: 'сесія закінчилась',
      checking: 'перевірка',
      unchecked: 'не перевірено'
    },

    messages: {
      loadError: 'Не вдалося завантажити акаунти',
      importSuccess: 'Акаунт успішно імпортовано',
      importedCount: 'Імпортовано {count} акаунтів',
      importFailed: 'Помилка імпорту',
      importPartialFail: '{count} акаунтів не вдалося імпортувати',
      enterSessionString: 'Введіть рядок сесії',
      accountValid: 'Акаунт активний',
      accountWorking: '@{name} працює',
      accountInvalid: 'Акаунт недійсний',
      sessionNotValid: 'Сесія недійсна',
      checkFailed: 'Помилка перевірки',
      checkingAll: 'Перевірка всіх акаунтів у фоні',
      deleted: 'Акаунт успішно видалено',
      deleteFailed: 'Не вдалося видалити акаунт',
      bulkSuccess: 'Дію виконано для {count} акаунтів'
    },

    allStatuses: 'Всі статуси',
    searchPlaceholder: 'Пошук за username, телефоном...',
    filterByStatus: 'Фільтр за статусом',
    selected: 'Обрано: {count}',
    bulkDeleteConfirm: 'Видалити {count} акаунтів?',

    bulk: {
      actions: 'Дії',
      check: 'Перевірити',
      setProxy: 'Призначити проксі',
      noProxy: 'Без проксі',
      setGroup: 'Призначити групу',
      noGroup: 'Без групи',
      delete: 'Видалити'
    }
  },

  groups: {
    title: 'Групи',
    allAccounts: 'Всі акаунти',
    create: 'Створити групу',
    name: 'Назва',
    namePlaceholder: 'Введіть назву групи',
    created: 'Групу створено',
    deleted: 'Групу видалено'
  },

  tags: {
    title: 'Теги',
    create: 'Створити тег',
    name: 'Назва',
    namePlaceholder: 'Введіть назву тегу',
    created: 'Тег створено',
    deleted: 'Тег видалено'
  },

  proxy: {
    title: 'Проксі',
    addProxy: 'Додати проксі',
    checkAll: 'Перевірити всі',
    noProxies: 'Проксі поки немає',
    auth: 'Авторизація',
    accounts: 'Акаунти',
    lastCheck: 'Остання перевірка',
    deleteConfirm: 'Видалити проксі {host}:{port}?',

    addDialog: {
      title: 'Додати проксі',
      type: 'Тип',
      host: 'Хост',
      port: 'Порт',
      username: 'Логін',
      password: 'Пароль',
      bulkImport: 'Масовий імпорт (по одному на рядок)',
      bulkFormat: 'Формат: host:port або host:port:user:pass'
    },

    editDialog: {
      title: 'Редагувати проксі'
    },

    messages: {
      loadError: 'Не вдалося завантажити проксі',
      proxyValid: 'Проксі працює',
      proxyInvalid: 'Проксі не працює',
      checkFailed: 'Не вдалося перевірити проксі',
      checking: 'Перевірка всіх проксі',
      checkComplete: 'Перевірено {count} проксі',
      addedCount: 'Додано {count} проксі',
      added: 'Проксі додано',
      addFailed: 'Не вдалося додати проксі',
      updated: 'Проксі оновлено',
      updateFailed: 'Не вдалося оновити проксі',
      deleted: 'Проксі видалено',
      deleteFailed: 'Не вдалося видалити проксі',
      enterHostPort: 'Введіть хост і порт'
    }
  },

  settings: {
    title: 'Налаштування',
    application: 'Програма',
    dataLocation: 'Розташування даних',
    clearAllData: 'Очистити всі дані',
    clearAllDataDesc: 'Видалити всі акаунти, проксі та завдання',
    change: 'Змінити',
    clear: 'Очистити',
    language: 'Мова',
    languageDesc: 'Оберіть бажану мову',
    theme: 'Тема',
    themeDesc: 'Кольорова тема програми',
    themeLight: 'Світла',
    themeDark: 'Темна',
    themeSystem: 'Системна'
  },

  comingSoon: 'Скоро буде',

  autoLikes: {
    createTask: 'Створити завдання',
    channel: 'Канал',
    channelPlaceholder: '@channel або https://t.me/channel',
    mode: 'Режим',
    modes: {
      single: 'Один пост',
      monitoring: 'Моніторинг нових'
    },
    postId: 'ID поста',
    postIdPlaceholder: 'Номер поста (порожньо = останній)',
    reaction: 'Реакція',
    totalReactions: 'Кількість реакцій',
    minDelay: 'Мін. затримка',
    maxDelay: 'Макс. затримка',
    filterByGroup: 'Фільтр за групою',
    selectAccounts: 'Оберіть акаунти',
    selectAccountsPlaceholder: 'Оберіть акаунти для завдання',
    available: 'доступно',
    startTask: 'Створити та запустити',
    tasks: 'Завдання',
    noTasks: 'Немає завдань',
    progress: 'Прогрес',
    taskDetails: 'Деталі завдання',
    failed: 'Невдалих',
    lastError: 'Остання помилка',
    startedAt: 'Початок',
    completedAt: 'Завершення',
    logs: 'Журнал дій',
    noLogs: 'Немає записів',
    time: 'Час',
    target: 'Ціль',
    result: 'Результат',
    message: 'Повідомлення',
    status: {
      pending: 'очікує',
      running: 'виконується',
      paused: 'пауза',
      completed: 'завершено',
      failed: 'помилка',
      cancelled: 'скасовано'
    },
    errors: {
      channelRequired: 'Вкажіть канал',
      accountsRequired: 'Оберіть хоча б один акаунт'
    },
    messages: {
      taskCreated: 'Завдання створено',
      createFailed: 'Не вдалося створити завдання',
      taskStarted: 'Завдання запущено',
      taskDeleted: 'Завдання видалено'
    }
  },

  autoComments: {
    createTask: 'Створити завдання',
    settings: 'Налаштування',
    templates: 'Шаблони',
    accounts: 'Акаунти',
    channels: 'Канали',
    channelsPlaceholder: 'Введіть @channel і натисніть Enter',
    channelsHint: 'Додайте кілька каналів через Enter або кому',
    mode: 'Режим',
    modes: {
      single: 'Один пост',
      monitoring: 'Моніторинг нових'
    },
    rotationMode: 'Ротація акаунтів',
    rotation: {
      random: 'Випадкова',
      roundRobin: 'По черзі'
    },
    commentsPerAccount: 'Коментарів на акаунт',
    totalComments: 'Всього коментарів',
    minDelay: 'Мін. затримка',
    maxDelay: 'Макс. затримка',
    filterByGroup: 'Фільтр за групою',
    selectAccounts: 'Оберіть акаунти',
    selectAccountsPlaceholder: 'Оберіть акаунти для завдання',
    available: 'доступно',
    selectTemplates: 'Оберіть шаблони',
    selectTemplatesPlaceholder: 'Оберіть шаблони коментарів',
    customTemplates: 'Свої шаблони',
    customTemplatesPlaceholder: 'Введіть текст коментаря',
    createTemplate: 'Створити шаблон',
    loadDefaults: 'Завантажити стандартні',
    templateName: 'Назва шаблону',
    templateNamePlaceholder: 'Наприклад: Позитивний відгук',
    templateContent: 'Текст коментаря',
    templateContentPlaceholder: '{Чудово|Круто|Клас}! {Дуже|Супер} {корисно|цікаво}!',
    spintaxHint: 'Використовуйте {варіант1|варіант2|варіант3} для випадкових варіацій',
    preview: 'Попередній перегляд:',
    startTask: 'Створити та запустити',
    tasks: 'Завдання',
    noTasks: 'Немає завдань',
    progress: 'Прогрес',
    taskDetails: 'Деталі завдання',
    failed: 'Невдалих',
    lastError: 'Остання помилка',
    targetChannels: 'Цільові канали',
    noChannels: 'Немає каналів',
    channel: 'Канал',
    title: 'Назва',
    sent: 'Надіслано',
    error: 'Помилка',
    logs: 'Журнал дій',
    noLogs: 'Немає записів',
    time: 'Час',
    target: 'Ціль',
    result: 'Результат',
    comment: 'Коментар',
    status: {
      pending: 'очікує',
      running: 'виконується',
      paused: 'пауза',
      completed: 'завершено',
      failed: 'помилка',
      cancelled: 'скасовано'
    },
    errors: {
      channelsRequired: 'Додайте хоча б один канал',
      templatesRequired: 'Оберіть або додайте хоча б один шаблон',
      accountsRequired: 'Оберіть хоча б один акаунт',
      templateRequired: 'Заповніть назву та текст шаблону'
    },
    messages: {
      taskCreated: 'Завдання створено',
      createFailed: 'Не вдалося створити завдання',
      taskStarted: 'Завдання запущено',
      taskDeleted: 'Завдання видалено',
      templateCreated: 'Шаблон створено',
      templateDeleted: 'Шаблон видалено',
      defaultsLoaded: 'Стандартні шаблони завантажено'
    }
  }
}
