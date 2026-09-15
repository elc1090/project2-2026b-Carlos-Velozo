const INITIAL_COORDS = [-29.6847, -53.8045];
const ZOOM_LEVEL = 13;

let map;
let markersGroup;
let userLocation = null;
let userMarker = null;

document.addEventListener('DOMContentLoaded', () => {
    map = L.map('map').setView(INITIAL_COORDS, ZOOM_LEVEL);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19
    }).addTo(map);

    markersGroup = L.layerGroup().addTo(map);

    document.getElementById('btn-search').addEventListener('click', executarBusca);
    document.getElementById('btn-location').addEventListener('click', obterLocalizacaoUsuario);
    document.getElementById('med-input').addEventListener('input', buscarSugestoes);

    carregarHistorico();
});

function calcularDistanciaKM(lat1, lon1, lat2, lon2) {
    const R = 6371;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = 
        Math.sin(dLat/2) * Math.sin(dLat/2) +
        Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * 
        Math.sin(dLon/2) * Math.sin(dLon/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c;
}

function obterLocalizacaoUsuario() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(position => {
            userLocation = {
                lat: position.coords.latitude,
                lng: position.coords.longitude
            };

            if (userMarker) map.removeLayer(userMarker);

            userMarker = L.circleMarker([userLocation.lat, userLocation.lng], {
                color: '#0284c7',
                fillColor: '#38bdf8',
                fillOpacity: 0.9,
                radius: 8,
                weight: 3
            }).addTo(map).bindPopup("<b>Sua Localização</b>").openPopup();

            map.setView([userLocation.lat, userLocation.lng], 14);
        }, () => {
            alert("Não foi possível obter sua localização.");
        });
    }
}

async function executarBusca() {
    const termo = document.getElementById('med-input').value.trim();
    if (!termo) return;

    document.getElementById('suggestions').innerHTML = '';

    const response = await fetch(`/api/buscar?medicamento=${encodeURIComponent(termo)}`);
    let farmacias = await response.json();

    if (userLocation) {
        farmacias.forEach(f => {
            f.distancia = calcularDistanciaKM(userLocation.lat, userLocation.lng, f.lat, f.lng);
        });
        farmacias.sort((a, b) => a.distancia - b.distancia);
    }

    renderizarResultados(farmacias);
    salvarHistoricoPOST(termo);
}

async function salvarHistoricoPOST(termo) {
    try {
        await fetch('/api/historico', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                termo: termo,
                lat: userLocation ? userLocation.lat : null,
                lng: userLocation ? userLocation.lng : null
            })
        });
        carregarHistorico();
    } catch (err) {
        console.error("Erro ao salvar histórico:", err);
    }
}

function renderizarResultados(farmacias) {
    markersGroup.clearLayers();
    const listContainer = document.getElementById('results-list');
    document.getElementById('count').innerText = farmacias.length;
    listContainer.innerHTML = '';

    if (farmacias.length === 0) {
        listContainer.innerHTML = `
            <div class="placeholder-state">
                <i class="fa-solid fa-circle-exclamation"></i>
                <p>Nenhuma farmácia encontrada para este medicamento.</p>
            </div>
        `;
        return;
    }

    const bounds = [];

    farmacias.forEach((f, idx) => {
        const marker = L.marker([f.lat, f.lng]).addTo(markersGroup);
                
        let popupContent = `
            <div class="custom-popup">
                <div class="popup-image-container">
                    ${f.imagem ? 
                        `<img src="${f.imagem}" alt="${f.nome}" onerror="this.outerHTML='<div class=\\'popup-image-placeholder\\'><i class=\\'fa-solid fa-image\\'></i><span>Imagem em breve</span></div>'">` : 
                        `<div class="popup-image-placeholder"><i class="fa-solid fa-image"></i><span>Imagem em breve</span></div>`
                    }
                </div>
                <h4>${f.nome}</h4>
                <p><i class="fa-solid fa-location-dot"></i> ${f.endereco}</p>
            </div>
        `;
        marker.bindPopup(popupContent);
        bounds.push([f.lat, f.lng]);

        const isBest = idx === 0 && userLocation;
        const card = document.createElement('div');
        card.className = `pharmacy-card ${isBest ? 'best-option' : ''}`;
        card.innerHTML = `
            ${isBest ? '<span class="tag-nearest"><i class="fa-solid fa-bolt"></i> Mais Próxima</span>' : ''}
            <h4>${f.nome}</h4>
            <p><i class="fa-solid fa-location-dot"></i> ${f.endereco}</p>
            ${f.distancia !== undefined ? `
                <div class="card-footer-info">
                    <span class="badge-distance"><i class="fa-solid fa-route"></i> ${f.distancia.toFixed(2)} km de você</span>
                </div>
            ` : ''}
        `;

        card.addEventListener('click', () => {
            map.setView([f.lat, f.lng], 16);
            marker.openPopup();
        });

        listContainer.appendChild(card);
    });

    if (bounds.length > 0) {
        map.fitBounds(bounds, { padding: [40, 40] });
    }
}

async function buscarSugestoes() {
    const q = document.getElementById('med-input').value.trim();
    const list = document.getElementById('suggestions');
    if (q.length < 2) {
        list.innerHTML = '';
        return;
    }

    const res = await fetch(`/api/sugestoes?q=${encodeURIComponent(q)}`);
    const sugestoes = await res.json();
    
    list.innerHTML = sugestoes.map(item => `<li>${item}</li>`).join('');

    list.querySelectorAll('li').forEach(li => {
        li.addEventListener('click', () => {
            document.getElementById('med-input').value = li.innerText;
            list.innerHTML = '';
            executarBusca();
        });
    });
}

async function carregarHistorico() {
    const res = await fetch('/api/historico');
    const historico = await res.json();
    const ul = document.getElementById('history-list');
    
    if (historico.length === 0) {
        ul.innerHTML = '<li style="color: var(--slate-400); border:none;">Sem buscas recentes</li>';
        return;
    }

    ul.innerHTML = historico.map(h => {      
        const dataUTC = new Date(h.data_hora.replace(' ', 'T') + 'Z');
        const horaFormatada = dataUTC.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});

        return `
            <li class="history-item" onclick="reutilizarBusca('${h.termo_busca.replace(/'/g, "\\'")}')">
                <span class="history-term"><i class="fa-solid fa-clock-rotate-left"></i> ${h.termo_busca}</span>
                <span class="history-time">${horaFormatada}</span>
            </li>
        `;
    }).join('');
}

function reutilizarBusca(termo) {
    document.getElementById('med-input').value = termo;
    executarBusca();
}