'use strict';

// Estado da tela. `manifesto` vem do cache; e ele que da as dimensoes da fonte.
const estado = { acervo: [], sequencia: null, manifesto: null, padroes: {}, limiteCache: 300 };

const $ = (id) => document.getElementById(id);
const VERTICAIS = ['1080x1920', '1440x2560', '2160x3840', '2560x3840'];
const CONTROLES = ['zoom', 'pos_x', 'pos_y', 'resolucao', 'enquadramento', 'fps', 'velocidade',
  'duracao', 'inicio', 'fim', 'passo', 'qualidade', 'preset', 'ordem', 'girar',
  'nome_saida', 'inverter'];

/* ---------- a conta do recorte, espelhando timelapse/cli.py ---------- */

function dimensoesSaida(p) {
  return p.resolucao.split('x').map(Number);
}

// 'auto' resolve pela etiqueta EXIF que o cache anotou.
function giroEfetivo(p) {
  return p.girar === 'auto' ? (estado.manifesto.giro_exif || 'nao') : p.girar;
}

// A fonte e o quadro DEPOIS do giro: e sobre ele que zoom e posicao valem.
function dimensoesFonte(p) {
  const { largura_bruta: lb, altura_bruta: ab } = estado.manifesto;
  const g = giroEfetivo(p);
  return (g === '90' || g === '270') ? [ab, lb] : [lb, ab];
}

// Devolve, em coordenadas da FONTE, o retangulo que aparece no video.
function janelaVisivel(p) {
  const [fw, fh] = dimensoesFonte(p);
  const px = (p.pos_x + 100) / 200;
  const py = (p.pos_y + 100) / 200;

  // 1) o zoom recorta primeiro, centrado por pos-x/pos-y
  let w = fw, h = fh, x = 0, y = 0;
  if (p.zoom !== 1) {
    w = Math.trunc(fw / p.zoom / 2) * 2;
    h = Math.trunc(fh / p.zoom / 2) * 2;
    x = (fw - w) * px;
    y = (fh - h) * py;
  }

  const [ow, oh] = dimensoesSaida(p);

  // 2) ajustar preserva tudo com barras; preencher corta de novo por pos-x/pos-y
  if (p.enquadramento === 'ajustar') return { x, y, w, h, ow, oh, barras: true };

  const escala = Math.max(ow / w, oh / h);
  const cw = ow / escala, ch = oh / escala;
  return { x: x + (w - cw) * px, y: y + (h - ch) * py, w: cw, h: ch, ow, oh, barras: false };
}

function desenhar() {
  if (!estado.manifesto) return;
  const p = lerParametros();
  const j = janelaVisivel(p);
  const moldura = $('moldura');
  const caixa = $('giro');
  const img = $('quadro');

  moldura.style.setProperty('--proporcao', `${j.ow} / ${j.oh}`);
  const larguraMoldura = moldura.clientWidth || 300;
  const alturaMoldura = larguraMoldura * j.oh / j.ow;

  // escala = px de tela por px da fonte (ja girada)
  const escala = j.barras
    ? Math.min(larguraMoldura / j.w, alturaMoldura / j.h)
    : larguraMoldura / j.w;

  const [fw, fh] = dimensoesFonte(p);
  caixa.style.width = `${fw * escala}px`;
  caixa.style.height = `${fh * escala}px`;
  caixa.style.left = `${(j.barras ? (larguraMoldura - j.w * escala) / 2 : 0) - j.x * escala}px`;
  caixa.style.top = `${(j.barras ? (alturaMoldura - j.h * escala) / 2 : 0) - j.y * escala}px`;

  // O cache guarda a foto SEM giro. A rotacao e aplicada aqui, para que trocar
  // --girar reflita na hora e a previa nunca divirja do render.
  const lb = estado.manifesto.largura_bruta * escala;
  const ab = estado.manifesto.altura_bruta * escala;
  img.style.width = `${lb}px`;
  img.style.transform = {
    nao: 'none',
    90: `translate(${ab}px, 0) rotate(90deg)`,
    180: `translate(${lb}px, ${ab}px) rotate(180deg)`,
    270: `translate(0, ${lb}px) rotate(270deg)`,
  }[giroEfetivo(p)];

  const g = giroEfetivo(p);
  $('dica-giro').textContent = p.girar === 'auto'
    ? (g === 'nao' ? 'A foto não traz etiqueta de rotação.' : `A etiqueta pede ${g}°.`)
    : 'Giro forçado, ignorando a etiqueta da foto.';

  $('dica-ajuste').textContent = p.enquadramento === 'preencher'
    ? 'A foto é 2:3 e o vídeo é 9:16: sobra largura, e ela é cortada.'
    : 'Nada é cortado; sobra barra preta em cima e embaixo.';

  const teto = (fh / j.oh).toFixed(2);
  $('dica-zoom').textContent = p.zoom > Number(teto)
    ? `acima de ${teto}x já é ampliação nesta resolução`
    : '';
}

