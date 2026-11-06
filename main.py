import asyncio
import os
import sys
import threading
import traceback
from html import escape as he

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
PORT = os.getenv("PORT", "").strip()

if not BOT_TOKEN:
    print("❗ BOT_TOKEN env o'zgaruvchisi o'rnatilmagan.", flush=True)
    print("   Render: Environment → BOT_TOKEN = BotFather bergan token", flush=True)
    sys.exit(1)


# ---------------- health server (Render uchun) ----------------

def _start_health():
    if not PORT:
        return
    try:
        port = int(PORT)
    except ValueError:
        print(f"[health] PORT noto'g'ri: {PORT}", flush=True)
        return
    from aiohttp import web

    async def health_page(request):
        return web.Response(text="Demo bot is running")

    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        app = web.Application()
        app.router.add_get("/", health_page)
        runner = web.AppRunner(app)
        loop.run_until_complete(runner.setup())
        site = web.TCPSite(runner, "0.0.0.0", port)
        loop.run_until_complete(site.start())
        print(f"[health] 0.0.0.0:{port} tinglanmoqda", flush=True)
        loop.run_forever()

    threading.Thread(target=run, daemon=True).start()


_start_health()


# ---------------- bot ----------------

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())

BOT_LABELS = {
    "pro": "🏆 Mukammal bot",
    "mid": "⚙️ O'rtacha mukammal bot",
}
ROLE_LABELS = {
    "user": "👤 User",
    "admin": "🛠 Admin",
    "owner": "👑 Owner",
}
ROLES = ("user", "admin", "owner")
HOME_KEYS = {"user": "uhome", "admin": "ahome", "owner": "ohome"}


# ---------------- ekranlar bazasi ----------------

SCREENS = {}


def screen(bot_key, role, key, title, body, buttons=(), parent=None):
    SCREENS[(bot_key, role, key)] = {
        "title": title,
        "body": body,
        "buttons": list(buttons),
        "parent": parent,
    }


def resolve(bot_key, role, target):
    if target.startswith("@"):
        b, r, k = target[1:].split(":")
        return b, r, k
    return bot_key, role, target


def target_cb(bot_key, role, target):
    b, r, k = resolve(bot_key, role, target)
    data = f"demo:s:{b}:{r}:{k}"
    if len(data.encode()) > 64:
        raise ValueError(f"callback juda uzun: {data}")
    return data


def render(bot_key, role, key):
    sc = SCREENS.get((bot_key, role, key))
    if not sc:
        return None, None
    rows = []
    buf = []
    for label, target in sc["buttons"]:
        buf.append(InlineKeyboardButton(text=label,
                                        callback_data=target_cb(bot_key, role, target)))
        if len(buf) == 2:
            rows.append(buf)
            buf = []
    if buf:
        rows.append(buf)
    nav = []
    if sc["parent"]:
        nav.append(InlineKeyboardButton(text="⬅️ Orqaga",
                                        callback_data=target_cb(bot_key, role, sc["parent"])))
    nav.append(InlineKeyboardButton(text="🔄 Rol tanlash",
                                    callback_data=f"demo:bot:{bot_key}"))
    nav.append(InlineKeyboardButton(text="🏠 Demo",
                                    callback_data="demo:start"))
    rows.append(nav)
    text = (f"🧪 <b>NAMOYISH BOTI</b>\n"
            f"{BOT_LABELS[bot_key]} · {ROLE_LABELS[role]}\n"
            "━━━━━━━━━━━━━━━━\n"
            f"<b>{sc['title']}</b>\n\n{sc['body']}")
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


# ---------------- boshlang'ich ekranlar ----------------

START_TEXT = (
    "👋 <b>Assalomu alaykum!</b>\n\n"
    "Bu — <b>ko'rgazma (demo) boti</b>. Unda ikki xil botning "
    "<b>asosiy menyusi, admin paneli va owner paneli</b> bilan tanishasiz.\n\n"
    "🎯 Har bir tugmani bosing — bot o'sha tugma haqiqiy botda "
    "<b>nima qilishini</b> qisqacha tushuntirib beradi.\n\n"
    "🔒 Bu yerda hech qanday haqiqiy ma'lumot o'zgarmaydi — hammasi namuna.\n\n"
    "👇 Qaysi botni ko'rmoqchisiz?"
)

ABOUT_TEXT = (
    "ℹ️ <b>Ikki botning farqi</b>\n\n"
    "🏆 <b>Mukammal bot — «KinoPlus PRO»</b>\n"
    "• Kod, nom va tur bo'yicha kuchli qidiruv\n"
    "• Fasl/qism tizimi, qism raqamini sarlavhadan avtomatik aniqlash\n"
    "• VIP, balans, referal\n"
    "• Admin panel + alohida <b>owner panel</b>\n"
    "• Owner: adminlar va huquqlar, kanallar, zaxira, statistika, "
    "obunachilarni boshqarish (pul/VIP + izoh + rasm/video/stiker)\n\n"
    "⚙️ <b>O'rtacha mukammal bot — «KinoPlus START»</b>\n"
    "• Kod va nom bo'yicha qidiruv, sevimlilar, davom ettirish\n"
    "• Buyurtma, shikoyat, premium va to'lovlar\n"
    "• Admin panel: kontent, qism, to'lovlar, kanallar, foydalanuvchilar, "
    "eksport/import, zaxira\n"
    "• Alohida owner paneli yo'q — <code>ADMIN_IDS</code> dagi hisob owner\n\n"
    "💡 Ikkalasi ham bitta tayyor kod bazasidan sozlanadi; narx va "
    "funksiyalar sizning ehtiyojingizga qarab tanlanadi."
)

PRO_INTRO = (
    "🏆 <b>MUKAMMAL BOT</b> — «KinoPlus PRO»\n\n"
    "To'liq avtomatlashtirilgan kino/serial platformasi:\n"
    "• 🔎 Kod, nom va tur bo'yicha qidiruv\n"
    "• 📺 Fasl/qism tizimi (raqamni sarlavhadan avtomatik aniqlaydi)\n"
    "• 💎 VIP va 💰 balans\n"
    "• 👥 Referal tizimi\n"
    "• 🛠 Admin panel — kontent, qism, tahrirlash\n"
    "• 👑 Owner panel — adminlar, huquqlar, kanallar, zaxira, statistika, "
    "obunachilarni boshqarish\n\n"
    "👤 Kim sifatida ko'rmoqchisiz?"
)

