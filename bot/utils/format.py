from telegram import User

def format_user(user: User) -> str:
    if user.username:
        return f"@{user.username}"
    return f"<a href='tg://user?id={user.id}'>{user.first_name}</a>"

def format_stats(stats: dict) -> str:
    return (
        f"📊 <b>Group Statistics</b>\n\n"
        f"👥 Members: {stats.get('member_count', 'N/A')}\n"
        f"💬 Total Messages: {stats.get('total_messages', 0)}\n"
        f"⚠️ Total Warnings: {stats.get('total_warns', 0)}\n"
    )
