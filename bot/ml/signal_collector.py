import logging
import json
from db.client import db

logger = logging.getLogger(__name__)

async def record_spam_signal(
    user_id: int, chat_id: int, message_text: str,
    signal_type: str, label: str,
    confidence: float = 1.0, metadata: dict = None
) -> None:
    """Insert into spam_signals. Catch ALL exceptions silently."""
    try:
        query = """
            INSERT INTO spam_signals (user_id, chat_id, message_text, signal_type, label, confidence, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
        """
        async with db.pool.acquire() as conn:
            await conn.execute(
                query, 
                user_id, 
                chat_id, 
                message_text, 
                signal_type, 
                label, 
                confidence, 
                json.dumps(metadata) if metadata else None
            )
    except Exception as e:
        logger.debug(f"Failed to record spam signal: {e}")

class VoteSession:
    def __init__(self, target_user_id, chat_id, scam_type, result, upvotes, downvotes, target_message_id, message_text=None):
        self.target_user_id = target_user_id
        self.chat_id = chat_id
        self.scam_type = scam_type
        self.result = result
        self.report_count = upvotes
        self.legit_count = downvotes
        self.target_message_id = target_message_id
        self.message_text = message_text

    def passed(self):
        return self.result == 'passed'

async def record_vote_outcome(session: VoteSession) -> None:
    """
    Called when a community vote closes.
    session is a VoteSession object with:
      .target_user_id, .chat_id, .scam_type, .passed(),
      .report_count, .legit_count, .target_message_id
    """
    try:
        label = 'spam' if session.passed() else 'ham'
        total_votes = session.report_count + session.legit_count
        confidence = session.report_count / total_votes if total_votes > 0 else 0.5
        
        # Try to get original message text if possible
        # Since we don't have the context or bot here, we might need to pass it or just use None
        # But wait, the session might have the text if we store it there.
        # For now, let's assume session.message_text exists or we'll get it from metadata if stored.
        message_text = getattr(session, 'message_text', None)
        
        metadata = {
            'scam_type': session.scam_type,
            'report_count': session.report_count,
            'legit_count': session.legit_count,
            'target_message_id': session.target_message_id
        }
        
        await record_spam_signal(
            user_id=session.target_user_id,
            chat_id=session.chat_id,
            message_text=message_text,
            signal_type='community_vote',
            label=label,
            confidence=confidence,
            metadata=metadata
        )
    except Exception as e:
        logger.debug(f"Failed to record vote outcome: {e}")

async def record_mod_action(
    user_id: int, chat_id: int, action: str, reason: str
) -> None:
    """action: 'ban' | 'warn' | 'mute' | 'kick'"""
    try:
        if action == 'ban':
            label = 'spam'
            confidence = 0.9
        elif action == 'warn':
            label = 'uncertain'
            confidence = 0.7
        elif action == 'mute':
            label = 'uncertain'
            confidence = 0.6
        else:
            label = 'uncertain'
            confidence = 0.5
            
        await record_spam_signal(
            user_id=user_id,
            chat_id=chat_id,
            message_text=None,
            signal_type='mod_action',
            label=label,
            confidence=confidence,
            metadata={'action': action, 'reason': reason}
        )
    except Exception as e:
        logger.debug(f"Failed to record mod action signal: {e}")

async def record_pattern_match(
    user_id: int, chat_id: int, message_text: str, pattern_type: str
) -> None:
    """Called when community_vote.py detect_scam() fires"""
    try:
        await record_spam_signal(
            user_id=user_id,
            chat_id=chat_id,
            message_text=message_text,
            signal_type='pattern_match',
            label='spam',
            confidence=0.8,
            metadata={'pattern_type': pattern_type}
        )
    except Exception as e:
        logger.debug(f"Failed to record pattern match signal: {e}")
