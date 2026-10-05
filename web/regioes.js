'use strict';

// Regioes da correcao: o painel desenha sobre o quadro GIRADO, mas o arquivo
// guarda tudo na foto CRUA (sem giro), que e como o cache e o ffmpeg a leem.
// Coordenadas normalizadas de 0 a 1. Giro como em --girar: '90' e horario.

function giradoParaCru(giro, x, y) {
  if (giro === '90') return [y, 1 - x];
  if (giro === '180') return [1 - x, 1 - y];
  if (giro === '270') return [1 - y, x];
  return [x, y];
}

function cruParaGirado(giro, x, y) {
  if (giro === '90') return [1 - y, x];
  if (giro === '180') return [1 - x, 1 - y];
  if (giro === '270') return [y, 1 - x];
  return [x, y];
}

// Retangulo [x, y, w, h] convertido pelos dois cantos opostos.
function converterRetangulo(conversao, giro, r) {
  const [ax, ay] = conversao(giro, r[0], r[1]);
  const [bx, by] = conversao(giro, r[0] + r[2], r[1] + r[3]);
  return [Math.min(ax, bx), Math.min(ay, by), Math.abs(bx - ax), Math.abs(by - ay)];
}

const regioes = {
  paraCru: (giro, r) => converterRetangulo(giradoParaCru, giro, r),
  paraTela: (giro, r) => converterRetangulo(cruParaGirado, giro, r),
};

if (typeof module !== 'undefined') module.exports = regioes;
