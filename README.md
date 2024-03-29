# chatpdf-embedder

## Setup

1. If you don’t have Python installed, [install it from here](https://www.python.org/downloads/).

2. Clone this repository.

3. Navigate into the project directory:

   ```
   cd chatpdf-embedder
   ```

4. Create a new virtual environment:

   ```
   python -m venv venv
   $ . venv/bin/activate
   ```

5. Install the requirements:

   ```bash
   pip install -r requirements.txt
   ```

6. Make a copy of the example environment variables file:

   ```bash
   cp .env.copy .env
   ```

7. Fill out the new environment variables file with your keys

8. Run the app:

   ```bash
   streamlit run app.py
   ```
