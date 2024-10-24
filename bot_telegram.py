import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

# Configura el registro
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Cargar el modelo y el tokenizador en español disponible
tokenizer = AutoTokenizer.from_pretrained('datificate/gpt2-small-spanish')
model = AutoModelForCausalLM.from_pretrained('datificate/gpt2-small-spanish')

# Inicializa el historial de conversación
chat_history_ids = None
max_length_history = 5  # Número máximo de interacciones a conservar

# Contexto inicial que guía al modelo
initial_context = (
    "Eres un experto en diabetes. Responde de forma clara, precisa y educativa a todas las preguntas relacionadas con "
    "la diabetes. Habla sobre los síntomas, el tratamiento, las causas, la prevención y cualquier aspecto relacionado "
    "con la diabetes. No hables de otros temas."
)

async def generate_response(user_message: str) -> str:
    global chat_history_ids
    
    # Combina el contexto inicial con el mensaje del usuario
    input_message = initial_context + " " + user_message

    # Tokeniza la entrada del usuario
    new_user_input_ids = tokenizer.encode(input_message + tokenizer.eos_token, return_tensors='pt')

    # Concatena el historial de conversación con la nueva entrada
    if chat_history_ids is not None:
        chat_history_ids = torch.cat([chat_history_ids, new_user_input_ids], dim=-1)
    else:
        chat_history_ids = new_user_input_ids

    # Limita el tamaño del historial
    if chat_history_ids.shape[1] > max_length_history * 20:
        chat_history_ids = chat_history_ids[:, -max_length_history * 20:]

    # Genera la respuesta
    bot_output = model.generate(
        chat_history_ids,
        max_length=150,  # Limita la longitud de la respuesta
        pad_token_id=tokenizer.eos_token_id,
        temperature=0.5,  # Ajusta la temperatura
        top_k=40,
        top_p=0.9,
        do_sample=True,
        repetition_penalty=1.5  # Penaliza la repetición
    )

    # Decodifica la respuesta
    response = tokenizer.decode(bot_output[:, chat_history_ids.shape[-1]:][0], skip_special_tokens=True)

    # Actualiza el historial de conversación
    chat_history_ids = bot_output

    # Filtro de palabras clave para asegurarse de que la respuesta esté relacionada con diabetes
    keywords = ['diabetes', 'glucosa', 'insulina', 'azúcar', 'prediabetes', 'glucemia', 'tipo 1', 'tipo 2']
    
    # Si la respuesta tiene más de 10 palabras, se asume que es válida aunque no tenga todas las palabras clave
    if len(response.split()) > 10 and any(keyword in response.lower() for keyword in keywords):
        return response.strip()  # Respuesta válida
    else:
        return "Lo siento, solo puedo hablar sobre diabetes. Por favor, haz una pregunta relacionada con este tema."

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    # Genera la respuesta usando el modelo
    response = await generate_response(user_message)

    # Verifica si la respuesta no está vacía antes de enviarla
    if response:
        await update.message.reply_text(response)
    else:
        await update.message.reply_text("No se pudo generar una respuesta.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("¡Hola! Soy un bot de Telegram especializado en diabetes. Envía un mensaje y te responderé sobre cualquier aspecto relacionado con la diabetes.")

if __name__ == '__main__':
    application = ApplicationBuilder().token('poner token de telegram aqui').build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()
