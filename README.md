# FastAPI + Vanilla Frontend

This is a starting point for building a fast web application with FastAPI and a vanilla frontend.

## Features

- FastAPI backend with a single endpoint for a health check
- Vanilla frontend with a single button to ping the backend
- Dockerfile for building and running the application
- Docker Compose file for running the application with multiple services

## How to use

1. Clone the repository
2. Build the Docker image by running `docker-compose build`
3. Run the application by running `docker-compose up`
4. Open a web browser and navigate to `http://localhost:8000`
5. Click the "Ping Backend" button to see the JSON response from the backend

## Road map

- Add ChatGPT like UI using Vanilla frontend
- Add functionality to chat with OpenAI
- Add Functionality to upload pdf, docx and txt from the frontend, and send them to backend for processing
- Extract and embed document text into a vector database for retrieval
- Add a UI section to list and manage uploaded documents
- Implement a RAG pipeline to retrieve relevant text chunks from uploaded documents and generate contextual answers
/*******  362ff348-f9d4-44f5-9cda-a752f66c42ad  *******/