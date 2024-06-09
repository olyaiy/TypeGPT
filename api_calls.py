from requests import post
import google.generativeai as genai


def read_api_keys(file_path):
   keys = {}
   with open(file_path, 'r') as file:
       for line in file:
           key, value = line.strip().split('=')
           keys[key] = value
   return keys

api_keys = read_api_keys('keys.txt')
OPENAI_API_KEY = api_keys['OPENAI_API_KEY']
GEMINI_API_KEY = api_keys['GEMINI_API_KEY']


# System prompt text
with open('system_prompt.txt', 'r') as file:
    system_prompt = file.read()

# Function to query OpenAI
def query_openai(text):
    url = 'https://api.openai.com/v1/chat/completions'
    headers = {
        'Authorization': f'Bearer {OPENAI_API_KEY}',
        'Content-Type': 'application/json'
    }
    data = {
        'model': 'gpt-4o',
        'messages': [
            {"role": "system", "content": system_prompt},
            {'role': 'user', 'content': text}
        ] 
    }
    response = post(url, json=data, headers=headers)
    return response.json()['choices'][0]['message']['content']

# Function to query Gemini
def query_gemini(input_text):
    genai.configure(api_key=GEMINI_API_KEY)
    generation_config = {
        "temperature": 1,
        "top_p": 0.95,
        "top_k": 64,
        "max_output_tokens": 8192,
        "response_mime_type": "text/plain",
    }
    model = genai.GenerativeModel(
        model_name="gemini-1.5-pro",
        generation_config=generation_config,
    )
    chat_session = model.start_chat(history=[])
    response = chat_session.send_message(input_text)
    return response.text