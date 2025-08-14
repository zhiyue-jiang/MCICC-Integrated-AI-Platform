# app.py - Simplified version with everything always displayed

import asyncio
from shiny import App, ui, render, reactive
from biomni_session import BiomniSession
import datetime

# Initialize the biomni session
biomni_session = BiomniSession()

app_ui = ui.page_fluid(
    ui.div(
        ui.h1("MCICC Integrated AI Platform", class_="text-center mb-4"),
        ui.row(
            # Left Column - Input
            ui.column(
                4,
                ui.div(
                    ui.h3("💬 Chat Input", class_="text-primary mb-3"),
                    ui.input_text_area(
                        "user_input", 
                        "Enter your message:", 
                        rows=8, 
                        width="100%"
                    ),
                    ui.div(
                        ui.input_action_button(
                            "submit", 
                            "📤 Send Message", 
                            class_="btn-primary btn-lg me-2",
                            style="width: 48%;"
                        ),
                        ui.input_action_button(
                            "clear_conversation", 
                            "🗑️ Clear Chat", 
                            class_="btn-outline-warning",
                            style="width: 48%;"
                        ),
                        class_="mt-3 d-flex justify-content-between"
                    ),
                    ui.hr(),
                    ui.h4("📊 Status", class_="text-info mb-2"),
                    ui.output_text("status"),
                    class_="h-100 p-3 border rounded bg-light"
                ),
                style="height: 90vh; overflow-y: auto;"
            ),
            
            # Right Column - Conversation History
            ui.column(
                8,
                ui.div(
                    ui.h3("🤖 Full Conversation", class_="text-success mb-3"),
                    ui.div(
                        ui.output_ui("conversation_display"),
                        id="conversation-container",
                        style="""
                            height: 80vh; 
                            overflow-y: auto; 
                            overflow-x: hidden;
                            border: 1px solid #ddd; 
                            padding: 15px; 
                            background: #fafafa; 
                            border-radius: 8px;
                        """
                    ),
                    class_="h-100 p-3 border rounded bg-light"
                ),
                style="height: 90vh;"
            )
        ),
        class_="container-fluid"
    ),
    
    # Enhanced CSS for different message types
    ui.tags.style("""
        .user-message {
            margin-bottom: 15px;
            padding: 12px;
            background-color: #e3f2fd;
            border-left: 4px solid #2196f3;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .ai-message {
            margin-bottom: 20px;
            padding: 12px;
            background-color: #f1f8e9;
            border-left: 4px solid #4caf50;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .planning-step {
            margin-bottom: 10px;
            padding: 10px;
            background-color: #fff3e0;
            border-left: 3px solid #ff9800;
            border-radius: 6px;
            font-size: 0.9em;
        }
        
        .tool-call {
            margin-bottom: 10px;
            padding: 10px;
            background-color: #f3e5f5;
            border-left: 3px solid #9c27b0;
            border-radius: 6px;
            font-size: 0.9em;
        }
        
        .system-message {
            margin-bottom: 10px;
            padding: 8px;
            background-color: #f5f5f5;
            border-left: 2px solid #757575;
            border-radius: 4px;
            font-size: 0.85em;
            color: #555;
        }
        
        .message-content {
            margin-top: 8px;
            margin-bottom: 0;
            white-space: pre-wrap;
            word-wrap: break-word;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.5;
        }
        
        .code-block {
            background-color: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 4px;
            padding: 10px;
            font-family: 'Courier New', monospace;
            font-size: 0.85em;
            overflow-x: auto;
            margin: 8px 0;
        }
        
        .message-header {
            font-weight: bold;
            margin-bottom: 5px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .timestamp {
            font-size: 0.8em;
            color: #666;
            font-weight: normal;
        }
        
        .conversation-separator {
            border: none;
            height: 2px;
            background: linear-gradient(to right, transparent, #ddd, transparent);
            margin: 25px 0;
        }
        
        .empty-conversation {
            text-align: center;
            color: #666;
            padding: 40px 20px;
            font-style: italic;
        }
        
        .loading-message {
            text-align: center;
            padding: 20px;
            background-color: #fff3cd;
            border: 1px solid #ffeaa7;
            border-radius: 8px;
            color: #856404;
        }
        
        .step-counter {
            background-color: #007bff;
            color: white;
            border-radius: 50%;
            width: 20px;
            height: 20px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 0.7em;
            margin-right: 8px;
        }
        
        /* Auto-scroll to bottom */
        #conversation-container {
            scroll-behavior: smooth;
        }
        
        /* Responsive design */
        @media (max-width: 768px) {
            .container-fluid .row .col-4 {
                flex: 0 0 100% !important;
                max-width: 100% !important;
                margin-bottom: 20px;
            }
            .container-fluid .row .col-8 {
                flex: 0 0 100% !important;
                max-width: 100% !important;
            }
        }
    """),
    
    # JavaScript for auto-scrolling
    ui.tags.script("""
        function scrollToBottom() {
            const container = document.getElementById('conversation-container');
            if (container) {
                container.scrollTop = container.scrollHeight;
            }
        }
        
        // Auto-scroll when content updates
        const observer = new MutationObserver(function(mutations) {
            setTimeout(scrollToBottom, 100);
        });
        
        document.addEventListener('DOMContentLoaded', function() {
            const container = document.getElementById('conversation-container');
            if (container) {
                observer.observe(container, { childList: true, subtree: true });
            }
        });
    """)
)

