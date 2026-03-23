from fastapi import APIRouter, Depends, HTTPException, Query

from api.auth import get_current_user
from bot.registry import get_all

router = APIRouter()


@router.get("/photo/{file_id}")
async def get_group_photo(file_id: str, user: dict = Depends(get_current_user)):
    """
    Get a photo by file_id using the bot's API.
    Returns the direct file URL from Telegram.
    """
    # Get any available bot
    bots = get_all()
    if not bots:
        raise HTTPException(status_code=503, detail="Bot service unavailable")

    # Bug #24 fix: Check cached_bot_info for is_primary since bot_data["is_primary"] is the correct key
    bot_instance = None
    for bid, app in bots.items():
        if app.bot_data.get("is_primary"):
            bot_instance = app.bot
            break

    if not bot_instance:
        # Use any available bot
        bot_instance = next(iter(bots.values())).bot

    try:
        # Get the file from Telegram
        file = await bot_instance.get_file(file_id)

        # Return the file URL - this can be used directly in img src
        # The URL is valid for ~1 hour
        return {
            "file_id": file_id,
            "file_url": file.file_path,
            "width": getattr(file, "width", None),
            "height": getattr(file, "height", None),
            "file_size": getattr(file, "file_size", None),
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Failed to get photo: {str(e)}")
