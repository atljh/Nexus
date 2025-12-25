export default {
  common: {
    save: 'Сохранить',
    cancel: 'Отмена',
    delete: 'Удалить',
    edit: 'Редактировать',
    add: 'Добавить',
    check: 'Проверить',
    import: 'Импорт',
    export: 'Экспорт',
    close: 'Закрыть',
    confirm: 'Подтвердить',
    create: 'Создать',
    confirmation: 'Подтверждение',
    yes: 'Да',
    no: 'Нет',
    loading: 'Загрузка...',
    error: 'Ошибка',
    success: 'Успешно',
    warning: 'Внимание',
    info: 'Информация',
    noData: 'Нет данных',
    actions: 'Действия',
    status: 'Статус',
    type: 'Тип',
    never: 'Никогда',
    optional: 'опционально',
    color: 'Цвет'
  },

  nav: {
    dashboard: 'Главная',
    accounts: 'Аккаунты',
    proxy: 'Прокси',
    autoLikes: 'Авто-лайки',
    autoComments: 'Авто-комментарии',
    settings: 'Настройки'
  },

  sidebar: {
    backendConnected: 'Сервер подключен',
    backendDisconnected: 'Сервер отключен'
  },

  dashboard: {
    title: 'Главная',
    accounts: 'Аккаунты',
    accountsActive: '{count} активных',
    proxies: 'Прокси',
    proxiesWorking: '{count} рабочих',
    likesToday: 'Лайков сегодня',
    tasksCount: '{count} задач',
    commentsToday: 'Комментариев сегодня',
    quickActions: 'Быстрые действия',
    addAccount: 'Добавить аккаунт',
    addProxy: 'Добавить прокси',
    newLikeTask: 'Новая задача лайков'
  },

  accounts: {
    title: 'Аккаунты',
    import: 'Импорт',
    checkAll: 'Проверить все',
    importAccounts: 'Импортировать аккаунты',
    noAccounts: 'Аккаунтов пока нет',
    account: 'Аккаунт',
    proxy: 'Прокси',
    noProxy: 'Без прокси',
    group: 'Группа',
    tags: 'Теги',
    deleteConfirm: 'Удалить аккаунт @{name}?',

    importDialog: {
      title: 'Импорт аккаунтов',
      useProxy: 'Использовать прокси',
      selectProxy: 'Выберите прокси',
      noProxyDirect: 'Без прокси (прямое подключение)'
    },

    tdata: {
      title: 'tdata',
      description: 'Импорт из Telegram Desktop (папка tdata в .zip)',
      step1: 'Закройте Telegram Desktop',
      step2: 'Найдите папку tdata в данных приложения',
      step3: 'Создайте .zip архив папки tdata',
      step4: 'Загрузите .zip файл ниже',
      selectFile: 'Выбрать tdata.zip'
    },

    jsonSession: {
      title: 'JSON сессия',
      description: 'Импорт сессий Telethon/Pyrogram (формат .json)',
      format: 'JSON должен содержать:',
      selectFile: 'Выбрать session.json'
    },

    sessionString: {
      title: 'Строка сессии',
      description: 'Вставьте строку сессии Telethon напрямую',
      label: 'Строка сессии',
      placeholder: '1BQANOTEuMTA4L...',
      importButton: 'Импортировать сессию'
    },

    status: {
      valid: 'активен',
      invalid: 'недействителен',
      banned: 'забанен',
      spamblock: 'спам-блок',
      session_expired: 'сессия истекла',
      checking: 'проверка',
      unchecked: 'не проверен'
    },

    messages: {
      loadError: 'Не удалось загрузить аккаунты',
      importSuccess: 'Аккаунт успешно импортирован',
      importedCount: 'Импортировано {count} аккаунтов',
      importFailed: 'Ошибка импорта',
      importPartialFail: '{count} аккаунтов не удалось импортировать',
      enterSessionString: 'Введите строку сессии',
      accountValid: 'Аккаунт активен',
      accountWorking: '@{name} работает',
      accountInvalid: 'Аккаунт недействителен',
      sessionNotValid: 'Сессия недействительна',
      checkFailed: 'Ошибка проверки',
      checkingAll: 'Проверка всех аккаунтов в фоне',
      deleted: 'Аккаунт успешно удален',
      deleteFailed: 'Не удалось удалить аккаунт',
      bulkSuccess: 'Действие выполнено для {count} аккаунтов'
    },

    allStatuses: 'Все статусы',
    searchPlaceholder: 'Поиск по username, телефону...',
    filterByStatus: 'Фильтр по статусу',
    selected: 'Выбрано: {count}',
    bulkDeleteConfirm: 'Удалить {count} аккаунтов?',

    bulk: {
      actions: 'Действия',
      check: 'Проверить',
      setProxy: 'Назначить прокси',
      noProxy: 'Без прокси',
      setGroup: 'Назначить группу',
      noGroup: 'Без группы',
      delete: 'Удалить'
    }
  },

  groups: {
    title: 'Группы',
    allAccounts: 'Все аккаунты',
    create: 'Создать группу',
    name: 'Название',
    namePlaceholder: 'Введите название группы',
    created: 'Группа создана',
    deleted: 'Группа удалена'
  },

  tags: {
    title: 'Теги',
    create: 'Создать тег',
    name: 'Название',
    namePlaceholder: 'Введите название тега',
    created: 'Тег создан',
    deleted: 'Тег удален'
  },

  proxy: {
    title: 'Прокси',
    addProxy: 'Добавить прокси',
    checkAll: 'Проверить все',
    noProxies: 'Прокси пока нет',
    auth: 'Авторизация',
    accounts: 'Аккаунты',
    lastCheck: 'Последняя проверка',
    deleteConfirm: 'Удалить прокси {host}:{port}?',

    addDialog: {
      title: 'Добавить прокси',
      type: 'Тип',
      host: 'Хост',
      port: 'Порт',
      username: 'Логин',
      password: 'Пароль',
      bulkImport: 'Массовый импорт (по одному на строку)',
      bulkFormat: 'Формат: host:port или host:port:user:pass'
    },

    editDialog: {
      title: 'Редактировать прокси'
    },

    messages: {
      loadError: 'Не удалось загрузить прокси',
      proxyValid: 'Прокси работает',
      proxyInvalid: 'Прокси не работает',
      checkFailed: 'Не удалось проверить прокси',
      checking: 'Проверка всех прокси',
      checkComplete: 'Проверено {count} прокси',
      addedCount: 'Добавлено {count} прокси',
      added: 'Прокси добавлен',
      addFailed: 'Не удалось добавить прокси',
      updated: 'Прокси обновлен',
      updateFailed: 'Не удалось обновить прокси',
      deleted: 'Прокси удален',
      deleteFailed: 'Не удалось удалить прокси',
      enterHostPort: 'Введите хост и порт'
    }
  },

  settings: {
    title: 'Настройки',
    application: 'Приложение',
    dataLocation: 'Расположение данных',
    clearAllData: 'Очистить все данные',
    clearAllDataDesc: 'Удалить все аккаунты, прокси и задачи',
    change: 'Изменить',
    clear: 'Очистить',
    language: 'Язык',
    languageDesc: 'Выберите предпочитаемый язык',
    theme: 'Тема',
    themeDesc: 'Цветовая тема приложения',
    themeLight: 'Светлая',
    themeDark: 'Темная',
    themeSystem: 'Системная'
  },

  comingSoon: 'Появится в Stage 3'
}
