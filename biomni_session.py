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


biomni_session = BiomniSession()
