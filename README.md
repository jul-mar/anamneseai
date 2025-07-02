# AnamneseAI

AI-powered medical history chatbot using QuestionnAIre.

This project provides a web-based chatbot interface for taking a patient's medical history prior to a consultation.

## Features

-   Conversational AI powered by LangChain and OpenAI.
-   FastAPI backend with a persistent database.
-   Vanilla JS frontend for a simple, responsive user experience.
-   Dependency management with UV.

## Getting Started

### Prerequisites

-   Python 3.10+
-   [UV](https://github.com/astral-sh/uv) (Python package installer)

### Installation & Running

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-repo/anamneseai.git
    cd anamneseai
    ```

2.  **Set up the environment:**
    Create a `.env` file in the root directory and add your OpenAI API key:
    ```
    OPENAI_API_KEY='your_api_key_here'
    ```

3.  **Install dependencies:**
    ```bash
    uv sync
    ```

4.  **Start the application:**
    ```bash
    ./start.sh
    ```

This will start the backend server on `http://localhost:8000` and the frontend server on `http://localhost:8080`. 