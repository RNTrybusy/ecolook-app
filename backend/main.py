# Importa as bibliotecas necessárias para FastAPI e outras funcionalidades
import os
import base64
import time # Para simular delay na busca mock
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
# Em produção, use um gerenciador de segredos (Secret Manager) ou variáveis de ambiente configuradas de forma segura.
API_KEY = os.environ.get('GOOGLE_API_KEY')

# Verifica se a chave da API está configurada. Se não, levanta um erro fatal ao iniciar o backend.
if not API_KEY:
    # Em um ambiente de produção, você pode querer logar isso e sair graciosamente.
    # Para desenvolvimento, podemos imprimir uma mensagem clara.
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

# --- Definição de Ferramentas para o Agente (Conceitual para este MVP) ---
# Sua ideia de usar um agente com ferramenta de mapas é excelente para uma versão real.
# A integração de ferramentas com Agentes no SDK Python é um recurso em evolução.
# Abaixo, demonstramos o CONCEITO de como uma ferramenta seria definida, mas a orquestração
# completa do Agente para usar essa ferramenta automaticamente requer suporte específico do SDK/Framework.
# Para este MVP, vamos SIMULAR o comportamento da busca de lojas diretamente no endpoint.

# @genai_tool
# def google_maps_search(query: str, location: UserLocation):
#     """Busca por lugares usando a API do Google Maps/Places.
#     Args:
#         query: A string de busca (ex: "lojas de roupa sustentável").
#         location: Um objeto UserLocation com as chaves 'lat' e 'lng' para a localização.
#     Returns:
#         Uma lista de lugares encontrados com nome, endereço e distância (simulado para o MVP).
#     """
#     print(f"Agente solicitou busca no Google Maps: Query='{query}', Localização='{location.model_dump() if hasattr(location, 'model_dump') else location}'")
#     # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
#     # AQUI SERIA A CHAMADA REAL PARA A API DO GOOGLE MAPS PLACES (PAGA)
#     # Usando a nova Places API (searchNearby) ou outra API de busca de locais.
#     # Esta chamada usaria a API_KEY do backend de forma segura.
#     # Exemplo conceitual (requer implementação real e tratamento de resposta):
#     # response = requests.post('https://places.googleapis.com/v1/places:searchNearby', json={...}, headers={'X-Goog-Api-Key': API_KEY})
#     # places_data = response.json()
#     # Mapear places_data para o formato de retorno esperado
#     # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

