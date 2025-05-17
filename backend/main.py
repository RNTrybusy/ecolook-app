# Importa as bibliotecas necessárias para FastAPI e outras funcionalidades
import os
import base64
import time # Para simular delay na busca mock (agora menos usado)
import requests # Para fazer requisições HTTP para a API Google Places
from fastapi import FastAPI, HTTPException, status, Form, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel # Para validar dados de entrada
from typing import Union # Para tipos de dados opcionais ou múltiplos

# Importa a biblioteca para carregar variáveis de ambiente do arquivo .env
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Importa o SDK do Google Generative AI
import google.generativeai as genai

# --- Configuração da Chave da API do Google ---
# É CRUCIAL configurar a variável de ambiente GOOGLE_API_KEY no seu servidor/ambiente de execução do backend.
# Esta chave será usada tanto para o Gemini quanto para a Google Places API.
# Em produção, use um gerenciador de segredos (Secret Manager) ou variáveis de ambiente configuradas de forma segura.
API_KEY = os.environ.get('GOOGLE_API_KEY')

# Verifica se a chave da API está configurada. Se não, levanta um erro fatal ao iniciar o backend.
if not API_KEY:
    print("--------------------------------------------------------------------")
    print("ERRO FATAL: Variável de ambiente GOOGLE_API_KEY não configurada.")
    print("Por favor, defina a variável de ambiente GOOGLE_API_KEY com sua chave do Google Cloud.")
    print("Certifique-se de ter um arquivo .env na raiz do backend com GOOGLE_API_KEY=SUA_CHAVE_AQUI")
    print("--------------------------------------------------------------------")
    # Em um ambiente de produção real, você provavelmente sairia aqui:
    # exit(1)

# Configura o SDK do Google Generative AI com a chave obtida
genai.configure(api_key=API_KEY)

# Define o modelo Gemini a ser usado (conforme o seu .env)
GEMINI_MODEL = "gemini-2.0-flash"

# Inicializa o aplicativo FastAPI
app = FastAPI()

# --- Configuração do CORS (Cross-Origin Resource Sharing) ---
# Permite que o frontend (sua PWA rodando em outro domínio/porta) faça requisições para este backend.
# Em produção, ajuste 'allow_origins' para a URL específica do seu frontend para maior segurança.
origins = [
    "http://localhost", # Permite localhost
    "http://localhost:8000", # Exemplo de porta comum para frontend local
    "http://localhost:5000", # Exemplo se o frontend estiver na mesma porta do Flask anterior
    "http://127.0.0.1", # Permite 127.0.0.1
    "http://127.0.0.1:8000", # Porta padrão do Uvicorn
    "http://127.0.0.1:5000", # Exemplo de outra porta comum para 127.0.0.1
    "http://127.0.0.1:5500", # <-- Adicionado a porta 5500 do Live Server (se aplicável)
    # Adicione a URL de produção da sua PWA aqui quando estiver em deploy
    # "https://sua-pwa-em-producao.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, # Lista de origens permitidas
    allow_credentials=True, # Permite cookies (não usados aqui, mas boa prática)
    allow_methods=["*"], # Permite todos os métodos (GET, POST, etc.)
    allow_headers=["*"], # Permite todos os headers
)

# --- Definição do Modelo Pydantic para Localização do Usuário ---
# Define a estrutura esperada para os dados de localização recebidos do frontend.
class UserLocation(BaseModel):
    lat: float
    lng: float