MID_INTRO = (
    "⚙️ <b>O'RTACHA MUKAMMAL BOT</b> — «KinoPlus START»\n\n"
    "Kichik va o'rta biznes uchun qulay bot:\n"
    "• 🔎 Kod va nom bo'yicha qidiruv\n"
    "• ▶️ Davom ettirish, ❤️ sevimlilar\n"
    "• 🛒 Buyurtma va 📝 shikoyat\n"
    "• 💎 Premium (VIP) va to'lovlar\n"
    "• 🛠 Admin panel — kontent, qism, to'lovlar, kanallar, "
    "foydalanuvchilar, eksport/import, zaxira\n"
    "• 👑 Owner huquqlari — sozlamalar, narxlar, zaxira, ban\n\n"
    "👤 Kim sifatida ko'rmoqchisiz?"
)


# =====================================================================
#  MUKAMMAL BOT — USER
# =====================================================================

screen("pro", "user", "uhome", "👤 Foydalanuvchi menyusi",
       "Bu — oddiy tomoshabin ko'radigan asosiy menyu. Tugmalar haqiqiy "
       "botdagidek ishlaydi.\n\n"
       "🎯 Istalgan tugmani bosing — qisqa tushuntirish chiqadi.\n"
       "💡 Qidiruv bo'limida «to'g'ridan-to'g'ri yozish» ham ko'rsatilgan.",
       [
           ("🔎 Anime va Kino izlash", "search"),
           ("🎬 Namuna kartochka", "card"),
           ("👤 Hisobim", "acct"),
           ("👥 Referal", "ref"),
           ("💰 Balans", "bal"),
           ("💎 VIP olish", "vip"),
           ("❓ VIP o'zi nima?", "vipinfo"),
           ("📖 Qo'llanma", "guide"),
       ])

screen("pro", "user", "search", "🔎 Qidiruv markazi",
       "Qidiruvning barcha usullari shu yerda.\n\n"
       "🔢 Kod — eng tez usul.\n"
       "🔠 Nom — to'liq yoki nomning bir qismi bo'yicha.\n"
       "📂 Tur bo'yicha ro'yxat — sahifalab ko'rsatiladi.",
       [
           ("🔢 Kod bo'yicha", "q_code"),
           ("🔠 Nom bo'yicha", "q_name"),
           ("🎞 Kinolar", "c_movie"),
           ("📺 Seriallar", "c_series"),
           ("🍥 Anime", "c_anime"),
           ("🎨 Multfilmlar", "c_cartoon"),
           ("💡 To'g'ridan-to'g'ri yozish", "direct"),
       ],
       parent="uhome")

screen("pro", "user", "q_code", "🔢 Kod bo'yicha qidiruv",
       "Foydalanuvchi <code>101</code> kabi kod yozadi. Bot bazadan aynan "
       "shu kodli kontentni topib, kartochkani ochadi.\n\n"
       "• Topilmasa — «❌ Kod topilmadi» xabari\n"
       "• Har ochilishda 👁 ko'rishlar soni +1 bo'ladi\n"
       "• VIP kontent bo'lsa — avval VIP tekshiriladi",
       parent="search")

screen("pro", "user", "q_name", "🔠 Nom bo'yicha qidiruv",
       "Nom to'liq yoki nomning bir qismi bo'yicha qidiriladi. "
       "Katta-kichik harf farqi yo'q.\n\n"
       "• Aniq mos nom — darhol kartochka\n"
       "• Bir nechta moslik — inline ro'yxat (20 tagacha)\n"
       "• Topilmasa — xabar va asosiy menyu",
       parent="search")

for _key, _title in (
    ("c_movie", "🎞 Kinolar ro'yxati"),
    ("c_series", "📺 Seriallar ro'yxati"),
    ("c_anime", "🍥 Anime ro'yxati"),
    ("c_cartoon", "🎨 Multfilmlar ro'yxati"),
):
    screen("pro", "user", _key, _title,
           "Ro'yxat sahifalab chiqadi (⬅️ / ➡️). Tugma bosilganda tanlangan "
           "kontentning kartochkasi ochiladi.\n\n"
           "Har bir kontentda tur belgisi, nomi va kodi ko'rinadi.",
           parent="search")

screen("pro", "user", "direct", "💡 To'g'ridan-to'g'ri qidiruv",
       "Yangilik: <b>asosiy menyu ochiq holatda</b> kod yoki nom yozilsa, "
       "qidiruv tugmasini bosish shart emas.\n\n"
       "• <code>101</code> → darhol kartochka\n"
       "• <code>interstellar</code> → nom bo'yicha natijalar\n"
       "• Topilmasa → «❌ Hech narsa topilmadi»\n\n"
       "🧪 Demo rejimida shu chatga istalgan matn yozib ko'ring.",
       parent="search")

screen("pro", "user", "acct", "👤 Hisobim",
       "Profil: ism, ID, VIP holati va tugash sanasi, balans, ko'rishlar "
       "tarixi va sevimlilar soni.\n\n"
       "Foydalanuvchi faqat o'z ma'lumotini ko'radi; o'zgartirishni faqat "
       "admin yoki owner qiladi.",
       parent="uhome")

screen("pro", "user", "ref", "👥 Referal",
       "Shaxsiy havola: <code>t.me/bot?start=ref_ID</code>.\n\n"
       "• Taklif qilinganlar soni\n"
       "• Har bir yangi foydalanuvchi uchun balansga bonus\n"
       "• Bonus miqdorini owner sozlaydi",
       parent="uhome")

screen("pro", "user", "bal", "💰 Balans",
       "Joriy balans va barcha amallar tarixi:\n"
       "• + qo'shildi / − yechildi\n"
       "• Izoh (tavsif)\n"
       "• Sana va kim tomonidan\n\n"
       "Balans VIP sotib olishda ishlatiladi.",
       parent="uhome")

screen("pro", "user", "vip", "💎 VIP olish",
       "1 oylik yoki umrlik VIP tarif.\n\n"
       "• Narx va muddatlar owner sozlamalaridan olinadi\n"
       "• To'lov kartasi ko'rsatiladi, chek adminga yuboriladi\n"
       "• Tasdiqlangach VIP avtomatik yoqiladi",
       parent="uhome")

