import os
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError
import uuid

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("MONGODB_DB_NAME", "aura_db")

class InMemoryCollection:
    def __init__(self):
        self._data = []

    def create_index(self, *args, **kwargs):
        pass

    def find(self, query=None):
        class MockCursor(list):
            def sort(self, key_or_list, direction=1):
                # Mimic pymongo's cursor.sort(field_name, direction)
                if isinstance(key_or_list, str):
                    reverse = direction == -1
                    list.sort(self, key=lambda d: d.get(key_or_list, ""), reverse=reverse)
                return self

            def limit(self, n):
                del self[n:]
                return self

            def skip(self, n):
                del self[:n]
                return self

        if not query:
            return MockCursor(list(self._data))
        res = []
        for doc in self._data:
            match = True
            for k, v in query.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                res.append(doc)
        return MockCursor(res)

    def find_one(self, query):
        res = self.find(query)
        return res[0] if res else None

    def insert_one(self, doc):
        if "_id" not in doc:
            doc["_id"] = f"mem_id_{uuid.uuid4().hex[:10]}"
        self._data.append(doc)
        return doc

    def update_one(self, filter_query, update_query):
        doc = self.find_one(filter_query)
        if not doc:
            return None
            
        inc_op = update_query.get("$inc", {})
        push_op = update_query.get("$push", {})
        set_op = update_query.get("$set", {})
        
        # Emulate $inc
        for key, val in inc_op.items():
            doc[key] = doc.get(key, 0) + val
            
        # Emulate $push
        for key, val in push_op.items():
            if key not in doc:
                doc[key] = []
            doc[key].append(val)

        # Emulate $set
        for key, val in set_op.items():
            doc[key] = val
            
        return doc

    def delete_one(self, query):
        doc = self.find_one(query)
        if doc and doc in self._data:
            self._data.remove(doc)

    def delete_many(self, query):
        docs = list(self.find(query))
        for doc in docs:
            if doc in self._data:
                self._data.remove(doc)

class InMemoryDatabase:
    def __init__(self):
        self.users = InMemoryCollection()
        self.payment_requests = InMemoryCollection()
        self.marketing_diagnoses = InMemoryCollection()
        self.seo_diagnostics = InMemoryCollection()
        self.campaigns = InMemoryCollection()
        self.touchpoints = InMemoryCollection()
        self.audit_logs = InMemoryCollection()

    def __getattr__(self, name):
        collection = InMemoryCollection()
        setattr(self, name, collection)
        return collection

in_memory_db = InMemoryDatabase()

def init_db_indexes(db_instance):
    """Initializes high-performance database indexes & TTL expiration rules."""
    try:
        db_instance.users.create_index("email", unique=True)
        db_instance.marketing_diagnoses.create_index([("user_email", 1), ("created_at", -1)])
        db_instance.seo_diagnostics.create_index([("user_email", 1), ("created_at", -1)])
        db_instance.campaigns.create_index([("user_email", 1), ("created_at", -1)])
        db_instance.touchpoints.create_index([("campaign_id", 1), ("timestamp", -1)])
        db_instance.touchpoints.create_index("user_identifier")
        db_instance.audit_logs.create_index("created_at", expireAfterSeconds=2592000) # 30 days TTL
    except Exception as err:
        print(f"Index initialization notice: {err}")

# Try connecting to the MongoDB daemon
try:
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=1500)
    client.admin.command('ping')
    db = client[DATABASE_NAME]
    init_db_indexes(db)
    print("SUCCESS: Connected to MongoDB instance. Indexes initialized.")
except (ServerSelectionTimeoutError, Exception) as e:
    print(f"WARNING: MongoDB offline ({e}). Initializing secure in-memory database fallback.")
    db = in_memory_db
    init_db_indexes(db)

def get_db():
    """Returns connection-ready Database instance (MongoDB or InMemory fallback)."""
    yield db