/* ---------- parametros ---------- */

function lerParametros() {
  const p = {};
  for (const id of CONTROLES) {
    const el = $(id);
    if (el.type === 'checkbox') p[id] = el.checked;
    else if (el.type === 'number' || el.type === 'range') p[id] = el.value === '' ? null : Number(el.value);
    else p[id] = el.value;
  }
  return p;
}

function aplicarParametros(p) {
  for (const id of CONTROLES) {
    if (p[id] === undefined || p[id] === null) continue;
    const el = $(id);
    if (el.type === 'checkbox') el.checked = Boolean(p[id]);
    else el.value = p[id];
  }
  ['zoom', 'pos_x', 'pos_y'].forEach((id) => { $('v-' + id).textContent = $(id).value; });
  desenhar();
}

function padroesDaSequencia() {
  const d = estado.padroes;
  return {
    zoom: d.zoom ?? 1, pos_x: d.pos_x ?? 0, pos_y: d.pos_y ?? 0,
    // o painel e sempre vertical: o padrao nao herda uma resolucao horizontal
    resolucao: VERTICAIS.includes(d.resolucao) ? d.resolucao : '1080x1920',
    enquadramento: d.enquadramento ?? 'preencher',
    fps: d.fps ?? 30, velocidade: d.velocidade ?? 1, duracao: d.duracao ?? null,
    inicio: d.inicio ?? 1, fim: d.fim ?? null, passo: d.passo ?? 1,
    qualidade: d.qualidade ?? 16, preset: d.preset ?? 'medium', ordem: d.ordem ?? 'nome',
    girar: d.girar ?? 'auto', inverter: d.inverter ?? false,
    nome_saida: '{peca}_{data}.mp4',
  };
}

/* ---------- acervo ---------- */

async function carregarAcervo() {
  const cfg = await (await fetch('/api/config')).json();
  estado.padroes = cfg.padroes;
  estado.limiteCache = cfg.limite_cache;
  $('caminho-acervo').textContent = cfg.acervo;
  $('raiz-acervo').value = cfg.acervo;
  desenharRecentes(cfg.recentes || []);

  estado.acervo = await (await fetch('/api/acervo')).json();
  pintarAcervo();
}

function desenharRecentes(lista) {
  const alvo = $('recentes');
  alvo.innerHTML = '';
  for (const caminho of lista.slice(1)) {
    const b = document.createElement('button');
    b.type = 'button';
    b.textContent = caminho;
    b.title = caminho;
    b.onclick = () => trocarRaiz(caminho);
    alvo.appendChild(b);
  }
}

async function trocarRaiz(caminho) {
  $('aviso-raiz').textContent = 'Lendo…';
  const resposta = await fetch('/api/acervo/raiz', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ caminho }),
  });
  const dados = await resposta.json();
  if (!resposta.ok) { $('aviso-raiz').textContent = dados.erro; return; }
  $('aviso-raiz').textContent = '';
  $('raiz-acervo').value = dados.acervo;
  $('caminho-acervo').textContent = dados.acervo;
  desenharRecentes(dados.recentes);
  estado.acervo = dados.projetos;
  estado.sequencia = null;
  estado.manifesto = null;
  pintarAcervo();
}

