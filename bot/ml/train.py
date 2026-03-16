import asyncio
import logging
from bot.ml.spam_classifier import classifier
from db.client import db
from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    logger.info("Starting training...")

    # Initialize DB connection
    await db.connect()

    # Track if we need to notify
    notify_success = False
    notify_failure = False
    training_result = None

    try:
        # Load samples
        async with db.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT message_text, label FROM spam_signals WHERE label IN ('spam', 'ham') AND message_text IS NOT NULL"
            )

        spam_count = sum(1 for r in rows if r['label'] == 'spam')
        ham_count = sum(1 for r in rows if r['label'] == 'ham')

        logger.info(f"Loaded {len(rows)} samples ({spam_count} spam / {ham_count} ham)")

        if len(rows) < 100:
            logger.error("Not enough samples to train (need at least 100 for basic testing).")
            notify_failure = True
            training_result = {"error": "Not enough samples", "samples": len(rows)}
        else:
            logger.info("Training...")
            import time
            start = time.time()
            result = await classifier.train(min_samples=100) # Lowering for manual run if needed
            duration = time.time() - start

            if result.get('trained'):
                logger.info(f"Done in {duration:.1f}s")
                logger.info(f"Accuracy: {result['accuracy']:.3f}")
                logger.info(f"Classification Report:\n{result['report']}")
                import os
                from bot.ml.spam_classifier import MODEL_PATH
                size = os.path.getsize(MODEL_PATH) / (1024 * 1024)
                logger.info(f"Model saved to {MODEL_PATH} ({size:.1f}MB)")
                notify_success = True
                training_result = result
            else:
                logger.error(f"Training failed: {result.get('error')}")
                notify_failure = True
                training_result = result

    except Exception as e:
        logger.error(f"Training error: {e}")
        notify_failure = True
        training_result = {"error": str(e)}

    finally:
        # Send notifications if OWNER_ID is configured
        if settings.OWNER_ID and (notify_success or notify_failure):
            try:
                from bot.utils.error_notifier import notify_owner
                from telegram import Bot

                # Create a temporary bot instance for notification
                bot = Bot(token=settings.PRIMARY_BOT_TOKEN)

                if notify_success:
                    await notify_owner(
                        bot,
                        settings.OWNER_ID,
                        "ML_TRAINING_COMPLETE",
                        context={
                            "accuracy": training_result.get('accuracy', 0),
                            "samples": training_result.get('samples', 0)
                        },
                        pool=db.pool
                    )
                elif notify_failure:
                    await notify_owner(
                        bot,
                        settings.OWNER_ID,
                        "ML_TRAINING_FAILED",
                        context={
                            "error": training_result.get('error', 'Unknown error'),
                            "samples": training_result.get('samples', 0)
                        },
                        pool=db.pool
                    )

                await bot.session.close()
            except Exception as notify_err:
                logger.warning(f"[TRAIN] Failed to send notification: {notify_err}")

        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
