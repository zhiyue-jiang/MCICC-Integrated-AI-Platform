library(shiny)
library(httr2)
library(jsonlite)
library(shinyjs)

# Source UI and Server
source("ui.R")
source("server.R")

# Enable shinyjs
shinyApp(ui = ui, server = server)