function pintarAcervo() {
  const alvo = $('lista-acervo');
  if (!estado.acervo.length) {
    alvo.innerHTML = '<p class="vazio">Nenhuma sequência nesta pasta. '
      + 'Procuro subpastas começadas em <b>fotos</b> com 20 fotos ou mais.</p>';
    return;
  }
  alvo.innerHTML = '';
  for (const projeto of estado.acervo) {
    const grupo = document.createElement('div');
    grupo.className = 'grupo';
    grupo.innerHTML = `<div class="grupo-nome">${projeto.nome}</div>`;
    for (const seq of projeto.sequencias) {
      const botao = document.createElement('button');
      botao.className = 'seq';
      botao.dataset.caminho = seq.caminho;
      const buracos = seq.buracos > 5
        ? `<span class="alerta"> · ${seq.buracos} buracos</span>` : '';
      botao.innerHTML = `<b>${seq.nome}</b><span>${seq.fotos} fotos · ${seq.segundos}s${buracos}</span>`;
      if (seq.buracos > 5) {
        botao.title = `${seq.buracos} números faltando na sequência dos nomes: `
          + 'fotos apagadas depois de tiradas. O vídeo dá salto onde elas faltam.';
      }
      botao.onclick = () => escolher(seq, projeto);
      grupo.appendChild(botao);
    }
    alvo.appendChild(grupo);
  }
}

let selecaoAtual = 0;

async function escolher(seq, projeto) {
  const minhaVez = ++selecaoAtual;
  document.querySelectorAll('.seq').forEach((b) => {
    b.classList.toggle('ativa', b.dataset.caminho === seq.caminho);
  });
  estado.sequencia = { ...seq, projeto: projeto.nome, projetoCaminho: projeto.caminho };
  estado.manifesto = null;
  esconderCarregando();
  $('cabecalho-previa').innerHTML =
    `<b>${projeto.nome} / ${seq.nome}</b> — ${seq.fotos} fotos, ${seq.segundos}s a 30fps`;
  $('quadro-atual').disabled = true;
  ['btn-gerar', 'btn-salvar', 'btn-padroes'].forEach((b) => { $(b).disabled = true; });

  const salvo = await (await fetch('/api/enquadramento?pasta=' + encodeURIComponent(seq.caminho))).json();
  if (minhaVez !== selecaoAtual) return;
  aplicarParametros({ ...padroesDaSequencia(), ...(salvo.salvo || {}) });
  $('fim').placeholder = seq.fotos;
  await garantirCache(seq, minhaVez);
}

function mostrarCarregando(seq, prontos) {
  const total = Math.min(seq.fotos, estado.limiteCache);
  $('carregando').hidden = false;
  $('carregando-conta').textContent = `${prontos} de ${total} quadros`;
  $('carregando-barra').style.width = `${Math.round((prontos / total) * 100)}%`;
  document.querySelectorAll('.seq').forEach((b) => {
    b.classList.toggle('montando', b.dataset.caminho === seq.caminho);
  });
}

function esconderCarregando() {
  $('carregando').hidden = true;
  document.querySelectorAll('.seq.montando').forEach((b) => b.classList.remove('montando'));
}

async function garantirCache(seq, minhaVez) {
  const url = '/api/manifesto?pasta=' + encodeURIComponent(seq.caminho);
  let dados = await (await fetch(url)).json();
  if (!dados.manifesto) {
    mostrarCarregando(seq, dados.prontos || 0);
    await fetch('/api/cache', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pasta: seq.caminho, limite: estado.limiteCache }),
    });
    while (!dados.manifesto) {
      await new Promise((r) => setTimeout(r, 700));
      // o usuario pode ter clicado noutra sequencia enquanto isto construia
      if (minhaVez !== selecaoAtual) { esconderCarregando(); return; }
      dados = await (await fetch(url)).json();
      mostrarCarregando(seq, dados.prontos || 0);
      if (typeof dados.construindo === 'string' && dados.construindo.startsWith('erro')) {
        esconderCarregando();
        $('aviso').textContent = dados.construindo;
        return;
      }
    }
  }
  if (minhaVez !== selecaoAtual) return;
  esconderCarregando();
  estado.manifesto = dados.manifesto;
  $('aviso').textContent = '';
  const ultimo = estado.manifesto.quadros - 1;
  const barra = $('quadro-atual');
  barra.max = ultimo;
  barra.value = ultimo;           // abre no fim: e la que a peca esta maior
  barra.disabled = false;
  $('rotulo-total').textContent = `${seq.fotos} fotos`;
  ['btn-gerar', 'btn-salvar', 'btn-padroes'].forEach((b) => { $(b).disabled = false; });
  trocarQuadro();
}