screen("pro", "user", "vipinfo", "❓ VIP o'zi nima?",
       "VIP imkoniyatlari:\n"
       "• Yopiq (VIP) kontentga kirish\n"
       "• Majburiy obunasiz foydalanish\n"
       "• Saqlash/ulashish himoyasi\n"
       "• Erta ko'rish va boshqa imtiyozlar",
       parent="uhome")

screen("pro", "user", "guide", "📖 Qo'llanma",
       "Yangi foydalanuvchi uchun qadam-baqadam yo'riqnoma:\n"
       "qanday qidirish, tomosha qilish, sevimlilarga saqlash va VIP olish.",
       parent="uhome")

screen("pro", "user", "card", "🎬 Namuna: kino kartochkasi",
       "<b>Interstellar</b> (2014)\n"
       "⭐ 8.9 (1 240 baho) · 👁 15 320 · 📁 12 qism\n"
       "🆓 Bepul · 🎞 Kinolar\n\n"
       "Qora tuynuk ortidagi sayohat — insoniyat kelajagi uchun.",
       [
           ("▶️ 1-qismni ko'rish", "card_watch"),
           ("❤️ Sevimlilarga", "card_fav"),
           ("⭐ Baholash", "card_rate"),
           ("🚩 Shikoyat", "card_rep"),
       ],
       parent="uhome")

screen("pro", "user", "card_watch", "▶️ Tomosha qilish",
       "Bot videoni yuboradi.\n\n"
       "• Qismlar tugmalari bilan navigatsiya\n"
       "• Keyingi qism avtomatik taklif qilinadi\n"
       "• VIP himoyasi sozlamasiga qarab <code>protect_content</code> yoqiladi\n"
       "• Ko'rishlar tarixiga yoziladi",
       parent="card")

screen("pro", "user", "card_fav", "❤️ Sevimlilar",
       "Kino «Sevimlilarim» ro'yxatiga qo'shiladi. Keyin uni profildan "
       "bir bosishda ochish mumkin.",
       parent="card")

screen("pro", "user", "card_rate", "⭐ Baholash",
       "Foydalanuvchi 1–10 ball qo'yadi. O'rtacha baho kartochkada ko'rinadi.\n\n"
       "Bir foydalanuvchi bir marta baholay oladi.",
       parent="card")

screen("pro", "user", "card_rep", "🚩 Shikoyat",
       "Foydalanuvchi sababni yozadi va tasdiqlaydi.\n\n"
       "Xabar adminlarga kino kodi va foydalanuvchi ID si bilan birga boradi.",
       parent="card")


# =====================================================================
#  MUKAMMAL BOT — ADMIN
# =====================================================================

screen("pro", "admin", "ahome", "🛠 Admin panel",
       "Admin — kontent bilan ishlaydi. Huquqlar ownerdan beriladi: "
       "har bir tugma alohida yoqiladi.\n\n"
       "<i>Quyidagilar haqiqiy admin panelning bo'limlari.</i>",
       [
           ("➕ Kino qo'shish", "add"),
           ("➕ Serial qo'shish", "add"),
           ("🍥 Anime qo'shish", "add"),
           ("🎨 Multfilm qo'shish", "add"),
           ("✂️ Qism / yangi fasl", "ep"),
           ("✏️ Nomini o'zgartirish", "ren"),
           ("🖼 Posterni o'zgartirish", "poster"),
           ("🔢 Kodini o'zgartirish", "code"),
           ("🗑 Kontent o'chirish", "del"),
           ("🗑 Qism o'chirish", "delep"),
           ("🗑 Fasl o'chirish", "delseason"),
           ("👤 User menyusini ko'rish", "@pro:user:uhome"),
       ])

screen("pro", "admin", "add", "➕ Kontent qo'shish",
       "Bosqichma-bosqich wizard:\n"
       "1) Tur (kino/serial/anime/multfilm)\n"
       "2) Kod\n"
       "3) Nom\n"
       "4) Yil\n"
       "5) Janr\n"
       "6) Tavsif\n"
       "7) Poster\n"
       "8) Qismlar\n"
       "9) Tasdiqlash\n\n"
       "Qo'shilganda obunachilarga «yangi kontent» xabari ketadi "
       "(owner sozlamasiga bog'liq).",
       parent="ahome")

screen("pro", "admin", "ep", "✂️ Qism / yangi fasl qo'shish",
       "Qism qo'shish qoidalari:\n"
       "• Video, rasm, GIF, audio yoki fayl yuboriladi\n"
       "• Raqam sarlavhadan avtomatik olinadi\n"
       "• Takror raqam: bir xil media — ogohlantirish, boshqa media — "
       "keyingi raqamga o'tadi\n"
       "• <code>/done</code> — tugatish, <code>/bekor</code> — bekor\n\n"
       "🧪 Namunalarni bosing:",
       [
           ("🧪 «5. BÖLÜM»", "ep_a"),
           ("🧪 «beshinchi qism»", "ep_b"),
           ("🧪 «3 fasl 5 qism»", "ep_c"),
       ],
       parent="ahome")

screen("pro", "admin", "ep_a", "🧪 Namuna: 5. BÖLÜM",
       "📥 Video qabul qilindi.\n"
       "🔎 Sarlavhadan aniqlandi: <b>5-qism</b>.\n"
       "✅ Saqlandi (jami: 12 ta).\n\n"
       "Katta harf, nuqta va turkcha harflar farqi yo'q — "
       "«5. BÖLÜM» ham 5-qism bo'ladi.",
       parent="ep")

screen("pro", "admin", "ep_b", "🧪 Namuna: beshinchi qism",
       "📥 Media qabul qilindi.\n"
       "🔎 «beshinchi qism» → <b>5-qism</b>.\n\n"
       "Raqam so'z bilan yozilgan bo'lsa ham aniqlanadi:\n"
       "birinchi, ikkinchi, beshinchi, yigirmanchi...",
       parent="ep")

screen("pro", "admin", "ep_c", "🧪 Namuna: 3 fasl 5 qism",
       "📥 Media qabul qilindi.\n"
       "🔎 «3 fasl 5 qism» → <b>3-fasl, 5-qism</b>.\n\n"
       "Fasl va qism alohida olinadi. <code>s3e5</code> va "
       "<code>3x5</code> ham tushuniladi.",
       parent="ep")

screen("pro", "admin", "ren", "✏️ Nomini o'zgartirish",
       "Kontent kodi kiritiladi, yangi nom yoziladi.\n\n"
       "Kartochka, ro'yxatlar va qidiruv natijalari darhol yangilanadi.",
       parent="ahome")

