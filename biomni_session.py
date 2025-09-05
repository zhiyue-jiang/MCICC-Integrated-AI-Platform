#biomni_session.py

import os
import traceback
import random
from datetime import datetime

EMBEDDED_API_KEY = "IDFS8XPknvWNngP5POBOeJzqPkaFKmjT"
AZURE_ENDPOINT = "https://iapi-test.merck.com/gpt/libsupport"
AZURE_DEPLOYMENT = "gpt-5-mini-2025-08-07"
DATA_PATH = "./biomni_data"

try:
    from Biomni.biomni.agent import A1
    from langchain_openai import AzureChatOpenAI
    from langchain_core.messages import HumanMessage
except Exception:
    A1 = None
    AzureChatOpenAI = None
    HumanMessage = None


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
        return cls._instance

    def initialize(self, api_key=None, azure_endpoint=None, azure_deployment=None, data_path=None):
        api_key = api_key or EMBEDDED_API_KEY
        azure_endpoint = azure_endpoint or AZURE_ENDPOINT
        azure_deployment = azure_deployment or AZURE_DEPLOYMENT
        data_path = data_path or DATA_PATH

        os.environ['AZURE_OPENAI_API_KEY'] = api_key
        os.environ['OPENAI_API_KEY'] = api_key

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
                azure_endpoint=azure_endpoint,
                azure_deployment=azure_deployment,
                openai_api_version='2023-05-15',
                api_key=api_key,
            )

            self.agent = A1(path=data_path, llm=azure_deployment, api_key=api_key)

            try:
                self.agent.llm = self.model
            except Exception:
                pass

            self.initialized = True
            self.conversation_count = 0
            self.config = {'recursion_limit': 500, 'configurable': {'thread_id': 1}}
            return True

        except Exception:
            traceback.print_exc()
            self.initialized = False
            return False

    def send_message(self, message, is_first_message=False):
        if not self.initialized or self.agent is None:
            return False, "Agent not initialized", None

        try:
            if is_first_message or self.conversation_count == 0:
                log, final_response = self.agent.go(message)
                self.conversation_count += 1
                return True, log, final_response

            try:
                state = self.agent.app.get_state(self.config)
                messages = state.values.get('messages', [])
                messages.append(HumanMessage(content=message))

                inputs = {'messages': messages, 'next_step': None}
                conversation_log = []
                final_message = None

                for s in self.agent.app.stream(inputs, stream_mode='values', config=self.config):
                    msg_list = s.get('messages', [])
                    if not msg_list:
                        continue
                    msg = msg_list[-1]
                    conversation_log.append(str(msg))
                    final_message = msg

                if final_message:
                    self.conversation_count += 1
                    final_text = getattr(final_message, 'content', str(final_message))
                    return True, conversation_log, final_text
                else:
                    return False, "No streamed response", None

            except Exception:
                try:
                    log, final_response = self.agent.go(message)
                    self.conversation_count += 1
                    return True, log, final_response
                except Exception:
                    traceback.print_exc()
                    return False, "Streaming and fallback both failed", None

        except Exception:
            traceback.print_exc()
            return False, "Error sending message", None

    def reset_conversation(self):
        if not self.initialized:
            return False
        self.config = {'recursion_limit': 500, 'configurable': {'thread_id': random.randint(1, 10000)}}
        self.conversation_count = 0
        return True

    def get_status(self):
        return {
            'initialized': self.initialized,
            'agent_present': self.agent is not None,
            'conversation_count': self.conversation_count,
            'config': self.config
        }

import os
import json
import hashlib
import time

DATA_DIR = "./biomni_data"
MANIFEST_FILE = os.path.join(DATA_DIR, "manifest.json")
LOCK_FILE = os.path.join(DATA_DIR, ".downloading.lock")
COMPLETE_FILE = os.path.join(DATA_DIR, ".download_complete")

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
        # completed previously; do a quick existence check and return
        missing = [f for f in required_files if not os.path.exists(os.path.join(DATA_DIR, f))]
        if not missing:
            return True, "All files present"
        # else fall through to standard download logic

    # Acquire lock by creating lock file; if exists, wait
    try:
        # fast path: try to create lock file atomically
        fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        we_own_lock = True
    except FileExistsError:
        we_own_lock = False

    if not we_own_lock:
        ok = wait_for_lock()
        if not ok:
            return False, "Timeout waiting for existing download to finish"
        # Another process finished; check for completeness
        if os.path.exists(COMPLETE_FILE):
            return True, "Files ready after waiting"
        # If not complete, try to acquire lock again
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
                    # assume present and valid
                    continue
                try:
                    checksum = file_checksum(dest)
                    manifest[fname] = {"checksum": checksum, "size": os.path.getsize(dest)}
                    updated = True
                    continue
                except Exception:
                    pass
            # download the file using your downloader
            ok = download_fn(fname, dest)
            if not ok:
                return False, f"Failed to download {fname}"
            checksum = file_checksum(dest)
            manifest[fname] = {"checksum": checksum, "size": os.path.getsize(dest)}
            updated = True

        if updated:
            write_manifest(manifest)

        # write marker for completion
        with open(COMPLETE_FILE, "w") as f:
            f.write("done")
        return True, "Downloaded or validated files"

    finally:
        try:
            os.remove(LOCK_FILE)
        except Exception:
            pass



biomni_session = BiomniSession()
