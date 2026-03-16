"""
bot/utils/localization.py

Localization system for Nexus Bot v21.
Supports 10 languages: en, ar, es, fr, hi, pt, ru, tr, id, de

No paid API used - all strings are hardcoded for reliability.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Supported languages
SUPPORTED_LANGUAGES = {
    "en": "English",
    "ar": "العربية (Arabic)",
    "es": "Español (Spanish)",
    "fr": "Français (French)",
    "hi": "हिन्दी (Hindi)",
    "pt": "Português (Portuguese)",
    "ru": "Русский (Russian)",
    "tr": "Türkçe (Turkish)",
    "id": "Bahasa Indonesia (Indonesian)",
    "de": "Deutsch (German)",
}

# Default language
DEFAULT_LANG = "en"

# String translations
STRINGS = {
    # Common / Moderation
    "warn_user": {
        "en": "⚠️ <b>Warning</b>\nUser {user} has been warned.\nReason: {reason}\nWarn count: {count}/{limit}",
        "ar": "⚠️ <b>تحذير</b>\nتم تحذير المستخدم {user}.\nالسبب: {reason}\nعدد التحذيرات: {count}/{limit}",
        "es": "⚠️ <b>Advertencia</b>\nEl usuario {user} ha sido advertido.\nRazón: {reason}\nAdvertencias: {count}/{limit}",
        "fr": "⚠️ <b>Avertissement</b>\nL'utilisateur {user} a été averti.\nRaison: {reason}\nAvertissements: {count}/{limit}",
        "hi": "⚠️ <b>चेतावनी</b>\nउपयोगकर्ता {user} को चेतावनी दी गई।\nकारण: {reason}\nचेतावनी संख्या: {count}/{limit}",
        "pt": "⚠️ <b>Aviso</b>\nO usuário {user} foi avisado.\nMotivo: {reason}\nAvisos: {count}/{limit}",
        "ru": "⚠️ <b>Предупреждение</b>\nПользователю {user} выдано предупреждение.\nПричина: {reason}\nПредупреждений: {count}/{limit}",
        "tr": "⚠️ <b>Uyarı</b>\n{user} kullanıcısı uyarıldı.\nSebep: {reason}\nUyarı sayısı: {count}/{limit}",
        "id": "⚠️ <b>Peringatan</b>\nPengguna {user} telah diperingatkan.\nAlasan: {reason}\nJumlah peringatan: {count}/{limit}",
        "de": "⚠️ <b>Warnung</b>\nBenutzer {user} wurde verwarnt.\nGrund: {reason}\nVerwarnungen: {count}/{limit}",
    },
    "ban_user": {
        "en": "🚫 <b>Banned</b>\nUser {user} has been banned.\nReason: {reason}",
        "ar": "🚫 <b>محظور</b>\nتم حظر المستخدم {user}.\nالسبب: {reason}",
        "es": "🚫 <b>Baneado</b>\nEl usuario {user} ha sido baneado.\nRazón: {reason}",
        "fr": "🚫 <b>Banni</b>\nL'utilisateur {user} a été banni.\nRaison: {reason}",
        "hi": "🚫 <b>प्रतिबंधित</b>\nउपयोगकर्ता {user} को प्रतिबंधित किया गया।\nकारण: {reason}",
        "pt": "🚫 <b>Banido</b>\nO usuário {user} foi banido.\nMotivo: {reason}",
        "ru": "🚫 <b>Заблокирован</b>\nПользователь {user} заблокирован.\nПричина: {reason}",
        "tr": "🚫 <b>Yasaklandı</b>\n{user} kullanıcısı yasaklandı.\nSebep: {reason}",
        "id": "🚫 <b>Diblokir</b>\nPengguna {user} telah diblokir.\nAlasan: {reason}",
        "de": "🚫 <b>Gebannt</b>\nBenutzer {user} wurde gebannt.\nGrund: {reason}",
    },
    "kick_user": {
        "en": "👢 <b>Kicked</b>\nUser {user} has been kicked.\nReason: {reason}",
        "ar": "👢 <b>طرد</b>\nتم طرد المستخدم {user}.\nالسبب: {reason}",
        "es": "👢 <b>Expulsado</b>\nEl usuario {user} ha sido expulsado.\nRazón: {reason}",
        "fr": "👢 <b>Expulsé</b>\nL'utilisateur {user} a été expulsé.\nRaison: {reason}",
        "hi": "👢 <b>निकाला गया</b>\nउपयोगकर्ता {user} को निकाल दिया गया।\nकारण: {reason}",
        "pt": "👢 <b>Expulso</b>\nO usuário {user} foi expulso.\nMotivo: {reason}",
        "ru": "👢 <b>Исключён</b>\nПользователь {user} исключён из группы.\nПричина: {reason}",
        "tr": "👢 <b>Atıldı</b>\n{user} kullanıcısı atıldı.\nSebep: {reason}",
        "id": "👢 <b>Ditendang</b>\nPengguna {user} telah ditendang.\nAlasan: {reason}",
        "de": "👢 <b>Entfernt</b>\nBenutzer {user} wurde entfernt.\nGrund: {reason}",
    },
    "mute_user": {
        "en": "🔇 <b>Muted</b>\nUser {user} has been muted.\nDuration: {duration}",
        "ar": "🔇 <b>مكتوم</b>\nتم كتم المستخدم {user}.\nالمدة: {duration}",
        "es": "🔇 <b>Silenciado</b>\nEl usuario {user} ha sido silenciado.\nDuración: {duration}",
        "fr": "🔇 <b>Muté</b>\nL'utilisateur {user} a été muté.\nDurée: {duration}",
        "hi": "🔇 <b>म्यूट किया गया</b>\nउपयोगकर्ता {user} को म्यूट कर दिया गया।\nअवधि: {duration}",
        "pt": "🔇 <b>Mutado</b>\nO usuário {user} foi mutado.\nDuração: {duration}",
        "ru": "🔇 <b>Заглушён</b>\nПользователь {user} заглушён.\nДлительность: {duration}",
        "tr": "🔇 <b>Susturuldu</b>\n{user} kullanıcısı susturuldu.\nSüre: {duration}",
        "id": "🔇 <b>Dibisukan</b>\nPengguna {user} telah dibisukan.\nDurasi: {duration}",
        "de": "🔇 <b>Stummgeschaltet</b>\nBenutzer {user} wurde stummgeschaltet.\nDauer: {duration}",
    },
    # Federation/TrustNet
    "fed_ban": {
        "en": "🌐 <b>Federation Ban</b>\nUser {user} banned across {count} groups.\nReason: {reason}",
        "ar": "🌐 <b>حظر الاتحاد</b>\nتم حظر المستخدم {user} في {count} مجموعات.\nالسبب: {reason}",
        "es": "🌐 <b>Ban de Federación</b>\nUsuario {user} baneado en {count} grupos.\nRazón: {reason}",
        "fr": "🌐 <b>Ban de Fédération</b>\nL'utilisateur {user} banni dans {count} groupes.\nRaison: {reason}",
        "hi": "🌐 <b>संघ प्रतिबंध</b>\nउपयोगकर्ता {user} को {count} समूहों में प्रतिबंधित किया गया।\nकारण: {reason}",
        "pt": "🌐 <b>Ban de Federação</b>\nUsuário {user} banido em {count} grupos.\nMotivo: {reason}",
        "ru": "🌐 <b>Бан федерации</b>\nПользователь {user} заблокирован в {count} группах.\nПричина: {reason}",
        "tr": "🌐 <b>Federasyon Yasaklaması</b>\n{user} kullanıcısı {count} grupta yasaklandı.\nSebep: {reason}",
        "id": "🌐 <b>Blokir Federasi</b>\nPengguna {user} diblokir di {count} grup.\nAlasan: {reason}",
        "de": "🌐 <b>Föderations-Bann</b>\nBenutzer {user} in {count} Gruppen gebannt.\nGrund: {reason}",
    },
    # Community Vote
    "vote_started": {
        "en": "⚖️ <b>Community Vote Started</b>\nTarget: {user}\nReason: {reason}\nVote with the buttons below.\nThreshold: {threshold} votes | Timeout: {timeout} min",
        "ar": "⚖️ <b>بدأ التصويت المجتمعي</b>\nالهدف: {user}\nالسبب: {reason}\nصوت باستخدام الأزرار أدناه.\nالحد: {threshold} أصوات | المهلة: {timeout} دقيقة",
        "es": "⚖️ <b>Votación Comunitaria Iniciada</b>\nObjetivo: {user}\nRazón: {reason}\nVota con los botones de abajo.\nUmbral: {threshold} votos | Tiempo: {timeout} min",
        "fr": "⚖️ <b>Vote Communautaire Commencé</b>\nCible: {user}\nRaison: {reason}\nVotez avec les boutons ci-dessous.\nSeuil: {threshold} votes | Délai: {timeout} min",
        "hi": "⚖️ <b>सामुदायिक मतदान शुरू</b>\nलक्ष्य: {user}\nकारण: {reason}\nनीचे दिए गए बटनों से मतदान करें।\nसीमा: {threshold} वोट | समय सीमा: {timeout} मिनट",
        "pt": "⚖️ <b>Votação da Comunidade Iniciada</b>\nAlvo: {user}\nMotivo: {reason}\nVote com os botões abaixo.\nLimite: {threshold} votos | Tempo: {timeout} min",
        "ru": "⚖️ <b>Началось Общественное Голосование</b>\nЦель: {user}\nПричина: {reason}\nГолосуйте кнопками ниже.\nПорог: {threshold} голосов | Таймаут: {timeout} мин",
        "tr": "⚖️ <b>Topluluk Oylaması Başladı</b>\nHedef: {user}\nSebep: {reason}\nAşağıdaki butonlarla oy verin.\nEşik: {threshold} oy | Süre: {timeout} dk",
        "id": "⚖️ <b>Pemungutan Suara Komunitas Dimulai</b>\nTarget: {user}\nAlasan: {reason}\nPilih dengan tombol di bawah.\nAmbang: {threshold} suara | Batas: {timeout} menit",
        "de": "⚖️ <b>Community-Abstimmung Gestartet</b>\nZiel: {user}\nGrund: {reason}\nStimmen Sie mit den Buttons unten ab.\nSchwelle: {threshold} Stimmen | Zeitlimit: {timeout} min",
    },
    "vote_passed": {
        "en": "✅ <b>Vote Passed</b>\nThe community has decided.\nAction: {action}",
        "ar": "✅ <b>تم التصويت</b>\nقررت المجتمع.\nالإجراء: {action}",
        "es": "✅ <b>Voto Aprobado</b>\nLa comunidad ha decidido.\nAcción: {action}",
        "fr": "✅ <b>Vote Adopté</b>\nLa communauté a décidé.\nAction: {action}",
        "hi": "✅ <b>मतदान पारित</b>\nसमुदाय ने निर्णय लिया है।\nकार्रवाई: {action}",
        "pt": "✅ <b>Votação Aprovada</b>\nA comunidade decidiu.\nAção: {action}",
        "ru": "✅ <b>Голосование Пройдено</b>\nСообщество приняло решение.\nДействие: {action}",
        "tr": "✅ <b>Oylama Kabul Edildi</b>\nTopluluk karar verdi.\nEylem: {action}",
        "id": "✅ <b>Pemungutan Suara Diterima</b>\nKomunitas telah memutuskan.\nTindakan: {action}",
        "de": "✅ <b>Abstimmung Bestanden</b>\nDie Community hat entschieden.\nAktion: {action}",
    },
    # Night Mode
    "night_mode_on": {
        "en": "🌙 <b>Night Mode Activated</b>\nGroup is now in restricted mode until {end_time}.",
        "ar": "🌙 <b>تم تفعيل الوضع الليلي</b>\nالمجموعة في الوضع المقيد الآن حتى {end_time}.",
        "es": "🌙 <b>Modo Nocturno Activado</b>\nEl grupo está en modo restringido hasta {end_time}.",
        "fr": "🌙 <b>Mode Nuit Activé</b>\nLe groupe est en mode restreint jusqu'à {end_time}.",
        "hi": "🌙 <b>नाइट मोड सक्रिय</b>\nसमूह अब प्रतिबंधित मोड में है {end_time} तक।",
        "pt": "🌙 <b>Modo Noturno Ativado</b>\nO grupo está em modo restrito até {end_time}.",
        "ru": "🌙 <b>Ночной Режим Активирован</b>\nГруппа в ограниченном режиме до {end_time}.",
        "tr": "🌙 <b>Gece Modu Etkinleştirildi</b>\nGrup, {end_time} kadar kısıtlı modda.",
        "id": "🌙 <b>Mode Malam Diaktifkan</b>\nGrup dalam mode terbatas sampai {end_time}.",
        "de": "🌙 <b>Nachtmodus Aktiviert</b>\nGruppe ist bis {end_time} im eingeschränkten Modus.",
    },
    "night_mode_off": {
        "en": "☀️ <b>Night Mode Deactivated</b>\nGroup permissions restored. Good morning!",
        "ar": "☀️ <b>تم إلغاء تنشيط الوضع الليلي</b>\nتمت استعادة أذونات المجموعة. صباح الخير!",
        "es": "☀️ <b>Modo Nocturno Desactivado</b>\nPermisos del grupo restaurados. ¡Buenos días!",
        "fr": "☀️ <b>Mode Nuit Désactivé</b>\nPermissions du groupe restaurées. Bonjour !",
        "hi": "☀️ <b>नाइट मोड निष्क्रिय</b>\nसमूह की अनुमतियाँ बहाल की गईं। शुभ प्रभात!",
        "pt": "☀️ <b>Modo Noturno Desativado</b>\nPermissões do grupo restauradas. Bom dia!",
        "ru": "☀️ <b>Ночной Режим Отключён</b>\nПрава группы восстановлены. Доброе утро!",
        "tr": "☀️ <b>Gece Modu Devre Dışı</b>\nGrup izinleri geri yüklendi. Günaydın!",
        "id": "☀️ <b>Mode Malam Dinonaktifkan</b>\nIzin grup dipulihkan. Selamat pagi!",
        "de": "☀️ <b>Nachtmodus Deaktiviert</b>\nGruppenberechtigungen wiederhergestellt. Guten Morgen!",
    },
    # Trust Score
    "trust_score": {
        "en": "🛡️ <b>Trust Score</b>: {score}/100\n{level}",
        "ar": "🛡️ <b>درجة الثقة</b>: {score}/100\n{level}",
        "es": "🛡️ <b>Puntuación de Confianza</b>: {score}/100\n{level}",
        "fr": "🛡️ <b>Score de Confiance</b>: {score}/100\n{level}",
        "hi": "🛡️ <b>ट्रस्ट स्कोर</b>: {score}/100\n{level}",
        "pt": "🛡️ <b>Pontuação de Confiança</b>: {score}/100\n{level}",
        "ru": "🛡️ <b>Рейтинг Доверия</b>: {score}/100\n{level}",
        "tr": "🛡️ <b>Güven Puanı</b>: {score}/100\n{level}",
        "id": "🛡️ <b>Skor Kepercayaan</b>: {score}/100\n{level}",
        "de": "🛡️ <b>Vertrauenswert</b>: {score}/100\n{level}",
    },
    # Common responses
    "no_permission": {
        "en": "❌ You don't have permission to use this command.",
        "ar": "❌ ليس لديك إذن لاستخدام هذا الأمر.",
        "es": "❌ No tienes permiso para usar este comando.",
        "fr": "❌ Vous n'avez pas la permission d'utiliser cette commande.",
        "hi": "❌ आपके पास इस कमांड का उपयोग करने की अनुमति नहीं है।",
        "pt": "❌ Você não tem permissão para usar este comando.",
        "ru": "❌ У вас нет прав для использования этой команды.",
        "tr": "❌ Bu komutu kullanma izniniz yok.",
        "id": "❌ Anda tidak memiliki izin untuk menggunakan perintah ini.",
        "de": "❌ Sie haben keine Berechtigung, diesen Befehl zu verwenden.",
    },
    "user_not_found": {
        "en": "❌ User not found. Please reply to a message or provide a valid user ID.",
        "ar": "❌ المستخدم غير موجود. يرجى الرد على رسالة أو تقديم معرف مستخدم صالح.",
        "es": "❌ Usuario no encontrado. Responda a un mensaje o proporcione un ID válido.",
        "fr": "❌ Utilisateur non trouvé. Veuillez répondre à un message ou fournir un ID valide.",
        "hi": "❌ उपयोगकर्ता नहीं मिला। कृपया किसी संदेश का उत्तर दें या वैध उपयोगकर्ता आईडी प्रदान करें।",
        "pt": "❌ Usuário não encontrado. Responda a uma mensagem ou forneça um ID válido.",
        "ru": "❌ Пользователь не найден. Ответьте на сообщение или укажите действительный ID.",
        "tr": "❌ Kullanıcı bulunamadı. Lütfen bir mesaja yanıt verin veya geçerli bir kullanıcı ID'si girin.",
        "id": "❌ Pengguna tidak ditemukan. Silakan balas pesan atau berikan ID pengguna yang valid.",
        "de": "❌ Benutzer nicht gefunden. Bitte antworten Sie auf eine Nachricht oder geben Sie eine gültige Benutzer-ID an.",
    },
    "action_success": {
        "en": "✅ Action completed successfully.",
        "ar": "✅ تم completing الإجراء بنجاح.",
        "es": "✅ Acción completada con éxito.",
        "fr": "✅ Action terminée avec succès.",
        "hi": "✅ कार्रवाई सफलतापूर्वक पूर्ण हुई।",
        "pt": "✅ Ação concluída com sucesso.",
        "ru": "✅ Действие успешно завершено.",
        "tr": "✅ İşlem başarıyla tamamlandı.",
        "id": "✅ Tindakan berhasil diselesaikan.",
        "de": "✅ Aktion erfolgreich abgeschlossen.",
    },
}


class LocaleProxy:
    """
    Clean integration for localization.
    Usage: locale.get("warn_user", user="@username", reason="spam", count=1, limit=3)
    """
    
    def __init__(self, language_code: str = DEFAULT_LANG):
        self.language_code = language_code if language_code in SUPPORTED_LANGUAGES else DEFAULT_LANG
    
    def get(self, key: str, **kwargs) -> str:
        """Get a localized string by key with optional formatting."""
        if key not in STRINGS:
            logger.warning(f"Missing translation key: {key}")
            return key
        
        translations = STRINGS[key]
        text = translations.get(self.language_code, translations.get(DEFAULT_LANG, key))
        
        if kwargs:
            try:
                text = text.format(**kwargs)
            except KeyError as e:
                logger.warning(f"Missing format arg {e} for key {key}")
        
        return text
    
    def __call__(self, key: str, **kwargs) -> str:
        """Allow locale("key") syntax."""
        return self.get(key, **kwargs)


def get_locale(language_code: Optional[str] = None) -> LocaleProxy:
    """Get a locale proxy for the given language code."""
    return LocaleProxy(language_code or DEFAULT_LANG)


async def get_user_language(pool, user_id: int) -> str:
    """Get user's preferred language from database."""
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT language_code FROM user_lang_prefs WHERE user_id = $1",
                user_id
            )
            if row:
                return row["language_code"]
    except Exception as e:
        logger.debug(f"Failed to get user language: {e}")
    return DEFAULT_LANG


