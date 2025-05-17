# Registro de Desenvolvimento - EcoLook até o MVP

Este documento detalha as etapas de desenvolvimento do EcoLook MVP, desde a concepção inicial até o estado atual, cobrindo a construção do frontend PWA, o backend FastAPI, a integração com Google Gemini Vision e a evolução da estratégia de busca de localização.

## 1. Concepção Inicial e Estrutura (Frontend Básico)

A ideia inicial era criar um aplicativo web que pudesse identificar roupas e sugerir alternativas sustentáveis. Decidiu-se por uma Progressive Web App (PWA) para permitir instalação e acesso a recursos do dispositivo como a câmera e geolocalização.

- **Frontend:** Uma estrutura HTML básica foi criada (`index.html`) com elementos para exibir o feed da câmera, uma imagem capturada, botões de controle e áreas para feedback e resultados. Tailwind CSS foi adicionado para estilização rápida. A funcionalidade básica de acesso à câmera e captura de imagem foi implementada usando a API `navigator.mediaDevices.getUserMedia`. Um Service Worker básico foi incluído para os recursos de PWA.
    

## 2. Introdução do Backend e Análise com Gemini Vision

Para realizar a análise da imagem com inteligência artificial, um backend se tornou necessário. FastAPI foi escolhido como framework devido à sua performance e facilidade de uso com Python.

- **Backend:** Um aplicativo FastAPI (`main.py`) foi configurado com CORS para permitir requisições do frontend. A integração com o Google Gemini Vision foi adicionada usando o SDK `google-generativeai`. O endpoint `/analyze_and_find_stores` foi criado para receber a imagem (como string base64) e a localização do usuário. A lógica inicial focava em decodificar a imagem e enviá-la ao modelo Gemini Vision com um prompt para identificar a peça de roupa.
    
- **Integração Frontend-Backend:** O JavaScript do frontend foi modificado para enviar a imagem capturada e a localização do usuário para o novo endpoint do backend usando `fetch` e `FormData`.
    

## 3. Gerenciamento Seguro da API Key e Sugestão Sustentável

Para gerenciar a chave de API do Google de forma segura, a biblioteca `python-dotenv` foi integrada ao backend. Uma lógica inicial para gerar sugestões sustentáveis também foi adicionada.

- **Backend:** `python-dotenv` foi adicionado para carregar a `GOOGLE_API_KEY` de um arquivo `.env`. Uma verificação inicial foi incluída para garantir que a chave esteja configurada. Uma lógica simples baseada em palavras-chave (ex: "camiseta" -> "algodão orgânico") foi adicionada no backend para gerar uma `sustainableSuggestion`.
    
- **Frontend:** O frontend foi atualizado para exibir a `sustainableSuggestion` recebida do backend.
    

## 4. Evolução da Busca de Lojas: Mock -> Google Places API

Inicialmente, a busca de lojas foi simulada no backend com dados mock para permitir o desenvolvimento do fluxo completo. A ideia de usar um agente Gemini com uma ferramenta de mapas foi considerada para o futuro. Em seguida, a busca foi atualizada para usar a API real do Google Places.

- **Backend (Mock):** Uma função simulada (`google_maps_search_tool`) foi criada no backend para retornar dados mock de lojas, imitando o que uma API de mapas faria. O endpoint principal chamava essa função após a análise da IA.
    
- **Backend (Google Places API):** A função `google_maps_search_tool` foi modificada para chamar a Google Places API (New) - `searchNearby` de forma real, utilizando a `API_KEY`. A lógica para construir a requisição (com raio de busca, tipos de lugar e query de texto) e processar a resposta foi implementada. Foi observado que a API Places (New) não retorna distância diretamente no `searchNearby`.
    
- **Frontend:** O frontend foi atualizado para exibir a lista de lojas recebida do backend (fosse mock ou da API Places). Um indicador "(Dados simulados para MVP)" foi adicionado quando a busca era mock.
    

## 5. Refinamento do Frontend: Feedback e Exibição de Item Detectado

Com a comunicação backend-frontend funcionando, o foco voltou para a experiência do usuário no frontend, melhorando o feedback durante o processamento e criando uma seção dedicada para o item detectado.

- **Frontend:** Mensagens de feedback mais sequenciais e descritivas foram implementadas para guiar o usuário pelas etapas do processo (captura, localização, envio, análise, busca). Um pequeno delay foi adicionado entre as etapas de feedback para melhor percepção. Uma nova seção HTML (`identified-item-section`) foi criada para exibir o nome do item detectado separadamente da área de feedback e resultados. Estilos CSS foram adicionados para essa nova seção. A lógica JavaScript foi ajustada para mostrar/esconder a nova seção e preencher o texto do item detectado. Um botão "Limpar Resultados" foi adicionado para resetar a UI.
    

## 6. Adaptação da Busca de Lojas: Google Places API -> OpenStreetMap/Overpass API

Devido aos custos associados à Google Places API para exibição de dados, a estratégia de busca de lojas foi alterada para utilizar a Overpass API do OpenStreetMap, uma alternativa gratuita.

- **Backend:** A função de busca de lojas foi renomeada para `osm_overpass_search_tool`. A lógica interna foi completamente reescrita para construir e enviar uma query para a Overpass API, buscando por tags relevantes para brechós e lojas de roupa dentro de um raio. A extração de dados da resposta JSON da Overpass API (nome, endereço) foi implementada. O endpoint principal foi atualizado para chamar a nova função `osm_overpass_search_tool`.
    
- **Frontend:** O texto no modal "Sobre" e nas mensagens de feedback foi atualizado para refletir que a busca de lojas agora utiliza dados do OpenStreetMap via Overpass API. A lógica de exibição da lista de lojas permaneceu a mesma, mas agora processando dados do OSM.
    

## 7. Refinamento Final do Frontend: Links para Google Maps e Indicador de Carregamento

Para complementar a busca via OSM e fornecer uma forma de visualizar a localização no mapa. Um indicador de carregamento visual (spinner) foi adicionado.

- **Frontend:** A função `displayNearbyStores` foi modificada para envolver o nome de cada loja em uma tag `<a>` com um `href` formatado para abrir uma busca OpenStreetMap com o nome e endereço da loja. Estilos CSS foram adicionados para os links. Um estilo CSS para um spinner de carregamento foi criado e a lógica JavaScript foi ajustada para adicionar/remover a classe `loading` (que controla o spinner) na área de feedback durante as chamadas ao backend. O texto do modal "Sobre" e o feedback foram novamente ajustados para explicar a abordagem de usar OSM e links para Google Maps.
    

## Estado Atual

Atualmente, o EcoLook MVP é uma PWA funcional que permite escanear roupas, obter sugestões sustentáveis (baseadas em lógica interna) e buscar lojas próximas usando dados do OpenStreetMap (via Overpass API) e idealmente mostrar lojas próximas. O frontend oferece feedback sequencial e exibe o item detectado em uma seção separada.

Este MVP serve como uma base sólida para futuras iterações, focando em refinar a precisão da busca de lojas (dependendo da completude dos dados OSM), melhorar as sugestões sustentáveis com dados mais ricos e potencialmente explorar a orquestração de ferramentas com Agentes Gemini em um backend mais complexo no futuro.