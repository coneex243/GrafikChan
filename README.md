# GrafikChan 🕸️

**GrafikChan** — Telegram-бот для автоматического анализа структурированных текстовых данных / досье и построения интерактивных графов связей (OSINT network graph) в киберпанк/neon стилистике.

---

## 🌟 Возможности

- **Анализ текста и документов:** Принимает текстовые сообщения, а также файлы `.txt` и `.pdf`.
- **Автоматический парсинг сущностей:**
  - Коллекции / базы утечек (`_collection: ...`)
  - ФИО и имена (`fio`, `name`, `fullname`)
  - Номера телефонов (`phone`, `phone2`, `phonemobile`)
  - Электронная почта (`email`, `email2`)
  - Адреса (`address`, `reg_address`, `placelife` и др.)
  - Документы и идентификаторы (`passport`, `snils`, `inn`)
  - Прочие произвольные поля
- **Построение графа связей:**
  - Центральный узел сущности (Person) с лучевыми связями к атрибутам.
  - Цветовая дифференциация по типу данных.
  - Подпись ребер источником (коллекцией данных).
  - Автоматическая кластеризация сообществ (Greedy Modularity Communities) для плотных графов (>20 узлов).
- **Интерактивный HTML-отчет (vis.js):**
  - Темная неоновая тема (шрифт Orbitron, эффекты свечения).
  - Поддержка зума, перемещения узлов, физической симуляции (forceAtlas2Based).
  - Боковая панель со сводкой информации и статистикой.

---

## 🚀 Установка и запуск

### 1. Клонирование репозитория

```bash
git clone https://github.com/coneex243/GrafikChan.git
cd GrafikChan
```

### 2. Установка зависимостей

Рекомендуется использовать виртуальное окружение:

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Настройка переменных окружения

Скопируйте пример файла конфигурации:

```bash
cp .env.example .env
```

Откройте `.env` и укажите ваш токен Telegram-бота:

```env
TELEGRAM_BOT_TOKEN=ваш_токен_от_BotFather
```

### 4. Запуск бота

```bash
python GrafikChan.py
```

---

## 📋 Пример формата данных

Бот понимает ключ-значение через `:` или `=` и разделение по коллекциям:

```text
_collection: Telegram Leaks
fio: Иванов Иван Иванович
phone: +79991234567
email: ivan@example.com
address: г. Москва, ул. Примерная, д. 1
snils: 123-456-789 00
```

---

## 🛠️ Стек технологий

- Python 3.10+
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- [NetworkX](https://networkx.org/)
- [PyPDF2](https://pypdf2.readthedocs.io/)
- [vis.js Network](https://visjs.github.io/vis-network/docs/network/)
