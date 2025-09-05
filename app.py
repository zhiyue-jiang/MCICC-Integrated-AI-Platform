# biomni_session.py
import sys
import os

# Add the Biomni directory to Python path
biomni_path = os.path.join(os.path.dirname(__file__), 'Biomni')
if biomni_path not in sys.path:
    sys.path.insert(0, biomni_path)

# Now Python can find biomni
from biomni.agent import A1
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage


class BiomniSession:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BiomniSession, cls).__new__(cls)
            cls._instance.agent = None
            cls._instance.config = None
            cls._instance.initialized = False
        return cls._instance

    def initialize(self):
        """Initialize the Biomni agent (with hard-coded Azure key)."""
        try:
            print("🚀 Initializing Biomni agent...")

            load_dotenv()

            #API Key
            EMBEDDED_API_KEY = "IDFS8XPknvWNngP5POBOeJzqPkaFKmjT"
            if not EMBEDDED_API_KEY or EMBEDDED_API_KEY == "f":
                raise RuntimeError("Hard-coded AZURE key not set in biomni_session.py")

            # Make it available to any library that reads the env var
            os.environ["AZURE_OPENAI_API_KEY"] = EMBEDDED_API_KEY

            # Create the Azure LLM client ONCE and reuse
            model = AzureChatOpenAI(
                azure_endpoint="https://iapi-test.merck.com/gpt/libsupport",
                azure_deployment="gpt-4o-2024-11-20",
                openai_api_version="2023-05-15",
                # Some versions support `openai_api_key=` too; env var covers it.
            )

            # Biomni agent: let *our* model be the only client
            data_path = "./biomni_data"
            self.agent = A1(
                path=data_path,
                llm="gpt-4o-2024-11-20",  # placeholder; we overwrite next line
                base_url=None,
                api_key=None,  # avoid spinning a second LLM client; we inject our own
            )
            self.agent.llm = model

            # Conversation/session config
            self.config = {"recursion_limit": 500, "configurable": {"thread_id": 42}}
            self.initialized = True

            print("✅ Biomni agent initialized successfully")
            return True

        except Exception as e:
            print(f"❌ Failed to initialize Biomni agent: {str(e)}")
            import traceback
            traceback.print_exc()
            self.initialized = False
            return False

    def send_message(self, message, is_first_message=False):
        """Send a message to the agent."""
        if not self.initialized:
            return False, "Agent not initialized", None

        try:
            print(f"💬 Processing message: {message[:50]}...")

            if is_first_message:
                # A1.go() commonly returns (log, final_response)
                result = self.agent.go(message)
                # Normalize tuple shapes defensively
                if isinstance(result, tuple):
                    if len(result) >= 2:
                        log, final = result[0], result[1]
                        return True, log, str(final)
                    else:
                        return True, [str(result[0])], ""
                else:
                    return True, [str(result)], str(result)

            # Stream branch for follow-ups
            current_state = self.agent.app.get_state(self.config)
            current_messages = current_state.values.get("messages", [])
            current_messages.append(HumanMessage(content=message))

            inputs = {"messages": current_messages, "next_step": None}
            conversation_log = []
            final_message = None

            for s in self.agent.app.stream(inputs, stream_mode="values", config=self.config):
                if isinstance(s, dict) and "messages" in s and s["messages"]:
                    message_obj = s["messages"][-1]
                    from biomni.utils import pretty_print
                    out = pretty_print(message_obj)
                    conversation_log.append(out)
                    final_message = message_obj

            if final_message:
                print("✅ Received response")
                return True, conversation_log, str(final_message.content)
            else:
                return False, "No response received", None

        except Exception as e:
            error_msg = f"Error processing message: {str(e)}"
            print(f"❌ {error_msg}")
            import traceback
            traceback.print_exc()
            return False, error_msg, None

    def reset_conversation(self):
        """Reset the conversation with a new thread ID."""
        if self.initialized:
            import random
            new_thread_id = random.randint(1, 10000)
            self.config = {"recursion_limit": 500, "configurable": {"thread_id": new_thread_id}}
            print(f"🔄 Conversation reset with thread_id: {new_thread_id}")
            return True
        return False

    def get_status(self):
        """Get current status."""
        return {
            "initialized": self.initialized,
            "agent_available": self.agent is not None,
            "config_available": self.config is not None,
        }

# Global instance (optional; your app.py constructs its own)
biomni_session = BiomniSession()