screen("pro", "admin", "poster", "🖼 Posterni o'zgartirish",
       "Yangi rasm yuboriladi. Poster kartochka va ro'yxatlarda "
       "darhol yangilanadi.",
       parent="ahome")

screen("pro", "admin", "code", "🔢 Kodini o'zgartirish",
       "Kontentga yangi unikal kod beriladi.\n\n"
       "Diqqat: eski kod bo'yicha qidiruv ishlamay qoladi — bot "
       "ogohlantirish chiqaradi.",
       parent="ahome")

screen("pro", "admin", "del", "🗑 Kontent o'chirish",
       "Kod kiritiladi va tasdiqlanadi.\n\n"
       "Serial bo'lsa — barcha fasl va qismlari bilan birga o'chadi.",
       parent="ahome")

screen("pro", "admin", "delep", "🗑 Qism o'chirish",
       "Fasl va qism raqami tanlanadi. Tasdiqlangach baza va kanaldagi "
       "yozuv o'chiriladi.",
       parent="ahome")

screen("pro", "admin", "delseason", "🗑 Fasl o'chirish",
       "Butun fasl qismlari bilan o'chiriladi. Tasdiqlash majburiy.",
       parent="ahome")


# =====================================================================
#  MUKAMMAL BOT — OWNER
# =====================================================================

screen("pro", "owner", "ohome", "👑 Owner panel",
       "Owner — bot egasi. Admin panelning barcha funksiyalari + adminlar, "
       "kanallar, sozlamalar, zaxira va moliyaviy amallar.",
       [
           ("👤 Adminlar", "admins"),
           ("🔐 Admin huquqlari", "perms"),
           ("📢 Kanallar", "channels"),
           ("🎨 Tugma ranglari", "look"),
           ("💾 Zaxira", "backup"),
           ("🛠 Texnik tanaffus", "maint"),
           ("💎 VIP yoqish/o'chirish", "vipm"),
           ("🔐 Saqlash himoyasi", "protect"),
           ("📣 Broadcast", "bcast"),
           ("⚙️ Bot sozlamalari", "settings"),
           ("👥 Obunachilarni boshqarish", "manage"),
           ("📊 Statistika", "stats"),
           ("📣 Yangi kontent xabari", "notify"),
           ("🛠 Admin panelini ko'rish", "@pro:admin:ahome"),
           ("👤 User menyusini ko'rish", "@pro:user:uhome"),
       ])

screen("pro", "owner", "admins", "👤 Adminlar",
       "ID bo'yicha admin qo'shish yoki o'chirish.\n\n"
       "Owner istalgan vaqtda adminlar ro'yxatini ko'radi va huquqlarini "
       "o'zgartiradi.",
       [
           ("➕ Admin qo'shish", "adm_add"),
           ("➖ Admin o'chirish", "adm_del"),
           ("🔐 Huquqlarni sozlash", "perms"),
       ],
       parent="ohome")

screen("pro", "owner", "adm_add", "➕ Admin qo'shish",
       "Foydalanuvchi ID si yuboriladi. U botga <code>/admin</code> orqali "
       "kira oladi.",
       parent="admins")

screen("pro", "owner", "adm_del", "➖ Admin o'chirish",
       "ID yuboriladi, admin huquqlari olib tashlanadi. Foydalanuvchi "
       "oddiy user sifatida ishlashda davom etadi.",
       parent="admins")

screen("pro", "owner", "perms", "🔐 Admin huquqlari",
       "Har bir admin uchun huquqlar alohida yoqiladi:\n"
       "• ➕ Kontent qo'shish\n"
       "• ✂️ Qism qo'shish\n"
       "• ✏️ Tahrirlash\n"
       "• 🗑 O'chirish\n\n"
       "Owner — barcha huquqlar bilan ishlaydi.",
       parent="ohome")

screen("pro", "owner", "channels", "📢 Kanallar",
       "Majburiy obuna kanallarini qo'shish yoki o'chirish. "
       "Bot kanalda admin bo'lishi kerak.\n\n"
       "Obuna bo'lmagan foydalanuvchi kontentni ko'ra olmaydi "
       "(VIPdan tashqari).",
       [
           ("➕ Kanal qo'shish", "chan_add"),
           ("➖ Kanal o'chirish", "chan_del"),
       ],
       parent="ohome")

screen("pro", "owner", "chan_add", "➕ Kanal qo'shish",
       "Kanal ID yoki <code>@username</code> yuboriladi, bot kanalga "
       "admin qilinadi.",
       parent="channels")

screen("pro", "owner", "chan_del", "➖ Kanal o'chirish",
       "Ro'yxatdan kanal tanlanadi va obuna talabi olib tashlanadi.",
       parent="channels")

screen("pro", "owner", "look", "🎨 Tugma ranglari",
       "Har bir inline tugma uchun rang tanlanadi. Botning ko'rinishi "
       "brendga moslanadi.",
       parent="ohome")

screen("pro", "owner", "backup", "💾 Zaxira",
       "Barcha ma'lumot bitta JSON fayl qilib zaxira kanalga yuboriladi.\n\n"
       "♻️ Tiklashda fayl yuboriladi va <code>/done</code> yoziladi — "
       "baza aynan zaxiradagi holatga qaytadi.",
       [
           ("💾 Zaxira olish", "bk_send"),
           ("♻️ Zaxirani tiklash", "bk_restore"),
           ("🗄 Zaxira kanalini o'zgartirish", "bk_chan"),
       ],
       parent="ohome")

screen("pro", "owner", "bk_send", "💾 Zaxira olish",
       "Foydalanuvchilar, kontent, to'lovlar va sozlamalar — hammasi "
       "bitta JSON faylda saqlanadi.",
       parent="backup")

screen("pro", "owner", "bk_restore", "♻️ Zaxirani tiklash",
       "Zaxira fayli yuboriladi va <code>/done</code> bilan tasdiqlanadi. "
       "Avvalgi ma'lumot almashtiriladi.",
       parent="backup")

screen("pro", "owner", "bk_chan", "🗄 Zaxira kanali",
       "Zaxira nusxa qayerga saqlanishini o'zgartirish. "
       "<code>off</code> yuborilsa — o'chiriladi.",
       parent="backup")

