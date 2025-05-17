# Importa as bibliotecas necessárias para FastAPI e outras funcionalidades
import os
import base64
import time
import requests # Para fazer requisições HTTP para a Overpass API
from fastapi import FastAPI, HTTPException, status, Form, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Union, List, Dict, Any

# Importa a biblioteca para carregar variáveis de ambiente do arquivo .env
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Importa o SDK do Google Generative AI
import google.generativeai as genai

# --- Configuração da Chave da API do Google ---
# A API Key ainda é necessária para a integração com o Gemini Vision.
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
    "http://localhost",
    "http://localhost:8000",
    "http://localhost:5000",
    "http://127.0.0.1",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:5000",
    "http://127.0.0.1:5500", # Porta comum do Live Server
    # Adicione a URL de produção da sua PWA aqui quando estiver em deploy
    # "https://sua-pwa-em-producao.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Definição do Modelo Pydantic para Localização do Usuário ---
class UserLocation(BaseModel):
    lat: float
    lng: float

# --- Função que CHAMA a Overpass API (OpenStreetMap) ---
# Esta função busca dados de lojas no OpenStreetMap usando a Overpass API.
def osm_overpass_search_tool(query: str, location: dict) -> List[Dict[str, Any]]:
    """
    Busca por lugares (lojas de roupa sustentável, brechós) no OpenStreetMap
    usando a Overpass API.

    Args:
        query: A string de busca (usada para refinar as tags OSM).
        location: Um dicionário com as chaves 'lat' e 'lng' para a localização.

    Returns:
        Uma lista de dicionários representando os lugares encontrados.
        Retorna lista vazia em caso de erro ou nenhum resultado.
    """
    print(f"Chamando a Overpass API para buscar: Query='{query}', Localização='{location}'")

    overpass_url = "http://overpass-api.de/api/interpreter"
    radius_meters = 5000 # Raio de busca em metros (ex: 5km). Ajuste conforme necessário.
    lat = location['lat']
    lng = location['lng']

    # Construindo a query Overpass dinamicamente
    # Buscamos por nodes, ways e relations com tags relevantes
    # Tentamos incluir termos da query na busca por nome ou descrição, se possível
    # Esta é uma query básica, pode ser refinada para incluir mais tags relevantes
    overpass_query = f"""
    [out:json][timeout:25];
    (
      node["shop"="second_hand"](around:{radius_meters}, {lat}, {lng});
      way["shop"="second_hand"](around:{radius_meters}, {lat}, {lng});
      relation["shop"="second_hand"](around:{radius_meters}, {lat}, {lng});

      node["shop"="clothes"](around:{radius_meters}, {lat}, {lng});
      way["shop"="clothes"](around:{radius_meters}, {lat}, {lng});
      relation["shop"="clothes"](around:{radius_meters}, {lat}, {lng});

      node["second_hand"="yes"](around:{radius_meters}, {lat}, {lng});
      way["second_hand"="yes"](around:{radius_meters}, {lat}, {lng});
      relation["second_hand"="yes"](around:{radius_meters}, {lat}, {lng});

      // Adicionar busca por nome ou descrição contendo termos da query (experimental)
      node(around:{radius_meters}, {lat}, {lng})[~"name|description"~".*{query}.*", i];
      way(around:{radius_meters}, {lat}, {lng})[~"name|description"~".*{query}.*", i];
      relation(around:{radius_meters}, {lat}, {lng})[~"name|description"~".*{query}.*", i];

    );
    out center;
    """
    # Nota sobre a busca por query: A busca por nome/descrição com regex pode ser lenta
    # e não é ideal para todas as queries. É uma tentativa de usar a query do Gemini.

    try:
        # Faz a requisição POST para a Overpass API
        response = requests.post(overpass_url, data={"data": overpass_query})
        response.raise_for_status() # Levanta um erro HTTP para status ruins (4xx ou 5xx)

        osm_data = response.json()
        print(f"Resposta da Overpass API recebida (elementos: {len(osm_data.get('elements', []))}):")
        # print(json.dumps(osm_data, indent=2)) # Descomente para ver a resposta completa da API

        nearby_stores = []
        if osm_data.get('elements'):
            for element in osm_data['elements']:
                # Extrai informações relevantes dos elementos OSM
                name = element.get('tags', {}).get('name', 'Nome não disponível')
                # Tenta obter o endereço de várias tags comuns
                address_parts = []
                tags = element.get('tags', {})
                if tags.get('addr:street'): address_parts.append(tags['addr:street'])
                if tags.get('addr:housenumber'): address_parts.append(tags['addr:housenumber'])
                if tags.get('addr:city'): address_parts.append(tags['addr:city'])
                if tags.get('addr:postcode'): address_parts.append(tags['addr:postcode'])

                address = ", ".join(address_parts) if address_parts else "Endereço não disponível"

                # Coordenadas do elemento (para nodes) ou centro (para ways/relations com out center)
                element_lat = element.get('lat', element.get('center', {}).get('lat'))
                element_lng = element.get('lon', element.get('center', {}).get('lon'))

                # Nota: Distância não é retornada pela Overpass API.
                # Poderíamos calcular a distância geodésica aqui se necessário,
                # mas para o MVP manteremos um placeholder ou omitiremos.
                distance = "Distância N/A" # Placeholder

                # Adiciona o lugar à lista de resultados
                nearby_stores.append({
                    "name": name,
                    "address": address,
                    "distance": distance, # Mantém o placeholder
                    "lat": element_lat, # Opcional: incluir coordenadas para uso futuro
                    "lng": element_lng  # Opcional: incluir coordenadas para uso futuro
                })

        return nearby_stores

    except requests.exceptions.RequestException as e:
        print(f"Erro na chamada da Overpass API: {e}")
        # Em caso de erro na API, retornamos uma lista vazia e logamos o erro.
        return []
    except Exception as e:
        print(f"Erro inesperado ao processar resposta da Overpass API: {e}")
        return []