function trocarQuadro() {
  if (!estado.manifesto) return;
  const posicao = Number($('quadro-atual').value);
  const indice = estado.manifesto.indices[posicao];
  $('rotulo-quadro').textContent = `${indice + 1} / ${estado.manifesto.total_fotos}`;
  // o manifesto traz o id do cache (sha1 do caminho), que e como o servidor o guarda
  $('quadro').src = `/q/${estado.manifesto.id}/q_${String(posicao).padStart(6, '0')}.jpg`;
  desenhar();
}

/* ---------- fila ---------- */

function parametrosParaCli(p) {
  const fora = { ...p };
  delete fora.nome_saida;
  const args = {
    resolucao: p.resolucao, enquadramento: p.enquadramento, zoom: p.zoom,
    'pos_x': p.pos_x, 'pos_y': p.pos_y, fps: p.fps, inicio: p.inicio,
    passo: p.passo, qualidade: p.qualidade, preset: p.preset, ordem: p.ordem,
    girar: p.girar,
  };
  if (p.fim) args.fim = p.fim;
  if (p.duracao) args.duracao = p.duracao;
  else if (p.velocidade && p.velocidade !== 1) args.velocidade = p.velocidade;
  if (p.inverter) args.inverter = true;
  return args;
}

async function enfileirar() {
  const seq = estado.sequencia;
  const p = lerParametros();
  const args = parametrosParaCli(p);
  const base = seq.nome.replace(/^fotos-?/, '') || seq.projeto;
  args['pasta_saida'] = seq.projetoCaminho + '/render';
  args['nome_saida'] = p.nome_saida.replace('{peca}', base.replace(/[^\w-]/g, '_'));

  const selecionadas = (p.fim || seq.fotos) - p.inicio + 1;
  await fetch('/api/fila', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      pasta: seq.caminho, rotulo: `${seq.projeto} / ${seq.nome}`,
      parametros: args, total_quadros: Math.ceil(selecionadas / p.passo),
    }),
  });
  $('aviso').textContent = 'Na fila. Pode ajustar a próxima.';
  atualizarFila();
}

async function atualizarFila() {
  const trabalhos = await (await fetch('/api/fila')).json();
  const alvo = $('lista-fila');
  if (!trabalhos.length) { alvo.innerHTML = '<p class="vazio">Nada na fila.</p>'; return; }
  alvo.innerHTML = trabalhos.slice().reverse().map((t) => `
    <div class="trabalho ${t.estado}">
      <div class="trabalho-cab"><b>${t.rotulo}</b><em>${t.estado} · ${Math.round(t.progresso * 100)}%</em></div>
      <div class="barra"><i style="width:${t.progresso * 100}%"></i></div>
      ${t.saida ? `<small>${t.saida}</small>` : ''}
      ${t.erro ? `<small>${t.erro}</small>` : ''}
    </div>`).join('');
}

/* ---------- ligacoes ---------- */

for (const id of ['zoom', 'pos_x', 'pos_y']) {
  $(id).addEventListener('input', () => { $('v-' + id).textContent = $(id).value; desenhar(); });
}
for (const id of ['resolucao', 'enquadramento', 'girar']) {
  $(id).addEventListener('change', desenhar);
}
$('quadro-atual').addEventListener('input', trocarQuadro);
window.addEventListener('resize', desenhar);

$('btn-trocar-raiz').onclick = () => trocarRaiz($('raiz-acervo').value.trim());
$('raiz-acervo').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') trocarRaiz($('raiz-acervo').value.trim());
});
$('btn-recarregar').onclick = () => trocarRaiz($('raiz-acervo').value.trim());

$('btn-gerar').onclick = enfileirar;
$('btn-padroes').onclick = () => aplicarParametros(padroesDaSequencia());
$('btn-salvar').onclick = async () => {
  await fetch('/api/enquadramento', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pasta: estado.sequencia.caminho, parametros: lerParametros() }),
  });
  $('aviso').textContent = 'Enquadramento salvo na pasta da peça.';
};

carregarAcervo();
setInterval(atualizarFila, 1500);