# --- Função que CHAMA a API Google Places (Real) ---
# Esta função representa a ferramenta que um Agente Gemini usaria para buscar locais.
# AGORA ela faz a chamada real para a Google Places API (New) - searchNearby.
def google_maps_search_tool(query: str, location: dict):
    """
    Chama a Google Places API (New) - searchNearby para buscar lugares.

    Args:
        query: A string de busca (ex: "lojas de roupa sustentável").
        location: Um dicionário com as chaves 'lat' e 'lng' para a localização.

    Returns:
        Uma lista de dicionários representando os lugares encontrados.
        Retorna lista vazia em caso de erro ou nenhum resultado.
    """
    print(f"Chamando a Google Places API para buscar: Query='{query}', Localização='{location}'")

    places_api_url = 'https://places.googleapis.com/v1/places:searchNearby'
    headers = {
        'X-Goog-Api-Key': API_KEY,
        'Content-Type': 'application/json',
        # Campos que queremos na resposta (reduz custo e melhora performance)
        'X-Goog-FieldMask': 'places.displayName,places.formattedAddress,places.types'
    }
    body = {
        'locationRestriction': {
            'circle': {
                'center': {'latitude': location['lat'], 'longitude': location['lng']},
                'radius': 5000 # Raio de busca em metros (ex: 5km). Ajuste conforme necessário.
            }
        },
        'textQuery': query,
        # Tipos de lugar que podem ser relevantes. Ajuste esta lista.
        'includedTypes': ['clothing_store', 'second_hand_store', 'boutique', 'department_store', 'shopping_mall'],
        'languageCode': 'pt-BR', # Idioma da resposta
        'maxResultCount': 10 # Número máximo de resultados. Ajuste conforme necessário.
    }

    try:
        response = requests.post(places_api_url, json=body, headers=headers)
        response.raise_for_status() # Levanta um erro HTTP para status ruins (4xx ou 5xx)

        places_data = response.json()
        print(f"Resposta da API Places recebida: {places_data}")

        real_stores = []
        # A resposta da API Places (New) searchNearby tem a lista de lugares em 'places'
        if places_data.get('places'):
            for place in places_data['places']:
                 # Mapeia a resposta da API para o formato esperado pelo frontend
                 real_stores.append({
                    "name": place.get('displayName', {}).get('text', 'Nome não disponível'),
                    "address": place.get('formattedAddress', 'Endereço não disponível'),
                    # Nota: A API Places (New) searchNearby NÃO retorna distância diretamente.
                    # Para obter a distância real, você precisaria usar a Distance Matrix API
                    # ou calcular a distância geodésica no backend.
                    # Manteremos um placeholder ou omitiremos por enquanto para simplificar o MVP.
                    "distance": "Distância N/A (requer Distance Matrix API)" # Placeholder
                 })
        return real_stores

    except requests.exceptions.RequestException as e:
        print(f"Erro na chamada da API Google Places: {e}")
        # Em caso de erro na API real, retornamos uma lista vazia e logamos o erro.
        # Você pode querer adicionar um tratamento de erro mais sofisticado aqui.
        return []
    except Exception as e:
        print(f"Erro inesperado ao processar resposta da API Places: {e}")
        return []


