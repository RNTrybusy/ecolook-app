// Nome do cache
const CACHE_NAME = 'ecolook-cache-v1';
// Arquivos para cachear
const urlsToCache = [
    '/',
    '/index.html', // Certifique-se de que este é o nome do seu arquivo HTML principal
    '/styles.css', // Se você tiver um arquivo CSS separado, inclua-o. Atualmente, o CSS está no HTML.
    '/script.js',  // Se você tiver um arquivo JS separado, inclua-o. Atualmente, o JS está no HTML.
    'https://cdnjs.cloudflare.com/ajax/libs/tailwindcss/2.2.19/tailwind.min.css' // Cache do Tailwind
    // Adicione outros assets (imagens, ícones na pasta /icons) aqui
];

// Instalação: Cacheia os arquivos
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('Service Worker: Cacheando arquivos');
                return cache.addAll(urlsToCache);
            })
    );
});

// Fetch: Serve do cache se disponível, senão busca na rede
self.addEventListener('fetch', event => {
    event.respondWith(
        caches.match(event.request)
            .then(response => {
                // Retorna do cache se encontrado
                if (response) {
                    return response;
                }
                // Caso contrário, busca na rede
                return fetch(event.request);
            })
    );
});

// Ativação: Limpa caches antigos
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => {
                    if (cacheName !== CACHE_NAME) {
                        console.log('Service Worker: Removendo cache antigo', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
});
