# bot_dietolog_president.py
import os
from datetime import datetime
import openai  # версия 0.28.*
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
# === CONFIG ===
import os
openai.api_key = os.getenv("OPENAI_API_KEY")
TG_BOT_TOKEN = "8288479102:AAGFn0vTj_Yd71TWKcfj4HyHazsOAmPxJtw"
# Белый список (по умолчанию пусто => пускать всех).
# Получи свой id командой /id и впиши сюда, например: {123456789}
ALLOWED_USER_IDS = set(int(x) for x in os.getenv("ALLOWED_USER_IDS", "").split(",") if x.strip().isdigit())
openai.api_key = OPENAI_API_KEY
bot = Bot(token=TG_BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)
# =================== User profile storage ===================
user_profile = {
    'age': 68,
    'weight_kg': 68,
    'height_cm': 153,
    'waist_cm': 83,
    'region': 'Север России',
    'bmi': 29,
    'gender': 'женщина',
    'post_mode': False,
    'goals': ["снижение веса", "улучшение липидного профиля", "стабилизация сахара", "здоровая печень"],
    'analyzes': {},
    'menu_nutrients': {}
}
# =================== Helpers ===================
def is_allowed(message: types.Message) -> bool:
    # если список пустой — пускаем всех; если нет — только тех, кто в списке
    return not ALLOWED_USER_IDS or (message.from_user and message.from_user.id in ALLOWED_USER_IDS)
def build_menu_prompt(profile, post_mode=False):
    prompt = (
        f"Составь меню на 2 дня для пользователя с параметрами:\n"
        f"- Возраст: {profile['age']} лет\n"
        f"- Рост: {profile['height_cm']} см\n"
        f"- Вес: {profile['weight_kg']} кг\n"
        f"- Окружность талии: {profile['waist_cm']} см\n"
        f"- Регион: {profile['region']}\n"
        f"- BMI: {profile['bmi']}\n\n"
        f"Учитывай ограничения:\n"
        f"- Печень: стеатоз; щадящее питание, без тяжёлых жиров и жареного\n"
        f"- Почки: СКФ 53,2 → умеренный белок, вода до 19:00\n"
        f"- Липиды: ЛПНП 4,36 ↑ → ПНЖК, исключить скрытые жиры\n"
        f"- Жёлчный: камень 9,5 мм → стабильное питание, без жёлчегонных\n"
        f"- LCHF + интервальное голодание (2 приёма пищи: 7-8 и 14-15)\n"
        f"- Вода ≥ 1,5 л до 19:00\n"
        f"- Не менее 10 разных продуктов за 2 дня\n"
    )
    prompt += "- Постный режим ВКЛ (без животных продуктов, белковые альтернативы)\n" if post_mode else "- Постный режим ВЫКЛ\n"
    prompt += (
       "- Цели: снижение веса, улучшение анализов, отказ от сладкого с заменой\n"
        "- Учесть продукцию и нутрицевтики Vilavi\n"
        "- Простые, сезонные рецепты для региона\n"
        "- Добавь короткий список покупок на 2 дня\n\n"
        "Сформируй меню с указанием блюд и порций, но без длинных рецептов."
    )
    return prompt
def suggest_supplements(menu_nutrients):
    recommended_daily = {
        'витамин D': 800, 'кальций': 1000, 'магний': 400,
        'витамин С': 90, 'железо': 18, 'цинк': 10, 'витамин B12': 2.4,
    }
    recs = []
    for n, need in recommended_daily.items():
        have = menu_nutrients.get(n, 0)
        if have < need:
            recs.append(f"• {n}: дефицит ~{need - have:.1f} (добавь соответствующую добавку).")
    return "Ваше меню закрывает ключевые витамины и минералы." if not recs else "Рекомендации по добавкам:\n" + "\n".join(recs)
def get_gpt_response(prompt: str) -> str:
    # openai==0.28 стиль
    try:
        resp = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.7,
        )
        return resp.choices[0].message["content"].strip()
    except Exception as e:
        # лог в консоль и безопасный ответ пользователю
        print(f"[OpenAI error] {e}")
        return "⚠️ Временная задержка на стороне ИИ. Попробуйте ещё раз через минуту."