# --- Endpoint principal para análise e busca ---
# Este endpoint recebe a imagem (como string base64) e a localização do frontend.
@app.post("/analyze_and_find_stores")
async def analyze_and_find_stores_endpoint(
    imageDataUrl: str = Form(...), # Recebe a URL de dados da imagem como string de formulário
    userLocation: str = Form(...) # Recebe a localização como string JSON de formulário
):
    # Verifica se a chave da API está configurada antes de prosseguir
    if not API_KEY:
         # Retorna um erro 500 se a chave não estiver configurada
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API Key do Google não configurada no backend."
        )

    # Converte a string JSON da localização para um dicionário/objeto Python
    import json
    try:
        user_location_data = json.loads(userLocation)
        # Opcional: Validar a estrutura da localização usando Pydantic se necessário
        # user_location_obj = UserLocation(**user_location_data)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato de localização do usuário inválido (não é JSON)."
        )
    except Exception as e:
         raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dados de localização do usuário inválidos: {e}"
        )


    try:
        # 1. Análise da Imagem com Gemini Vision
        # Extrai os dados base64 da URL (remove o prefixo 'data:image/png;base64,')
        # Verifica se a string base64 tem o formato esperado
        if ',' not in imageDataUrl:
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato de URL de dados da imagem inválido."
            )
        image_base64 = imageDataUrl.split(',')[1]

        # Decodifica a string base64 para bytes
        try:
            image_bytes = base64.b64decode(image_base64)
        except base64.binascii.Error:
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Dados da imagem não estão em formato base64 válido."
            )


        # Cria o conteúdo para a requisição do Gemini Vision
        # Prompt ajustado para focar apenas na identificação da peça
        prompt_parts = [
            "Descreva a peça de roupa nesta imagem em poucas palavras, focando no tipo e cor principal. Ex: 'camiseta azul', 'calça jeans preta'. Se não for uma peça de roupa, diga 'Não é uma peça de roupa'.",
            {"mime_type": "image/png", "data": image_bytes} # Adiciona a imagem como parte do prompt
        ]

        # Inicializa o modelo Gemini Vision
        try:
            model = genai.GenerativeModel(model_name=GEMINI_MODEL)
        except Exception as e:
            print(f"Erro ao inicializar modelo Gemini: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro ao configurar o modelo de IA: {e}"
            )

        # Gera o conteúdo (analisa a imagem)
        try:
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
            response = model.generate_content(prompt_parts, safety_settings=safety_settings)

            if not response._result.candidates:
                 print(f"Resposta da API Gemini bloqueada: {response._result.prompt_feedback}")
                 block_reason = "Motivo desconhecido."
                 if response._result.prompt_feedback and response._result.prompt_feedback.safety_ratings:
                     reasons = [
                         f"{rating.category}: {rating.probability}"
                         for rating in response._result.prompt_feedback.safety_ratings
                         if rating.probability != 'UNKNOWN' and rating.probability != 'NEGLIGIBLE'
                     ]
                     if reasons:
                         block_reason = "; ".join(reasons)

                 raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Conteúdo bloqueado pela política de segurança da IA. Motivo: {block_reason}"
                )

        except Exception as e:
            print(f"Erro na chamada da API Gemini Vision: {e}")
            if "401" in str(e) or "API key not valid" in str(e):
                 raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Chave de API do Google inválida ou sem permissão para usar o modelo."
                )
            elif "404" in str(e) or "Model" in str(e) and "not found" in str(e) or "disabled" in str(e):
                 raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Modelo Gemini '{GEMINI_MODEL}' não encontrado ou desabilitado para sua conta."
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Erro ao analisar a imagem com a IA: {str(e)}"
                )

        # Processa a resposta da análise para obter a peça identificada
        identified_clothing = "Não foi possível identificar a peça."
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
             text_result = response.candidates[0].content.parts[0].text.strip()
             if text_result.lower().startswith("descreva a peça de roupa nesta imagem"):
                 parts = text_result.split(':')
                 if len(parts) > 1 and parts[1].strip():
                     identified_clothing = parts[1].strip()
                 else:
                      identified_clothing = "Não foi possível identificar a peça com clareza."
             else:
                  identified_clothing = text_result

             if identified_clothing.lower() == "não é uma peça de roupa":
                 identified_clothing = "Não foi identificado uma peça de roupa na imagem."


        # 2. Sugestão Sustentável (Lógica aprimorada no backend)
        # A sugestão ainda é baseada na lógica interna do backend por enquanto
        sustainable_suggestion = "Não foi possível sugerir uma alternativa sustentável."
        if "Não foi identificado" not in identified_clothing and "Erro" not in identified_clothing and "Não foi possível identificar" not in identified_clothing:
            clothing_lower = identified_clothing.lower()
            if "camiseta" in clothing_lower or "blusa" in clothing_lower or "top" in clothing_lower:
                sustainable_suggestion = "Para esta peça, considere alternativas de algodão orgânico certificado, algodão reciclado ou malha de fibras como bambu ou Tencel™ Lyocell. Essas opções reduzem o impacto ambiental do cultivo e produção."
            elif "calça jeans" in clothing_lower or "jeans" in clothing_lower:
                sustainable_suggestion = "Busque por calças jeans feitas com processos de lavagem a seco, ozônio ou laser para reduzir o uso de água e químicos. Jeans reciclados ou de segunda mão também são excelentes escolhas sustentáveis."
            elif "vestido" in clothing_lower or "saia" in clothing_lower:
                sustainable_suggestion = "Opte por vestidos ou saias feitos de materiais naturais como linho, cânhamo, algodão orgânico, ou de tecidos reciclados. O reuso e a compra de peças de segunda mão são ótimas formas de sustentabilidade."
            elif "jaqueta" in clothing_lower or "casaco" in clothing_lower or "blazer" in clothing_lower:
                 sustainable_suggestion = "Considere jaquetas, casacos ou blazers feitos de materiais reciclados (como poliéster de garrafas PET), lã reciclada, ou de segunda mão. A durabilidade e o reuso são chaves aqui."
            elif "sapato" in clothing_lower or "tênis" in clothing_lower or "calçado" in clothing_lower:
                 sustainable_suggestion = "Considere calçados feitos com materiais reciclados (borracha, plástico), materiais veganos sustentáveis (couro de cogumelo, Pinatex), ou de couro de origem responsável. Brechós de calçados também são uma opção."
            elif "bolsa" in clothing_lower or "mochila" in clothing_lower or "acessório" in clothing_lower:
                 sustainable_suggestion = "Busque por bolsas, mochilas ou acessórios feitos com materiais reciclados, tecidos reaproveitados, ou materiais veganos sustentáveis. A durabilidade e o design atemporal também contribuem para a sustentabilidade."
            elif "shorts" in clothing_lower or "bermuda" in clothing_lower:
                 sustainable_suggestion = "Considere shorts/bermudas de algodão orgânico, linho ou materiais reciclados. Peças de segunda mão são uma alternativa prática e sustentável."
            else:
                sustainable_suggestion = "Para esta peça, busque por opções feitas com materiais sustentáveis, reciclados, orgânicos ou de segunda mão. A escolha de materiais de baixo impacto ambiental faz uma grande diferença."


        # 3. Busca de Lojas Próximas (Usando a função que CHAMA a API REAL)
        # A query para a ferramenta agora é mais específica com base na peça identificada.
        search_query = f"loja de roupa sustentável ou brechó que vende {identified_clothing}"
        # Chama a função que agora integra com a API Google Places
        nearby_stores = google_maps_search_tool(query=search_query, location=user_location_data)

        # Nota: Se a chamada à API Places falhar ou não encontrar resultados,
        # a função google_maps_search_tool retornará uma lista vazia,
        # e o frontend exibirá "Nenhuma loja sustentável ou brechó encontrado próximo."


        # Retorna os resultados para o frontend em formato JSON
        return {
            "identifiedClothing": identified_clothing,
            "sustainableSuggestion": sustainable_suggestion,
            "nearbyStores": nearby_stores # Retorna os dados reais (ou lista vazia) da API Places
        }

    except HTTPException as e:
        # Captura e re-lança exceções HTTP personalizadas que criamos
        raise e
    except Exception as e:
        # Captura quaisquer outros erros inesperados e retorna um erro 500
        print(f"Erro inesperado no backend: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ocorreu um erro inesperado no servidor: {str(e)}"
        )

# Para rodar o servidor FastAPI (apenas para desenvolvimento local)
# Use 'uvicorn main:app --reload' no terminal onde este arquivo (main.py) está salvo
# Certifique-se de ter uvicorn e fastapi instalados (`pip install fastapi uvicorn python-multipart python-dotenv requests`)
# python-multipart é necessário para receber Form data
# python-dotenv é necessário para carregar variáveis do .env
# google-generativeai é necessário para a integração com Gemini (`pip install google-generativeai`)
# requests é necessário para fazer chamadas HTTP para APIs externas (`pip install requests`)
