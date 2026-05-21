import requests
import json
import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = "8035969678:AAFldURlAJllZxxNpYBab50E6g4eSETmdqM"
FAVORITES_FILE = "favorites.json"

#--------------- Работа с избранными городами
def load_favorites():
    if os.path.exists(FAVORITES_FILE):
        with open(FAVORITES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_favorites(data):
    with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user_favorites(user_id):
    data = load_favorites()
    return data.get(str(user_id), [])

def add_favorite(user_id, city):
    data = load_favorites()
    uid = str(user_id)
    if uid not in data:
        data[uid] = []
    if city not in data[uid]:
        data[uid].append(city)
        save_favorites(data)
        return True
    return False

def remove_favorite(user_id, city):
    data = load_favorites()
    uid = str(user_id)
    if uid in data and city in data[uid]:
        data[uid].remove(city)
        save_favorites(data)
        return True
    return False

# ------------API функции

def get_coordinates(city):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": city, "format": "json", "limit": 1}
    headers = {"User-Agent": "WeatherBot/1.0"}
    response = requests.get(url, params=params, headers=headers)
    data = response.json()
    if data:
        return float(data[0]["lat"]), float(data[0]["lon"]), data[0]["display_name"]
    return None, None, None

def get_weather(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weathercode,uv_index",
        "hourly": "temperature_2m,weathercode",
        "daily": "temperature_2m_max,temperature_2m_min,weathercode,uv_index_max,sunrise,sunset",
        "timezone": "auto",
        "forecast_days": 5
    }
    response = requests.get(url, params=params)
    return response.json()

def weather_description(code):
    descriptions = {
        0: "☀️ Ясно",
        1: "🌤 Преимущественно ясно",
        2: "⛅️ Переменная облачность",
        3: "☁️ Пасмурно",
        45: "🌫 Туман",
        48: "🌫 Изморозь",
        51: "🌦 Лёгкая морось",
        61: "🌧 Небольшой дождь",
        63: "🌧 Умеренный дождь",
        65: "🌧 Сильный дождь",
        71: "🌨 Небольшой снег",
        73: "🌨 Умеренный снег",
        75: "❄️ Сильный снег",
        95: "⛈ Гроза",
    }
    return descriptions.get(code, "🌡 Неизвестно")

def get_uv_description(uv):
    if uv <= 2:
        return f"🟢 {uv} — Низкий"
    elif uv <= 5:
        return f"🟡 {uv} — Умеренный"
    elif uv <= 7:
        return f"🟠 {uv} — Высокий"
    elif uv <= 10:
        return f"🔴 {uv} — Очень высокий"
    else:
        return f"🟣 {uv} — Экстремальный"

def get_clothing_advice(temp, apparent_temp, code):
    advice = []
    if apparent_temp < -15:
        advice.append("🧥 Очень холодно — надевай пуховик, шапку, шарф и тёплые перчатки")
    elif apparent_temp < -5:
        advice.append("🧥 Холодно — нужна тёплая куртка, шапка и перчатки")
    elif apparent_temp < 5:
        advice.append("🧣 Прохладно — куртка и шарф не помешают")
    elif apparent_temp < 15:
        advice.append("👕 Умеренно — лёгкая куртка или толстовка")
    elif apparent_temp < 22:
        advice.append("👔 Тепло — достаточно лёгкой одежды")
    else:
        advice.append("🩳 Жарко — одевайся легко, футболка и шорты в самый раз")
    if code in [51, 61, 63, 65]:
        advice.append("☂️ Возьми зонт — ожидается дождь")
    elif code in [71, 73, 75]:
        advice.append("👢 Надень водонепроницаемую обувь — ожидается снег")
    elif code == 95:
        advice.append("⛈ Лучше остаться дома — гроза!")
    return "\n".join(advice)

def format_current_weather(weather, city_name):
    current = weather["current"]
    temp = current["temperature_2m"]
    apparent = current["apparent_temperature"]
    humidity = current["relative_humidity_2m"]
    wind = current["wind_speed_10m"]
    code = current["weathercode"]
    uv = current.get("uv_index", 0)
    description = weather_description(code)
    advice = get_clothing_advice(temp, apparent, code)
    uv_desc = get_uv_description(round(uv))

    return (
        f"📍 {city_name}\n\n"
        f"{description}\n"
        f"🌡 Температура: {temp}°C\n"
        f"🤔 Ощущается как: {apparent}°C\n"
        f"💧 Влажность: {humidity}%\n"
        f"💨 Ветер: {wind} км/ч\n"
        f"🔆 УФ-индекс: {uv_desc}\n\n"
        f"👗 Совет по одежде:\n{advice}"
    )

def format_5day_forecast(weather):
    daily = weather["daily"]
    days_ru = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    lines = ["📅 *Прогноз на 5 дней:*\n"]

    for i in range(5):
        date_str = daily["time"][i]
        from datetime import datetime
        date = datetime.strptime(date_str, "%Y-%m-%d")
        day_name = days_ru[date.weekday()]
        t_max = daily["temperature_2m_max"][i]
        t_min = daily["temperature_2m_min"][i]
        code = daily["weathercode"][i]
        uv = daily["uv_index_max"][i]
        desc = weather_description(code)
        uv_desc = get_uv_description(round(uv))

        lines.append(
            f"*{day_name} {date.strftime('%d.%m')}*\n"
            f"{desc}\n"
            f"🌡 {t_min}°C — {t_max}°C\n"
            f"🔆 УФ: {uv_desc}\n"
        )

    return "\n".join(lines)

def format_hourly_forecast(weather):
    hourly = weather["hourly"]
    from datetime import datetime
    now = datetime.now()
    current_hour = now.hour

    lines = ["🕐 *Почасовой прогноз на сегодня:*\n"]
    count = 0

    for i, time_str in enumerate(hourly["time"]):
        dt = datetime.strptime(time_str, "%Y-%m-%dT%H:%M")
        if dt.date() != now.date():
            continue
        if dt.hour < current_hour:
            continue
        if count >= 8:
            break

        temp = hourly["temperature_2m"][i]
        code = hourly["weathercode"][i]
        desc = weather_description(code)
        lines.append(f"*{dt.strftime('%H:%M')}* — {temp}°C {desc}")
        count += 1

    return "\n".join(lines)

#------------------------------Клавиатуры 

def main_keyboard():
    keyboard = [
        ["🌤 Узнать погоду"],
        ["⭐️ Избранные города"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def weather_keyboard():
    keyboard = [
        ["📅 Прогноз на 5 дней", "🕐 Почасовой прогноз"],
        ["🔙 Назад"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def favorites_keyboard(user_id):
    favorites = get_user_favorites(user_id)
    keyboard = []
    for city in favorites:
        keyboard.append([f"📍 {city}"])
    keyboard.append(["➕ Добавить город", "➖ Удалить город"])
    keyboard.append(["🔙 Назад"])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def delete_keyboard(user_id):
    favorites = get_user_favorites(user_id)
    keyboard = []
    for city in favorites:
        keyboard.append([f"🗑 {city}"])
    keyboard.append(["🔙 Назад"])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

#-----------------Хендлеры

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["state"] = None
    context.user_data["last_weather"] = None
    await update.message.reply_text(
        "👋 Привет! Я погодный бот.\nНапиши название города — и я покажу погоду!",
        reply_markup=main_keyboard()
    )

async def send_weather(update, city, context):
    await update.message.reply_text(f"🔍 Ищу погоду для «{city}»...")

    lat, lon, full_name = get_coordinates(city)
    if lat is None:
        await update.message.reply_text("❌ Город не найден. Попробуй ещё раз.")
        return

    weather = get_weather(lat, lon)
    city_name = full_name.split(",")[0]

    #------Сохраняем данные для прогнозов
    context.user_data["last_weather"] = weather
    context.user_data["last_city"] = city_name

    text = format_current_weather(weather, city_name)
    await update.message.reply_text(text, reply_markup=weather_keyboard())
    context.user_data["state"] = "weather_menu"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.message.from_user.id
    state = context.user_data.get("state")

    #------Главное меню
    if text == "🌤 Узнать погоду":
        context.user_data["state"] = "waiting_city"
        await update.message.reply_text("Введи название города:")
        return

    if text == "⭐️ Избранные города":
        context.user_data["state"] = "favorites"
        favorites = get_user_favorites(user_id)
        msg = "⭐️ Твои избранные города:\nНажми на город чтобы узнать погоду" if favorites else "⭐️ У тебя пока нет избранных городов.\nДобавь через кнопку ниже!"
        await update.message.reply_text(msg, reply_markup=favorites_keyboard(user_id))
        return

    #-------Прогноз на 5 дней
    if text == "📅 Прогноз на 5 дней":
        weather = context.user_data.get("last_weather")
        if not weather:
            await update.message.reply_text("❌ Сначала узнай погоду для какого-нибудь города!")
            return
        forecast = format_5day_forecast(weather)
        await update.message.reply_text(forecast, parse_mode="Markdown", reply_markup=weather_keyboard())
        return

    #-----Почасовой прогноз
    if text == "🕐 Почасовой прогноз":
        weather = context.user_data.get("last_weather")
        if not weather:
            await update.message.reply_text("❌ Сначала узнай погоду для какого-нибудь города!")
            return
        hourly = format_hourly_forecast(weather)
        await update.message.reply_text(hourly, parse_mode="Markdown", reply_markup=weather_keyboard())
        return

    #--------Кнопка Назад
    if text == "🔙 Назад":
        if state == "deleting_favorite":
            context.user_data["state"] = "favorites"
            await update.message.reply_text("⭐️ Избранные города:", reply_markup=favorites_keyboard(user_id))
        elif state == "favorites":
            context.user_data["state"] = None
            await update.message.reply_text("Главное меню:", reply_markup=main_keyboard())
        else:
            context.user_data["state"] = None
            await update.message.reply_text("Главное меню:", reply_markup=main_keyboard())
        return

    #----------Добавление города
    if text == "➕ Добавить город":
        context.user_data["state"] = "adding_favorite"
        await update.message.reply_text("Введи название города для добавления в избранное:")
        return

    if state == "adding_favorite":
        added = add_favorite(user_id, text)
        if added:
            await update.message.reply_text(f"✅ «{text}» добавлен в избранное!", reply_markup=favorites_keyboard(user_id))
        else:
            await update.message.reply_text(f"⚠️ «{text}» уже есть в избранном.", reply_markup=favorites_keyboard(user_id))
        context.user_data["state"] = "favorites"
        return

    #------------Удаление города
    if text == "➖ Удалить город":
        favorites = get_user_favorites(user_id)
        if not favorites:
            await update.message.reply_text("⚠️ У тебя нет избранных городов для удаления.")
            return
        context.user_data["state"] = "deleting_favorite"
        await update.message.reply_text("🗑 Нажми на город чтобы удалить его:", reply_markup=delete_keyboard(user_id))
        return

    if state == "deleting_favorite" and text.startswith("🗑 "):
        city = text.replace("🗑 ", "")
        remove_favorite(user_id, city)
        await update.message.reply_text(f"🗑 «{city}» удалён из избранного!", reply_markup=delete_keyboard(user_id))
        return

    #------------Нажатие на избранный город
    if text.startswith("📍 "):
        city = text.replace("📍 ", "")
        await send_weather(update, city, context)
        return

    #----------Ввод города вручную
    if state == "waiting_city" or state is None:
        await send_weather(update, text, context)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
