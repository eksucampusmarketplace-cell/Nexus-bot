import re

def parse_duration(duration_str: str) -> int:
    if not duration_str:
        return 0
    
    match = re.match(r"(\d+)([smhd])", duration_str.lower())
    if not match:
        return 0
    
    amount = int(match.group(1))
    unit = match.group(2)
    
    if unit == 's':
        return amount
    elif unit == 'm':
        return amount * 60
    elif unit == 'h':
        return amount * 3600
    elif unit == 'd':
        return amount * 86400
    return 0
