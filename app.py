import sys
import os
import asyncio
import datetime

# Add the Biomni directory to Python path if needed
biomni_path = os.path.join(os.path.dirname(__file__), 'Biomni')
if biomni_path not in sys.path:
    sys.path.insert(0, biomni_path)

from shiny import App, ui, render, reactive
from biomni_session import BiomniSession

# Create/obtain the global biomni session
biomni_session = BiomniSession()

app_ui = ui.page_fluid(
    ui.div(
        ui.h1("MCICC Integrated AI Platform", class_="text-center mb-4"),
        ui.row(
            ui.column(
                4,
                ui.div(
                    ui.h3("💬 Chat Input", class_="text-primary mb-3"),
                    ui.input_text_area("user_input", "Enter your message:", rows=8, width="100%"),
                    ui.div(
                        ui.input_action_button("submit", "📤 Send Message", class_="btn-primary btn-lg me-2", style="width:48%;"),
                        ui.input_action_button("clear_conversation", "🗑️ Clear Chat", class_="btn-outline-warning", style="width:48%;"),
                        class_="mt-3 d-flex justify-content-between"
                    ),
                    ui.hr(),
                    ui.h4("📊 Status", class_="text-info mb-2"),
                    ui.output_text("status"),
                    class_="h-100 p-3 border rounded bg-light"
                ),
                style="height: 90vh; overflow-y: auto;"
            ),
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
        #conversation-container {
            scroll-behavior: smooth;
        }
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

    ui.tags.script("""
        function scrollToBottom() {
            const container = document.getElementById('conversation-container');
            if (container) {
                container.scrollTop = container.scrollHeight;
            }
        }
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
    conversation_history = reactive.Value([])
    status_text = reactive.Value("🚀 Initializing Agent...")
    is_processing = reactive.Value(False)

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

    def format_message_content(content):
        if content is None:
            return ""
        content_str = str(content)
        if "```" in content_str:
            parts = content_str.split("```")
            parts_ui = []
            for i, p in enumerate(parts):
                if i % 2 == 1:
                    parts_ui.append(ui.div(p.strip(), class_="code-block"))
                else:
                    if p.strip():
                        parts_ui.append(ui.div(p, class_="message-content"))
            return ui.div(*parts_ui)
        else:
            return ui.div(content_str, class_="message-content")

    @output
    @render.ui
    def conversation_display():
        history = conversation_history()
        if not history:
            return ui.div(
                ui.p("💬 No messages yet. Start a conversation!", class_="empty-conversation"),
                ui.p("🧠 The agent's final response will be shown here.", class_="empty-conversation")
            )

        elements = []
        for i, exchange in enumerate(history):
            ts = exchange.get("timestamp", "")
            elements.append(
                ui.div(
                    ui.div(
                        ui.span("👤 Human", style="font-weight: bold;"),
                        ui.span(ts, class_="timestamp"),
                        class_="message-header"
                    ),
                    format_message_content(exchange.get("user", "")),
                    class_="user-message"
                )
            )

            elements.append(
                ui.div(
                    ui.div(
                        ui.span("🤖 Agent Response", style="font-weight: bold;"),
                        ui.span(ts, class_="timestamp"),
                        class_="message-header"
                    ),
                    format_message_content(exchange.get("agent", "")),
                    class_="ai-message"
                )
            )

            if i < len(history) - 1:
                elements.append(ui.hr(class_="conversation-separator"))

        return ui.div(*elements)

    @reactive.Effect
    @reactive.event(input.clear_conversation)
    def clear_conversation():
        try:
            biomni_session.reset_conversation()
            conversation_history.set([])
            status_text.set("🔄 Conversation cleared. Ready for new chat.")
        except Exception as e:
            status_text.set(f"⚠️ Error clearing conversation: {str(e)}")

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

        is_processing.set(True)
        status_text.set("🔄 Processing your message...")

        current_history = conversation_history()
        loading_exchange = {
            "user": user_message,
            "agent": "🔄 Processing your message... This may take a few moments.",
            "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
            "is_loading": True
        }
        conversation_history.set(current_history + [loading_exchange])

        ui.update_text_area("user_input", value="")

        try:
            is_first = len(current_history) == 0

            result = await asyncio.get_event_loop().run_in_executor(
                None,
                biomni_session.send_message,
                user_message,
                is_first
            )

            success, conversation_log, final_response = result

            if success:
                new_exchange = {
                    "user": user_message,
                    "agent": str(final_response) if final_response else "No final response",
                    "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
                }
                conversation_history.set(current_history + [new_exchange])
                status_text.set("✅ Message processed successfully")
            else:
                error_exchange = {
                    "user": user_message,
                    "agent": f"❌ Error: {conversation_log}",
                    "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
                }
                conversation_history.set(current_history + [error_exchange])
                status_text.set("❌ Error processing message")

        except Exception as e:
            error_exchange = {
                "user": user_message,
                "agent": f"❌ Exception occurred: {str(e)}",
                "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
            }
            conversation_history.set(current_history + [error_exchange])
            status_text.set(f"❌ Exception: {str(e)}")

        finally:
            is_processing.set(False)

app = App(app_ui, server)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
