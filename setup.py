import asyncio
import logging
import re
from pyrogram import Client, filters, enums, raw
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import AuthKeyInvalid, SessionRevoked, UserDeactivated, FloodWait
from datetime import datetime

# ==================== KONFIGURASI (PAKAI PUNYA LO) ====================
API_ID = 32170185
API_HASH = "27fdeb3b05889ef614903a87cada5e72"
BOT_TOKEN = "8573079275:AAFW4xI2BwmjuSm_kdzGHWVjAWqMiPj5HBM"

logging.basicConfig(level=logging.INFO)
bot = Client("zieesecuritybot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_sessions = {}

# ==================== HELPERS DETAIL AKUN ====================
async def get_full_details(app, me):
    # CEK 2FA YANG AKURAT
    try:
        password_info = await app.invoke(raw.functions.account.GetPassword())
        
        if hasattr(password_info, 'has_password'):
            pwd_status = "✅ AKTIF" if password_info.has_password else "❌ TIDAK AKTIF"
        elif hasattr(password_info, 'current_algo') and password_info.current_algo:
            pwd_status = "✅ AKTIF"
        else:
            pwd_status = "❌ TIDAK AKTIF"
    except Exception as e:
        if "PASSWORD_HASH_INVALID" in str(e) or "password" in str(e).lower():
            pwd_status = "✅ AKTIF"
        else:
            pwd_status = "⚠️ GAGAL DETEKSI"
    
    # Ambil Daftar Device
    auths = await app.invoke(raw.functions.account.GetAuthorizations())
    dev_list = ""
    current_hash = None
    
    for i, auth in enumerate(auths.authorizations, 1):
        status = "🔵 AKTIF INI" if auth.current else ""
        if auth.current:
            current_hash = auth.hash
        
        dev_model = auth.device_model or "Unknown Device"
        platform = auth.platform or "Unknown Platform"
        system_ver = auth.system_version or "Unknown OS"
        country = auth.country or "Unknown"
        ip = auth.ip or "Unknown IP"
        date_active = datetime.fromtimestamp(auth.date_active).strftime('%d/%m/%Y %H:%M:%S')
        app_name = auth.app_name or "Telegram"
        
        dev_list += (
            f"{i}. {status}\n"
            f"   📱 **App:** {app_name}\n"
            f"   📱 **Device:** {dev_model}\n"
            f"   💻 **Platform:** {platform}\n"
            f"   🌐 **OS:** {system_ver}\n"
            f"   📍 **Lokasi:** {country}\n"
            f"   📡 **IP:** {ip}\n"
            f"   🕒 **Terakhir:** {date_active}\n\n"
        )
    return pwd_status, dev_list, auths.authorizations, current_hash

def format_main_text(me, pwd, dev_list, device_count, otp=None):
    phone = getattr(me, 'phone_number', '-')
    if phone != '-':
        phone = f"+{phone}"
    
    text = (
        f"🔐 **DETAIL AKUN TELEGRAM**\n\n"
        f"👤 **Nama:** {me.first_name} {me.last_name or ''}\n"
        f"👤 **Username:** @{me.username or '-'}\n"
        f"🆔 **User ID:** `{me.id}`\n"
        f"📞 **Nomor:** `{phone}`\n"
        f"🌟 **Premium:** {'✅ Ya' if me.is_premium else '❌ Tidak'}\n\n"
        f"🔐 **2FA (Two Factor Authentication)**\n"
        f"└ **Status:** {pwd}\n\n"
        f"📱 **DAFTAR DEVICE AKTIF ({device_count})**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{dev_list}"
    )
    if otp:
        text += f"\n🔑 **OTP TERBARU:** `{otp['code']}`\n⏰ **Waktu:** {otp['time']}"
    return text

# ==================== KEYBOARDS ====================
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh Data", callback_data="ref")],
        [InlineKeyboardButton("🔍 Cek OTP Masuk", callback_data="otp")],
        [InlineKeyboardButton("📱 Logout Device Tertentu", callback_data="list_kick")],
        [InlineKeyboardButton("🚪 Logout Semua Device (Kecuali Bot)", callback_data="out_all")],
        [InlineKeyboardButton("🔐 Reset Password Akun", callback_data="reset_pwd")],
        [InlineKeyboardButton("❌ Logout dari Bot", callback_data="bot_out")],
        [InlineKeyboardButton("❓ Bantuan", callback_data="hlp")]
    ])

