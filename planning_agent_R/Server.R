library(shiny)
library(shinyjs)
library(httr2)
library(jsonlite)

# Azure OpenAI Configuration
AZURE_ENDPOINT <- "https://iapi-test.merck.com/gpt/libsupport"
AZURE_DEPLOYMENT <- "gpt-4o-2024-11-20"
API_VERSION <- "2023-05-15"
API_KEY <- "IDFS8XPknvWNngP5POBOeJzqPkaFKmjT"

# Logging function
log_message <- function(level, message) {
  timestamp <- Sys.time()
  cat(sprintf("[%s] %s: %s\n", timestamp, level, message))
}

# Function to call Azure OpenAI
call_azure_openai <- function(messages) {
  
  log_message("INFO", "Starting Azure OpenAI API call")
  
  url <- paste0(AZURE_ENDPOINT, "/openai/deployments/", AZURE_DEPLOYMENT, "/chat/completions")
  log_message("INFO", paste("API URL:", url))
  
  body <- list(
    messages = messages,
    max_tokens = 1000,
    temperature = 0.7
  )
  
  log_message("INFO", paste("Request body prepared with", length(messages), "messages"))
  
  tryCatch({
    log_message("INFO", "Sending HTTP request to Azure OpenAI")
    
    response <- request(url) |>
      req_url_query(`api-version` = API_VERSION) |>
      req_headers(
        `Content-Type` = "application/json",
        `api-key` = API_KEY
      ) |>
      req_body_json(body) |>
      req_perform()
    
    log_message("INFO", paste("HTTP response status:", resp_status(response)))
    
    if (resp_status(response) != 200) {
      error_body <- tryCatch({
        resp_body_string(response)
      }, error = function(e) "Unable to read error response")
      
      log_message("ERROR", paste("HTTP", resp_status(response), "error:", error_body))
      return(paste("API Error (", resp_status(response), "): ", error_body))
    }
    
    content <- response |> resp_body_json()
    log_message("INFO", "Successfully parsed JSON response")
    
    if (!is.null(content$choices) && length(content$choices) > 0) {
      response_text <- content$choices[[1]]$message$content
      log_message("INFO", paste("Generated response length:", nchar(response_text), "characters"))
      return(response_text)
    } else {
      log_message("ERROR", "No choices found in API response")
      log_message("DEBUG", paste("Response structure:", jsonlite::toJSON(content, auto_unbox = TRUE)))
      return("Sorry, I couldn't generate a response. Please try again.")
    }
    
  }, error = function(e) {
    log_message("ERROR", paste("Exception occurred:", e$message))
    log_message("DEBUG", paste("Full error:", toString(e)))
    return(paste("Connection Error:", e$message))
  })
}

function(input, output, session) {
  
  log_message("INFO", "Shiny server started")
  
  # Store conversation history
  conversation <- reactiveVal(list(
    list(role = "system", content = "You are a helpful biomedical planning assistant assigned with the task of problem-solving. Provide detailed, step-by-step plans for biomedical queries. Focus on what can be done non clinically from a research perspective. Focus on practical, actionable advice.The plan should be a numbered list of steps that you will take to solve the task. Be specific and detailed.
Be concise and limit your response that is not in the steps.")
  ))
  
  # Handle submit button
  observeEvent(input$submit_btn, {
    log_message("INFO", "Submit button clicked")
    
    req(input$user_input)
    
    if (nchar(trimws(input$user_input)) == 0) {
      log_message("WARN", "Empty input submitted")
      return()
    }
    
    user_question <- input$user_input
    log_message("INFO", paste("User question:", substr(user_question, 1, 100), "..."))
    
    # Add user message to conversation
    current_conv <- conversation()
    user_message <- list(role = "user", content = user_question)
    current_conv <- append(current_conv, list(user_message))
    conversation(current_conv)
    
    # Update UI with user message
    insertUI(
      selector = "#chat_history",
      where = "beforeEnd",
      ui = div(class = "user-message",
               strong("You: "), user_question
      )
    )
    
    # Show loading message
    loading_id <- paste0("loading_", as.numeric(Sys.time()) * 1000)
    insertUI(
      selector = "#chat_history",
      where = "beforeEnd",
      ui = div(id = loading_id, class = "agent-message loading",
               strong("Agent: "), "Generating your biological plan..."
      )
    )
    
    # Clear input
    updateTextAreaInput(session, "user_input", value = "")
    
    # Scroll to bottom
    runjs("document.getElementById('chat_history').scrollTop = document.getElementById('chat_history').scrollHeight;")
    
    log_message("INFO", "Calling Azure OpenAI API")
    
    # Call Azure OpenAI
    response <- call_azure_openai(current_conv)
    
    # Remove loading message
    removeUI(selector = paste0("#", loading_id))
    
    # Determine if response is an error
    is_error <- grepl("^(API Error|Connection Error|Error:)", response)
    message_class <- if(is_error) "agent-message error-message" else "agent-message"
    
    if (is_error) {
      log_message("ERROR", paste("Displaying error to user:", substr(response, 1, 100)))
    } else {
      log_message("INFO", "Successfully generated and displaying response")
      # Add agent response to conversation
      agent_message <- list(role = "assistant", content = response)
      current_conv <- append(current_conv, list(agent_message))
      conversation(current_conv)
    }
    
    # Update UI with agent response
    insertUI(
      selector = "#chat_history",
      where = "beforeEnd",
      ui = div(class = message_class,
               strong("Agent: "), 
               tags$div(style = "white-space: pre-wrap;", response)
      )
    )
    
    # Scroll to bottom
    runjs("document.getElementById('chat_history').scrollTop = document.getElementById('chat_history').scrollHeight;")
  })
  
  # Handle clear button
  observeEvent(input$clear_btn, {
    log_message("INFO", "Clear button clicked")
    
    # Reset conversation
    conversation(list(
      list(role = "system", content = "You are a helpful biomedical planning assistant assigned with the task of problem-solving. Provide detailed, step-by-step plans for biomedical queries. Focus on what can be done non clinically from a research perspective. Focus on practical, actionable advice.The plan should be a numbered list of steps that you will take to solve the task. Be specific and detailed.
Be concise and limit your response that is not in the steps.")
    ))
    
    # Clear chat history UI
    removeUI(selector = "#chat_history .user-message, #chat_history .agent-message:not(:first-child)")
    
    log_message("INFO", "Conversation cleared")
  })
  
  # Enable enter key submission (Ctrl+Enter)
  observe({
    runjs('
      $(document).on("keydown", "#user_input", function(e) {
        if(e.which == 13 && e.ctrlKey) {
          e.preventDefault();
          $("#submit_btn").click();
        }
      });
    ')
  })
  
  # Session end logging
  session$onSessionEnded(function() {
    log_message("INFO", "Shiny session ended")
  })
}