# =================== UI: клавиатура ===================
def main_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(types.KeyboardButton("/меню"), types.KeyboardButton("/пост"))
    kb.row(types.KeyboardButton("/замена"), types.KeyboardButton("/совет"))
    kb.row(types.KeyboardButton("/анализы"), types.KeyboardButton("/цели"))
    kb.row(types.KeyboardButton("/вопрос"))
    return kb
# =================== Handlers ===================
@dp.message_handler(commands=['id'])
async def id_handler(message: types.Message):
    await message.answer(f"Ваш Telegram ID: <b>{message.from_user.id}</b>")
@dp.message_handler(commands=['start', 'help', 'старт'])
async def start_handler(message: types.Message):
    if not is_allowed(message):
        return await message.answer("🔒 Этот бот — частный. Доступ только для владельца.")
    text = (
        "👋 Добро пожаловать!\n\n"
        "📋 /меню (или /menu) — меню на 2 дня\n"
        "🔄 /замена (или /replace) — заменить продукт/рецепт\n"
        "🌱 /пост (или /post) — включить/выключить постный режим\n"
        "🧪 /анализы (или /labs) — внести новые данные анализов\n"
        "💡 /совет (или /advice) — рекомендация дня\n"
        "🎯 /цели (или /goals) — показать текущие цели\n"
        "❓ /вопрос (или /ask) — задать вопрос диетологу\n\n"
        "💬 Или просто напишите свой вопрос в чат."
    )
    await message.answer(text, reply_markup=main_kb())
@dp.message_handler(commands=['меню','menu'])
async def menu_handler(message: types.Message):
    if not is_allowed(message): return
    await message.answer("⏳ Готовлю персональное меню…")
    prompt = build_menu_prompt(user_profile, post_mode=user_profile['post_mode'])
    menu_text = get_gpt_response(prompt)
    await message.answer(menu_text)
# временная «заглушка» нутриентов
    user_profile['menu_nutrients'] = {'витамин D': 400,'кальций': 750,'магний': 350,'витамин С': 60,'железо': 15,'цинк': 8,'витамин B12': 1.5}
    await message.answer(suggest_supplements(user_profile['menu_nutrients']))
@dp.message_handler(commands=['пост','post'])
async def post_handler(message: types.Message):
    if not is_allowed(message): return
    user_profile['post_mode'] = not user_profile['post_mode']
    mode = "включён" if user_profile['post_mode'] else "выключен"
    await message.answer(f"🌱 Постный режим {mode}.")
@dp.message_handler(commands=['цели','goals'])
async def goals_handler(message: types.Message):
    if not is_allowed(message): return
    goals = "\n".join([f"• {g}" for g in user_profile['goals']])
    await message.answer(f"🎯 Текущие цели:\n{goals}")
@dp.message_handler(commands=['совет','advice'])
async def advice_handler(message: types.Message):
    if not is_allowed(message): return
    tip = get_gpt_response(
        "Дай короткую (до 2 предложений) персональную рекомендацию дня по LCHF, "
        "учитывая умеренный белок (СКФ 53), щадящую печень и питьё до 19:00."
    )
    await message.answer(f"💡 Совет дня:\n{tip}")
@dp.message_handler(commands=['замена','replace'])
async def replacement_handler(message: types.Message):
    if not is_allowed(message): return
    await message.answer("Пожалуйста, укажите продукт или рецепт, который хотите заменить. (Функция в разработке)")
@dp.message_handler(commands=['анализы','labs'])
async def analyzes_handler(message: types.Message):
    if not is_allowed(message): return
    await message.answer("Для внесения анализов используйте формат:\n<b>Показатель: значение</b>\n(Функция в разработке)")
@dp.message_handler(commands=['вопрос','ask'])
async def question_handler(message: types.Message):
    if not is_allowed(message): return
    await message.answer("Напишите свой вопрос диетологу, я постараюсь помочь вам ответом.")
@dp.message_handler(lambda m: m.text and not m.text.startswith('/'))
async def default_handler(message: types.Message):
    if not is_allowed(message): return
    prompt = f"Вопрос пользователя:\n{message.text}\nОтветь как опытный диетолог кратко и предметно."
    answer = get_gpt_response(prompt)
    await message.answer(answer)
# ================ Run bot ================
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