screen("pro", "owner", "maint", "🛠 Texnik tanaffus",
       "Bot vaqtincha yopiladi: foydalanuvchilarga xabar ko'rinadi, "
       "owner esa ishlashda davom etadi.",
       parent="ohome")

screen("pro", "owner", "vipm", "💎 VIP yoqish/o'chirish",
       "VIP tizimini butunlay yoqadi yoki o'chiradi. O'chirilganda VIP "
       "sotib olish va VIP kontent vaqtincha to'xtaydi.",
       parent="ohome")

screen("pro", "owner", "protect", "🔐 Saqlash himoyasi",
       "VIP kontentni forward/save qilishni cheklash "
       "(<code>protect_content</code>).",
       parent="ohome")

screen("pro", "owner", "bcast", "📣 Broadcast",
       "Barcha foydalanuvchilarga xabar yuborish (matn, rasm, video).\n\n"
       "Yuborish tezligi cheklanadi, xatolar sanaladi.",
       parent="ohome")

screen("pro", "owner", "settings", "⚙️ Bot sozlamalari",
       "Owner o'zgartiradigan qiymatlar:\n"
       "• 👥 Referal mukofoti\n"
       "• 👑 VIP 1 oy narxi\n"
       "• 📅 VIP maksimal muddati\n"
       "• ⏳ VIP oy davomiyligi\n"
       "• 🎬 Erta ko'rish kunlari\n"
       "• 💬 To'lov admini username",
       parent="ohome")

screen("pro", "owner", "manage", "👥 Obunachilarni boshqarish",
       "Tartib:\n"
       "1) Foydalanuvchi ID si yuboriladi\n"
       "2) Amal tanlanadi: balans +/− yoki VIP\n"
       "3) Summa yoki muddat\n"
       "4) Izoh (tavsif)\n"
       "5) Rasm / video / txt / stiker ilova qilish "
       "(yoki <code>/skipp</code>)\n"
       "6) Tasdiqlash\n\n"
       "✅ Tasdiqlangach foydalanuvchiga xabar + pul/VIP boradi.",
       [("🧪 Namunani ko'rish", "manex")],
       parent="ohome")

screen("pro", "owner", "manex", "💸 Tasdiqlash namunasi",
       "👤 Aziz Karimov (<code>123456789</code>)\n"
       "💰 Summa: <b>+50 000 so'm</b>\n"
       "📝 Izoh: Turnir sovrini\n"
       "📎 Ilova: 🖼 rasm (chek)\n\n"
       "Foydalanuvchiga xabar va pul yuborilsinmi?",
       [
           ("✅ Tasdiqlash", "manok"),
           ("❌ Bekor qilish", "manage"),
       ],
       parent="manage")

screen("pro", "owner", "manok", "✅ Tasdiqlandi",
       "Foydalanuvchiga quyidagi xabar yuborildi:\n"
       "«💰 Balansingizga 50 000 so'm qo'shildi.\n"
       "📝 Izoh: Turnir sovrini»\n\n"
       "Yangi balans: 120 000 so'm.",
       parent="manage")

screen("pro", "owner", "stats", "📊 Statistika",
       "Obunachilar soni va o'sishi, faol/tark etganlar, VIP statistikasi, "
       "kontent va qismlar soni, to'lovlar, buyurtmalar.",
       parent="ohome")

screen("pro", "owner", "notify", "📣 Yangi kontent xabari",
       "Kontent qo'shilganda obunachilarga avtomatik xabar yuborishni "
       "yoqadi yoki o'chiradi.",
       parent="ohome")


# =====================================================================
#  O'RTACHA MUKAMMAL BOT — USER
# =====================================================================

screen("mid", "user", "uhome", "👤 Foydalanuvchi menyusi",
       "Bu — mijoz botining asosiy menyusi (pastdagi doimiy tugmalar). "
       "Har biri alohida bo'lim.\n\n"
       "🎯 Tugmani bosing — tushuntirish chiqadi.",
       [
           ("▶️ Davom ettirish", "cont"),
           ("🔎 Qidiruv", "search"),
           ("❤️ Sevimlilarim", "favs"),
           ("👤 Hisobim", "acct"),
           ("🛒 Buyurtma qilish", "order"),
           ("📝 Shikoyat", "comp"),
           ("📞 Admin bilan bog'lanish", "contact"),
           ("💎 Premium", "prem"),
           ("🎬 Namuna kartochka", "card"),
           ("💡 To'g'ridan-to'g'ri qidiruv", "direct"),
       ])

screen("mid", "user", "cont", "▶️ Davom ettirish",
       "Oxirgi ko'rilgan kino va qismdan davom etadi. Ko'rishlar tarixi "
       "saqlanadi.",
       parent="uhome")

screen("mid", "user", "search", "🔎 Qidiruv markazi",
       "Nom, kod yoki tur bo'yicha qidiruv.",
       [
           ("🔠 Nom bo'yicha", "q_name"),
           ("🔢 Kod bo'yicha", "q_code"),
           ("🎬 Kinolar", "c_kino"),
           ("📺 Seriallar", "c_serial"),
           ("🎌 Animelar", "c_anime"),
           ("🧸 Multfilmlar", "c_multik"),
           ("🎭 Dramalar", "c_drama"),
       ],
       parent="uhome")

screen("mid", "user", "q_name", "🔠 Nom bo'yicha",
       "Nomning to'liq yoki bir qismi bo'yicha qidiriladi. Mosliklar "
       "inline ro'yxat sifatida chiqadi; aniq moslik — darhol kartochka.",
       parent="search")

screen("mid", "user", "q_code", "🔢 Kod bo'yicha",
       "Aynan kod tekshiriladi. Topilmasa — xabar va asosiy menyu.",
       parent="search")

for _key, _title in (
    ("c_kino", "🎬 Kinolar"),
    ("c_serial", "📺 Seriallar"),
    ("c_anime", "🎌 Animelar"),
    ("c_multik", "🧸 Multfilmlar"),
    ("c_drama", "🎭 Dramalar"),
):
    screen("mid", "user", _key, _title,
           "Ro'yxat sahifalab chiqadi. Tugma bosilganda tanlangan "
           "kontentning kartochkasi ochiladi.",
           parent="search")

screen("mid", "user", "direct", "💡 To'g'ridan-to'g'ri qidiruv",
       "Asosiy menyuda kod yoki nom yozilsa — bot darhol qidiradi, "
       "qidiruv tugmasini bosish shart emas.\n\n"
       "• Kod → kartochka\n"
       "• Nom → natijalar ro'yxati\n"
       "• Topilmasa → xabar\n\n"
       "🧪 Demo rejimida shu chatga matn yozib ko'ring.",
       parent="uhome")