def device_list_menu(authorizations, current_hash):
    buttons = []
    for auth in authorizations:
        if auth.hash != current_hash:
            device_name = auth.device_model or "Unknown Device"
            platform = auth.platform or "Unknown"
            location = auth.country or "Unknown"
            app_name = auth.app_name or "Telegram"
            
            buttons.append([
                InlineKeyboardButton(
                    f"❌ {app_name} - {device_name} ({platform}) - {location}",
                    callback_data=f"kick_{auth.hash}"
                )
            ])
    
    buttons.append([InlineKeyboardButton("⬅️ Kembali ke Menu", callback_data="back_main")])
    
    if not buttons:
        buttons = [[InlineKeyboardButton("⚠️ Tidak ada device lain", callback_data="none")]]
        buttons.append([InlineKeyboardButton("⬅️ Kembali", callback_data="back_main")])
    
    return InlineKeyboardMarkup(buttons)

# ==================== HANDLERS ====================
@bot.on_message(filters.command("start"))
async def start_cmd(_, message):
    await message.reply(
        "🤖 **BOT RECOVERY AKUN TELEGRAM**\n\n"
        "📌 **Cara Penggunaan:**\n"
        "1. Kirim **String Session** Pyrogram\n"
        "2. Bot akan menampilkan detail akun\n"
        "3. Pilih aksi yang diinginkan\n\n"
        "⚠️ **Peringatan:**\n"
        "• Jangan share string session ke siapapun\n"
        "• Bot ini hanya menyimpan session sementara\n"
        "• Logout dari bot untuk hapus session\n\n"
        "📥 Kirim string session sekarang!",
        parse_mode=enums.ParseMode.MARKDOWN
    )

@bot.on_message(filters.text & filters.private)
async def handle_session(_, message):
    # Cek apakah ini string session (minimal 50 karakter)
    if len(message.text) < 50:
        return
    
    msg = await message.reply("🔄 **Memproses string session...**\n\n⏳ Mohon tunggu, sedang mengambil data akun...")
    
    session_string = "".join(message.text.split())
    
    try:
        app = Client(
            f"user_{message.chat.id}",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=session_string,
            in_memory=True
        )
        
        await app.start()
        me = await app.get_me()
        pwd_status, dev_list, auths, current_hash = await get_full_details(app, me)
        
        user_sessions[message.chat.id] = {
            'client': app,
            'user': me,
            'otp': None,
            'current_hash': current_hash
        }
        
        await msg.edit_text(
            format_main_text(me, pwd_status, dev_list, len(auths)),
            reply_markup=main_menu(),
            parse_mode=enums.ParseMode.MARKDOWN
        )
        
    except FloodWait as e:
        await msg.edit_text(f"⏳ **Terjadi flood!**\n\nHarap tunggu {e.value} detik sebelum mencoba lagi.")
    except (AuthKeyInvalid, SessionRevoked, UserDeactivated) as e:
        await msg.edit_text(f"❌ **Session tidak valid!**\n\nError: `{str(e)}`\n\nString session sudah di-revoke atau expired.\n\n**Solusi:** Generate ulang string session dari akun Telegram yang mau di-track.")
    except Exception as e:
        await msg.edit_text(f"❌ **Gagal login!**\n\nError: `{str(e)}`")
        logging.error(f"Error: {e}")

