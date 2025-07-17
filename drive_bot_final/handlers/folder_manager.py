import time
from rapidfuzz import process

class FolderManager:
    def __init__(self, gdrive, cache_ttl=3600):
        self.gdrive = gdrive
        self.cache = {}
        self.cache_ttl = cache_ttl
        self.cache_time: float = 0.0
    
    async def get_contractor_folders_async(self):
        now = time.time()
        if 'contractor_folders' not in self.cache or now - self.cache_time > self.cache_ttl:
            folders = await self.gdrive.list_folders()
            self.cache['contractor_folders'] = {f['name']: f['id'] for f in folders}
            self.cache_time = now
        return self.cache['contractor_folders']
    
    async def get_suggestions_async(self, filename):
        folders = await self.get_contractor_folders_async()
        words = filename.lower().replace('_', ' ').split()
        suggestions = []
        for folder_name, folder_id in folders.items():
            for word in words:
                if len(word) > 2:
                    matches = process.extract(word, [folder_name.lower()], limit=1)
                    if matches and matches[0][1] > 70:
                        suggestions.append((folder_name, folder_id))
                        break
        return suggestions[:3]
