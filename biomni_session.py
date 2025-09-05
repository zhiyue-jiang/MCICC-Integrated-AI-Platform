# biomni_session.py
import os
from dotenv import load_dotenv
from Biomni.biomni.agent import A1
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
            cls._instance.conversation_count = 0
        return cls._instance
    
    def initialize(self):
    try:
        print("🚀 Initializing Biomni agent...")
        
        load_dotenv()
        
        # Set API key directly
        EMBEDDED_API_KEY = 'IDFS8XPknvWNngP5POBOeJzqPkaFKmjT'
        os.environ['AZURE_OPENAI_API_KEY'] = EMBEDDED_API_KEY
        
        # Initialize model
        model = AzureChatOpenAI(
            azure_endpoint='https://iapi-test.merck.com/gpt/libsupport',
            azure_deployment='gpt-5-mini-2025-08-07',
            openai_api_version='2023-05-15',
            api_key="IDFS8XPknvWNngP5POBOeJzqPkaFKmjT",
        )
        
            
            # Initialize model
            model = AzureChatOpenAI(
                azure_endpoint='https://iapi-test.merck.com/gpt/libsupport',
                azure_deployment='gpt-5-mini-2025-08-07',
                openai_api_version='2023-05-15',
            )
            
            # Initialize agent with your data path
            data_path = "./biomni_data"
            
            self.agent = A1(
                path=data_path,
                llm='gpt-4o-2024-11-20',
                base_url=None,
                api_key=os.getenv('AZURE_OPENAI_API_KEY'),
            )
            self.agent.llm = model
            
            # Initialize conversation config
            self.config = {'recursion_limit': 500, 'configurable': {'thread_id': 42}}
            self.initialized = True
            self.conversation_count = 0
            
            print("✅ Biomni agent initialized successfully")
            return True
            
        except Exception as e:
            print(f"❌ Failed to initialize Biomni agent: {str(e)}")
            import traceback
            traceback.print_exc()
            self.initialized = False
            return False
    
    def send_message(self, message, is_first_message=False):
        """Send a message to the agent"""
        if not self.initialized:
            return False, "Agent not initialized", None
        
        try:
            print(f"💬 Processing message #{self.conversation_count + 1}: {message[:50]}...")
            
            if is_first_message or self.conversation_count == 0:
                print("🎯 Using agent.go() for first message")
                # Use the agent's go() method for first message
                log, final_response = self.agent.go(message)
                self.conversation_count += 1
                return True, log, final_response
            else:
                print("🔄 Using stream interface for continuation")
                # For continuing conversation, use the stream interface
                current_state = self.agent.app.get_state(self.config)
                current_messages = current_state.values.get('messages', [])
                current_messages.append(HumanMessage(content=message))
                
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
                    print(f"✅ Received response ({len(final_message.content)} chars)")
                    self.conversation_count += 1
                    return True, conversation_log, final_message.content
                else:
                    return False, "No response received", None
                
        except Exception as e:
            error_msg = f"Error processing message: {str(e)}"
            print(f"❌ {error_msg}")
            import traceback
            traceback.print_exc()
            return False, error_msg, None
    
    def reset_conversation(self):
        """Reset the conversation with a new thread ID"""
        if self.initialized:
            import random
            new_thread_id = random.randint(1, 10000)
            self.config = {'recursion_limit': 500, 'configurable': {'thread_id': new_thread_id}}
            self.conversation_count = 0
            print(f"🔄 Conversation reset with thread_id: {new_thread_id}")
            return True
        return False
    
    def get_status(self):
        """Get current status"""
        return {
            'initialized': self.initialized,
            'agent_available': self.agent is not None,
            'config_available': self.config is not None,
            'conversation_count': self.conversation_count
        }

# Create global instance
biomni_session = BiomniSession()
