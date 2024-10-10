CFA_BOT

Prerequisites

	•	Access to the Dialogflow Console
	•	Python 3.x installed
	•	Flask web framework installed
	•	Ngrok installed (for macOS)

Setup Instructions (macOS only)

1. Clone or Download the Chatbot Code

	•	Obtain the Flask application code (app.py) and any additional files such as requirements.txt and price_list.py.
	•	Place them in a directory on your local machine.

2. Install Required Python Packages

	•	Open a terminal.
	•	Navigate to the directory containing the chatbot code.

(Optional) Create and activate a virtual environment:
python3 -m venv venv

# Activate the virtual environment:
source venv/bin/activate

	•	Install dependencies using requirements.txt:
pip install -r requirements.txt

If you don’t have a requirements.txt file, manually install Flask and any other required packages:
pip install flask

3. Run the Flask Application

	•	Start the Flask app by running:
python app.py

	•	Ensure your app.py is configured to run on port 5000 (default).

4. Download and Install Ngrok

	•	Download Ngrok for macOS from the official Ngrok website.
	•	Unzip the downloaded file.
	•	Place the Ngrok executable in a directory that’s included in your system’s PATH or specify the full path when running it.

5. Expose the Flask App Using Ngrok

	•	Open a new terminal.
	•	Run Ngrok to tunnel HTTP traffic on port 5000:

ngrok http 5000

Ngrok will display a forwarding URL that looks like https://<random-id>.ngrok.io.

6. Connect Ngrok URL to Dialogflow Webhook

	•	In the Dialogflow Console:
	•	Navigate to your agent.
	•	Click on Fulfillment in the left sidebar.
	•	Enable the Webhook option and paste the Ngrok URL.










