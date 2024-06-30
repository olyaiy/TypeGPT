import requests
from requests import post
import google.generativeai as genai
import json
import base64
import os
from anthropic import Anthropic

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
ANTHROPIC_API_KEY = api_keys['ANTHROPIC_API_KEY']

# System prompt text
with open('system_prompt.txt', 'r') as file:
    # system_prompt = file.read()
    system_prompt = ''

# Function to query OpenAI
def query_openai(text, image_base64=None):
    url = 'https://api.openai.com/v1/chat/completions'
    headers = {
        'Authorization': f'Bearer {OPENAI_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": [{"type": "text", "text": text}]}
    ]
    
    if image_base64:
        messages[1]["content"].append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{image_base64}",
                "detail": "high"
            }
        })
    
    data = {
        'model': 'gpt-4-turbo',
        'messages': messages,
    }
    
    try:
        response = post(url, json=data, headers=headers)
        response.raise_for_status()
        response_data = response.json()
        
        if 'choices' in response_data and len(response_data['choices']) > 0:
            return response_data['choices'][0]['message']['content']
        else:
            return f"Unexpected response format: {json.dumps(response_data, indent=2)}"
    except Exception as e:
        return f"Error in API call: {str(e)}\nResponse: {response.text if 'response' in locals() else 'No response'}"

# Function to query Gemini
def query_gemini(input_text, image_base64=None):
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        generation_config = {
            "temperature": 1,
            "top_p": 0.95,
            "top_k": 64,
            "max_output_tokens": 8192,
        }
        model = genai.GenerativeModel(
            model_name="gemini-1.0-pro-vision-latest",
            generation_config=generation_config,
        )
        
        prompt_parts = [system_prompt, input_text]
        if image_base64:
            image_parts = [
                {
                    "mime_type": "image/png",
                    "data": image_base64
                }
            ]
            prompt_parts.extend(image_parts)
        
        response = model.generate_content(prompt_parts)
        return response.text
    except Exception as e:
        return f"Error in Gemini API call: {str(e)}"

# Function to query Claude
def query_claude(text, image_base64=None):
    try:
        anthropic = Anthropic(api_key=ANTHROPIC_API_KEY)
        
        messages = [
            {"role": "user", "content": [{"type": "text", "text": text}]}
        ]
        
        if image_base64:
            messages[0]["content"].insert(0, {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": image_base64
                }
            })
        
        response = anthropic.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=1024,
            system=system_prompt,
            messages=messages
        )
        
        return response.content[0].text
    except Exception as e:
        return f"Error in Claude API call: {str(e)}"



# Function to query Ollama's llama3 model
def query_llama3(text, image_base64=None):
    url = "http://localhost:11434/api/chat"
    
    payload = {
        "model": "llama3",
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": text
            }
        ],
        "stream": False
    }
    
    if image_base64:
        payload["messages"][1]["images"] = [image_base64]
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
        return result['message']['content']
    except requests.exceptions.RequestException as e:
        return f"Error in Ollama API call: {str(e)}"

# main function 
def api_call(model, text, image_base64=None):
    api_functions = {
        'chatgpt': query_openai,
        'gemini': query_gemini,
        'claude': query_claude,
        'llama3': query_llama3
    }
    
    if model in api_functions:
        return api_functions[model](text, image_base64)
    else:
        return f"Error: Unsupported model '{model}'"
    api_functions = {
        'chatgpt': query_openai,
        'gemini': query_gemini,
        'claude': query_claude
    }
    
    if model.startswith('ollama:'):
        ollama_model = model.split(':', 1)[1]
        return query_ollama(text, ollama_model, image_base64)
    elif model in api_functions:
        return api_functions[model](text, image_base64)
    else:
        return f"Error: Unsupported model '{model}'"