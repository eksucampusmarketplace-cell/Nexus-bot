"""
api/routes/backup.py

Backup & Restore system for group configurations.
Export and import all group settings as JSON.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from datetime import datetime
from api.auth import get_current_user
from db.client import db
from bot.utils.input_sanitizer import validate_multiple_inputs

router = APIRouter(prefix="/api/groups")


@router.get("/{chat_id}/backup")
async def export_backup(chat_id: int, user: dict = Depends(get_current_user)):
    """
    Export full group configuration as JSON.
    Includes settings, automod config, modules, webhooks, text config.
    """
    async with db.pool.acquire() as conn:
        # Get group settings
        group_row = await conn.fetchrow(
            "SELECT * FROM groups WHERE chat_id = $1", chat_id
        )
        if not group_row:
            raise HTTPException(404, "Group not found")
        
        group_data = dict(group_row)
        # Remove internal fields
        for key in ['id']:
            group_data.pop(key, None)
        
        # Get automod settings
        automod_row = await conn.fetchrow(
            "SELECT * FROM automod_settings WHERE chat_id = $1", chat_id
        )
        automod_data = dict(automod_row) if automod_row else {}
        
        # Get modules
        modules = group_data.get('modules', {})
        if isinstance(modules, str):
            import json
            modules = json.loads(modules)
        
        # Get text config
        text_config = group_data.get('text_config', {})
        if isinstance(text_config, str):
            import json
            text_config = json.loads(text_config)
        
        # Get webhooks
        webhook_rows = await conn.fetch(
            "SELECT url, events, secret FROM webhooks WHERE chat_id = $1",
            chat_id
        )
        webhooks = [dict(row) for row in webhook_rows]
        
        # Get log channel
        log_channel_row = await conn.fetchrow(
            "SELECT channel_id FROM log_channels WHERE chat_id = $1",
            chat_id
        )
        log_channel = log_channel_row['channel_id'] if log_channel_row else None

    backup_data = {
        'version': '1.0',
        'exported_at': datetime.utcnow().isoformat(),
        'chat_id': chat_id,
        'group': {
            'title': group_data.get('title'),
            'settings': {
                'modules': modules,
                'text_config': text_config,
                'silent_commands': group_data.get('silent_commands', False),
                'delete_join_leave': group_data.get('delete_join_leave', False),
                'inline_mode_enabled': group_data.get('inline_mode_enabled', False),
                'booster_enabled': group_data.get('booster_enabled', False),
            }
        },
        'automod': {
            'settings': automod_data.get('settings', {}),
            'locks': automod_data.get('locks', {}),
            'penalties': automod_data.get('penalties', {}),
            'time_windows': automod_data.get('time_windows', {}),
        },
        'webhooks': webhooks,
        'log_channel': log_channel,
    }

    return JSONResponse(
        content=backup_data,
        headers={
            'Content-Disposition': f'attachment; filename=nexus_backup_{chat_id}_{datetime.utcnow().strftime("%Y%m%d")}.json'
        }
    )


@router.post("/{chat_id}/restore")
async def import_backup(chat_id: int, request: Request, user: dict = Depends(get_current_user)):
    """
    Restore group configuration from exported JSON.
    Only restores compatible settings, preserves member data.
    """
    body = await request.json()
    
    # Validate version
    if body.get('version') != '1.0':
        raise HTTPException(400, "Unsupported backup version. Expected 1.0")
    
    # Validate and sanitize input fields
    # Define validation rules for different fields
    validation_rules = {
        'version': {'max_length': 10, 'check_sql': True, 'check_xss': False, 'check_command': True},
        'exported_at': {'max_length': 50, 'check_sql': True, 'check_xss': True, 'check_command': True},
        'chat_id': {'max_length': 20, 'check_sql': True, 'check_xss': True, 'check_command': True},
    }
    
    # Extract string fields for validation
    inputs_to_validate = {}
    if 'version' in body:
        inputs_to_validate['version'] = str(body.get('version'))
    if 'exported_at' in body:
        inputs_to_validate['exported_at'] = str(body.get('exported_at'))
    if 'chat_id' in body:
        inputs_to_validate['chat_id'] = str(body.get('chat_id'))
    
    # Validate inputs
    is_valid, errors = validate_multiple_inputs(inputs_to_validate, validation_rules)
    
    if not is_valid:
        error_messages = ', '.join(f"{k}: {v['message']}" for k, v in errors.items())
        raise HTTPException(
            400,
            f"Invalid backup data: {error_messages}"
        )
    
    # Additional security: Check for malicious JSON structure
    if 'group' in body and isinstance(body['group'], dict):
        group_data = body['group']
        if 'settings' in group_data:
            # Ensure settings is a dict
            if not isinstance(group_data['settings'], dict):
                raise HTTPException(400, "Invalid settings format in backup")
    
    if 'automod' in body and isinstance(body['automod'], dict):
        # Validate automod settings structure
        for key in ['settings', 'locks', 'penalties', 'time_windows']:
            if key in body['automod'] and not isinstance(body['automod'][key], dict):
                raise HTTPException(400, f"Invalid {key} format in automod settings")
    
    async with db.pool.acquire() as conn:
        # Verify group exists
        exists = await conn.fetchval(
            "SELECT 1 FROM groups WHERE chat_id = $1", chat_id
        )
        if not exists:
            raise HTTPException(404, "Group not found")
        
        # Restore group settings
        group_data = body.get('group', {})
        settings = group_data.get('settings', {})
        
        import json
        
        await conn.execute(
            """UPDATE groups SET
                modules = $1::jsonb,
                text_config = $2::jsonb,
                silent_commands = $3,
                delete_join_leave = $4,
                inline_mode_enabled = $5,
                booster_enabled = $6
               WHERE chat_id = $7""",
            json.dumps(settings.get('modules', {})),
            json.dumps(settings.get('text_config', {})),
            settings.get('silent_commands', False),
            settings.get('delete_join_leave', False),
            settings.get('inline_mode_enabled', False),
            settings.get('booster_enabled', False),
            chat_id
        )
        
        # Restore automod settings
        automod_data = body.get('automod', {})
        if automod_data:
            await conn.execute(
                """INSERT INTO automod_settings (chat_id, settings, locks, penalties, time_windows)
                   VALUES ($1, $2::jsonb, $3::jsonb, $4::jsonb, $5::jsonb)
                   ON CONFLICT (chat_id) DO UPDATE SET
                       settings = EXCLUDED.settings,
                       locks = EXCLUDED.locks,
                       penalties = EXCLUDED.penalties,
                       time_windows = EXCLUDED.time_windows""",
                chat_id,
                json.dumps(automod_data.get('settings', {})),
                json.dumps(automod_data.get('locks', {})),
                json.dumps(automod_data.get('penalties', {})),
                json.dumps(automod_data.get('time_windows', {}))
            )
        
        # Restore log channel
        log_channel = body.get('log_channel')
        if log_channel:
            await conn.execute(
                """INSERT INTO log_channels (chat_id, channel_id)
                   VALUES ($1, $2)
                   ON CONFLICT (chat_id) DO UPDATE SET channel_id = $2""",
                chat_id, log_channel
            )
        
        # Note: We don't restore webhooks automatically for security
        # Admins need to reconfigure webhooks manually

    return {
        'status': 'restored',
        'restored_at': datetime.utcnow().isoformat(),
        'restored_sections': ['group_settings', 'automod', 'log_channel'],
        'note': 'Webhooks not restored for security. Please reconfigure manually.'
    }
