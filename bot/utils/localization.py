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

# String translations - Complete v21 catalogue
STRINGS = {
    # ============================================
    # WELCOME / GOODBYE
    # ============================================
    "welcome": {
        "en": "👋 Welcome {name} to {group}!",
        "ar": "👋 أهلاً وسهلاً {name} في {group}!",
        "es": "👋 ¡Bienvenido {name} a {group}!",
        "fr": "👋 Bienvenue {name} dans {group}!",
        "hi": "👋 {group} में आपका स्वागत है {name}!",
        "pt": "👋 Bem-vindo {name} ao {group}!",
        "ru": "👋 Добро пожаловать, {name}, в {group}!",
        "tr": "👋 {group}'a hoş geldin {name}!",
        "id": "👋 Selamat datang {name} di {group}!",
        "de": "👋 Willkommen {name} in {group}!",
    },
    "goodbye": {
        "en": "👋 Goodbye {name}!",
        "ar": "👋 مع السلامة {name}!",
        "es": "👋 ¡Adiós {name}!",
        "fr": "👋 Au revoir {name}!",
        "hi": "👋 अलविदा {name}!",
        "pt": "👋 Adeus {name}!",
        "ru": "👋 До свидания, {name}!",
        "tr": "👋 Güle güle {name}!",
        "id": "👋 Sampai jumpa {name}!",
        "de": "👋 Auf Wiedersehen {name}!",
    },
    # ============================================
    # WARN / UNWARN
    # ============================================
    "warn_issued": {
        "en": "⚠️ <b>Warning Issued</b>\nUser: {name}\nReason: {reason}\nCount: {count}/{max}",
        "ar": "⚠️ <b>تحذير صادر</b>\nالمستخدم: {name}\nالسبب: {reason}\nالعدد: {count}/{max}",
        "es": "⚠️ <b>Advertencia Emitida</b>\nUsuario: {name}\nRazón: {reason}\nConteo: {count}/{max}",
        "fr": "⚠️ <b>Avertissement Émis</b>\nUtilisateur: {name}\nRaison: {reason}\nCompte: {count}/{max}",
        "hi": "⚠️ <b>चेतावनी जारी</b>\nउपयोगकर्ता: {name}\nकारण: {reason}\nसंख्या: {count}/{max}",
        "pt": "⚠️ <b>Aviso Emitido</b>\nUsuário: {name}\nMotivo: {reason}\nContagem: {count}/{max}",
        "ru": "⚠️ <b>Предупреждение Выдано</b>\nПользователь: {name}\nПричина: {reason}\nСчёт: {count}/{max}",
        "tr": "⚠️ <b>Uyarı Verildi</b>\nKullanıcı: {name}\nSebep: {reason}\nSayı: {count}/{max}",
        "id": "⚠️ <b>Peringatan Diberikan</b>\nPengguna: {name}\nAlasan: {reason}\nJumlah: {count}/{max}",
        "de": "⚠️ <b>Warnung Ausgestellt</b>\nBenutzer: {name}\nGrund: {reason}\nAnzahl: {count}/{max}",
    },
    "warn_max_reached": {
        "en": "🚫 <b>Max Warnings Reached!</b>\nUser {name} has reached {max} warnings.\nAction: {action}",
        "ar": "🚫 <b>تم الوصول للحد الأقصى!</b>\nوصل المستخدم {name} إلى {max} تحذيرات.\nالإجراء: {action}",
        "es": "🚫 <b>¡Máximo de Advertencias Alcanzado!</b>\nEl usuario {name} ha alcanzado {max} advertencias.\nAcción: {action}",
        "fr": "🚫 <b>Nombre Max d'Avertissements Atteint!</b>\nL'utilisateur {name} a atteint {max} avertissements.\nAction: {action}",
        "hi": "🚫 <b>अधिकतम चेतावनियाँ पूर्ण!</b>\nउपयोगकर्ता {name} ने {max} चेतावनियाँ पूरी कर ली हैं।\nकार्रवाई: {action}",
        "pt": "🚫 <b>Máximo de Avisos Atingido!</b>\nO usuário {name} atingiu {max} avisos.\nAção: {action}",
        "ru": "🚫 <b>Достигнуто Макс. Предупреждений!</b>\nПользователь {name} получил {max} предупреждений.\nДействие: {action}",
        "tr": "🚫 <b>Maks Uyarı Sayısına Ulaşıldı!</b>\n{name} kullanıcısı {max} uyarıya ulaştı.\nEylem: {action}",
        "id": "🚫 <b>Batas Maks Peringatan Tercapai!</b>\nPengguna {name} telah mencapai {max} peringatan.\nTindakan: {action}",
        "de": "🚫 <b>Maximale Warnungen Erreicht!</b>\nBenutzer {name} hat {max} Warnungen erreicht.\nAktion: {action}",
    },
    "warn_removed": {
        "en": "✅ <b>Warning Removed</b>\nUser: {name}\nRemaining: {count}",
        "ar": "✅ <b>تم إزالة التحذير</b>\nالمستخدم: {name}\nالمتبقي: {count}",
        "es": "✅ <b>Advertencia Eliminada</b>\nUsuario: {name}\nRestantes: {count}",
        "fr": "✅ <b>Avertissement Supprimé</b>\nUtilisateur: {name}\nRestants: {count}",
        "hi": "✅ <b>चेतावनी हटा दी गई</b>\nउपयोगकर्ता: {name}\nशेष: {count}",
        "pt": "✅ <b>Aviso Removido</b>\nUsuário: {name}\nRestantes: {count}",
        "ru": "✅ <b>Предупреждение Снято</b>\nПользователь: {name}\nОсталось: {count}",
        "tr": "✅ <b>Uyarı Kaldırıldı</b>\nKullanıcı: {name}\nKalan: {count}",
        "id": "✅ <b>Peringatan Dihapus</b>\nPengguna: {name}\nTersisa: {count}",
        "de": "✅ <b>Warnung Entfernt</b>\nBenutzer: {name}\nVerbleibend: {count}",
    },
    # ============================================
    # BAN / KICK / MUTE
    # ============================================
    "user_banned": {
        "en": "🚫 <b>User Banned</b>\nUser: {name}\nReason: {reason}",
        "ar": "🚫 <b>المستخدم محظور</b>\nالمستخدم: {name}\nالسبب: {reason}",
        "es": "🚫 <b>Usuario Baneado</b>\nUsuario: {name}\nRazón: {reason}",
        "fr": "🚫 <b>Utilisateur Banni</b>\nUtilisateur: {name}\nRaison: {reason}",
        "hi": "🚫 <b>उपयोगकर्ता प्रतिबंधित</b>\nउपयोगकर्ता: {name}\nकारण: {reason}",
        "pt": "🚫 <b>Usuário Banido</b>\nUsuário: {name}\nMotivo: {reason}",
        "ru": "🚫 <b>Пользователь Заблокирован</b>\nПользователь: {name}\nПричина: {reason}",
        "tr": "🚫 <b>Kullanıcı Yasaklandı</b>\nKullanıcı: {name}\nSebep: {reason}",
        "id": "🚫 <b>Pengguna Diblokir</b>\nPengguna: {name}\nAlasan: {reason}",
        "de": "🚫 <b>Benutzer Gebannt</b>\nBenutzer: {name}\nGrund: {reason}",
    },
    "user_unbanned": {
        "en": "✅ <b>User Unbanned</b>\nUser: {name}",
        "ar": "✅ <b>تم إلغاء حظر المستخدم</b>\nالمستخدم: {name}",
        "es": "✅ <b>Usuario Desbaneado</b>\nUsuario: {name}",
        "fr": "✅ <b>Utilisateur Débanni</b>\nUtilisateur: {name}",
        "hi": "✅ <b>उपयोगकर्ता प्रतिबंध हटाया</b>\nउपयोगकर्ता: {name}",
        "pt": "✅ <b>Usuário Desbanido</b>\nUsuário: {name}",
        "ru": "✅ <b>Пользователь Разблокирован</b>\nПользователь: {name}",
        "tr": "✅ <b>Kullanıcı Yasağı Kaldırıldı</b>\nKullanıcı: {name}",
        "id": "✅ <b>Blokir Pengguna Dibuka</b>\nPengguna: {name}",
        "de": "✅ <b>Benutzer Entbannt</b>\nBenutzer: {name}",
    },
    "user_kicked": {
        "en": "👢 <b>User Kicked</b>\nUser: {name}\nReason: {reason}",
        "ar": "👢 <b>تم طرد المستخدم</b>\nالمستخدم: {name}\nالسبب: {reason}",
        "es": "👢 <b>Usuario Expulsado</b>\nUsuario: {name}\nRazón: {reason}",
        "fr": "👢 <b>Utilisateur Expulsé</b>\nUtilisateur: {name}\nRaison: {reason}",
        "hi": "👢 <b>उपयोगकर्ता निकाला गया</b>\nउपयोगकर्ता: {name}\nकारण: {reason}",
        "pt": "👢 <b>Usuário Expulso</b>\nUsuário: {name}\nMotivo: {reason}",
        "ru": "👢 <b>Пользователь Исключён</b>\nПользователь: {name}\nПричина: {reason}",
        "tr": "👢 <b>Kullanıcı Atıldı</b>\nKullanıcı: {name}\nSebep: {reason}",
        "id": "👢 <b>Pengguna Ditendang</b>\nPengguna: {name}\nAlasan: {reason}",
        "de": "👢 <b>Benutzer Entfernt</b>\nBenutzer: {name}\nGrund: {reason}",
    },
    "user_muted": {
        "en": "🔇 <b>User Muted</b>\nUser: {name}\nDuration: {duration}",
        "ar": "🔇 <b>تم كتم المستخدم</b>\nالمستخدم: {name}\nالمدة: {duration}",
        "es": "🔇 <b>Usuario Silenciado</b>\nUsuario: {name}\nDuración: {duration}",
        "fr": "🔇 <b>Utilisateur Muté</b>\nUtilisateur: {name}\nDurée: {duration}",
        "hi": "🔇 <b>उपयोगकर्ता म्यूट किया गया</b>\nउपयोगकर्ता: {name}\nअवधि: {duration}",
        "pt": "🔇 <b>Usuário Mutado</b>\nUsuário: {name}\nDuração: {duration}",
        "ru": "🔇 <b>Пользователь Заглушён</b>\nПользователь: {name}\nДлительность: {duration}",
        "tr": "🔇 <b>Kullanıcı Susturuldu</b>\nKullanıcı: {name}\nSüre: {duration}",
        "id": "🔇 <b>Pengguna Dibisukan</b>\nPengguna: {name}\nDurasi: {duration}",
        "de": "🔇 <b>Benutzer Stummgeschaltet</b>\nBenutzer: {name}\nDauer: {duration}",
    },
    "user_unmuted": {
        "en": "🔊 <b>User Unmuted</b>\nUser: {name}",
        "ar": "🔊 <b>تم إلغاء كتم المستخدم</b>\nالمستخدم: {name}",
        "es": "🔊 <b>Usuario Desilenciado</b>\nUsuario: {name}",
        "fr": "🔊 <b>Utilisateur Démuté</b>\nUtilisateur: {name}",
        "hi": "🔊 <b>उपयोगकर्ता अनम्यूट किया गया</b>\nउपयोगकर्ता: {name}",
        "pt": "🔊 <b>Usuário Desmutado</b>\nUsuário: {name}",
        "ru": "🔊 <b>Пользователь Разглушён</b>\nПользователь: {name}",
        "tr": "🔊 <b>Kullanıcının Susturulması Kaldırıldı</b>\nKullanıcı: {name}",
        "id": "🔊 <b>Pembisuan Pengguna Dibuka</b>\nPengguna: {name}",
        "de": "🔊 <b>Benutzer Entstummt</b>\nBenutzer: {name}",
    },
    # ============================================
    # CAPTCHA
    # ============================================
    "captcha_prompt": {
        "en": "🔐 <b>CAPTCHA Verification</b>\nPlease verify you're human by clicking the button below.",
        "ar": "🔐 <b>التحقق من CAPTCHA</b>\nيرجى التحقق من أنك إنسان بالنقر على الزر أدناه.",
        "es": "🔐 <b>Verificación CAPTCHA</b>\nPor favor verifica que eres humano haciendo clic en el botón de abajo.",
        "fr": "🔐 <b>Vérification CAPTCHA</b>\nVeuillez vérifier que vous êtes humain en cliquant sur le bouton ci-dessous.",
        "hi": "🔐 <b>CAPTCHA सत्यापन</b>\nकृपया नीचे दिए बटन पर क्लिक करके सत्यापित करें कि आप मानव हैं।",
        "pt": "🔐 <b>Verificação CAPTCHA</b>\nPor favor, verifique que você é humano clicando no botão abaixo.",
        "ru": "🔐 <b>Проверка CAPTCHA</b>\nПожалуйста, подтвердите, что вы человек, нажав кнопку ниже.",
        "tr": "🔐 <b>CAPTCHA Doğrulaması</b>\nLütfen aşağıdaki butona tıklayarak insan olduğunuzu doğrulayın.",
        "id": "🔐 <b>Verifikasi CAPTCHA</b>\nSilakan verifikasi bahwa Anda manusia dengan mengklik tombol di bawah.",
        "de": "🔐 <b>CAPTCHA-Verifizierung</b>\nBitte verifizieren Sie, dass Sie ein Mensch sind, indem Sie auf die Schaltfläche unten klicken.",
    },
    "captcha_passed": {
        "en": "✅ <b>CAPTCHA Passed!</b>\nWelcome {name}! You can now chat.",
        "ar": "✅ <b>تم اجتياز CAPTCHA!</b>\nأهلاً {name}! يمكنك الآن الدردشة.",
        "es": "✅ <b>¡CAPTCHA Aprobado!</b>\n¡Bienvenido {name}! Ya puedes chatear.",
        "fr": "✅ <b>CAPTCHA Réussi!</b>\nBienvenue {name}! Vous pouvez maintenant discuter.",
        "hi": "✅ <b>CAPTCHA पास!</b>\nस्वागत है {name}! अब आप चैट कर सकते हैं।",
        "pt": "✅ <b>CAPTCHA Aprovado!</b>\nBem-vindo {name}! Agora você pode conversar.",
        "ru": "✅ <b>CAPTCHA Пройдена!</b>\nДобро пожаловать, {name}! Теперь вы можете общаться.",
        "tr": "✅ <b>CAPTCHA Başarılı!</b>\nHoş geldin {name}! Artık sohbet edebilirsin.",
        "id": "✅ <b>CAPTCHA Lulus!</b>\nSelamat datang {name}! Anda sekarang dapat mengobrol.",
        "de": "✅ <b>CAPTCHA Bestanden!</b>\nWillkommen {name}! Sie können jetzt chatten.",
    },
    "captcha_failed": {
        "en": "❌ <b>CAPTCHA Failed!</b>\nPlease try again.",
        "ar": "❌ <b>فشل CAPTCHA!</b>\nيرجى المحاولة مرة أخرى.",
        "es": "❌ <b>¡CAPTCHA Fallido!</b>\nPor favor intenta de nuevo.",
        "fr": "❌ <b>CAPTCHA Échoué!</b>\nVeuillez réessayer.",
        "hi": "❌ <b>CAPTCHA विफल!</b>\nकृपया पुनः प्रयास करें।",
        "pt": "❌ <b>CAPTCHA Falhou!</b>\nPor favor, tente novamente.",
        "ru": "❌ <b>CAPTCHA Провалена!</b>\nПожалуйста, попробуйте снова.",
        "tr": "❌ <b>CAPTCHA Başarısız!</b>\nLütfen tekrar deneyin.",
        "id": "❌ <b>CAPTCHA Gagal!</b>\nSilakan coba lagi.",
        "de": "❌ <b>CAPTCHA Fehlgeschlagen!</b>\nBitte versuchen Sie es erneut.",
    },
    "captcha_timeout": {
        "en": "⏰ <b>CAPTCHA Timeout</b>\nYou took too long to respond. Please try joining again.",
        "ar": "⏰ <b>انتهى وقت CAPTCHA</b>\nلقد استغرقت وقتًا طويلاً للرد. يرجى المحاولة مرة أخرى.",
        "es": "⏰ <b>Tiempo Agotado CAPTCHA</b>\nTardaste demasiado en responder. Intenta unirte de nuevo.",
        "fr": "⏰ <b>Délai CAPTCHA Dépassé</b>\nVous avez mis trop de temps à répondre. Veuillez réessayer.",
        "hi": "⏰ <b>CAPTCHA समय समाप्त</b>\nआपने जवाब देने में बहुत अधिक समय लिया। कृपया फिर से जुड़ने का प्रयास करें।",
        "pt": "⏰ <b>Tempo Esgotado CAPTCHA</b>\nVocê demorou muito para responder. Tente entrar novamente.",
        "ru": "⏰ <b>Время CAPTCHA Истекло</b>\nВы слишком долго отвечали. Пожалуйста, попробуйте присоединиться снова.",
        "tr": "⏰ <b>CAPTCHA Zaman Aşımı</b>\nYanıt vermek çok uzun sürdü. Lütfen tekrar katılmayı deneyin.",
        "id": "⏰ <b>Waktu Habis CAPTCHA</b>\nAnda terlalu lama merespons. Silakan coba bergabung lagi.",
        "de": "⏰ <b>CAPTCHA-Zeitüberschreitung</b>\nSie haben zu lange gebraucht zu antworten. Bitte versuchen Sie erneut beizutreten.",
    },
    # ============================================
    # TRUSTNET (FEDERATION)
    # ============================================
    "fed_ban_notice": {
        "en": "🌐 <b>Federation Ban Notice</b>\nUser {name} is banned in {federation}.\nReason: {reason}",
        "ar": "🌐 <b>إشعار حظر الاتحاد</b>\nالمستخدم {name} محظور في {federation}.\nالسبب: {reason}",
        "es": "🌐 <b>Aviso de Ban de Federación</b>\nEl usuario {name} está baneado en {federation}.\nRazón: {reason}",
        "fr": "🌐 <b>Avis de Ban de Fédération</b>\nL'utilisateur {name} est banni dans {federation}.\nRaison: {reason}",
        "hi": "🌐 <b>संघ प्रतिबंध सूचना</b>\nउपयोगकर्ता {name} {federation} में प्रतिबंधित है।\nकारण: {reason}",
        "pt": "🌐 <b>Aviso de Ban de Federação</b>\nO usuário {name} está banido em {federation}.\nMotivo: {reason}",
        "ru": "🌐 <b>Уведомление о Бане Федерации</b>\nПользователь {name} заблокирован в {federation}.\nПричина: {reason}",
        "tr": "🌐 <b>Federasyon Yasağı Bildirimi</b>\n{name} kullanıcısı {federation}'da yasaklı.\nSebep: {reason}",
        "id": "🌐 <b>Pemberitahuan Blokir Federasi</b>\nPengguna {name} diblokir di {federation}.\nAlasan: {reason}",
        "de": "🌐 <b>Föderations-Bann-Benachrichtigung</b>\nBenutzer {name} ist in {federation} gebannt.\nGrund: {reason}",
    },
    "trust_score_label": {
        "en": "🛡️ Trust Score: {score}/100",
        "ar": "🛡️ درجة الثقة: {score}/100",
        "es": "🛡️ Puntuación de Confianza: {score}/100",
        "fr": "🛡️ Score de Confiance: {score}/100",
        "hi": "🛡️ ट्रस्ट स्कोर: {score}/100",
        "pt": "🛡️ Pontuação de Confiança: {score}/100",
        "ru": "🛡️ Рейтинг Доверия: {score}/100",
        "tr": "🛡️ Güven Puanı: {score}/100",
        "id": "🛡️ Skor Kepercayaan: {score}/100",
        "de": "🛡️ Vertrauenswert: {score}/100",
    },
    # ============================================
    # NIGHT MODE
    # ============================================
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
    "morning": {
        "en": "Good morning! The group is now open.",
        "ar": "صباح الخير! المجموعة مفتوحة الآن.",
        "es": "¡Buenos días! El grupo está abierto ahora.",
        "fr": "Bonjour ! Le groupe est maintenant ouvert.",
        "hi": "शुभ प्रभात! समूह अब खुला है।",
        "pt": "Bom dia! O grupo está aberto agora.",
        "ru": "Доброе утро! Группа теперь открыта.",
        "tr": "Günaydın! Grup şimdi açık.",
        "id": "Selamat pagi! Grup sekarang terbuka.",
        "de": "Guten Morgen! Die Gruppe ist jetzt offen.",
    },
    # ============================================
    # COMMUNITY VOTE
    # ============================================
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
    "vote_failed": {
        "en": "❌ <b>Vote Failed</b>\nNot enough votes. The user stays.",
        "ar": "❌ <b>فشل التصويت</b>\nلم يكن هناك أصوات كافية. يبقى المستخدم.",
        "es": "❌ <b>Votación Fallida</b>\nNo suficientes votos. El usuario se queda.",
        "fr": "❌ <b>Vote Échoué</b>\nPas assez de votes. L'utilisateur reste.",
        "hi": "❌ <b>मतदान विफल</b>\nपर्याप्त वोट नहीं। उपयोगकर्ता रहता है।",
        "pt": "❌ <b>Votação Falhou</b>\nVotos insuficientes. O usuário fica.",
        "ru": "❌ <b>Голосование Провалено</b>\nНедостаточно голосов. Пользователь остаётся.",
        "tr": "❌ <b>Oylama Başarısız</b>\nYeterli oy yok. Kullanıcı kalıyor.",
        "id": "❌ <b>Pemungutan Suara Gagal</b>\nTidak cukup suara. Pengguna tetap.",
        "de": "❌ <b>Abstimmung Fehlgeschlagen</b>\nNicht genug Stimmen. Der Benutzer bleibt.",
    },
    # ============================================
    # RULES / NOTES
    # ============================================
    "rules_header": {
        "en": "📋 <b>Group Rules</b>",
        "ar": "📋 <b>قواعد المجموعة</b>",
        "es": "📋 <b>Reglas del Grupo</b>",
        "fr": "📋 <b>Règles du Groupe</b>",
        "hi": "📋 <b>समूह के नियम</b>",
        "pt": "📋 <b>Regras do Grupo</b>",
        "ru": "📋 <b>Правила Группы</b>",
        "tr": "📋 <b>Grup Kuralları</b>",
        "id": "📋 <b>Aturan Grup</b>",
        "de": "📋 <b>Gruppenregeln</b>",
    },
    "no_rules": {
        "en": "📋 No rules have been set for this group yet.",
        "ar": "📋 لم يتم تعيين قواعد لهذه المجموعة بعد.",
        "es": "📋 Aún no se han establecido reglas para este grupo.",
        "fr": "📋 Aucune règle n'a encore été définie pour ce groupe.",
        "hi": "📋 इस समूह के लिए अभी तक कोई नियम निर्धारित नहीं किए गए हैं।",
        "pt": "📋 Nenhuma regra foi definida para este grupo ainda.",
        "ru": "📋 Для этой группы ещё не установлены правила.",
        "tr": "📋 Bu grup için henüz kural belirlenmemiş.",
        "id": "📋 Belum ada aturan yang ditetapkan untuk grup ini.",
        "de": "📋 Für diese Gruppe wurden noch keine Regeln festgelegt.",
    },
    # ============================================
    # LANGUAGE SETTINGS
    # ============================================
    "lang_set": {
        "en": "✅ Your language has been set to {lang}.",
        "ar": "✅ تم تعيين لغتك إلى {lang}.",
        "es": "✅ Tu idioma ha sido configurado a {lang}.",
        "fr": "✅ Votre langue a été définie sur {lang}.",
        "hi": "✅ आपकी भाषा {lang} पर सेट कर दी गई है।",
        "pt": "✅ Seu idioma foi configurado para {lang}.",
        "ru": "✅ Ваш язык установлен на {lang}.",
        "tr": "✅ Diliniz {lang} olarak ayarlandı.",
        "id": "✅ Bahasa Anda telah diatur ke {lang}.",
        "de": "✅ Ihre Sprache wurde auf {lang} gesetzt.",
    },
    "grouplang_set": {
        "en": "✅ Group language has been set to {lang}.",
        "ar": "✅ تم تعيين لغة المجموعة إلى {lang}.",
        "es": "✅ El idioma del grupo ha sido configurado a {lang}.",
        "fr": "✅ La langue du groupe a été définie sur {lang}.",
        "hi": "✅ समूह की भाषा {lang} पर सेट कर दी गई है।",
        "pt": "✅ O idioma do grupo foi configurado para {lang}.",
        "ru": "✅ Язык группы установлен на {lang}.",
        "tr": "✅ Grup dili {lang} olarak ayarlandı.",
        "id": "✅ Bahasa grup telah diatur ke {lang}.",
        "de": "✅ Gruppensprache wurde auf {lang} gesetzt.",
    },
    # ============================================
    # GENERAL ERRORS / SUCCESS
    # ============================================
    "not_admin": {
        "en": "❌ You must be an admin to use this command.",
        "ar": "❌ يجب أن تكون مسؤولاً لاستخدام هذا الأمر.",
        "es": "❌ Debes ser administrador para usar este comando.",
        "fr": "❌ Vous devez être administrateur pour utiliser cette commande.",
        "hi": "❌ इस कमांड का उपयोग करने के लिए आपको व्यवस्थापक होना चाहिए।",
        "pt": "❌ Você deve ser um administrador para usar este comando.",
        "ru": "❌ Вы должны быть администратором, чтобы использовать эту команду.",
        "tr": "❌ Bu komutu kullanmak için yönetici olmalısınız.",
        "id": "❌ Anda harus menjadi admin untuk menggunakan perintah ini.",
        "de": "❌ Sie müssen Administrator sein, um diesen Befehl zu verwenden.",
    },
    "no_reply": {
        "en": "❌ Please reply to a message to use this command.",
        "ar": "❌ يرجى الرد على رسالة لاستخدام هذا الأمر.",
        "es": "❌ Por favor responde a un mensaje para usar este comando.",
        "fr": "❌ Veuillez répondre à un message pour utiliser cette commande.",
        "hi": "❌ इस कमांड का उपयोग करने के लिए कृपया एक संदेश का उत्तर दें।",
        "pt": "❌ Por favor, responda a uma mensagem para usar este comando.",
        "ru": "❌ Пожалуйста, ответьте на сообщение, чтобы использовать эту команду.",
        "tr": "❌ Bu komutu kullanmak için lütfen bir mesaja yanıt verin.",
        "id": "❌ Silakan balas pesan untuk menggunakan perintah ini.",
        "de": "❌ Bitte antworten Sie auf eine Nachricht, um diesen Befehl zu verwenden.",
    },
    "groups_only": {
        "en": "❌ This command only works in groups.",
        "ar": "❌ هذا الأمر يعمل فقط في المجموعات.",
        "es": "❌ Este comando solo funciona en grupos.",
        "fr": "❌ Cette commande fonctionne uniquement dans les groupes.",
        "hi": "❌ यह कमांड केवल समूहों में काम करता है।",
        "pt": "❌ Este comando funciona apenas em grupos.",
        "ru": "❌ Эта команда работает только в группах.",
        "tr": "❌ Bu komut yalnızca gruplarda çalışır.",
        "id": "❌ Perintah ini hanya berfungsi di grup.",
        "de": "❌ Dieser Befehl funktioniert nur in Gruppen.",
    },
    "generic_error": {
        "en": "❌ An error occurred. Please try again later.",
        "ar": "❌ حدث خطأ. يرجى المحاولة مرة أخرى لاحقاً.",
        "es": "❌ Ocurrió un error. Por favor intenta de nuevo más tarde.",
        "fr": "❌ Une erreur s'est produite. Veuillez réessayer plus tard.",
        "hi": "❌ एक त्रुटि हुई। कृपया बाद में पुनः प्रयास करें।",
        "pt": "❌ Ocorreu um erro. Por favor, tente novamente mais tarde.",
        "ru": "❌ Произошла ошибка. Пожалуйста, попробуйте позже.",
        "tr": "❌ Bir hata oluştu. Lütfen daha sonra tekrar deneyin.",
        "id": "❌ Terjadi kesalahan. Silakan coba lagi nanti.",
        "de": "❌ Ein Fehler ist aufgetreten. Bitte versuchen Sie es später erneut.",
    },
    "success": {
        "en": "✅ Done!",
        "ar": "✅ تم!",
        "es": "✅ ¡Hecho!",
        "fr": "✅ Fait!",
        "hi": "✅ हो गया!",
        "pt": "✅ Feito!",
        "ru": "✅ Готово!",
        "tr": "✅ Tamamlandı!",
        "id": "✅ Selesai!",
        "de": "✅ Erledigt!",
    },
    # ============================================
    # SYNC COMMAND
    # ============================================
    "sync_success": {
        "en": "✅ Group synced successfully!",
        "ar": "✅ تمت مزامنة المجموعة بنجاح!",
        "es": "✅ ¡Grupo sincronizado exitosamente!",
        "fr": "✅ Groupe synchronisé avec succès!",
        "hi": "✅ समूह सफलतापूर्वक सिंक किया गया!",
        "pt": "✅ Grupo sincronizado com sucesso!",
        "ru": "✅ Группа успешно синхронизирована!",
        "tr": "✅ Grup başarıyla senkronize edildi!",
        "id": "✅ Grup berhasil disinkronkan!",
        "de": "✅ Gruppe erfolgreich synchronisiert!",
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
                "SELECT language_code FROM user_lang_prefs WHERE user_id = $1", user_id
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
                user_id,
                language_code,
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
                chat_id,
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


# get_user_lang is defined below as an async function


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
    "LANGUAGES",
]
