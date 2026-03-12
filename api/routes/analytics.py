import random
from fastapi import APIRouter, Depends, HTTPException
from api.auth import get_current_user
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/groups")

@router.get("/{chat_id}/analytics")
async def group_analytics(chat_id: int, user: dict = Depends(get_current_user)):
    # Generate mock analytics data for now, since we just added tracking
    # In a real app, query from actions_log and messages count
    
    # Activity Line Chart (30 days)
    activity = []
    now = datetime.now()
    for i in range(30):
        date = (now - timedelta(days=29-i)).strftime("%Y-%m-%d")
        activity.append({"date": date, "messages": random.randint(100, 500)})
    
    # Member Growth
    growth = []
    current_members = 1000
    for i in range(30):
        date = (now - timedelta(days=29-i)).strftime("%Y-%m-%d")
        joins = random.randint(5, 20)
        leaves = random.randint(0, 10)
        current_members += (joins - leaves)
        growth.append({"date": date, "joins": joins, "leaves": leaves, "total": current_members})
        
    # Module Activity Pie
    modules = [
        {"name": "antispam", "actions": 45},
        {"name": "antiflood", "actions": 32},
        {"name": "warn_system", "actions": 21},
        {"name": "welcome_message", "actions": 88},
        {"name": "word_filter", "actions": 12}
    ]
    
    return {
        "activity": activity,
        "growth": growth,
        "modules": modules
    }

@router.get("/{chat_id}/analytics/heatmap")
async def sentiment_heatmap(chat_id: int, user: dict = Depends(get_current_user)):
    # 7x24 grid data
    heatmap = []
    for day in range(7):
        for hour in range(24):
            heatmap.append({
                "day": day,
                "hour": hour,
                "count": random.randint(10, 100),
                "sentiment": random.uniform(-1, 1) # -1 (negative) to 1 (positive)
            })
    return heatmap