#     # --- Simulação de resposta para o MVP gratuito ---
#     # No MVP, simulamos a resposta que viria de uma busca real.
#     mock_stores = [
#         {"name": f"Brechó Central (Simulado para '{query}')", "address": "Rua Imaginária A, 123", "distance": "500m"},
#         {"name": f"Moda Ecológica (Simulado para '{query}')", "address": "Av. Fantasia B, 456", "distance": "1.2km"},
#     ]
#     return mock_stores.copy() # Retorna uma cópia para evitar modificações inesperadas


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
        image_parts = [
            {
                "mime_type": "image/png", # Assumindo PNG do frontend canvas
                "data": image_bytes
            }
        ]
        prompt_parts = [
            "Descreva a peça de roupa nesta imagem em poucas palavras, focando no tipo e cor principal. Ex: 'camiseta azul', 'calça jeans preta'. Se não for uma peça de roupa, diga 'Não é uma peça de roupa'.",
            image_parts[0] # Adiciona a imagem como parte do prompt
        ]

        # Inicializa o modelo Gemini Vision
        # Adicionado tratamento de erro caso o modelo não seja encontrado ou API Key inválida
        try:
            model = genai.GenerativeModel(model_name=GEMINI_MODEL)
        except Exception as e:
            print(f"Erro ao inicializar modelo Gemini: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro ao configurar o modelo de IA: {e}"
            )


        # Gera o conteúdo (analisa a imagem)
        # Configura safety settings para evitar bloqueio de conteúdo de vestuário (ajuste conforme necessário)
        # Adicionado tratamento de erro para a chamada da API
        try:
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
            response = model.generate_content(prompt_parts, safety_settings=safety_settings)

            # Verifica se a resposta contém bloqueios de segurança
            if not response._result.candidates:
                 print(f"Resposta da API Gemini bloqueada: {response._result.prompt_feedback}")
                 # Tenta extrair o motivo do bloqueio se disponível
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
            # Verifica se o erro é relacionado à API Key inválida ou falta de permissão
            if "401" in str(e) or "API key not valid" in str(e):
                 raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Chave de API do Google inválida ou sem permissão para usar o modelo."
                )
            # Verifica se o erro é relacionado ao modelo não encontrado ou desabilitado
            elif "404" in str(e) or "Model" in str(e) and "not found" in str(e) or "disabled" in str(e):
                 raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Modelo Gemini '{GEMINI_MODEL}' não encontrado ou desabilitado para sua conta."
                )
            # Outros erros da API
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Erro ao analisar a imagem com a IA: {str(e)}"
                )


        # Processa a resposta da análise
        identified_clothing = "Não foi possível identificar a peça."
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
             text_result = response.candidates[0].content.parts[0].text.strip()
             # Limpa a resposta para remover texto indesejado ou repetições do prompt
             if text_result.lower().startswith("descreva a peça de roupa nesta imagem"):
                 # Tenta extrair a parte relevante após o prompt
                 parts = text_result.split(':')
                 if len(parts) > 1 and parts[1].strip():
                     identified_clothing = parts[1].strip()
                 else:
                      identified_clothing = "Não foi possível identificar a peça com clareza."
             else:
                  identified_clothing = text_result

             if identified_clothing.lower() == "não é uma peça de roupa": # Normaliza para comparação
                 identified_clothing = "Não foi identificado uma peça de roupa na imagem."


        # 2. Sugestão Sustentável (Lógica aprimorada no backend)
        sustainable_suggestion = "Não foi possível sugerir uma alternativa sustentável."
        if "Não foi identificado" not in identified_clothing and "Erro" not in identified_clothing and "Não foi possível identificar" not in identified_clothing:
            # Lógica de sugestão mais elaborada baseada em palavras-chave identificadas
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
                 sustainable_suggestion = "Procure por calçados feitos com materiais reciclados (borracha, plástico), materiais veganos sustentáveis (couro de cogumelo, Pinatex), ou de couro de origem responsável. Brechós de calçados também são uma opção."
            elif "bolsa" in clothing_lower or "mochila" in clothing_lower or "acessório" in clothing_lower:
                 sustainable_suggestion = "Busque por bolsas, mochilas ou acessórios feitos com materiais reciclados, tecidos reaproveitados, ou materiais veganos sustentáveis. A durabilidade e o design atemporal também contribuem para a sustentabilidade."
            elif "shorts" in clothing_lower or "bermuda" in clothing_lower:
                 sustainable_suggestion = "Considere shorts/bermudas de algodão orgânico, linho ou materiais reciclados. Peças de segunda mão são uma alternativa prática e sustentável."
            else:
                sustainable_suggestion = "Para esta peça, busque por opções feitas com materiais sustentáveis, reciclados, orgânicos ou de segunda mão. A escolha de materiais de baixo impacto ambiental faz uma grande diferença."


        # 3. Busca de Lojas Próximas (Simulada para o MVP gratuito)
        # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
        # AQUI SERIA ONDE O AGENTE GEMINI COM A FERRAMENTA google_maps SERIA USADO
        # OU A CHAMADA REAL PARA A API DO GOOGLE MAPS PLACES (PAGA)
        # Exemplo conceitual de como seria a chamada ao agente (requer SDK/Framework com suporte a Agentes e Ferramentas):
        # agent_response = planejador.call_agent(entrada_do_agente_buscador)
        # nearby_stores = agent_response # Assumindo que a resposta do agente contém a lista de lojas
        # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

        # --- Simulação de busca de lojas para o MVP gratuito ---
        # Mantemos a simulação da busca de lojas no backend para este MVP.
        # Em uma versão real, a chamada para a API Google Places (paga) seria feita aqui
        # de forma segura, usando a API_KEY do backend.
        print(f"Backend simulando busca de lojas para '{identified_clothing}' na localização {user_location_data}...")
        # Simulação de delay para imitar uma chamada de API externa
        time.sleep(2) # Simula 2 segundos de delay

        # Dados mock de lojas próximas (podem ser refinados com base no identified_clothing)
        mock_stores = [
            {"name": f"Brechó da Cidade (Simulado)", "address": "Centro, Rua Fictícia 1", "distance": "1.5 km"},
            {"name": f"Loja Eco (Simulado)", "address": "Bairro Verde, Av. Sustentável 2", "distance": "3.1 km"},
             {"name": f"Second Hand Online (Simulado)", "address": "Entrega para sua região", "distance": "Online"},
             {"name": f"Brechó Vintage (Simulado)", "address": "Rua das Antiguidades, 5", "distance": "0.8 km"}
        ]

        # Exemplo de como refinar a simulação com base na identificação
        if "jeans" in identified_clothing.lower():
             mock_stores.append({"name": "Brechó Jeans & Cia (Simulado)", "address": "Rua do Denim, 7", "distance": "4.0 km"})
        if "vestido" in identified_clothing.lower():
             mock_stores.append({"name": "Vestidos Sustentáveis (Simulado)", "address": "Galeria Moda Consciente, Loja 10", "distance": "2.2 km"})


        # Retorna os resultados para o frontend em formato JSON
        return {
            "identifiedClothing": identified_clothing,
            "sustainableSuggestion": sustainable_suggestion,
            "nearbyStores": mock_stores # Retorna os dados mock de lojas
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
# Certifique-se de ter uvicorn e fastapi instalados (`pip install fastapi uvicorn python-multipart python-dotenv`)
# python-multipart é necessário para receber Form data
# python-dotenv é necessário para carregar variáveis do .env
# google-generativeai é necessário para a integração com Gemini (`pip install google-generativeai`)