screen("mid", "user", "favs", "❤️ Sevimlilarim",
       "Saqlangan kinolar ro'yxati. Bir bosishda kartochka ochiladi.",
       parent="uhome")

screen("mid", "user", "acct", "👤 Hisobim",
       "Ism, ID, VIP holati, balans va ko'rishlar tarixi.",
       parent="uhome")

screen("mid", "user", "order", "🛒 Buyurtma qilish",
       "Foydalanuvchi kino nomini yozadi (poster va yil ixtiyoriy).\n\n"
       "Buyurtma adminga tushadi; tayyor bo'lgach foydalanuvchiga xabar "
       "keladi.",
       parent="uhome")

screen("mid", "user", "comp", "📝 Shikoyat",
       "Matn yoziladi va tasdiqlanadi, so'ng adminlarga yuboriladi. "
       "Shikoyat foydalanuvchi ID si bilan boradi.",
       parent="uhome")

screen("mid", "user", "contact", "📞 Admin bilan bog'lanish",
       "Sozlamalardagi support yoki admin username/havolasi orqali "
       "bog'lanish.",
       parent="uhome")

screen("mid", "user", "prem", "💎 Premium",
       "1 oylik yoki umrlik tarif. Karta orqali to'lov, chek yuboriladi, "
       "admin tasdiqlaydi.",
       parent="uhome")

screen("mid", "user", "card", "🎬 Namuna: kino kartochkasi",
       "<b>Oq kema</b> (2020)\n"
       "⭐ 8.4 (312 baho) · 👁 4 210 · 📁 8 qism\n"
       "🆓 Bepul · 🎬 Kinolar\n\n"
       "Dengiz ortidagi yashirin orol va qutqaruv ekspeditsiyasi.",
       [
           ("▶️ 1-qismni ko'rish", "card_watch"),
           ("❤️ Sevimlilarga", "card_fav"),
           ("⭐ Baholash", "card_rate"),
       ],
       parent="uhome")

screen("mid", "user", "card_watch", "▶️ Tomosha qilish",
       "Bot videoni yuboradi. Qismlar tugmalari bilan navigatsiya, "
       "keyingi qism taklifi va ko'rishlar tarixiga yozish.",
       parent="card")

screen("mid", "user", "card_fav", "❤️ Sevimlilar",
       "Kino sevimlilar ro'yxatiga qo'shiladi.",
       parent="card")

screen("mid", "user", "card_rate", "⭐ Baholash",
       "1–10 ball; o'rtacha baho kartochkada ko'rinadi.",
       parent="card")


# =====================================================================
#  O'RTACHA MUKAMMAL BOT — ADMIN
# =====================================================================

screen("mid", "admin", "ahome", "🛠 Admin panel",
       "Kontent, to'lovlar, kanallar, foydalanuvchilar va zaxira.\n\n"
       "Bu botda adminlar <code>ADMIN_IDS</code> orqali belgilanadi — "
       "ya'ni owner huquqi shu hisobda.",
       [
           ("📊 Statistika", "stats"),
           ("🎬 Kontent", "content"),
           ("➕ Kontent qo'shish", "add"),
           ("✂️ Qism qo'shish", "ep"),
           ("🗑 O'chirish", "del"),
           ("📢 Xabar yuborish", "bcast"),
           ("🧾 To'lovlar", "orders"),
           ("🛒 Buyurtmalar", "uorders"),
           ("⚠️ Shikoyatlar", "comp"),
           ("📣 Kanallar", "chan"),
           ("👥 Foydalanuvchilar", "users"),
           ("🚫 Ban/Unban", "ban"),
           ("📈 Analitika", "anal"),
           ("📤 Eksport", "expe"),
           ("📥 Import", "impi"),
           ("💎 Premium", "prem"),
           ("⚙️ Sozlamalar", "sett"),
           ("💾 Zaxira", "backup"),
           ("👤 User menyusini ko'rish", "@mid:user:uhome"),
       ])

screen("mid", "admin", "stats", "📊 Statistika",
       "Foydalanuvchilar, VIP, kontent va qismlar, kutilayotgan to'lovlar, "
       "buyurtmalar, kanallar va bloklanganlar soni.",
       parent="ahome")

screen("mid", "admin", "content", "🎬 Kontent",
       "Barcha kontentlar ro'yxati. Kartochkani ochib tahrirlash mumkin.",
       parent="ahome")

screen("mid", "admin", "add", "➕ Kontent qo'shish",
       "Wizard: tur → kod → nom → yil → tavsif → poster → tarif → "
       "tasdiqlash.\n\n"
       "Qo'shilganda obunachilarga yangi kontent xabari ketishi mumkin.",
       parent="ahome")

screen("mid", "admin", "ep", "✂️ Qism qo'shish",
       "Qism qo'shish qoidalari:\n"
       "• Video, rasm, GIF, audio yoki fayl yuboriladi\n"
       "• Raqam sarlavhadan avtomatik olinadi\n"
       "• Takror raqamlar xavfsiz hal qilinadi\n"
       "• <code>/done</code> — tugatish, <code>/bekor</code> — bekor\n\n"
       "🧪 Namunalarni bosing:",
       [
           ("🧪 «5. BÖLÜM»", "ep_a"),
           ("🧪 «beshinchi qism»", "ep_b"),
           ("🧪 «3 fasl 5 qism»", "ep_c"),
       ],
       parent="ahome")

screen("mid", "admin", "ep_a", "🧪 Namuna: 5. BÖLÜM",
       "📥 Video qabul qilindi.\n"
       "🔎 Aniqlandi: <b>5-qism</b>.\n"
       "✅ Saqlandi (jami: 12 ta).\n\n"
       "Katta harf, nuqta va turkcha harflar farqi yo'q.",
       parent="ep")

screen("mid", "admin", "ep_b", "🧪 Namuna: beshinchi qism",
       "📥 Media qabul qilindi.\n"
       "🔎 «beshinchi qism» → <b>5-qism</b>.\n\n"
       "Raqam so'z bilan yozilganda ham aniqlanadi.",
       parent="ep")

