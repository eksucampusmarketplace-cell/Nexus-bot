import asyncio
import logging
import json
from datetime import datetime, timezone
from bot.handlers.channel import send_to_channel

logger = logging.getLogger(__name__)


async def scheduled_post_runner(db_pool, bot_registry):
    logger.info("[SCHEDULER] Started scheduled post runner")

    while True:
        try:
            now = datetime.now(timezone.utc)
            async with db_pool.acquire() as conn:
                due_posts = await conn.fetch(
                    """
                    SELECT * FROM channel_posts 
                    WHERE status = 'scheduled' AND scheduled_at <= $1
                """,
                    now,
                )

            for post in due_posts:
                try:
                    # Registry is a global function in main.py, I'll need to pass it or import it.
                    # Since it's passed here as bot_registry
                    ptb_app = bot_registry(post["bot_id"])
                    if not ptb_app:
                        logger.warning(f"[SCHEDULER] Bot not in registry | bot_id={post['bot_id']}")
                        continue

                    msg = await send_to_channel(
                        bot=ptb_app.bot,
                        channel_id=post["channel_id"],
                        text=post["text"],
                        media_file_id=post.get("media_file_id"),
                        media_type=post.get("media_type"),
                    )

                    async with db_pool.acquire() as conn:
                        await conn.execute(
                            """
                            UPDATE channel_posts 
                            SET status = 'sent', sent_at = $1, sent_message_id = $2
                            WHERE id = $3
                        """,
                            datetime.now(timezone.utc),
                            msg.message_id,
                            post["id"],
                        )

                    logger.info(
                        f"[SCHEDULER] Sent scheduled post | post_id={post['id']} | channel={post['channel_id']}"
                    )

                except Exception as e:
                    logger.error(
                        f"[SCHEDULER] Failed to send post_id={post['id']}: {e}", exc_info=True
                    )
                    async with db_pool.acquire() as conn:
                        await conn.execute(
                            """
                            UPDATE channel_posts 
                            SET status = 'failed', fail_reason = $1 
                            WHERE id = $2
                        """,
                            str(e),
                            post["id"],
                        )

        except Exception as e:
            logger.error(f"[SCHEDULER] Runner error: {e}", exc_info=True)

        await asyncio.sleep(60)
