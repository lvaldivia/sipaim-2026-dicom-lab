"""Comprueba Bedrock y Polly con el perfil autorizado sin imprimir credenciales."""
import json
import os
from pathlib import Path
import boto3
from botocore.config import Config
from aws_config import crear_sesion

session = crear_sesion()
runtime = session.client("bedrock-runtime", config=Config(read_timeout=60, retries={"max_attempts": 1}))
response = runtime.converse(modelId="amazon.nova-lite-v1:0", messages=[{"role": "user", "content": [{"text": "Responde únicamente: conexión correcta"}]}], inferenceConfig={"maxTokens": 40, "temperature": 0})
print("Bedrock:", response["output"]["message"]["content"][0]["text"])
polly = session.client("polly")
for voice, language in [("Lupe", "es-US"), ("Joanna", "en-US")]:
    result = polly.synthesize_speech(Text="Prueba de audio." if language == "es-US" else "Audio test.", OutputFormat="mp3", VoiceId=voice, LanguageCode=language, Engine="neural")
    sound = result["AudioStream"].read()
    print("Polly:", voice, language, len(sound), "bytes MP3")