screen("mid", "admin", "ep_c", "🧪 Namuna: 3 fasl 5 qism",
       "📥 Media qabul qilindi.\n"
       "🔎 <b>3-fasl, 5-qism</b>.\n\n"
       "<code>s3e5</code> va <code>3x5</code> ham tushuniladi.",
       parent="ep")

screen("mid", "admin", "del", "🗑 O'chirish",
       "Kod bo'yicha o'chirish; tasdiqlash majburiy. Serial bo'lsa — "
       "qismlari bilan birga o'chadi.",
       parent="ahome")

screen("mid", "admin", "bcast", "📢 Xabar yuborish",
       "Barcha foydalanuvchilarga matn yoki media yuborish. Tezlik "
       "cheklangan, xatolar sanaladi.",
       parent="ahome")

screen("mid", "admin", "orders", "🧾 To'lovlar",
       "To'lov cheklarini ko'rish, tasdiqlash yoki rad etish. "
       "Tasdiqlangach VIP avtomatik yoqiladi.",
       parent="ahome")

screen("mid", "admin", "uorders", "🛒 Buyurtmalar",
       "Foydalanuvchi buyurtmalari: yangi, tayyor, rad etilgan. "
       "Javob yuborish mumkin.",
       parent="ahome")

screen("mid", "admin", "comp", "⚠️ Shikoyatlar",
       "Shikoyat matni, foydalanuvchi va kino kodi. Ko'rib chiqish, "
       "javob berish yoki o'chirish.",
       parent="ahome")

screen("mid", "admin", "chan", "📣 Kanallar",
       "Majburiy obuna kanallari: qo'shish, o'chirish va tekshirish.",
       [
           ("➕ Kanal qo'shish", "chan_add"),
           ("➖ Kanal o'chirish", "chan_del"),
       ],
       parent="ahome")

screen("mid", "admin", "chan_add", "➕ Kanal qo'shish",
       "Kanal ID yoki <code>@username</code> yuboriladi, bot admin "
       "qilinadi.",
       parent="chan")

screen("mid", "admin", "chan_del", "➖ Kanal o'chirish",
       "Ro'yxatdan tanlanadi, obuna talabi olib tashlanadi.",
       parent="chan")

screen("mid", "admin", "users", "👥 Foydalanuvchilar",
       "Ro'yxat: ID, ism, VIP holati, balans. Qidirish va boshqarish.",
       parent="ahome")

screen("mid", "admin", "ban", "🚫 Ban/Unban",
       "ID yuboriladi: foydalanuvchi bloklanadi yoki blokdan chiqariladi.",
       parent="ahome")

screen("mid", "admin", "anal", "📈 Analitika",
       "Kunlik faollik, ko'rishlar, qidiruvlar va konversiya.",
       parent="ahome")

screen("mid", "admin", "expe", "📤 Eksport",
       "Baza JSON fayl qilib yuboriladi.",
       parent="ahome")

screen("mid", "admin", "impi", "📥 Import",
       "JSON yoki ZIP yuboriladi, <code>/done</code> bilan tasdiqlanadi.",
       parent="ahome")

screen("mid", "admin", "prem", "💎 Premium",
       "Tariflar, narxlar, karta va kanal sozlamalari.",
       parent="ahome")

screen("mid", "admin", "sett", "⚙️ Sozlamalar",
       "Til, support, karta raqami va egasi, 1 oylik/umrlik narx, "
       "admin contact.",
       parent="ahome")

screen("mid", "admin", "backup", "💾 Zaxira",
       "JSON zaxira olish, tiklash va zaxira kanalini sozlash.",
       [
           ("💾 Zaxira olish", "bk_send"),
           ("♻️ Zaxirani tiklash", "bk_restore"),
           ("🗄 Zaxira kanali", "bk_chan"),
       ],
       parent="ahome")

screen("mid", "admin", "bk_send", "💾 Zaxira olish",
       "Barcha ma'lumot bitta JSON faylda zaxira kanalga yuboriladi.",
       parent="backup")

screen("mid", "admin", "bk_restore", "♻️ Zaxirani tiklash",
       "Fayl yuborilib <code>/done</code> yoziladi — ma'lumot aynan "
       "zaxiradagi holatga qaytadi.",
       parent="backup")

screen("mid", "admin", "bk_chan", "🗄 Zaxira kanali",
       "Zaxira nusxa saqlanadigan kanalni o'zgartirish.",
       parent="backup")


# =====================================================================
#  O'RTACHA MUKAMMAL BOT — OWNER
# =====================================================================

screen("mid", "owner", "ohome", "👑 Owner rejimi",
       "Mijoz botida alohida owner paneli yo'q: <code>ADMIN_IDS</code> "
       "dagi hisob owner hisoblanadi.\n\n"
       "Bu yerda eng muhim owner darajasidagi bo'limlar ko'rsatilgan.",
       [
           ("⚙️ Sozlamalar", "@mid:admin:sett"),
           ("💎 Premium narxlari", "@mid:admin:prem"),
           ("💾 Zaxira", "@mid:admin:backup"),
           ("📣 Kanallar", "@mid:admin:chan"),
           ("🚫 Ban/Unban", "@mid:admin:ban"),
           ("👥 Foydalanuvchilar", "@mid:admin:users"),
           ("📈 Analitika", "@mid:admin:anal"),
           ("📤 Eksport / 📥 Import", "@mid:admin:expe"),
           ("🛠 To'liq admin panel", "@mid:admin:ahome"),
           ("👤 User menyusi", "@mid:user:uhome"),
       ])


# ---------------- ekranlarni tekshirish ----------------

def validate_screens():
    problems = []
    for (b, r, k), sc in SCREENS.items():
        for label, target in sc["buttons"]:
            tb, tr, tk = resolve(b, r, target)
            if (tb, tr, tk) not in SCREENS:
                problems.append(f"{b}/{r}/{k} → {tb}/{tr}/{tk} ({label})")
        if sc["parent"]:
            pb, pr, pk = resolve(b, r, sc["parent"])
            if (pb, pr, pk) not in SCREENS:
                problems.append(f"{b}/{r}/{k} → parent {pb}/{pr}/{pk}")
    for role in ROLES:
        for b in ("pro", "mid"):
            if (b, role, HOME_KEYS[role]) not in SCREENS:
                problems.append(f"home yo'q: {b}/{role}")
    return problems


# ---------------- klaviaturalar ----------------