def server(input, output, session):
    # Reactive values for conversation state
    conversation_history = reactive.Value([])
    status_text = reactive.Value("🚀 Initializing Agent...")
    is_processing = reactive.Value(False)
    
    # Initialize biomni session on startup
    @reactive.Effect
    def initialize_session():
        try:
            if biomni_session.initialize():
                status_text.set("✅ Agent initialized successfully! Ready to chat.")
            else:
                status_text.set("❌ Failed to initialize Agent. Check logs.")
        except Exception as e:
            status_text.set(f"❌ Initialization error: {str(e)}")
    
    @output
    @render.text
    def status():
        return status_text()
    
    def format_message_content(content, message_type="ai"):
        """Format message content with proper styling"""
        if not content:
            return ""
        
        # Convert to string if it's not already
        content_str = str(content)
        
        # Handle code blocks
        if "```" in content_str:
            parts = content_str.split("```")
            formatted_parts = []
            for i, part in enumerate(parts):
                if i % 2 == 1:  # Code block
                    formatted_parts.append(ui.div(part.strip(), class_="code-block"))
                else:  # Regular text
                    if part.strip():
                        formatted_parts.append(ui.div(part, class_="message-content"))
            return ui.div(*formatted_parts)
        else:
            return ui.div(content_str, class_="message-content")
    
    def parse_conversation_log(log_data):
        """Parse the conversation log to extract different types of messages"""
        if not log_data:
            return []
        
        parsed_steps = []
        
        if isinstance(log_data, list):
            for i, item in enumerate(log_data):
                item_str = str(item)
                
                # Detect different types of messages
                if "Planning" in item_str or "plan" in item_str.lower():
                    parsed_steps.append({
                        'type': 'planning',
                        'content': item_str,
                        'step_number': len([s for s in parsed_steps if s['type'] == 'planning']) + 1
                    })
                elif "Tool" in item_str or "tool" in item_str.lower() or "function" in item_str.lower():
                    parsed_steps.append({
                        'type': 'tool',
                        'content': item_str,
                        'step_number': len([s for s in parsed_steps if s['type'] == 'tool']) + 1
                    })
                elif "System" in item_str or "system" in item_str.lower():
                    parsed_steps.append({
                        'type': 'system',
                        'content': item_str
                    })
                else:
                    parsed_steps.append({
                        'type': 'response',
                        'content': item_str
                    })
        else:
            # Single item
            parsed_steps.append({
                'type': 'response',
                'content': str(log_data)
            })
        
        return parsed_steps
    
    @output
    @render.ui
    def conversation_display():
        history = conversation_history()
        
        if not history:
            return ui.div(
                ui.p("💬 No messages yet. Start a conversation!", class_="empty-conversation"),
                ui.p("🧠 You'll see all planning steps and tool calls automatically", class_="empty-conversation")
            )
        
        # Build conversation elements
        elements = []
        
        for i, exchange in enumerate(history):
            timestamp_display = exchange['timestamp']
            
            # User message
            elements.append(
                ui.div(
                    ui.div(
                        ui.span("👤 Human", style="font-weight: bold;"),
                        ui.span(timestamp_display, class_="timestamp"),
                        class_="message-header"
                    ),
                    format_message_content(exchange['user'], "user"),
                    class_="user-message"
                )
            )
            
            # Parse the agent response to show planning steps
            if 'full_log' in exchange and exchange['full_log']:
                parsed_steps = parse_conversation_log(exchange['full_log'])
                
                # Show all planning steps
                planning_steps = [step for step in parsed_steps if step['type'] == 'planning']
                for step in planning_steps:
                    elements.append(
                        ui.div(
                            ui.div(
                                ui.span(f"{step['step_number']}", class_="step-counter"),
                                ui.span("🧠 Planning Step", style="font-weight: bold;"),
                                ui.span(timestamp_display, class_="timestamp"),
                                class_="message-header"
                            ),
                            format_message_content(step['content'], "planning"),
                            class_="planning-step"
                        )
                    )
                
                # Show all tool calls
                tool_steps = [step for step in parsed_steps if step['type'] == 'tool']
                for step in tool_steps:
                    elements.append(
                        ui.div(
                            ui.div(
                                ui.span(f"{step['step_number']}", class_="step-counter"),
                                ui.span("🔧 Tool Call", style="font-weight: bold;"),
                                ui.span(timestamp_display, class_="timestamp"),
                                class_="message-header"
                            ),
                            format_message_content(step['content'], "tool"),
                            class_="tool-call"
                        )
                    )
                
                # Show all system messages
                system_steps = [step for step in parsed_steps if step['type'] == 'system']
                for step in system_steps:
                    elements.append(
                        ui.div(
                            ui.div(
                                ui.span("⚙️ System", style="font-weight: bold;"),
                                ui.span(timestamp_display, class_="timestamp"),
                                class_="message-header"
                            ),
                            format_message_content(step['content'], "system"),
                            class_="system-message"
                        )
                    )
            
            # Final AI response
            elements.append(
                ui.div(
                    ui.div(
                        ui.span("🤖 Agent Response", style="font-weight: bold;"),
                        ui.span(timestamp_display, class_="timestamp"),
                        class_="message-header"
                    ),
                    format_message_content(exchange['agent'], "ai"),
                    class_="ai-message"
                )
            )
            
            # Add separator between conversations (except for last)
            if i < len(history) - 1:
                elements.append(ui.hr(class_="conversation-separator"))
        
        return ui.div(*elements)
    
    # Clear conversation
    @reactive.Effect
    @reactive.event(input.clear_conversation)
    def clear_conversation():
        try:
            # Reset biomni session
            biomni_session.reset_conversation()
            # Clear local history
            conversation_history.set([])
            status_text.set("🔄 Conversation cleared. Ready for new chat.")
        except Exception as e:
            status_text.set(f"⚠️ Error clearing conversation: {str(e)}")
    
    # Main message processing
    @reactive.Effect
    @reactive.event(input.submit)
    async def process_message():
        user_message = input.user_input().strip()
        
        if not user_message:
            status_text.set("⚠️ Please enter a message")
            return
        
        if is_processing():
            status_text.set("⚠️ Already processing a message, please wait...")
            return
        
        # Set processing state
        is_processing.set(True)
        status_text.set("🔄 Processing your message...")
        
        # Add loading indicator to conversation
        current_history = conversation_history()
        loading_exchange = {
            'user': user_message,
            'agent': "🔄 Processing your message... This may take a few moments.",
            'full_log': [],
            'timestamp': datetime.datetime.now().strftime("%H:%M:%S"),
            'is_loading': True
        }
        conversation_history.set(current_history + [loading_exchange])
        
        # Clear input immediately
        ui.update_text_area("user_input", value="")
        
        try:
            # Determine if this is the first message
            is_first_message = len(current_history) == 0
            
            # Send message to biomni
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                biomni_session.send_message,
                user_message,
                is_first_message
            )
            
            success, conversation_log, final_response = result
            
            if success:
                # Create new exchange with full log
                new_exchange = {
                    'user': user_message,
                    'agent': str(final_response) if final_response else "No final response",
                    'full_log': conversation_log,  # Store the full log for parsing
                    'timestamp': datetime.datetime.now().strftime("%H:%M:%S")
                }
                
                # Update conversation history (remove loading, add real response)
                conversation_history.set(current_history + [new_exchange])
                status_text.set("✅ Message processed successfully")
                
            else:
                # Error case
                error_exchange = {
                    'user': user_message,
                    'agent': f"❌ Error: {conversation_log}",
                    'full_log': [],
                    'timestamp': datetime.datetime.now().strftime("%H:%M:%S")
                }
                conversation_history.set(current_history + [error_exchange])
                status_text.set("❌ Error processing message")
                
        except Exception as e:
            # Exception case
            error_exchange = {
                'user': user_message,
                'agent': f"❌ Exception occurred: {str(e)}",
                'full_log': [],
                'timestamp': datetime.datetime.now().strftime("%H:%M:%S")
            }
            conversation_history.set(current_history + [error_exchange])
            status_text.set(f"❌ Exception: {str(e)}")
            
        finally:
            is_processing.set(False)

app = App(app_ui, server)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
