import asyncio
import logging
from bot.ml.spam_classifier import classifier
from db.client import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    logger.info("Starting training...")
    
    # Initialize DB connection
    await db.connect()
    
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
            return

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
        else:
            logger.error(f"Training failed: {result.get('error')}")
            
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
