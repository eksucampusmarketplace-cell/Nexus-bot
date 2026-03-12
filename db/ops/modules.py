import json
import logging
from db.client import db

logger = logging.getLogger(__name__)

async def get_modules(chat_id: int):
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow("SELECT modules FROM groups WHERE chat_id = $1", chat_id)
        if row and row['modules']:
            modules = row['modules']
            if isinstance(modules, str):
                modules = json.loads(modules)
            return modules
        return {}

async def set_module(chat_id: int, module_name: str, enabled: bool):
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow("SELECT modules FROM groups WHERE chat_id = $1", chat_id)
        modules = {}
        if row and row['modules']:
            modules = row['modules']
            if isinstance(modules, str):
                modules = json.loads(modules)
        
        modules[module_name] = enabled
        
        await conn.execute(
            "UPDATE groups SET modules = $1 WHERE chat_id = $2",
            json.dumps(modules), chat_id
        )
        logger.info(f"[TOGGLE] Module toggled | chat_id={chat_id} | module={module_name} | enabled={enabled}")
        return True
