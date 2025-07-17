import time
from collections import defaultdict
from typing import Dict, List

class RateLimiter:
    def __init__(self, requests_per_minute: int = 30):
        self.requests_per_minute = requests_per_minute
        self.user_requests: Dict[int, List[float]] = defaultdict(list)
    
    def is_allowed(self, user_id: int) -> bool:
        now = time.time()
        user_requests = self.user_requests[user_id]
        cutoff = now - 60
        user_requests[:] = [req for req in user_requests if req > cutoff]
        if len(user_requests) >= self.requests_per_minute:
            return False
        user_requests.append(now)
        return True
    
    def get_reset_time(self, user_id: int) -> int:
        if not self.user_requests[user_id]:
            return 0
        oldest_request = min(self.user_requests[user_id])
        return int(oldest_request + 60 - time.time()) 