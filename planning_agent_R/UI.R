library(shiny)
library(shinyjs)

fluidPage(
  useShinyjs(),
  
  titlePanel("MCICC Planning Agent"),
  
  # Custom CSS for left-right layout
  tags$head(
    tags$style(HTML("
      .main-container {
        display: flex;
        height: 85vh;
        gap: 10px;
      }
      .input-panel {
        flex: 0 0 35%;
        padding: 15px;
        border: 1px solid #ddd;
        border-radius: 5px;
        background: white;
        display: flex;
        flex-direction: column;
      }
      .output-panel {
        flex: 1;
        padding: 15px;
        border: 1px solid #ddd;
        border-radius: 5px;
        background: white;
        display: flex;
        flex-direction: column;
      }
      .chat-history {
        flex: 1;
        background: #f9f9f9;
        border: 1px solid #ddd;
        border-radius: 5px;
        padding: 10px;
        overflow-y: auto;
        margin-top: 10px;
      }
      .input-section {
        flex: 1;
        display: flex;
        flex-direction: column;
      }
      .user-message {
        background: #e3f2fd;
        padding: 10px;
        margin: 8px 0;
        border-radius: 8px;
        border-left: 4px solid #2196f3;
        word-wrap: break-word;
      }
      .agent-message {
        background: #f3e5f5;
        padding: 10px;
        margin: 8px 0;
        border-radius: 8px;
        border-left: 4px solid #9c27b0;
        word-wrap: break-word;
      }
      .loading {
        color: #666;
        font-style: italic;
      }
      .error-message {
        background: #ffebee;
        border-left: 4px solid #f44336;
        color: #c62828;
      }
      #user_input {
        flex: 1;
        min-height: 100px;
        resize: vertical;
      }
      .button-group {
        margin-top: 15px;
      }
      .example-section {
        margin-top: 20px;
        padding-top: 15px;
        border-top: 1px solid #eee;
      }
    "))
  ),
  
  div(class = "main-container",
      # Left Panel - User Input
      div(class = "input-panel",
          h4("Ask Your Question"),
          
          div(class = "input-section",
              textAreaInput("user_input", 
                            label = NULL,
                            placeholder = "Enter your prompt",
                            rows = 6,
                            width = "100%")
          ),
          
          div(class = "button-group",
              actionButton("submit_btn", "Generate Plan", 
                           class = "btn-primary", width = "100%", style = "margin-bottom: 10px;"),
              
              actionButton("clear_btn", "Clear Conversation", 
                           class = "btn-warning", width = "100%")
          )
      ),
      
      # Right Panel - Agent Output
      div(class = "output-panel",
          h4("Agent Response"),
          
          div(id = "chat_history", class = "chat-history",
              div(class = "agent-message",
                  strong("Biological Planning Agent: "), 
                  "Hello! I'm here to help you plan your course of action."
              )
          )
      )
  )
)

