"""Opt-in Mem0 adapter. Never automatically ingest private conversation text.
Only explicitly approved, non-sensitive facts may be indexed.
"""
class Mem0Adapter:
    def __init__(self, config=None):
        from mem0 import Memory
        self.memory = Memory.from_config(config) if config else Memory()

    def add_consented_fact(self, contact_id, fact, consent=False):
        if consent is not True:
            raise PermissionError('Explicit consent is required before indexing a fact')
        if not isinstance(fact, str) or not 1 <= len(fact) <= 500:
            raise ValueError('Invalid fact')
        return self.memory.add([{'role': 'user', 'content': fact}], user_id=contact_id, infer=False)

    def search(self, contact_id, query, consent=False):
        if consent is not True:
            raise PermissionError('Explicit consent is required before searching memory')
        return self.memory.search(query, filters={'user_id': contact_id})

    def delete_contact(self, contact_id):
        return self.memory.delete_all(user_id=contact_id)