def start_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏆 Mukammal bot", callback_data="demo:bot:pro")],
        [InlineKeyboardButton(text="⚙️ O'rtacha mukammal bot", callback_data="demo:bot:mid")],
        [InlineKeyboardButton(text="ℹ️ Ikki botning farqi", callback_data="demo:about")],
    ])


def role_kb(bot_key):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 User sifatida kirish",
                              callback_data=f"demo:role:{bot_key}:user")],
        [InlineKeyboardButton(text="🛠 Admin sifatida kirish",
                              callback_data=f"demo:role:{bot_key}:admin")],
        [InlineKeyboardButton(text="👑 Owner sifatida kirish",
                              callback_data=f"demo:role:{bot_key}:owner")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="demo:start")],
    ])


async def show(cq, text, kb):
    try:
        await cq.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc):
            return
        await cq.message.answer(text, reply_markup=kb)


# ---------------- handlerlar ----------------

@dp.message(CommandStart())
async def cmd_start(m: Message, state: FSMContext):
    await state.clear()
    await m.answer(START_TEXT, reply_markup=start_kb())


@dp.message(Command("panel", "menu"))
async def cmd_panel(m: Message, state: FSMContext):
    data = await state.get_data()
    bot_key, role = data.get("bot"), data.get("role")
    if (bot_key, role) not in [(b, r) for b in ("pro", "mid") for r in ROLES]:
        return await m.answer(START_TEXT, reply_markup=start_kb())
    text, kb = render(bot_key, role, HOME_KEYS[role])
    await m.answer(text, reply_markup=kb)


@dp.message(Command("help"))
async def cmd_help(m: Message):
    await m.answer(
        "🧪 <b>Demo bot qo'llanmasi</b>\n\n"
        "• /start — boshidan boshlash\n"
        "• /panel — joriy panelga qaytish\n"
        "• «Rol tanlash» — bot turi va rolni almashtirish\n"
        "• Har bir tugma — haqiqiy botdagi funksiyani tushuntiradi\n\n"
        "User rejimida chatga matn yozib, qidiruv namunasini ko'rish mumkin.")


@dp.callback_query(F.data == "demo:start")
async def cb_start(cq: CallbackQuery, state: FSMContext):
    await state.clear()
    await show(cq, START_TEXT, start_kb())
    await cq.answer()


@dp.callback_query(F.data == "demo:about")
async def cb_about(cq: CallbackQuery):
    await show(cq, ABOUT_TEXT, InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="demo:start")]]))
    await cq.answer()


@dp.callback_query(F.data.startswith("demo:bot:"))
async def cb_bot(cq: CallbackQuery, state: FSMContext):
    parts = cq.data.split(":")
    if len(parts) != 3 or parts[2] not in ("pro", "mid"):
        return await cq.answer("❌ Noma'lum bot", show_alert=True)
    bot_key = parts[2]
    await state.update_data(bot=bot_key, role=None)
    text = PRO_INTRO if bot_key == "pro" else MID_INTRO
    await show(cq, text, role_kb(bot_key))
    await cq.answer()


@dp.callback_query(F.data.startswith("demo:role:"))
async def cb_role(cq: CallbackQuery, state: FSMContext):
    parts = cq.data.split(":")
    if len(parts) != 4 or parts[2] not in ("pro", "mid") or parts[3] not in ROLES:
        return await cq.answer("❌ Noma'lum rol", show_alert=True)
    bot_key, role = parts[2], parts[3]
    await state.update_data(bot=bot_key, role=role)
    text, kb = render(bot_key, role, HOME_KEYS[role])
    await show(cq, text, kb)
    await cq.answer()


@dp.callback_query(F.data.startswith("demo:s:"))
async def cb_screen(cq: CallbackQuery, state: FSMContext):
    parts = cq.data.split(":")
    if len(parts) != 5:
        return await cq.answer("❌ Noma'lum bo'lim", show_alert=True)
    _, _, bot_key, role, key = parts
    if (bot_key, role, key) not in SCREENS:
        return await cq.answer("⚠️ Bu bo'lim topilmadi", show_alert=True)
    await state.update_data(bot=bot_key, role=role)
    text, kb = render(bot_key, role, key)
    await show(cq, text, kb)
    await cq.answer()


@dp.message(F.chat.type == "private", F.text, ~F.text.startswith("/"))
async def on_text(m: Message, state: FSMContext):
    data = await state.get_data()
    bot_key, role = data.get("bot"), data.get("role")
    if bot_key not in ("pro", "mid") or role not in ROLES:
        return await m.answer(START_TEXT, reply_markup=start_kb())
    query = m.text.strip()
    if not query:
        return
    if role == "user":
        text = (
            f"🔎 <b>Namoyish qidiruvi</b>\n\n"
            f"Siz yozdingiz: «{he(query)}»\n\n"
            "Haqiqiy botda shu o'rinda:\n"
            "• kod bo'lsa — kartochka ochiladi;\n"
            "• nom bo'lsa — mos kinolar ro'yxati chiqadi;\n"
            "• topilmasa — «❌ Hech narsa topilmadi».\n\n"
            "👇 Namunani ko'ring."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎬 Namuna kartochka",
                                  callback_data=target_cb(bot_key, role, "card"))],
            [InlineKeyboardButton(text="⬅️ Menyuga qaytish",
                                  callback_data=target_cb(bot_key, role, "uhome"))],
        ])
        return await m.answer(text, reply_markup=kb)
    await m.answer(
        "🛠 <b>Admin/owner rejimi</b>\n\n"
        "Bu rejimda matn yozish faqat wizard ichida ishlatiladi "
        "(masalan, kino nomi yoki qism raqami).\n\n"
        "Boshqarish uchun tugmalardan foydalaning.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Panelga qaytish",
                                  callback_data=target_cb(bot_key, role, HOME_KEYS[role]))],
        ]),
    )


# ---------------- ishga tushirish ----------------

async def main():
    print("[1/4] Demo bot ishga tushmoqda...", flush=True)
    problems = validate_screens()
    if problems:
        print(f"[!] {len(problems)} ta muammo topildi:", flush=True)
        for item in problems:
            print("   -", item, flush=True)
    else:
        print("[2/4] Menyu tekshirildi: barcha havolalar joyida.", flush=True)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception as exc:
        print(f"[!] delete_webhook: {exc}", flush=True)
    print("[3/4] Polling boshlandi.", flush=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        print(f"Bot xato bilan to'xtadi:\n{traceback.format_exc()}", flush=True)
        sys.exit(1)
