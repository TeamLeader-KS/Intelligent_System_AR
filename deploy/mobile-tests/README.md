# Maestro: локальный APK

Два сценария для установленного `com.example.intelligent_system_ar`. Это заготовки до фактического прогона: наличие YAML не подтверждает прохождение теста или качество CV. Запускать из корня проекта на отдельном тестовом эмуляторе. `clearState: true` удаляет локальную сессию и очередь приложения.

Предусловия: работающий локальный API, учётная запись `pump_engineer`, карточка `pump_demo_001` с заводским номером `DEMO-PUMP-2026-001`, установленный APK и Maestro. Хосту API не нужен внешний интернет после предварительной загрузки образов/моделей. На стандартном Android Emulator адрес хоста обычно `http://10.0.2.2:8001`; при другом сетевом подключении адрес задаётся явно. Сервер должен слушать доступный эмулятору интерфейс.

`smoke.yaml` проверяет вход с ручным адресом и карточку насоса. Проверки точности CV нет. `camera.yaml` повторяет smoke, проходит «Требуют внимания» → «Навести камеру на узел», снимает кадр через камеру, отправляет его и находит комментарий в серверной истории.

Для camera заранее подготовить **в изолированном стенде** компонент насоса с причиной внимания: `DUE`, `APPROACHING`, `INSUFFICIENT_DATA` или наступившим ТО. Стандартные 3500 ч, ресурс 16000 ч и ТО через 500 ч сами по себе такой причины не дают. Не менять рабочую наработку ради теста. Пустая очередь намеренно завершает flow ошибкой.

Перед camera оператор стенда подаёт тестовое изображение в заднюю камеру эмулятора API 30. Конкретный способ задаётся конфигурацией эмулятора; flow не подменяет камеру загрузкой из галереи. Изображение должно быть без QR, иначе приложение может открыть отдельное окно идентификации. Сохранение осмотра не требует найденного дефекта; отсутствие рамок не означает исправность. Flow проверяет транспорт кадра и историю, а не recall/precision, соответствие рамок, нагрев или работу на физическом телефоне.

Пример для Bash, без пароля в истории команд/аргументах Maestro:

```bash
export IV_TEST_SERVER='http://10.0.2.2:8001'
read -r -s -p 'Пароль тестового pump_engineer: ' IV_TEST_PASSWORD
export MAESTRO_IV_TEST_SERVER="$IV_TEST_SERVER"
export MAESTRO_IV_TEST_PASSWORD="$IV_TEST_PASSWORD"
mkdir -p .local-testing/results
maestro test --test-output-dir=.local-testing/results deploy/mobile-tests/smoke.yaml
# После подготовки причины внимания и подачи изображения в камеру:
maestro test --test-output-dir=.local-testing/results deploy/mobile-tests/camera.yaml
unset IV_TEST_PASSWORD MAESTRO_IV_TEST_PASSWORD
```

Maestro автоматически читает переменные shell с префиксом `MAESTRO_`; YAML сопоставляет их с `IV_TEST_SERVER`/`IV_TEST_PASSWORD`. Кнопка показа пароля не нажимается, ручных скриншотов экрана входа нет. Диагностические артефакты Maestro могут содержать введённые данные: хранить `.local-testing/results` локально, не коммитить и не публиковать без проверки. Вызов `takeScreenshot` сохраняет PNG в `takeScreenshot` внутри каталога артефактов каждого запуска под `.local-testing/results`.

Проверены надписи текущего Kotlin UI и документированный синтаксис: [переменные](https://docs.maestro.dev/maestro-flows/flow-control-and-logic/parameters-and-constants), [launchApp](https://docs.maestro.dev/reference/commands-available/launchapp), [runFlow](https://docs.maestro.dev/reference/commands-available/runflow), [селекторы](https://docs.maestro.dev/reference/selectors/core-selectors), [scrollUntilVisible](https://docs.maestro.dev/reference/commands-available/scrolluntilvisible), [артефакты](https://docs.maestro.dev/maestro-flows/workspace-management/test-reports-and-artifacts). Реальный прогон обязан подтвердить Compose-селекторы и прокрутку; успешный запуск нельзя объявлять по одной статической проверке YAML.

Очистка адреса рассчитана на английский системный интерфейс Android 11/API 30: после фокусировки временно вводится многословная строка, затем `longPressOn` по полю с `focused: true` → `Select all` (через `More options`, если пункт скрыт) → `eraseText: 1`. После ввода проверяется полное значение сфокусированного поля. Это очищает сохранённый адрес целиком при любом положении курсора и позволяет обработать изначально пустое поле. Временная строка не отправляется серверу. При другом языке системного меню нужны соответствующие подписи; сценарий остановится до входа, если выделение всего текста не выполнено. Основание: официальный [eraseText / Select All](https://docs.maestro.dev/reference/commands-available/erasetext), [longPressOn](https://docs.maestro.dev/reference/commands-available/longpresson) и [focused selector](https://docs.maestro.dev/reference/selectors/state-selectors). Повторный запуск после этой правки выполняет оператор стенда.
