import os
import traceback
import random
from datetime import datetime

EMBEDDED_API_KEY = "aJjnb4X80rE0GWSYAcf5hpwKia8omZ2o"
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
            cls._instance._local_history = []
        return cls._instance

    def initialize(self, download_fn=None, force_refresh=False, api_key=None, azure_endpoint=None, azure_deployment=None, data_path=None):
        print("🚀 Initializing agent...")
        api_key = api_key or EMBEDDED_API_KEY
        azure_endpoint = azure_endpoint or AZURE_ENDPOINT
        azure_deployment = azure_deployment or AZURE_DEPLOYMENT
        data_path = data_path or DATA_PATH

        # Ensure local data files are present
        try:
            ok, msg = download_missing_files(REQUIRED_FILES, download_fn or self._noop_download, force_refresh=force_refresh)
            print(f"ensure data result: {ok} - {msg}")
        except Exception:
            print("ensure data call failed, continuing initialization")
            traceback.print_exc()

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
            self._local_history = []
            print("✅ MCICC agent initialized successfully")
            return True

        except Exception as e:
            print(f"❌ Failed to initialize agent: {str(e)}")
            traceback.print_exc()
            self.initialized = False
            return False

    def send_message(self, message, is_first_message=False):
        if not self.initialized:
            return False, "Agent not initialized", None

        try:
            print(f"💬 Processing message #{self.conversation_count + 1}: {message[:50]}...")
            # Append to local history
            self._local_history.append({'role': 'user', 'content': message})

            # If first message or no prior conversation, use agent.go()
            if is_first_message or self.conversation_count == 0:
                log, final_response = self.agent.go(message)
                self.conversation_count += 1
                # store assistant reply in local history
                self._local_history.append({'role': 'assistant', 'content': final_response})
                return True, log, final_response

            # Try to get agent state and stream with combined history
            try:
                current_state = self.agent.app.get_state(self.config)
            except Exception:
                current_state = None

            if current_state:
                current_messages = current_state.values.get('messages', [])
                # Append local history user messages to current_messages
                for entry in self._local_history:
                    if entry['role'] == 'user':
                        current_messages.append(HumanMessage(content=entry['content']))

                inputs = {'messages': current_messages, 'next_step': None}
                conversation_log = []
                final_message = None

                for s in self.agent.app.stream(inputs, stream_mode='values', config=self.config):
                    message_obj = s['messages'][-1]
                    from Biomni.biomni.utils import pretty_print
                    out = pretty_print(message_obj)
                    conversation_log.append(out)
                    final_message = message_obj

                if final_message:
                    final_text = getattr(final_message, 'content', str(final_message))
                    self._local_history.append({'role': 'assistant', 'content': final_text})
                    self.conversation_count += 1
                    print(f"✅ Received response ({len(final_text)} chars)")
                    return True, conversation_log, final_text

            # Fallback to agent.go with last user message
            log, final_response = self.agent.go(message)
            self._local_history.append({'role': 'assistant', 'content': final_response})
            self.conversation_count += 1
            return True, log, final_response

        except Exception as e:
            error_msg = f"Error processing message: {str(e)}"
            print(f"❌ {error_msg}")
            traceback.print_exc()
            return False, error_msg, None

    def reset_conversation(self):
        if self.initialized:
            new_thread_id = random.randint(1, 10000)
            self.config = {'recursion_limit': 500, 'configurable': {'thread_id': new_thread_id}}
            self.conversation_count = 0
            self._local_history = []
            print(f"🔄 Conversation reset with thread_id: {new_thread_id}")
            return True
        return False

    def get_status(self):
        return {
            'initialized': self.initialized,
            'agent_available': self.agent is not None,
            'config_available': self.config is not None,
            'conversation_count': self.conversation_count
        }

# Download helper functions and manifest logic

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

REQUIRED_FILES = [
    "affinity_capture-ms.parquet",
    "affinity_capture-rna.parquet",
    "BindingDB_All_202409.tsv"
]

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

# global singleton instance
biomni_session = BiomniSession()