async def set_user_language(pool, user_id: int, language_code: str) -> bool:
    """Set user's preferred language in database."""
    if language_code not in SUPPORTED_LANGUAGES:
        return False
    
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO user_lang_prefs (user_id, language_code)
                   VALUES ($1, $2)
                   ON CONFLICT (user_id) DO UPDATE 
                   SET language_code = EXCLUDED.language_code, updated_at = NOW()""",
                user_id, language_code
            )
        return True
    except Exception as e:
        logger.error(f"Failed to set user language: {e}")
        return False


async def get_group_language(pool, chat_id: int) -> str:
    """Get group's default language from database."""
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT settings->>'default_language' as lang FROM groups WHERE chat_id = $1",
                chat_id
            )
            if row and row["lang"]:
                return row["lang"]
    except Exception as e:
        logger.debug(f"Failed to get group language: {e}")
    return DEFAULT_LANG


def get_trust_level(score: int) -> str:
    """Get trust level description based on score."""
    if score >= 90:
        return "Trusted 🟢"
    elif score >= 70:
        return "Reliable 🟡"
    elif score >= 50:
        return "Neutral ⚪"
    elif score >= 30:
        return "Suspicious 🟠"
    else:
        return "Untrusted 🔴"


# Compatibility aliases for v21 upload code
LANGUAGES = SUPPORTED_LANGUAGES


def get_locale(language_code: Optional[str] = None) -> LocaleProxy:
    """Get a locale proxy for the given language code (compatibility alias)."""
    return LocaleProxy(language_code or DEFAULT_LANG)


def get_user_lang(pool, user_id: int, chat_id: Optional[int] = None) -> str:
    """
    Get user's preferred language (compatibility wrapper).
    Delegates to get_user_language.
    """
    from bot.utils.lang_detect import get_user_lang as detect_lang
    return detect_lang(pool, user_id, chat_id)


# Export for convenience
__all__ = [
    "LocaleProxy",
    "get_locale",
    "get_user_language",
    "set_user_language",
    "get_group_language",
    "SUPPORTED_LANGUAGES",
    "DEFAULT_LANG",
    "get_trust_level",
    "LANGUAGES",  # Alias for upload compatibility
    "get_user_lang",  # Compatibility wrapper
]