@bot.on_callback_query()
async def handle_callback(client, callback_query: CallbackQuery):
    user_id = callback_query.message.chat.id
    user_data = user_sessions.get(user_id)
    
    if not user_data:
        await callback_query.answer("❌ Sesi tidak ditemukan! Kirim ulang string session.", show_alert=True)
        return
    
    app = user_data['client']
    
    # ========== REFRESH DATA ==========
    if callback_query.data == "ref":
        await callback_query.answer("🔄 Refreshing data...")
        try:
            pwd_status, dev_list, auths, current_hash = await get_full_details(app, user_data['user'])
            user_data['current_hash'] = current_hash
            await callback_query.message.edit_text(
                format_main_text(user_data['user'], pwd_status, dev_list, len(auths), user_data.get('otp')),
                reply_markup=main_menu(),
                parse_mode=enums.ParseMode.MARKDOWN
            )
        except Exception as e:
            await callback_query.answer(f"Gagal refresh: {str(e)[:50]}", show_alert=True)
    
    # ========== KEMBALI KE MENU ==========
    elif callback_query.data == "back_main":
        await callback_query.answer("Kembali ke menu...")
        try:
            pwd_status, dev_list, auths, current_hash = await get_full_details(app, user_data['user'])
            await callback_query.message.edit_text(
                format_main_text(user_data['user'], pwd_status, dev_list, len(auths), user_data.get('otp')),
                reply_markup=main_menu(),
                parse_mode=enums.ParseMode.MARKDOWN
            )
        except Exception as e:
            await callback_query.answer(f"Gagal: {str(e)[:50]}", show_alert=True)
    
    # ========== LIST DEVICE UNTUK LOGOUT ==========
    elif callback_query.data == "list_kick":
        await callback_query.answer("📱 Mengambil daftar device...")
        try:
            auths = await app.invoke(raw.functions.account.GetAuthorizations())
            await callback_query.message.edit_text(
                "📱 **Pilih device yang akan di-logout:**\n\n"
                "⚠️ Device dengan 🔵 adalah device yang sedang aktif (BOT INI).\n"
                "Device aktif tidak bisa di-logout dari sini.\n\n"
                "Klik tombol device yang ingin dikeluarkan:",
                reply_markup=device_list_menu(auths.authorizations, user_data['current_hash']),
                parse_mode=enums.ParseMode.MARKDOWN
            )
        except Exception as e:
            await callback_query.answer(f"Gagal ambil daftar: {str(e)[:50]}", show_alert=True)
    
    # ========== LOGOUT DEVICE TERTENTU ==========
    elif callback_query.data.startswith("kick_"):
        hash_value = int(callback_query.data.split("_")[1])
        
        if hash_value == user_data['current_hash']:
            await callback_query.answer("❌ Tidak bisa logout sesi bot yang sedang aktif!", show_alert=True)
            return
        
        await callback_query.answer("🔄 Sedang me-logout device...")
        
        try:
            await app.invoke(raw.functions.account.ResetAuthorization(hash=hash_value))
            await callback_query.answer("✅ Berhasil me-logout device!", show_alert=True)
            
            pwd_status, dev_list, auths, current_hash = await get_full_details(app, user_data['user'])
            user_data['current_hash'] = current_hash
            await callback_query.message.edit_text(
                format_main_text(user_data['user'], pwd_status, dev_list, len(auths), user_data.get('otp')),
                reply_markup=main_menu(),
                parse_mode=enums.ParseMode.MARKDOWN
            )
            
        except FloodWait as e:
            await callback_query.answer(f"⏳ Flood! Tunggu {e.value} detik", show_alert=True)
        except Exception as e:
            await callback_query.answer(f"❌ Gagal logout: {str(e)[:50]}", show_alert=True)
    
    # ========== LOGOUT SEMUA DEVICE (KECUALI BOT) ==========
    elif callback_query.data == "out_all":
        confirm_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Ya, Logout Semua Device (Kecuali Bot)", callback_data="confirm_out_all")],
            [InlineKeyboardButton("❌ Batal", callback_data="back_main")]
        ])
        await callback_query.message.edit_text(
            "⚠️ **PERINGATAN!** ⚠️\n\n"
            "Kamu akan logout dari **SEMUA DEVICE** termasuk:\n"
            "• Telegram di HP\n"
            "• Telegram di PC/Laptop\n"
            "• Telegram Web\n"
            "• Dan device lainnya\n\n"
            "✅ **KECUALI device bot ini yang sedang kamu pakai.**\n\n"
            "Setelah ini, kamu harus login ulang di semua perangkat lain.\n\n"
            "**Yakin ingin melanjutkan?**",
            reply_markup=confirm_keyboard,
            parse_mode=enums.ParseMode.MARKDOWN
        )
    
    elif callback_query.data == "confirm_out_all":
        await callback_query.answer("🔄 Sedang me-logout semua device (kecuali bot)...")
        try:
            auths = await app.invoke(raw.functions.account.GetAuthorizations())
            
            success_count = 0
            fail_count = 0
            
            for auth in auths.authorizations:
                if auth.hash != user_data['current_hash']:
                    try:
                        await app.invoke(raw.functions.account.ResetAuthorization(hash=auth.hash))
                        success_count += 1
                    except Exception as e:
                        fail_count += 1
            
            if success_count > 0:
                await callback_query.answer(f"✅ Berhasil logout {success_count} device!", show_alert=True)
            else:
                await callback_query.answer("⚠️ Tidak ada device lain yang di-logout", show_alert=True)
            
            pwd_status, dev_list, auths, current_hash = await get_full_details(app, user_data['user'])
            user_data['current_hash'] = current_hash
            await callback_query.message.edit_text(
                format_main_text(user_data['user'], pwd_status, dev_list, len(auths), user_data.get('otp')),
                reply_markup=main_menu(),
                parse_mode=enums.ParseMode.MARKDOWN
            )
            
        except Exception as e:
            await callback_query.answer(f"❌ Gagal: {str(e)[:50]}", show_alert=True)
    
    # ========== CEK OTP (BENERAN AMBIL DARI INBOX) ==========
    elif callback_query.data == "otp":
        await callback_query.answer("🔍 Mencari OTP di inbox Telegram...")
        try:
            otp_found = False
            # Ambil 10 pesan terakhir dari Telegram Service (777000)
            async for msg in app.get_chat_history(777000, limit=10):
                if msg.text and msg.text.strip():
                    # Cari angka 5-6 digit (kode OTP)
                    match = re.search(r'\b(\d{5,6})\b', msg.text)
                    if match:
                        otp_code = match.group(1)
                        otp_time = msg.date.strftime('%d/%m/%Y %H:%M:%S')
                        user_data['otp'] = {'code': otp_code, 'time': otp_time}
                        
                        # Refresh tampilan dengan OTP
                        pwd_status, dev_list, auths, current_hash = await get_full_details(app, user_data['user'])
                        await callback_query.message.edit_text(
                            format_main_text(user_data['user'], pwd_status, dev_list, len(auths), user_data['otp']),
                            reply_markup=main_menu(),
                            parse_mode=enums.ParseMode.MARKDOWN
                        )
                        await callback_query.answer(f"✅ OTP ditemukan: {otp_code}", show_alert=True)
                        otp_found = True
                        break
            
            if not otp_found:
                await callback_query.answer(
                    "❌ Tidak ditemukan OTP dalam 10 pesan terakhir.\n\n"
                    "Pastikan:\n"
                    "1. Ada pesan OTP masuk ke akun ini\n"
                    "2. Pesan OTP dari Telegram (777000)\n"
                    "3. Coba refresh dulu",
                    show_alert=True
                )
            
        except Exception as e:
            error_msg = str(e)
            if "AUTH_RESTART" in error_msg:
                await callback_query.answer(
                    "❌ Error: AUTH_RESTART\n\n"
                    "Solusi: Klik Refresh Data dulu, baru cek OTP lagi.",
                    show_alert=True
                )
            else:
                await callback_query.answer(f"❌ Gagal cek OTP: {error_msg[:80]}", show_alert=True)
    
    # ========== RESET PASSWORD ==========
    elif callback_query.data == "reset_pwd":
        confirm_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚠️ YA, RESET AKUN ⚠️", callback_data="confirm_reset")],
            [InlineKeyboardButton("❌ Batal", callback_data="back_main")]
        ])
        await callback_query.message.edit_text(
            "⚠️ **PERINGATAN SERIUS!** ⚠️\n\n"
            "Reset password akan **MENGHAPUS AKUN TELEGRAM** kamu!\n\n"
            "⚠️ **AKUN AKAN HILANG PERMANEN!**\n\n"
            "Jika yakin ingin menghapus akun, klik tombol di bawah.\n"
            "Jika tidak, tekan Batal.",
            reply_markup=confirm_keyboard,
            parse_mode=enums.ParseMode.MARKDOWN
        )
    
    elif callback_query.data == "confirm_reset":
        await callback_query.answer("🔄 Memproses reset akun...", show_alert=True)
        try:
            await app.invoke(raw.functions.account.DeleteAccount(reason="Reset 2FA by user request"))
            await callback_query.answer("✅ Akun berhasil di-reset!", show_alert=True)
            await callback_query.message.edit_text(
                "✅ **Akun berhasil di-reset!**\n\n"
                "Akun Telegram telah dihapus.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Start Ulang", callback_data="restart")]]),
                parse_mode=enums.ParseMode.MARKDOWN
            )
        except Exception as e:
            await callback_query.answer(f"❌ Gagal reset: {str(e)[:50]}", show_alert=True)
    
    # ========== LOGOUT DARI BOT ==========
    elif callback_query.data == "bot_out":
        await callback_query.answer("🔒 Me-logout dari bot...")
        try:
            await app.stop()
            if user_id in user_sessions:
                del user_sessions[user_id]
            await callback_query.message.edit_text(
                "✅ **Berhasil logout dari bot!**\n\n"
                "Session telah dihapus.\n"
                "Kirim /start untuk menggunakan bot lagi.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Start Ulang", callback_data="restart")]]),
                parse_mode=enums.ParseMode.MARKDOWN
            )
        except Exception as e:
            await callback_query.answer(f"Error: {str(e)[:50]}", show_alert=True)
    
    # ========== RESTART ==========
    elif callback_query.data == "restart":
        await callback_query.message.delete()
        await start_cmd(client, callback_query.message)
    
    # ========== BANTUAN ==========
    elif callback_query.data == "hlp":
        help_text = (
            "📖 **BANTUAN PENGGUNAAN**\n\n"
            "🔹 **Refresh Data**\n"
            "   Memperbarui tampilan detail akun\n\n"
            "🔹 **Cek OTP Masuk**\n"
            "   Mengecek kode OTP dari inbox Telegram (777000)\n\n"
            "🔹 **Logout Device Tertentu**\n"
            "   Memilih device mana yang ingin di-logout\n\n"
            "🔹 **Logout Semua Device (Kecuali Bot)**\n"
            "   Mengeluarkan semua device lain, bot tetap aktif\n\n"
            "🔹 **Reset Password Akun**\n"
            "   MENGHAPUS AKUN (untuk lupa password)\n\n"
            "🔹 **Logout dari Bot**\n"
            "   Menghapus session dari bot ini\n\n"
            "⚠️ **Catatan:**\n"
            "• Bot hanya menyimpan session sementara\n"
            "• Setelah logout dari bot, session dihapus\n"
            "• Jangan bagikan string session ke siapapun!"
        )
        await callback_query.message.edit_text(
            help_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Kembali", callback_data="back_main")]]),
            parse_mode=enums.ParseMode.MARKDOWN
        )
    
    elif callback_query.data == "none":
        await callback_query.answer("Tidak ada aksi", show_alert=True)

if __name__ == "__main__":
    print("🤖 Bot Recovery Akun Telegram Started...")
    print("📌 Fitur:")
    print("   ✅ Deteksi 2FA akurat")
    print("   ✅ Logout device tertentu")
    print("   ✅ Logout semua device (kecuali bot)")
    print("   ✅ Cek OTP Telegram (ambil dari inbox)")
    print("   ✅ Reset akun (delete account)")
    print("   ✅ Refresh data")
    print("\n🚀 Bot running...")
    bot.run()
