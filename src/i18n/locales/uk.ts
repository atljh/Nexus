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
    color: 'Колір',
    back: 'Назад',
    done: 'Готово'
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
    deleteConfirm: "Видалити акаунт {'@'}{name}?",

    importDialog: {
      title: 'Імпорт акаунтів',
      useProxy: 'Проксі',
      selectProxy: 'Оберіть проксі',
      noProxyDirect: 'Без проксі (пряме підключення)',
      proxyRequired: 'Проксі обов\'язковий для імпорту',
      noWorkingProxies: 'Немає робочих проксі. Спочатку додайте і перевірте проксі.',
      addNewProxy: 'Додати проксі',
      addAndCheck: 'Додати і перевірити',
      proxyString: 'Рядок',
      proxyForm: 'Форма',
      proxyStringLabel: 'Рядок проксі',
      proxyStringPlaceholder: 'host:port або host:port:user:pass',
      proxyStringPlaceholderFull: 'socks5://user:pass@host:port',
      proxyStringFormats: 'Формати: socks5://user:pass@host:port, user:pass@host:port, host:port:user:pass'
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

    sessionJson: {
      title: 'Session + JSON',
      description: 'Імпорт .session файлів з відповідними .json файлами метаданих',
      sessionFiles: 'Session файли',
      jsonFiles: 'JSON файли',
      selectSessionFiles: 'Обрати .session файли',
      selectJsonFiles: 'Обрати .json файли',
      filesSelected: '{count} файлів обрано',
      importButton: 'Імпортувати пари'
    },

    dropZone: {
      dropTitle: 'Перетягніть файли сюди або натисніть',
      dropHint: 'Оберіть папку з кількома tdata для масового імпорту',
      selectedFiles: 'Обрані файли',
      importButton: 'Імпортувати',
      orPasteSession: 'або вставте рядок сесії',
      clearFiles: 'Очистити файли'
    },

    batchCheck: {
      title: 'Масова перевірка акаунтів',
      description: 'Перевірка декількох акаунтів паралельно',
      checkSpamblock: 'Перевірити статус спам-блоку',
      spamblockWarning: 'Перевірка спам-блоку вимагає надсилання повідомлень до @SpamBot',
      maxConcurrent: 'Макс. паралельних перевірок',
      startCheck: 'Почати перевірку',
      progress: 'Перевірка: {current}/{total}',
      complete: 'Перевірку завершено: {valid} активних, {invalid} недійсних'
    },

    status: {
      valid: 'активний',
      invalid: 'недійсний',
      banned: 'забанений',
      spamblock: 'спам-блок',
      frozen: 'заморожений',
      session_expired: 'сесія закінчилась',
      checking: 'перевірка',
      unchecked: 'не перевірено',
      muted: 'заглушений',
      deactivated: 'деактивований',
      needs_reauth: 'потребує авторизації',
      connection_failed: 'помилка з\'єднання'
    },

    messages: {
      loadError: 'Не вдалося завантажити акаунти',
      importSuccess: 'Акаунт успішно імпортовано',
      importedCount: 'Імпортовано {count} акаунтів',
      importFailed: 'Помилка імпорту',
      importPartialFail: '{count} акаунтів не вдалося імпортувати',
      enterSessionString: 'Введіть рядок сесії',
      accountValid: 'Акаунт активний',
      accountWorking: "{'@'}{name} працює",
      accountInvalid: 'Акаунт недійсний',
      sessionNotValid: 'Сесія недійсна',
      checkFailed: 'Помилка перевірки',
      checkingAll: 'Перевірка всіх акаунтів у фоні',
      deleted: 'Акаунт успішно видалено',
      deleteFailed: 'Не вдалося видалити акаунт',
      bulkSuccess: 'Дію виконано для {count} акаунтів',
      selectAccountsFirst: 'Спочатку оберіть акаунти',
      selectSessionFiles: 'Оберіть session файли',
      selectJsonFiles: 'Оберіть JSON файли',
      batchCheckComplete: 'Перевірку завершено: {valid} активних, {invalid} невдалих',
      proxyCheckComplete: 'Перевірка проксі: {working}/{total} працюють',
      noProxiesToCheck: 'Немає проксі у обраних акаунтів',
      bulk2FAComplete: '2FA встановлено: {succeeded} успішно, {failed} невдало',
      sessionJsonImported: 'Імпортовано {count} акаунтів з пар session+json',
      sessionJsonErrors: '{count} файлів не вдалося імпортувати'
    },

    allStatuses: 'Всі статуси',
    searchPlaceholder: 'Пошук за username, телефоном, проксі...',
    filterByStatus: 'Фільтр за статусом',
    filterByProxy: 'Фільтр за проксі',
    searchProxy: 'Пошук проксі...',
    selected: 'Обрано: {count}',
    bulkDeleteConfirm: 'Видалити {count} акаунтів?',

    bulk: {
      actions: 'Ще',
      check: 'Перевірити',
      checkAccounts: 'Перевірити акаунти',
      checkProxies: 'Перевірити проксі',
      set2FA: 'Встановити 2FA',
      set2FATitle: 'Масове встановлення 2FA',
      set2FADescription: 'Встановити 2FA пароль для {count} обраних акаунтів',
      set2FANote: 'Пароль буде збережено і його можна переглянути в таблиці. Акаунти з вже встановленим 2FA буде пропущено.',
      setProxy: 'Призначити проксі',
      noProxy: 'Без проксі',
      setGroup: 'Призначити групу',
      noGroup: 'Без групи',
      delete: 'Видалити',
      clearSelection: 'Скасувати вибір'
    },

    importFlow: {
      parsing: 'Обробка файлів...',
      noAccountsParsed: 'Не вдалося розпарсити жодного акаунту',
      orSelectTdata: 'або оберіть папку tdata',
      selectTdataFolder: 'Обрати папку tdata',
      selectTdataFolders: 'Папка з tdata',
      selectFiles: 'Файли (.session, .json)',
      notTdataFolder: 'Папки tdata не знайдено',
      tdataFound: 'Знайдено tdata',
      tdataFoundCount: 'Знайдено {count} папок tdata',
      folder: 'папка',
      assignProxyFirst: 'Спочатку призначте проксі всім акаунтам',
      checkProxiesFirst: 'Спочатку перевірте проксі',
      assignProxyToAll: 'Призначити проксі всім',
      applyToAll: 'Застосувати',
      selectProxy: 'Оберіть проксі',
      verifyAll: 'Перевірити всі',
      verifyComplete: 'Перевірку завершено: {valid} активних, {invalid} невалідних',
      noValidAccounts: 'Немає валідних акаунтів для збереження',
      saveValid: 'Зберегти ({count})',
      savedCount: 'Збережено {count} акаунтів',
      sourceFile: 'Файл',
      unknown: 'Невідомо',
      total: 'Всього',
      valid: 'Активні',
      invalid: 'Невалідні',
      pending: 'Очікують',
      error: 'Помилка',
      orDragHere: 'або перетягніть файли сюди',
      format: 'Формат',
      phone: 'Телефон',
      accountStatus: 'Статус акаунту',
      proxyStatus: 'Статус проксі',
      checkProxies: 'Перевірити проксі',
      checkAccounts: 'Перевірити акаунти',
      saveToApp: 'Зберегти',
      clearAll: 'Очистити все',
      noAccountsYet: 'Акаунтів поки немає',
      addProxy: 'Додати проксі',
      proxyString: 'Рядок проксі',
      proxyStringPlaceholder: 'socks5://user:pass@host:port',
      invalidProxyFormat: 'Невірний формат проксі',
      proxyAdded: 'Проксі додано',
      status: {
        pending: 'очікує',
        verifying: 'перевірка...',
        valid: 'активний',
        invalid: 'невалідний'
      }
    },

    twoFA: {
      title: 'Управління 2FA',
      status: 'Статус 2FA',
      checking: 'Перевірка статусу 2FA...',
      enabled: '2FA увімкнено',
      disabled: '2FA вимкнено',
      hint: 'Підказка паролю',
      set: 'Встановити 2FA',
      change: 'Змінити 2FA',
      remove: 'Видалити 2FA',
      password: 'Пароль',
      enterPassword: 'Введіть пароль',
      confirmPassword: 'Підтвердіть пароль',
      confirmPasswordPlaceholder: 'Підтвердіть пароль',
      currentPassword: 'Поточний пароль',
      enterCurrentPassword: 'Введіть поточний пароль',
      newPassword: 'Новий пароль',
      enterNewPassword: 'Введіть новий пароль',
      confirmNewPassword: 'Підтвердіть новий пароль',
      confirmNewPasswordPlaceholder: 'Підтвердіть новий пароль',
      newHint: 'Нова підказка',
      passwordHint: 'Підказка паролю (опціонально)',
      hintPlaceholder: 'Напр. Ім\'я кота',
      removeWarning: 'Видалення 2FA зробить ваш акаунт менш захищеним',
      setSuccess: '2FA успішно увімкнено',
      changeSuccess: 'Пароль 2FA успішно змінено',
      removeSuccess: '2FA успішно видалено',
      errors: {
        alreadyEnabled: '2FA вже увімкнено',
        notEnabled: '2FA не увімкнено',
        invalidPassword: 'Невірний пароль',
        passwordMismatch: 'Паролі не співпадають'
      }
    },

    auth: {
      title: 'Додати новий акаунт',
      steps: {
        phone: 'Телефон',
        code: 'Код',
        password: '2FA',
        success: 'Готово'
      },
      phone: {
        title: 'Введіть номер телефону',
        description: 'Введіть номер телефону, пов\'язаний з вашим Telegram акаунтом',
        label: 'Номер телефону',
        placeholder: '+380123456789',
        hint: 'Включаючи код країни (напр. +380 для UA, +7 для RU)'
      },
      code: {
        title: 'Введіть SMS код',
        description: 'Введіть код підтвердження, надісланий на ваш телефон',
        label: 'Код',
        placeholder: '12345'
      },
      password: {
        title: 'Введіть пароль 2FA',
        description: 'Цей акаунт має увімкнену двофакторну автентифікацію',
        label: 'Пароль 2FA',
        placeholder: 'Ваш пароль 2FA'
      },
      proxy: {
        title: 'Проксі (рекомендовано)',
        placeholder: 'Оберіть проксі',
        noProxy: 'Без проксі (пряме з\'єднання)'
      },
      success: {
        title: 'Акаунт додано',
        description: 'Ваш акаунт успішно авторизовано'
      },
      sendCode: 'Надіслати код',
      verify: 'Підтвердити',
      resendCode: 'Надіслати знову',
      resendIn: 'Повторити через',
      codeSent: 'Код підтвердження надіслано',
      codeResent: 'Код успішно надіслано повторно',
      errors: {
        invalidPhone: 'Невірний номер телефону',
        invalidCode: 'Невірний код підтвердження',
        invalidPassword: 'Невірний пароль 2FA',
        phoneFlood: 'Забагато спроб. Спробуйте пізніше',
        phoneBanned: 'Цей номер телефону заблоковано'
      }
    },

    addAccount: 'Додати акаунт',

    errors: {
      banned: 'Акаунт забанений',
      deactivated: 'Акаунт деактивовано',
      restricted: 'Акаунт обмежено',
      frozen: 'Акаунт заморожено',
      authKeyDuplicated: 'Сесія використовується на іншому пристрої',
      sessionExpired: 'Сесія закінчилася',
      sessionRevoked: 'Сесію відкликано',
      floodWait: 'Забагато запитів, зачекайте',
      floodWaitSeconds: 'Забагато запитів, зачекайте {seconds} сек',
      connectionFailed: 'Помилка підключення',
      timeout: 'Час очікування вичерпано'
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

    status: {
      unchecked: 'Не перевірено',
      checking: 'Перевірка...',
      pending: 'Очікує',
      working: 'Працює',
      slow: 'Повільний',
      very_slow: 'Дуже повільний',
      not_working: 'Не працює',
      timeout: 'Таймаут',
      duplicate: 'Дублікат'
    },

    addDialog: {
      title: 'Додати проксі',
      type: 'Тип',
      host: 'Хост',
      port: 'Порт',
      username: 'Логін',
      password: 'Пароль',
      stringMode: 'Рядок',
      formMode: 'Форма',
      proxyString: 'Рядок проксі',
      proxyStringPlaceholder: 'socks5://user:pass@host:port',
      proxyStringFormats: 'Формати: socks5://user:pass@host:port, user:pass@host:port, host:port:user:pass',
      bulkImport: 'Масовий імпорт (по одному на рядок)',
      bulkHint: 'Підтримуються всі формати. Дублікати будуть пропущені.',
      bulkPlaceholder: 'socks5://user:pass@192.168.1.1:1080\n192.168.1.2:1080:user:pass',
      bulkFormat: 'Формат: host:port або host:port:user:pass',
      checkAndAdd: 'Перевірити і додати',
      checkResults: 'Результати перевірки',
      working: 'працюють',
      selected: 'обрано',
      selectWorking: 'Тільки робочі',
      selectAll: 'Обрати всі',
      deselectAll: 'Зняти всі',
      addSelected: 'Додати обрані ({count})'
    },

    editDialog: {
      title: 'Редагувати проксі',
      applyString: 'Застосувати'
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
      enterHostPort: 'Введіть хост і порт',
      invalidProxyFormat: 'Невірний формат проксі. Приклад: socks5://user:pass@host:port',
      duplicateProxy: 'Такий проксі вже існує',
      duplicatesSkipped: 'Пропущено дублікатів: {count}',
      allDuplicates: 'Всі проксі вже існують',
      selectProxies: 'Оберіть проксі для додавання',
      proxyParsed: 'Рядок розпізнано, перевірте дані'
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
  },

  webviewer: {
    title: 'Telegram WebK',
    loading: 'Завантаження...',
    initializing: 'Ініціалізація Telegram Web...',
    connected: 'Підключено',
    disconnected: 'Відключено',
    injected: 'Сесію інжектовано',
    error: 'Помилка',
    reload: 'Перезавантажити',
    refreshSession: 'Оновити сесію',
    cannotOpen: 'Неможливо відкрити цей акаунт',
    requirementsNotMet: 'Вимоги до акаунту не виконані:',
    noTelegramId: 'Акаунт не має Telegram ID (не верифіковано)',
    noProxy: 'Проксі не призначено акаунту',
    notValid: 'Статус акаунту не валідний',
    openInWebK: 'Відкрити у WebK'
  },

  errors: {
    // Мережеві помилки
    NETWORK_ERROR: 'Помилка з\'єднання з мережею. Перевірте інтернет-з\'єднання.',
    TIMEOUT: 'Час очікування запиту вичерпано. Спробуйте ще раз.',
    CONNECTION_REFUSED: 'Неможливо підключитися до сервера. Переконайтеся, що backend запущено.',

    // Помилки авторизації
    UNAUTHORIZED: 'Потрібна авторизація. Увійдіть в систему.',
    SESSION_EXPIRED: 'Сесія закінчилась. Підключіть акаунт повторно.',
    INVALID_CREDENTIALS: 'Невірні облікові дані.',

    // Помилки акаунтів
    ACCOUNT_NOT_FOUND: 'Акаунт не знайдено.',
    ACCOUNT_BANNED: 'Цей акаунт заблоковано.',
    ACCOUNT_SPAMBLOCK: 'На цей акаунт накладено спам-обмеження.',
    INVALID_SESSION: 'Невірна сесія. Імпортуйте акаунт повторно.',
    PROXY_REQUIRED: 'Для цієї операції потрібен проксі.',

    // Помилки проксі
    PROXY_NOT_FOUND: 'Проксі не знайдено.',
    PROXY_NOT_WORKING: 'Проксі не працює.',
    PROXY_TIMEOUT: 'Час очікування проксі вичерпано.',

    // Помилки імпорту
    IMPORT_FAILED: 'Не вдалося імпортувати акаунт.',
    INVALID_FILE_FORMAT: 'Невірний формат файлу.',
    NO_VALID_SESSIONS: 'У файлі не знайдено валідних сесій.',

    // Помилки 2FA
    TWO_FA_REQUIRED: 'Потрібна двофакторна автентифікація.',
    TWO_FA_INVALID: 'Невірний пароль 2FA.',

    // Загальні помилки
    VALIDATION_ERROR: 'Перевірте введені дані.',
    SERVER_ERROR: 'Помилка сервера. Спробуйте пізніше.',
    UNKNOWN: 'Сталася непередбачена помилка.',

    // Заголовки
    summary: {
      network: 'Помилка з\'єднання',
      auth: 'Помилка авторизації',
      validation: 'Помилка валідації',
      default: 'Помилка'
    }
  }
}
