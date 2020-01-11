import secrets
import threading

class ActorId(object):
    _rand_id_lock = threading.Lock()

    def __init__(self, id):
        if not isinstance(id, str):
            raise TypeError(f"Argument id must be of type str, not {type(id)}")
        self._id = id
    
    def create_random(self):
        random_id = ""

        with self._rand_id_lock:
            random_id = secrets.token_hex(8)

        return ActorId(random_id)
    
    @property
    def id(self):
        return self._id
    
    def __hash__(self):
        return hash(self._id)
    
    def __str__(self):
        # TODO: maybe it needs prefix
        return "{}".format(self._id)
    
    def __eq__(self, other):
        if not other:
            return False
        
        return self._id == other.id

    def __ne__(self, other):
        if not other:
            return False

        return self._id != other.id