# --- Endpoint principal para análise e busca ---
# Este endpoint recebe a imagem (como string base64) e a localização do frontend.
@app.post("/analyze_and_find_stores")
async def analyze_and_find_stores_endpoint(
    imageDataUrl: str = Form(...),
    userLocation: str = Form(...)
):
    if not API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API Key do Google não configurada no backend."
        )

    import json
    try:
        user_location_data = json.loads(userLocation)
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
        if ',' not in imageDataUrl:
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato de URL de dados da imagem inválido."
            )
        image_base64 = imageDataUrl.split(',')[1]

        try:
            image_bytes = base64.b64decode(image_base64)
        except base64.binascii.Error:
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Dados da imagem não estão em formato base64 válido."
            )

        prompt_parts = [
            "Descreva a peça de roupa nesta imagem em poucas palavras, focando no tipo e cor principal. Ex: 'camiseta azul', 'calça jeans preta'. Se não for uma peça de roupa, diga 'Não é uma peça de roupa'.",
            {"mime_type": "image/png", "data": image_bytes}
        ]

        try:
            model = genai.GenerativeModel(model_name=GEMINI_MODEL)
        except Exception as e:
            print(f"Erro ao inicializar modelo Gemini: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro ao configurar o modelo de IA: {e}"
            )

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

        # 2. Sugestão Sustentável
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

        # 3. Busca de Lojas Próximas (Usando a Overpass API)
        # A query para a ferramenta agora é mais específica com base na peça identificada.
        # Usamos a peça identificada para tentar refinar a busca no OSM, embora a precisão dependa das tags no OSM.
        search_term_for_osm = "brechó" # Termo base para busca no OSM
        clothing_lower = identified_clothing.lower()
        if "roupa" in clothing_lower or "vestuário" in clothing_lower or "moda" in clothing_lower:
             search_term_for_osm = "roupa sustentável" # Tenta refinar se a identificação for genérica
        elif "jeans" in clothing_lower:
             search_term_for_osm = "brechó jeans" # Tenta refinar para jeans
        # Adicione mais lógica aqui para refinar search_term_for_osm com base em outras peças

        nearby_stores = osm_overpass_search_tool(query=search_term_for_osm, location=user_location_data)

        # Retorna os resultados para o frontend em formato JSON
        return {
            "identifiedClothing": identified_clothing,
            "sustainableSuggestion": sustainable_suggestion,
            "nearbyStores": nearby_stores # Retorna os dados obtidos da Overpass API
        }

    except HTTPException as e:
        raise e
    except Exception as e:
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
