import json
import os
import re
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import instaloader
import yt_dlp
from datetime import datetime

# تنظیم لاگ
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# توکن و آیدی
TELEGRAM_TOKEN = "6356625866:AAGHHjzULscEYra8NUzRjSpXCSPl4lDxNJI"
MAIN_ADMIN_ID = 550076399
DATA_FILE = "/home/Amimoniya/bot_data.json"
STATS_FILE = "/home/Amimoniya/bot_stats.json"

# تنظیمات اینستالودر
L = instaloader.Instaloader()

# دیتابیس اولیه
INITIAL_DATA = {
    "users": [],
    "admins": [{"user_id": MAIN_ADMIN_ID, "permissions": ["all"]}],
    "commands": {
        "start": "🎉 به ربات دانلود اینستا و یوتیوب خوش اومدی! لینک اینستا یا یوتیوب بفرست.",
        "help": "📚 راهنما:\nلینک اینستا (پست، ریلز، پروفایل) یا یوتیوب بفرست.\n/admins برای مدیریت ادمین‌ها\n/stats برای آمار ربات"
    },
    "sections": ["instagram", "youtube"]
}

# مقداردهی اولیه فایل‌ها
def init_data():
    try:
        if not os.path.exists(DATA_FILE):
            with open(DATA_FILE, "w") as f:
                json.dump(INITIAL_DATA, f, ensure_ascii=False, indent=2)
        if not os.path.exists(STATS_FILE):
            with open(STATS_FILE, "w") as f:
                json.dump({"downloads": {}, "section_usage": {}}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error initializing data: {str(e)}")

# ذخیره داده‌ها
def save_data(data, file_path):
    try:
        with open(file_path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving data to {file_path}: {str(e)}")

# لود داده‌ها
def load_data(file_path):
    try:
        if not os.path.exists(file_path):
            init_data()
        with open(file_path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading data from {file_path}: {str(e)}")
        return INITIAL_DATA if file_path == DATA_FILE else {"downloads": {}, "section_usage": {}}

# ثبت کاربر
def register_user(user_id, username):
    data = load_data(DATA_FILE)
    if not any(u["user_id"] == user_id for u in data["users"]):
        data["users"].append({"user_id": user_id, "username": username, "join_date": str(datetime.now())})
        save_data(data, DATA_FILE)
        logger.info(f"User {username} ({user_id}) registered")

# ثبت آمار دانلود
def log_download(user_id, content_type, content_id):
    stats = load_data(STATS_FILE)
    key = f"{content_type}_{content_id}"
    stats["downloads"][key] = stats["downloads"].get(key, 0) + 1
    stats["section_usage"][content_type] = stats["section_usage"].get(content_type, 0) + 1
    save_data(stats, STATS_FILE)

# گرفتن آمار
def get_stats():
    data = load_data(DATA_FILE)
    stats = load_data(STATS_FILE)
    user_count = len(data["users"])
    popular_sections = sorted(stats["section_usage"].items(), key=lambda x: x[1], reverse=True)
    popular_downloads = sorted(stats["downloads"].items(), key=lambda x: x[1], reverse=True)[:5]
    return (
        f"👥 تعداد اعضا: {user_count}\n"
        f"📊 محبوب‌ترین بخش‌ها:\n" + "\n".join(f"{k}: {v} استفاده" for k, v in popular_sections) +
        f"\n📥 محبوب‌ترین دانلودها:\n" + "\n".join(f"{k}: {v} دانلود" for k, v in popular_downloads)
    )

# گرفتن لیست کاربران
def get_users():
    data = load_data(DATA_FILE)
    return "\n".join(f"{u['username']} ({u['user_id']})" for u in data["users"]) or "هیچ کاربری نیست!"

# افزودن ادمین
def add_admin(user_id, username, permissions):
    data = load_data(DATA_FILE)
    data["admins"] = [a for a in data["admins"] if a["user_id"] != user_id]
    data["admins"].append({"user_id": user_id, "username": username, "permissions": permissions})
    save_data(data, DATA_FILE)
    logger.info(f"Admin {username} added with permissions: {','.join(permissions)}")

# چک کردن دسترسی ادمین
def check_admin_permission(user_id, permission):
    data = load_data(DATA_FILE)
    for admin in data["admins"]:
        if admin["user_id"] == user_id and ("all" in admin["permissions"] or permission in admin["permissions"]):
            return True
    return False

# دانلود از اینستاگرام
async def download_instagram(update: Update, context: ContextTypes.DEFAULT_TYPE, url):
    try:
        if "/p/" in url or "/reel/" in url:
            post = instaloader.Post.from_shortcode(L.context, url.split("/")[-2])
            caption = post.caption or "بدون کپشن"
            likes = post.likes
            comments = post.comments
            views = post.video_view_count if post.is_video else 0
            response = (
                f"📸 پست: {post.title or 'بدون عنوان'}\n"
                f"📝 کپشن: {caption[:200]}...\n"
                f"❤️ لایک: {likes}\n"
                f"💬 کامنت: {comments}\n"
                f"👀 بازدید: {views if views else 'نامشخص'}"
            )
            file_path = f"temp_{post.shortcode}.mp4" if post.is_video else f"temp_{post.shortcode}.jpg"
            L.download_post(post, target=file_path)
            log_download(update.effective_user.id, "instagram_post", post.shortcode)
            if post.is_video:
                await update.message.reply_video(video=open(file_path, "rb"), caption=response)
            else:
                await update.message.reply_photo(photo=open(file_path, "rb"), caption=response)
            os.remove(file_path)
        elif "/stories/" in url:
            username = url.split("/")[-2]
            profile = instaloader.Profile.from_username(L.context, username)
            if not profile.is_private:
                stories = L.get_stories(userids=[profile.userid])
                for story in stories:
                    for item in story.get_items():
                        file_path = f"temp_{item.mediaid}.mp4" if item.is_video else f"temp_{item.mediaid}.jpg"
                        L.download_storyitem(item, target=file_path)
                        log_download(update.effective_user.id, "instagram_story", item.mediaid)
                        if item.is_video:
                            await update.message.reply_video(video=open(file_path, "rb"), caption=f"استوری از {username}")
                        else:
                            await update.message.reply_photo(photo=open(file_path, "rb"), caption=f"استوری از {username}")
                        os.remove(file_path)
            else:
                await update.message.reply_text("این اکانت خصوصی است!")
        else:
            username = url.split("/")[-1].replace("?", "")
            profile = instaloader.Profile.from_username(L.context, username)
            response = (
                f"👤 پروفایل: {username}\n"
                f"👥 فالوور: {profile.followers}\n"
                f"➡️ فالووینگ: {profile.followees}\n"
                f"📷 تعداد پست: {profile.mediacount}"
            )
            L.download_profilepic(profile)
            file_path = f"{username}_profile_pic.jpg"
            log_download(update.effective_user.id, "instagram_profile", username)
            await update.message.reply_photo(photo=open(file_path, "rb"), caption=response)
            os.remove(file_path)
            if not profile.is_private:
                keyboard = [
                    [InlineKeyboardButton("📸 پست‌ها", callback_data=f"posts_{username}")],
                    [InlineKeyboardButton("🌟 هایلایت‌ها", callback_data=f"highlights_{username}")]
                ]
                await update.message.reply_text("انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"Error downloading Instagram content: {str(e)}")
        await update.message.reply_text(f"خطا در دانلود: {str(e)}")

# دانلود از یوتیوب
async def download_youtube(update: Update, context: ContextTypes.DEFAULT_TYPE, url):
    try:
        ydl_opts = {
            "format": "bestvideo[height<=720]+bestaudio/best[height<=720]",
            "outtmpl": "temp_%(id)s.%(ext)s",
            "merge_output_format": "mp4"
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = f"temp_{info['id']}.mp4"
            title = info.get("title", "بدون عنوان")
            views = info.get("view_count", 0)
            likes = info.get("like_count", 0)
            response = f"🎥 عنوان: {title}\n👀 بازدید: {views}\n❤️ لایک: {likes}"
            log_download(update.effective_user.id, "youtube_video", info["id"])
            await update.message.reply_video(video=open(file_path, "rb"), caption=response)
            os.remove(file_path)
    except Exception as e:
        logger.error(f"Error downloading YouTube content: {str(e)}")
        await update.message.reply_text(f"خطا در دانلود: {str(e)}")

# تابع شروع
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    register_user(user_id, username)
    data = load_data(DATA_FILE)
    keyboard = [
        [InlineKeyboardButton("📥 دانلود اینستا", callback_data="section_instagram")],
        [InlineKeyboardButton("🎥 دانلود یوتیوب", callback_data="section_youtube")],
        [InlineKeyboardButton("🎛 مدیریت (ادمین)", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(data["commands"]["start"], reply_markup=reply_markup)

# منوی بخش‌ها
async def section_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    section = query.data.split("_")[1]
    keyboard = [[InlineKeyboardButton("⬅️ بازگشت", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text(f"لینک {section} رو بفرست:", reply_markup=reply_markup)
    context.user_data["section"] = section

# منوی اصلی
async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("📥 دانلود اینستا", callback_data="section_instagram")],
        [InlineKeyboardButton("🎥 دانلود یوتیوب", callback_data="section_youtube")],
        [InlineKeyboardButton("🎛 مدیریت (ادمین)", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text("🎉 منوی اصلی:", reply_markup=reply_markup)

# منوی ادمین
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not check_admin_permission(user_id, "manage"):
        await query.message.reply_text("فقط ادمین‌ها دسترسی دارن!")
        return
    keyboard = [
        [InlineKeyboardButton("📊 آمار ربات", callback_data="stats")],
        [InlineKeyboardButton("👥 لیست کاربران", callback_data="users")],
        [InlineKeyboardButton("➕ افزودن ادمین", callback_data="add_admin")],
        [InlineKeyboardButton("📝 تغییر پیام خوش‌آمد", callback_data="change_welcome")],
        [InlineKeyboardButton("🆕 افزودن بخش جدید", callback_data="add_section")],
        [InlineKeyboardButton("📜 افزودن/تغییر دستور", callback_data="manage_commands")],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text("🎛 پنل مدیریت:", reply_markup=reply_markup)

# نمایش پست‌های اینستا
async def show_posts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    username = query.data.split("_")[1]
    profile = instaloader.Profile.from_username(L.context, username)
    if profile.is_private:
        await query.message.reply_text("این اکانت خصوصی است!")
        return
    posts = list(profile.get_posts())[:5]
    if not posts:
        keyboard = [[InlineKeyboardButton("⬅️ بازگشت", callback_data="main_menu")]]
        await query.message.edit_text("هیچ پستی پیدا نشد!", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    keyboard = []
    for post in posts:
        keyboard.append([InlineKeyboardButton(post.title or "پست", callback_data=f"post_{post.shortcode}")])
    keyboard.append([InlineKeyboardButton("⬅️ بازگشت", callback_data="main_menu")])
    await query.message.edit_text(f"پست‌های {username}:", reply_markup=InlineKeyboardMarkup(keyboard))

# نمایش هایلایت‌ها
async def show_highlights(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    username = query.data.split("_")[1]
    profile = instaloader.Profile.from_username(L.context, username)
    if profile.is_private:
        await query.message.reply_text("این اکانت خصوصی است!")
        return
    highlights = L.get_highlights(profile)
    if not highlights:
        keyboard = [[InlineKeyboardButton("⬅️ بازگشت", callback_data="main_menu")]]
        await query.message.edit_text("هیچ هایلایتی پیدا نشد!", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    keyboard = []
    for highlight in highlights:
        keyboard.append([InlineKeyboardButton(highlight.title, callback_data=f"highlight_{highlight.unique_id}")])
    keyboard.append([InlineKeyboardButton("⬅️ بازگشت", callback_data="main_menu")])
    await query.message.edit_text(f"هایلایت‌های {username}:", reply_markup=InlineKeyboardMarkup(keyboard))

# نمایش پست
async def show_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    shortcode = query.data.split("_")[1]
    post = instaloader.Post.from_shortcode(L.context, shortcode)
    caption = post.caption or "بدون کپشن"
    likes = post.likes
    comments = post.comments
    views = post.video_view_count if post.is_video else 0
    response = (
        f"📸 پست: {post.title or 'بدون عنوان'}\n"
        f"📝 کپشن: {caption[:200]}...\n"
        f"❤️ لایک: {likes}\n"
        f"💬 کامنت: {comments}\n"
        f"👀 بازدید: {views if views else 'نامشخص'}"
    )
    file_path = f"temp_{post.shortcode}.mp4" if post.is_video else f"temp_{post.shortcode}.jpg"
    L.download_post(post, target=file_path)
    log_download(query.from_user.id, "instagram_post", post.shortcode)
    keyboard = [[InlineKeyboardButton("⬅️ بازگشت", callback_data="main_menu")]]
    if post.is_video:
        await query.message.reply_video(video=open(file_path, "rb"), caption=response, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await query.message.reply_photo(photo=open(file_path, "rb"), caption=response, reply_markup=InlineKeyboardMarkup(keyboard))
    os.remove(file_path)

# نمایش هایلایت
async def show_highlight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    unique_id = query.data.split("_")[1]
    highlights = L.get_highlights(instaloader.Profile.from_username(L.context, query.data.split("_")[1]))
    for highlight in highlights:
        if str(highlight.unique_id) == unique_id:
            for item in highlight.get_items():
                file_path = f"temp_{item.mediaid}.mp4" if item.is_video else f"temp_{item.mediaid}.jpg"
                L.download_storyitem(item, target=file_path)
                log_download(query.from_user.id, "instagram_highlight", item.mediaid)
                keyboard = [[InlineKeyboardButton("⬅️ بازگشت", callback_data="main_menu")]]
                if item.is_video:
                    await query.message.reply_video(video=open(file_path, "rb"), caption=f"هایلایت: {highlight.title}", reply_markup=InlineKeyboardMarkup(keyboard))
                else:
                    await query.message.reply_photo(photo=open(file_path, "rb"), caption=f"هایلایت: {highlight.title}", reply_markup=InlineKeyboardMarkup(keyboard))
                os.remove(file_path)
            break

# آمار ربات
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not check_admin_permission(query.from_user.id, "stats"):
        await query.message.reply_text("فقط ادمین‌ها دسترسی دارن!")
        return
    response = get_stats()
    keyboard = [[InlineKeyboardButton("⬅️ بازگشت", callback_data="admin_panel")]]
    await query.message.edit_text(response, reply_markup=InlineKeyboardMarkup(keyboard))

# لیست کاربران
async def users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not check_admin_permission(query.from_user.id, "users"):
        await query.message.reply_text("فقط ادمین‌ها دسترسی دارن!")
        return
    response = get_users()
    keyboard = [[InlineKeyboardButton("⬅️ بازگشت", callback_data="admin_panel")]]
    await query.message.edit_text(f"👥 کاربران:\n{response}", reply_markup=InlineKeyboardMarkup(keyboard))

# افزودن ادمین
async def add_admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not check_admin_permission(query.from_user.id, "manage_admins"):
        await query.message.reply_text("فقط ادمین اصلی می‌تونه ادمین اضافه کنه!")
        return
    context.user_data["state"] = "add_admin_id"
    keyboard = [[InlineKeyboardButton("⬅️ لغو", callback_data="admin_panel")]]
    await query.message.edit_text("آیدی عددی ادمین جدید رو وارد کنید:", reply_markup=InlineKeyboardMarkup(keyboard))

# تغییر پیام خوش‌آمد
async def change_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not check_admin_permission(query.from_user.id, "manage_commands"):
        await query.message.reply_text("فقط ادمین‌ها دسترسی دارن!")
        return
    context.user_data["state"] = "change_welcome"
    keyboard = [[InlineKeyboardButton("⬅️ لغو", callback_data="admin_panel")]]
    await query.message.edit_text("پیام خوش‌آمد جدید رو وارد کنید:", reply_markup=InlineKeyboardMarkup(keyboard))

# افزودن بخش جدید
async def add_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not check_admin_permission(query.from_user.id, "manage_sections"):
        await query.message.reply_text("فقط ادمین‌ها دسترسی دارن!")
        return
    context.user_data["state"] = "add_section"
    keyboard = [[InlineKeyboardButton("⬅️ لغو", callback_data="admin_panel")]]
    await query.message.edit_text("نام بخش جدید رو وارد کنید:", reply_markup=InlineKeyboardMarkup(keyboard))

# مدیریت دستورات
async def manage_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not check_admin_permission(query.from_user.id, "manage_commands"):
        await query.message.reply_text("فقط ادمین‌ها دسترسی دارن!")
        return
    context.user_data["state"] = "manage_commands"
    keyboard = [[InlineKeyboardButton("⬅️ لغو", callback_data="admin_panel")]]
    await query.message.edit_text("نام دستور جدید یا موجود (مثل /help) و متنش رو وارد کنید (فرمت: /command متن):", reply_markup=InlineKeyboardMarkup(keyboard))

# مدیریت پیام‌ها
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    state = context.user_data.get("state")

    try:
        if state == "add_admin_id":
            if not text.isdigit():
                await update.message.reply_text("لطفاً آیدی عددی معتبر وارد کنید!")
                return
            context.user_data["admin_id"] = int(text)
            context.user_data["state"] = "add_admin_username"
            await update.message.reply_text("یوزرنیم ادمین (بدون @) رو وارد کنید:")
        elif state == "add_admin_username":
            context.user_data["admin_username"] = text
            context.user_data["state"] = "add_admin_permissions"
            await update.message.reply_text("دسترسی‌ها رو وارد کنید (مثل stats,manage_admins با کاما):")
        elif state == "add_admin_permissions":
            permissions = text.split(",")
            add_admin(context.user_data["admin_id"], context.user_data["admin_username"], permissions)
            context.user_data.clear()
            await update.message.reply_text("ادمین جدید اضافه شد! 👤")
        elif state == "change_welcome":
            data = load_data(DATA_FILE)
            data["commands"]["start"] = text
            save_data(data, DATA_FILE)
            context.user_data.clear()
            await update.message.reply_text("پیام خوش‌آمد تغییر کرد!")
        elif state == "add_section":
            data = load_data(DATA_FILE)
            if text not in data["sections"]:
                data["sections"].append(text)
                save_data(data, DATA_FILE)
                await update.message.reply_text(f"بخش {text} اضافه شد!")
            else:
                await update.message.reply_text("این بخش قبلاً وجود داره!")
            context.user_data.clear()
        elif state == "manage_commands":
            match = re.match(r"^/(\w+)\s+(.+)$", text)
            if not match:
                await update.message.reply_text("فرمت اشتباه! مثال: /help متن جدید")
                return
            command, message = match.groups()
            data = load_data(DATA_FILE)
            data["commands"][command] = message
            save_data(data, DATA_FILE)
            context.user_data.clear()
            await update.message.reply_text(f"دستور /{command} اضافه/تغییر کرد!")
        elif re.match(r"https?://(www\.)?(instagram\.com|youtu\.be|youtube\.com)", text):
            section = context.user_data.get("section", "instagram")
            if "instagram.com" in text:
                await download_instagram(update, context, text)
            elif "youtu.be" in text or "youtube.com" in text:
                await download_youtube(update, context, text)
        else:
            keyboard = [[InlineKeyboardButton("🎉 منوی اصلی", callback_data="main_menu")]]
            await update.message.reply_text(
                "لطفاً لینک اینستا یا یوتیوب بفرستید یا از دکمه‌ها استفاده کنید!",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    except Exception as e:
        logger.error(f"Error in handle_message: {str(e)}")
        await update.message.reply_text(f"خطا: {str(e)}")

# تابع اصلی
def main():
    try:
        init_data()
        app = Application.builder().token(TELEGRAM_TOKEN).build()

        # دستورات
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CallbackQueryHandler(main_menu, pattern="^main_menu$"))
        app.add_handler(CallbackQueryHandler(section_menu, pattern="^section_.*$"))
        app.add_handler(CallbackQueryHandler(admin_panel, pattern="^admin_panel$"))
        app.add_handler(CallbackQueryHandler(stats, pattern="^stats$"))
        app.add_handler(CallbackQueryHandler(users, pattern="^users$"))
        app.add_handler(CallbackQueryHandler(add_admin_handler, pattern="^add_admin$"))
        app.add_handler(CallbackQueryHandler(change_welcome, pattern="^change_welcome$"))
        app.add_handler(CallbackQueryHandler(add_section, pattern="^add_section$"))
        app.add_handler(CallbackQueryHandler(manage_commands, pattern="^manage_commands$"))
        app.add_handler(CallbackQueryHandler(show_posts, pattern="^posts_.*$"))
        app.add_handler(CallbackQueryHandler(show_highlights, pattern="^highlights_.*$"))
        app.add_handler(CallbackQueryHandler(show_post, pattern="^post_.*$"))
        app.add_handler(CallbackQueryHandler(show_highlight, pattern="^highlight_.*$"))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        logger.info("ربات شروع شد! 🎉")
        app.run_polling()
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        raise

if __name__ == "__main__":
    main()
