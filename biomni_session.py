import os
import json
import hashlib
import time
import traceback
import random
from datetime import datetime

EMBEDDED_API_KEY = "IDFS8XPknvWNngP5POBOeJzqPkaFKmjT"
AZURE_ENDPOINT = "https://iapi-test.merck.com/gpt/libsupport"
AZURE_DEPLOYMENT = "gpt-5-mini-2025-08-07"
DATA_DIR = "./biomni_data"

MANIFEST_FILE = os.path.join(DATA_DIR, "manifest.json")
LOCK_FILE = os.path.join(DATA_DIR, ".downloading.lock")
COMPLETE_FILE = os.path.join(DATA_DIR, ".download_complete")

try:
    from Biomni.biomni.agent import A1
    from langchain_openai import AzureChatOpenAI
    from langchain_core.messages import HumanMessage
except Exception:
    A1 = None
    AzureChatOpenAI = None
    HumanMessage = None

REQUIRED_FILES = [
    "affinity_capture-ms.parquet",
    "affinity_capture-rna.parquet",
    "BindingDB_All_202409.tsv"
]

def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

def read_manifest():
    if not os.path.exists(MANIFEST_FILE):
        return {}
    try:
        with open(MANIFEST_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def write_manifest(m):
    with open(MANIFEST_FILE, "w") as f:
        json.dump(m, f, indent=2)

def file_checksum(path, chunk_size=8192):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()

def wait_for_lock(timeout=300, poll=1.0):
    start = time.time()
    while os.path.exists(LOCK_FILE):
        if time.time() - start > timeout:
            return False
        time.sleep(poll)
    return True

def download_missing_files(required_files, download_fn, force_refresh=False):
    ensure_data_dir()

    if force_refresh and os.path.exists(COMPLETE_FILE):
        os.remove(COMPLETE_FILE)

    if os.path.exists(COMPLETE_FILE) and not force_refresh:
        missing = [f for f in required_files if not os.path.exists(os.path.join(DATA_DIR, f))]
        if not missing:
            return True, "All files present"

    try:
        fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        we_own_lock = True
    except FileExistsError:
        we_own_lock = False

    if not we_own_lock:
        ok = wait_for_lock()
        if not ok:
            return False, "Timeout waiting for existing download to finish"
        if os.path.exists(COMPLETE_FILE):
            missing = [f for f in required_files if not os.path.exists(os.path.join(DATA_DIR, f))]
            if not missing:
                return True, "Files ready after waiting"
        try:
            fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            we_own_lock = True
        except FileExistsError:
            return False, "Could not acquire lock"

    try:
        manifest = read_manifest()
        updated = False
        for fname in required_files:
            dest = os.path.join(DATA_DIR, fname)
            if os.path.exists(dest):
                rec = manifest.get(fname)
                if rec:
                    continue
                try:
                    checksum = file_checksum(dest)
                    manifest[fname] = {"checksum": checksum, "size": os.path.getsize(dest)}
                    updated = True
                    continue
                except Exception:
                    pass
            ok = download_fn(fname, dest)
            if not ok:
                return False, f"Failed to download {fname}"
            checksum = file_checksum(dest)
            manifest[fname] = {"checksum": checksum, "size": os.path.getsize(dest)}
            updated = True

        if updated:
            write_manifest(manifest)

        with open(COMPLETE_FILE, "w") as f:
            f.write("done")
        return True, "Downloaded or validated files"

    finally:
        try:
            os.remove(LOCK_FILE)
        except Exception:
            pass

class BiomniSession:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.agent = None
            cls._instance.model = None
            cls._instance.initialized = False
            cls._instance.conversation_count = 0
            cls._instance.config = {'recursion_limit': 500, 'configurable': {'thread_id': 1}}
            cls._instance._local_history = []  # list of dicts with role and content
        return cls._instance

    def initialize(self, download_fn=None, force_refresh=False):
        print("initialize: starting")
        ok, msg = download_missing_files(REQUIRED_FILES, download_fn or self._noop_download, force_refresh=force_refresh)
        print(f"ensure data result: {ok}, {msg}")
        if not ok:
            print("initialize: data preparation failed, continuing to try agent init")

        os.environ['AZURE_OPENAI_API_KEY'] = EMDEDDED_API_KEY if 'EMDEDDED_API_KEY' in globals() else EMDEDDED_API_KEY if True else EMDEDDED_API_KEY
        os.environ['OPENAI_API_KEY'] = EMDEDDED_API_KEY if 'EMDEDDED_API_KEY' in globals() else EMDEDDED_API_KEY if True else EMDEDDED_API_KEY

        global A1, AzureChatOpenAI, HumanMessage
        try:
            if A1 is None or AzureChatOpenAI is None or HumanMessage is None:
                from Biomni.biomni.agent import A1
                from langchain_openai import AzureChatOpenAI
                from langchain_core.messages import HumanMessage
        except Exception:
            traceback.print_exc()
            self.initialized = False
            return False

        try:
            self.model = AzureChatOpenAI(
                azure_endpoint=AZURE_ENDPOINT,
                azure_deployment=AZURE_DEPLOYMENT,
                openai_api_version='2023-05-15',
                api_key=EMBEDDED_API_KEY,
            )

            self.agent = A1(path=DATA_DIR, llm=AZURE_DEPLOYMENT, api_key=EMBEDDED_API_KEY)

            try:
                self.agent.llm = self.model
            except Exception:
                pass

            self.initialized = True
            self.conversation_count = 0
            self.config = {'recursion_limit': 500, 'configurable': {'thread_id': 1}}
            self._local_history = []
            print("initialize: agent ready")
            return True

        except Exception:
            traceback.print_exc()
            self.initialized = False
            return False

    def _noop_download(self, fname, dest):
        print(f"_noop_download called for {fname}, creating empty file at {dest}")
        try:
            with open(dest, "wb") as f:
                f.write(b"")
            return True
        except Exception:
            return False

    def send_message(self, message, is_first_message=False):
        if not self.initialized or self.agent is None:
            return False, "Agent not initialized", None

        self._local_history.append({"role": "user", "content": message})

        try:
            state = None
            try:
                state = self.agent.app.get_state(self.config)
            except Exception:
                state = None

            if state:
                # try streaming with combined messages from local history and state if available
                existing = state.values.get('messages', [])
                # convert local history into HumanMessage objects appended to existing
                combined = list(existing)
                for entry in self._local_history:
                    if entry['role'] == 'user':
                        combined.append(HumanMessage(content=entry['content']))
                inputs = {'messages': combined, 'next_step': None}
                conversation_log = []
                final_message = None
                for s in self.agent.app.stream(inputs, stream_mode='values', config=self.config):
                    msg_list = s.get('messages', []) or []
                    if not msg_list:
                        continue
                    msg = msg_list[-1]
                    conversation_log.append(str(msg))
                    final_message = msg
                if final_message:
                    self.conversation_count += 1
                    final_text = getattr(final_message, 'content', str(final_message))
                    self._local_history.append({"role": "assistant", "content": final_text})
                    return True, conversation_log, final_text
                # fall through to fallback
            # Fallback to agent.go using the most recent user message
            log, final_response = self.agent.go(message)
            self.conversation_count += 1
            self._local_history.append({"role": "assistant", "content": final_response})
            return True, log, final_response

        except Exception:
            traceback.print_exc()
            return False, "Error sending message", None

    def reset_conversation(self):
        if not self.initialized:
            return False
        self.config = {'recursion_limit': 500, 'configurable': {'thread_id': random.randint(1, 10000)}}
        self.conversation_count = 0
        self._local_history = []
        return True

    def get_status(self):
        return {
            'initialized': self.initialized,
            'agent_present': self.agent is not None,
            'conversation_count': self.conversation_count,
            'config': self.config
        }

biomni_session = BiomniSession()
